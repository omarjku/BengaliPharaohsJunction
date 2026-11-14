"""Server-side mandates, one per buyer. The agent flow and the front door load the mandate from here, never from
the client: the approver's saved mandate (data/mandates.json, via PUT /api/mandate) first, the seeded default second.

ponytail: a JSON file read on every get (tiny, and always current for the agent and the door); Postgres when the
disk stops being enough (Render's disk is ephemeral, like the orders file).
"""
import json
import logging
import os
import threading

from fastapi import HTTPException
from trade_contracts import HardRule, Mandate, Preference
from trade_contracts.common import PreferenceScope, RuleKind

from . import config

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


STORE = config.DATA_DIR / "mandates.json"  # all front-door state lives under DATA_DIR
_lock = threading.Lock()
log = logging.getLogger(__name__)


def _read() -> dict[str, dict]:
    """Fail closed: a corrupt store is a 503 for everyone (never 'no mandate', never overwritten by a save)."""
    try:
        data = json.loads(STORE.read_text()) if STORE.exists() else {}
        if not isinstance(data, dict):
            raise ValueError("not an object")
        return data
    except (OSError, ValueError) as e:
        log.error("mandate store unreadable (%s)", type(e).__name__)
        raise HTTPException(503, detail="The saved rules can't be read; nothing is ordered until data/mandates.json "
                                        "is repaired.") from None


def _stored() -> dict[str, dict]:
    with _lock:
        return _read()


def get(buyer_id: str) -> Mandate | None:
    saved = _stored().get(buyer_id)
    if not saved:
        return _MANDATES.get(buyer_id)
    try:
        return Mandate.model_validate(saved)
    except ValueError:
        log.error("saved mandate for %s fails the contract", buyer_id)
        raise HTTPException(503, detail="The saved rules for this buyer are invalid; nothing is ordered until they "
                                        "are saved again.") from None


def _write(data: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    os.replace(tmp, STORE)  # atomic


def put(m: Mandate) -> dict | None:
    """Store the approver-confirmed mandate for m.buyer_id; returns the previous stored entry (for restore)."""
    with _lock:
        data = _read()
        previous = data.get(m.buyer_id)
        data[m.buyer_id] = m.model_dump(mode="json")
        _write(data)
        return previous


def restore(buyer_id: str, previous: dict | None) -> None:
    """Undo a put() whose audit entry couldn't be written: no rule change without its audit."""
    with _lock:
        data = _read()
        if previous is None:
            data.pop(buyer_id, None)
        else:
            data[buyer_id] = previous
        _write(data)


# Gemini Decisions confidence below this → ask the chef. Kept beside the mandate because the v0.2 Mandate contract
# has no field for it (extra fields are forbidden); add `min_confidence` to the contract in the next version.
DEFAULT_CONFIDENCE_THRESHOLD = 0.8
_CONFIDENCE_THRESHOLDS = {"lapland-kitchen": 0.8}


def confidence_threshold(buyer_id: str) -> float:
    return _CONFIDENCE_THRESHOLDS.get(buyer_id, DEFAULT_CONFIDENCE_THRESHOLD)


# What the Gemini Decisions guards may know about each kitchen (plausibility of an order size). Server-side, like the
# mandate. Persona: Valio's brief orders 1,000 L of milk at once, so the demo buyer is a resort's central kitchen.
_KITCHENS = {"lapland-kitchen": "the central kitchen of a Lapland ski resort: hotel restaurants and catering, about "
                                "1,500 meals a day in season, ordering a week of supplies at a time"}
DEFAULT_KITCHEN = "a professional restaurant kitchen, about 100 covers a day, ordering a few days of supplies at a time"


def kitchen(buyer_id: str) -> str:
    return _KITCHENS.get(buyer_id, DEFAULT_KITCHEN)
