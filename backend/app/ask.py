"""One input for everyone: POST /api/agent/ask routes free text to the order flow or the menu flow.

Gemini (structured output, text as untrusted data) only classifies: `order` (things to buy), `menu` (dishes to cook
for N people) or `unclear`, and reads the number of guests. Code decides everything else:
- covers count only if that number is in the text; a menu without covers → "For how many guests?" (never guessed);
- the delivery date is read deterministically from the text (tomorrow, Friday, maanantaiksi, 16.11., 2026-11-16);
  if the client also sends one and they differ → ask which; neither → ask;
- order → agent.run, menu → menu.propose: the response is their body plus {intent, covers, requested_date,
  date_source, question}, so the UI reuses its components.
"""
import re
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from trade_contracts import ReasonCode as C

from . import agent, gate, menu, urgent

TZ = ZoneInfo("Europe/Helsinki")
INTENT_PROMPT = agent.UNTRUSTED + """
You route a food buyer's message for a wholesaler's ordering agent. Classify it:
- "order": a list of products to buy (e.g. "20 kg döner kebab meat", "milk and 30 croissants for tomorrow").
- "menu": dishes to cook, usually for a number of guests (e.g. "Menu for 80 guests: reindeer stew, cheesecake").
- "unclear": neither, or you can't tell.
covers: the number of guests/people/portions if the message states one, else null. Never estimate it."""
_INTENT_SCHEMA = {"type": "object", "required": ["intent", "covers"], "properties": {
    "intent": {"type": "string", "enum": ["order", "menu", "unclear"]},
    "covers": {"type": "integer", "nullable": True}}}

_WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
             "maanantai": 0, "tiistai": 1, "keskiviikko": 2, "torstai": 3, "perjantai": 4, "lauantai": 5,
             "sunnuntai": 6}
_COVERS = re.compile(r"\b(\d{1,4})\s*(guests?|people|persons?|covers?|portions?|pax|diners?|hengelle|hengen|henkeä|"
                     r"annosta|vierasta|vieraalle)\b", re.I)


def date_from_text(text: str, today: date) -> date | None:
    """The delivery date the text states, deterministically: ISO, d.m.(yyyy), today/tomorrow (Finnish too), a
    weekday (the next one; the same weekday as today means next week). None if no date is stated."""
    low = text.lower()
    if m := re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", low):
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    if m := re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})?", low):
        try:
            d = date(int(m[3] or today.year), int(m[2]), int(m[1]))
            return d if m[3] or d >= today else d.replace(year=today.year + 1)
        except ValueError:
            return None
    if re.search(r"\b(day after tomorrow|ylihuomenna)\b", low):
        return today + timedelta(days=2)
    if re.search(r"\b(tomorrow|huomenna|huomiseksi)\b", low):
        return today + timedelta(days=1)
    if re.search(r"\b(today|tänään)\b", low):
        return today
    for word, wd in _WEEKDAYS.items():
        if re.search(rf"\b{word}\w*", low):  # Finnish inflections: maanantaiksi, perjantaina
            return today + timedelta(days=(wd - today.weekday() - 1) % 7 + 1)
    return None


async def classify(text: str) -> tuple[str, int | None, bool]:
    """→ (intent, covers, by_gemini). Covers only if the number is written in the text."""
    out = await agent._gemini(INTENT_PROMPT, agent._wrap(text), _INTENT_SCHEMA)
    if out and out.get("intent") in ("order", "menu", "unclear"):
        covers = out.get("covers")
        ok = isinstance(covers, int) and not isinstance(covers, bool) and 1 <= covers <= 2000 \
            and float(covers) in agent._numbers(text)
        return out["intent"], covers if ok else None, True
    # fallback without Gemini: a guest count or the word menu → menu; an amount → order
    m = _COVERS.search(text)
    covers = int(m[1]) if m and 1 <= int(m[1]) <= 2000 else None
    if covers or re.search(r"\b(menu|ruokalista)\b", text, re.I):
        return "menu", covers, False
    return ("order" if re.search(r"\d", text) else "unclear"), None, False


def _ask(intent: str, covers, when, source, question: str, code: C, fix: str) -> dict:
    now = datetime.now(timezone.utc)
    decision = agent._decision(str(uuid4()), [gate._r(code, gate.ASK, question, None, fix)], [], now)
    return {"intent": intent, "covers": covers, "requested_date": when and when.isoformat(), "date_source": source,
            "question": question, "decision": decision.model_dump(mode="json")}


async def ask(text: str, requested: date | None, buyer_id: str) -> dict:
    today = datetime.now(TZ).date()
    intent, covers, _ = await classify(text)
    stated = date_from_text(text, today)
    if requested and stated and requested != stated:
        return _ask(intent, covers, requested, "request", f"Which delivery day: {stated:%A %d %B} (as written) or "
                    f"{requested:%A %d %B} (as selected)?", C.LOW_CONFIDENCE, "Pick one delivery date.")
    when, source = (requested, "request") if requested else (stated, "text") if stated else (None, None)
    if when is None and urgent.URGENT.search(text):  # "ASAP" / "now": the earliest day is today
        when, source = today, "text"
    if when is None:
        return _ask(intent, covers, None, None, "For which delivery day?", C.DATA_MISSING,
                    "Say the day, e.g. 'for Monday' or 'tomorrow'.")
    if when < today or (when - today).days > 60:
        return _ask(intent, covers, when, source, f"{when:%A %d %B %Y} is outside the 60-day ordering window. Which "
                    "delivery day?", C.DATA_MISSING, "Pick a date from today to 60 days ahead.")
    meta = {"intent": intent, "covers": covers, "requested_date": when.isoformat(), "date_source": source,
            "question": None, "urgent_options": None}
    if intent == "unclear":
        return _ask(intent, covers, when, source, "What would you like to order? Name the products and amounts, or "
                    "paste a menu with the number of guests.", C.QTY_AMBIGUOUS, "e.g. '20 kg butter' or "
                    "'Menu for 80 guests: …'")
    if intent == "menu":
        if covers is None:  # never guessed: portions decide every quantity in the cart
            return _ask(intent, None, when, source, "For how many guests?", C.QTY_AMBIGUOUS,
                        "Add the number of guests, e.g. 'for 80 guests'.")
        body = await menu.propose(text, covers, when, buyer_id)
    else:
        body = await agent.run(text, when, buyer_id)
    # Suggestions only (walk-in, Click & Collect, next delivery): never an order the agent places.
    meta["urgent_options"] = urgent.urgent_options(text, buyer_id, when, datetime.now(TZ), body.get("lines", []))
    return meta | body
