"""Urgent needs: suggestions beyond the delivery the agent can order. Never an order the agent places.

Facts are only what Valio publishes (valioaimo.fi Cash & Carry pages, checked Sat 14 Nov 2026): the Helsinki Cash &
Carry address and opening hours, and that Click & Collect is Helsinki-only and ready from about four hours after
confirming. Store stock and pickup are NOT in the mock API, so every suggestion says so.
"""
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import mandates

CASH_AND_CARRY = {
    "name": "Valio Aimo Cash & Carry Helsinki",
    "address": "Vanha Talvitie 2, Helsinki (Sörnäinen, Tukkutori)",
    "phone": "010 381 7645",
    "hours": {0: (7, 18), 1: (7, 18), 2: (7, 18), 3: (7, 18), 4: (7, 18), 5: (8, 17), 6: (9, 16)},  # Mon=0
}
CLICK_AND_COLLECT_HOURS = 4  # "as early as four hours after confirmation", Helsinki only
HELSINKI = ZoneInfo("Europe/Helsinki")

# Timing wording only: a bare "now"/"nyt" elsewhere in a sentence is not urgency (QA round 2).
URGENT = re.compile(r"\b(asap|as soon as possible|right away|right now|(need|needed|want)\w*\s+(it\s+|them\s+|this\s+)?now|"
                    r"now please|urgent\w*|today|tonight|this morning|this afternoon|in \d+\s*(min|mins|minutes|h|"
                    r"hours?)|heti|kiire\w*|tänään|pikaisesti|nyt heti)\b", re.I)


def _late(lines: list[dict], requested: date) -> bool:
    """The earliest delivery Valio quotes is later than needed, or nothing can be delivered for that day."""
    quotes = [ln["quote"] for ln in lines if ln.get("quote")]
    if not quotes:
        return False
    on_time = [q for q in quotes if not ({"cutoff_passed", "undeliverable", "out_of_stock"} & set(q["flags"]))
               and (not q.get("available_date") or q["available_date"][:10] <= requested.isoformat())]
    return not on_time


def _hours_text(now: datetime) -> str:
    opens, closes = CASH_AND_CARRY["hours"][now.weekday()]
    state = "open now" if opens <= now.hour < closes else "closed now"
    return f"today {opens:02d}:00–{closes:02d}:00 ({state})"


def _helsinki(now: datetime) -> datetime:
    return (now.astimezone(HELSINKI) if now.tzinfo else now.replace(tzinfo=HELSINKI))


def _pickup_time(now: datetime) -> datetime:
    candidate = now + timedelta(hours=CLICK_AND_COLLECT_HOURS)
    for _ in range(8):
        opens, closes = CASH_AND_CARRY["hours"][candidate.weekday()]
        opening = candidate.replace(hour=opens, minute=0, second=0, microsecond=0)
        closing = candidate.replace(hour=closes, minute=0, second=0, microsecond=0)
        if candidate < opening:
            return opening
        if candidate < closing:
            return candidate
        candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return candidate


def _next_delivery(lines: list[dict]) -> dict:
    """The honest answer outside Helsinki: the earliest delivery day and its cut-off, from the live quotes."""
    now = datetime.now(HELSINKI)
    best = min(((q["available_date"][:10], q.get("order_cutoff")) for ln in lines if (q := ln.get("quote"))
                and q.get("available_date") and q.get("orderable")  # orderable: no stock/block/cut-off trap (Codex #7)
                and not (q.get("order_cutoff") and datetime.fromisoformat(q["order_cutoff"]) <= now)),
               default=None)
    text = (f"The earliest Valio delivery for these products is {best[0]}"
            + (f" if ordered before {best[1]}" if best[1] else "") + "." if best else
            "No earlier Valio delivery is available for these products; see the order lines for dates and cut-offs.")
    return {"kind": "next_delivery", "label": "Next delivery", "text": text, "assumption": False}


def urgent_options(text: str, buyer_id: str, requested: date, now: datetime, lines: list[dict]) -> list[dict] | None:
    """Only when it IS urgent (timing wording, or delivery wanted today) AND Valio's earliest delivery is later than
    needed: otherwise the normal delivery already serves the chef and pickup suggestions are noise."""
    now = _helsinki(now)
    if not ((URGENT.search(text) or requested <= now.date()) and _late(lines, requested)):
        return None
    if mandates.location(buyer_id) != "helsinki":
        return [_next_delivery(lines)]
    cc = CASH_AND_CARRY
    ready = _pickup_time(now).strftime("%H:%M")
    return [
        {"kind": "walk_in", "label": f"Pick it up yourself now: {cc['name']}", "address": cc["address"],
         "hours": _hours_text(now), "phone": cc["phone"], "assumption": True,
         "text": f"{cc['address']}, {_hours_text(now)}. Store stock is not confirmed via the API: call {cc['phone']} "
                 "before you go."},
        {"kind": "click_and_collect", "label": "Click & Collect (Helsinki only)", "assumption": True,
         "text": f"Order for pickup at {cc['name']}: ready from about {CLICK_AND_COLLECT_HOURS} hours after it is "
                 f"confirmed (around {ready} Helsinki time if confirmed now, within opening hours). Placed on Valio's own site; the "
                 "agent doesn't place pickup orders."},
        _next_delivery(lines),
    ]
