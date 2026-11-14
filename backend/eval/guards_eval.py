"""Labelled cases for the Gemini Decisions GUARDS: questions that can only make the agent more cautious.

Each guard is switched on only after its cases pass here. Run live:

    cd backend && .venv/bin/python -m eval.guards_eval          # prints one table per guard, writes guards.json
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import agent, catalogue, mandates, quantity  # noqa: E402

KITCHEN = mandates.kitchen("lapland-kitchen")

# Q1 plausibility: (amount, unit, query, claims, product_id, plausible?)
PLAUSIBILITY = [
    (1000, "L", "milk", ["FREE_FROM_LACTOSE"], "463335", True),   # the brief's own example, weekly for a resort
    (10000, "L", "milk", ["FREE_FROM_LACTOSE"], "463335", False),  # an extra zero
    (20, "kg", "butter", [], "464411", True),
    (2000, "kg", "butter", [], "464411", False),
    (60, "kg", "reindeer meat", [], "462959", True),
    (5, "L", "whipping cream", ["FREE_FROM_LACTOSE"], "464194", True),
]


async def plausibility() -> list[dict]:
    rows = []
    for amount, unit, query, claims, pid, label in PLAUSIBILITY:
        p = catalogue.get(pid)
        item = agent._item(query, amount, unit, [t for t, (c, _) in agent.DIETARY.items() if c and set(c) <= set(claims)])
        q = quantity.resolve(p, amount, unit)
        total = round(q["quantity"] * agent.gate.eur_to_cents((await agent.valio.get_quotes([pid], "2026-11-16"))[0]["price"]))
        y = await agent.plausible(KITCHEN, agent.canonical(item), p, q["explanation"], total)
        rows.append({"case": agent.canonical(item), "product": agent._name(p), "label": label, "p_yes": y,
                     "ok": y is not None and (y >= agent.PLAUSIBLE_MIN) == label})
    return rows


GUARDS = {"plausibility (asks below %.2f)" % agent.PLAUSIBLE_MIN: plausibility}


async def run() -> dict:
    catalogue.load()
    return {name: await fn() for name, fn in GUARDS.items()}


def main() -> None:
    out = asyncio.run(run())
    Path(__file__).with_name("guards.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    for name, rows in out.items():
        print(f"\n{name}: {sum(r['ok'] for r in rows)}/{len(rows)} correct")
        for r in rows:
            p = "-" if r["p_yes"] is None else f"{r['p_yes']:.2f}"
            print(f"  {'ok ' if r['ok'] else 'MISS'} {'yes' if r['label'] else 'no ':3} p={p:5} {r['case'][:70]}")


if __name__ == "__main__":
    main()
