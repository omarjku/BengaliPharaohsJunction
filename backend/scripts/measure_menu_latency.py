"""Measure one real three-dish menu without writing any repository data.

Run from ``backend`` with ``--mode before`` and ``--mode after``. The before mode recreates the old
per-assumption fan-out and duplicate menu steering call; both modes use the configured Gemini services.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import agent, ask, catalogue, config, conversation, mandates, menu, orders, profile, valio


TEXT = "Menu for 40 guests on Friday: salmon soup, blueberry pie, reindeer stew"


def _stage() -> dict[str, float | int]:
    return {"calls": 0, "sum_ms": 0.0, "max_ms": 0.0}


def _instrument(module, name: str, stages: dict[str, dict]) -> None:
    original = getattr(module, name)
    stats = stages.setdefault(name, _stage())

    async def timed(*args, _original=original, _stats=stats, **kwargs):
        started = time.perf_counter()
        try:
            return await _original(*args, **kwargs)
        finally:
            elapsed = (time.perf_counter() - started) * 1000
            _stats["calls"] += 1
            _stats["sum_ms"] += elapsed
            _stats["max_ms"] = max(_stats["max_ms"], elapsed)

    setattr(module, name, timed)


async def measure(mode: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="kitchen-menu-bench-") as scratch:
        root = Path(scratch)
        config.DATA_DIR = root
        orders.AUDIT_FILE = root / "audit.jsonl"
        orders.ORDERS_FILE = root / "orders.json"
        orders.IDEM_FILE = root / "idempotency.json"
        mandates.STORE = root / "mandates.json"
        conversation.STORE = root / "conversations.json"
        orders._orders = None
        orders._idem = None
        profile._STORE[:] = [None, None]
        catalogue.load()
        agent._GEMINI_CACHE.clear()
        agent._DECISION_CACHE.clear()
        valio._cache.clear()

        stages: dict[str, dict] = {}
        for module, name in (
            (menu, "parse_menu"),
            (agent, "spare_proposals"),
            (menu, "check_assumption"),
            (menu, "check_assumptions"),
            (agent, "match"),
            (agent, "_judge_one"),
            (agent, "judge_line"),
            (agent, "plausible"),
            (agent, "_decisions"),
        ):
            _instrument(module, name, stages)

        if mode == "before":
            async def old_check_assumptions(assumptions):
                return await asyncio.gather(*(
                    agent.none() if a["set_by"] == "chef" else menu.check_assumption(
                        a["dish"], a["ingredient"], a["per_cover"], a["unit"], a["text"])
                    for a in assumptions))

            menu.check_assumptions = old_check_assumptions
            original_propose = menu.propose

            async def old_propose(*args, **kwargs):
                kwargs.pop("steer_score", None)
                return await original_propose(*args, **kwargs)

            menu.propose = old_propose

        started = time.perf_counter()
        body = await ask.ask(TEXT, None, "helsinki-bistro")
        total_ms = (time.perf_counter() - started) * 1000
        return {"mode": mode, "text": TEXT, "total_ms": round(total_ms, 1),
                "stages": {name: {"calls": int(values["calls"]), "sum_ms": round(values["sum_ms"], 1),
                                  "max_ms": round(values["max_ms"], 1)} for name, values in stages.items()},
                "cart_lines": len(body.get("order_lines") or []),
                "decision": (body.get("decision") or {}).get("outcome")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("before", "after"), required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(measure(args.mode)), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
