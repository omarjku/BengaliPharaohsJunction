"""Server-side mandates, one per buyer. The agent flow and the front door load the mandate from here, never from
the client: the approver's saved mandate (data/mandates.json, via PUT /api/mandate) first, the seeded default second.

ponytail: a JSON file read on every get (tiny, and always current for the agent and the door); Postgres when the
disk stops being enough (Render's disk is ephemeral, like the orders file).
"""
import json
import os
import threading
from pathlib import Path

from trade_contracts import HardRule, Mandate, Preference
from trade_contracts.common import PreferenceScope, RuleKind

_MANDATES = {m.buyer_id: m for m in [
    # Demo persona: a restaurant kitchen in Lapland. Money is net-of-VAT cents.
    Mandate(
        id="lapland-kitchen-2026-11",
        buyer_id="lapland-kitchen",
        hard_rules=[
            HardRule(kind=RuleKind.EXCLUDED_ALLERGEN, value="AP", source_text="Our kitchen is peanut-free."),
            HardRule(kind=RuleKind.AUTO_APPROVE_LIMIT_CENTS, value=150000,
                     source_text="Order on your own up to 1,500 euros per order; above that, ask me."),
            # Sign-off rule (D13): below 90% on time the order is held for the chef, never refused.
            HardRule(kind=RuleKind.MIN_DELIVERY_RELIABILITY, value=0.9,
                     source_text="Deliveries up here are fragile: ask me before anything that arrives on time under 90%."),
        ],
        # Soft: a ranking signal for the agent, never a reason to block or ask.
        guidance=[Preference(text="Prefer Finnish-origin products when the price is similar.",
                             scope=PreferenceScope.ALWAYS)],
        per_line_cap_cents=200000,
        weekly_budget_cents=600000,
    ),
]}


STORE = Path(__file__).resolve().parents[2] / "data" / "mandates.json"
_lock = threading.Lock()


def _stored() -> dict[str, dict]:
    with _lock:
        return json.loads(STORE.read_text()) if STORE.exists() else {}


def get(buyer_id: str) -> Mandate | None:
    saved = _stored().get(buyer_id)
    return Mandate.model_validate(saved) if saved else _MANDATES.get(buyer_id)


def put(m: Mandate) -> None:
    """Store the approver-confirmed mandate for m.buyer_id (atomic write)."""
    with _lock:
        data = json.loads(STORE.read_text()) if STORE.exists() else {}
        data[m.buyer_id] = m.model_dump(mode="json")
        STORE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STORE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False))
        os.replace(tmp, STORE)


# Gemini Decisions confidence below this → ask the chef. Kept beside the mandate because the v0.2 Mandate contract
# has no field for it (extra fields are forbidden); add `min_confidence` to the contract in the next version.
DEFAULT_CONFIDENCE_THRESHOLD = 0.8
_CONFIDENCE_THRESHOLDS = {"lapland-kitchen": 0.8}


def confidence_threshold(buyer_id: str) -> float:
    return _CONFIDENCE_THRESHOLDS.get(buyer_id, DEFAULT_CONFIDENCE_THRESHOLD)
