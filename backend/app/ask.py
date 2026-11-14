"""One input for everyone: POST /api/agent/ask routes free text to the order flow or the menu flow.

Gemini (structured output, text as untrusted data) only classifies: `order` (things to buy), `menu` (dishes to cook
for N people) or `unclear`, and reads the number of guests. Code decides everything else:
- covers count only if that number is in the text; a menu without covers → "For how many guests?" (never guessed);
- the delivery date is read deterministically from the text (tomorrow, Friday, maanantaiksi, 16.11., 2026-11-16);
  if the client also sends one and they differ → ask which; neither → ask;
- order → agent.run, menu → menu.propose: the response is their body plus {intent, covers, requested_date,
  date_source, question}, so the UI reuses its components.
"""
import asyncio
import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from trade_contracts import ReasonCode as C

from . import agent, conversation, gate, menu, progress, urgent

TZ = ZoneInfo("Europe/Helsinki")
log = logging.getLogger(__name__)
INTENT_PROMPT = agent.UNTRUSTED + """
You route a food buyer's message for a wholesaler's ordering agent. Classify it:
- "order": one or more products to buy, WITH OR WITHOUT an amount (e.g. "20 kg döner kebab meat", "milk and 30
  croissants for tomorrow", "gluten-free pizza", "cream"). A product name alone is an order; the agent asks how much.
- "menu": dishes to cook, usually for a number of guests (e.g. "Menu for 80 guests: reindeer stew, cheesecake").
- "unclear": neither, or you can't tell.
covers: the number of guests/people/portions if the message states one, else null. Never estimate it."""
_INTENT_SCHEMA = {"type": "object", "required": ["intent", "covers"], "properties": {
    "intent": {"type": "string", "enum": ["order", "menu", "unclear"]},
    "covers": {"type": "integer", "nullable": True}}}

_MENU_WORD = re.compile(r"\b(menu|ruokalista|lounaslista)\b", re.I)
_COMPOUND_DATE = re.compile(r"\b(after next|week after|following|viikon päästä|ensi viikon jälkeen)\b", re.I)
_WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
             "maanantai": 0, "tiistai": 1, "keskiviikko": 2, "torstai": 3, "perjantai": 4, "lauantai": 5,
             "sunnuntai": 6}
_COVERS = re.compile(r"\b(\d{1,4})\s*(guests?|people|persons?|covers?|portions?|pax|diners?|hengelle|hengen|henkeä|"
                     r"annosta|vierasta|vieraalle)\b", re.I)


def date_from_text(text: str, today: date) -> date | None:
    """The delivery date the text states, deterministically: ISO, d.m.(yyyy), today/tomorrow (Finnish too), a
    weekday (the next one; the same weekday as today means next week). None if no date is stated."""
    low = text.lower()
    if _COMPOUND_DATE.search(low):  # "the Monday after next": never guess which Monday (Codex #4)
        return None
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
        # covers only when the text writes that number AS a guest count ("80 kg flour" is not 80 guests; Codex #6)
        ok = isinstance(covers, int) and not isinstance(covers, bool) and 1 <= covers <= 2000 \
            and any(int(m[1]) == covers for m in _COVERS.finditer(text))
        intent = out["intent"]
        if intent == "order" and (_COVERS.search(text) or _MENU_WORD.search(text)):
            intent = "menu"  # menu markers route to the proposal-only path whatever the model said (Codex #5)
        return intent, covers if ok else None, True
    # fallback without Gemini: a guest count or the word menu → menu; an amount → order
    m = _COVERS.search(text)
    covers = int(m[1]) if m and 1 <= int(m[1]) <= 2000 else None
    if covers or re.search(r"\b(menu|ruokalista)\b", text, re.I):
        return "menu", covers, False
    return ("order" if re.search(r"\d", text) else "unclear"), None, False


def _ask(intent: str, covers, when, source, question: str, code: C, fix: str, kind: str | None = None) -> dict:
    """A question back to the chef. `kind` (date | guests) marks one an answer can continue from."""
    now = datetime.now(timezone.utc)
    decision = agent._decision(str(uuid4()), [gate._r(code, gate.ASK, question, None, fix)], [], now)
    return {"intent": intent, "covers": covers, "requested_date": when and when.isoformat(), "date_source": source,
            "question": question, "decision": decision.model_dump(mode="json"), "_kind": kind}


async def ask(text: str, requested: date | None, buyer_id: str, follow_up: dict | None = None) -> dict:
    """One input box, plus conversational follow-ups: with `follow_up` {to, answer} the chef's answer continues the
    request that asked (conversation.py). Every response gets `speak` and, when it asks something an answer can
    continue, `conversation_id`."""
    agent.start_budget()  # order-sized, before the preflight calls (Codex #17); menu.propose raises it to menu size
    if follow_up:
        entry = conversation.take(follow_up["to"], buyer_id)
        out, text, requested = await _answer(entry, follow_up["answer"], buyer_id)
    else:
        out = await _flow(text, requested, buyer_id)
    return _finish(out, text, requested, buyer_id)


def _finish(out: dict, text: str, requested: date | None, buyer_id: str) -> dict:
    kind, state = out.pop("_kind", None), out.pop("_state", {})
    reasons = (out.get("decision") or {}).get("reasons", [])
    if kind is None and out.get("request"):  # questions raised inside the order pipeline
        items = out["request"]["items"]
        how = next((r for r in reasons if r["code"] == "QTY_AMBIGUOUS" and r["message"].startswith("How much ")), None)
        again = next((r for r in reasons if r["code"] == "QTY_AMBIGUOUS" and "Order again?" in r["message"]), None)
        missing = [n for n, it in enumerate(items) if it["amount"] is None]
        if how and missing:
            kind, state = "amount", {"request": out["request"], "item": missing[0]}
            out["question"] = how["message"].split("?")[0] + "?"
        elif again:
            kind = "confirm"
            out["question"] = again["message"].split(". Nothing")[0]
    out["conversation_id"] = None
    if kind and out.get("question"):
        out["conversation_id"] = conversation.save(buyer_id, kind, {
            "text": text, "requested": out.get("requested_date") or (requested and requested.isoformat()), **state})
    out["speak"] = conversation.speak(out, conversation.language(text))
    return out


async def _answer(entry: dict, answer: str, buyer_id: str) -> tuple[dict, str, date | None]:
    """Fill only the asked field from the answer, then re-run every check. → (response, original text, date)."""
    text, kind = entry["text"], entry["kind"]
    requested = date.fromisoformat(entry["requested"]) if entry.get("requested") else None
    steer = await agent.steering(answer)  # the answer is untrusted text too
    if agent._INSTRUCTION.search(answer) or agent._BILLING.search(answer) or (steer or 0) >= agent.INJECTION_MAX:
        return _ask("order", None, requested, None, "That answer seems to try to steer the agent. Nothing was "
                    "ordered.", C.LOW_CONFIDENCE, "Answer just the question."), text, requested

    def again(question: str, fix: str) -> dict:  # couldn't read the answer: ask the same thing again
        out = _ask("order", entry.get("covers"), requested, None, question, C.QTY_AMBIGUOUS, fix, kind)
        out["_state"] = {k: entry[k] for k in ("request", "item") if k in entry}
        return out

    today = datetime.now(TZ).date()
    if kind == "date":
        d = conversation.date_answer(answer, today, date_from_text)
        if d is None:
            return again("For which delivery day?", "Say a day, e.g. 'Monday' or 'tomorrow'."), text, requested
        return await _flow(text, d, buyer_id), text, d
    if kind == "guests":
        n = conversation.number_in(answer)
        if n is None or n != int(n) or not 1 <= n <= 2000:
            return again("For how many guests?", "Say a number, e.g. '80'."), text, requested
        return await _flow(text, requested, buyer_id, covers=int(n)), text, requested
    if kind == "confirm":
        if conversation.NO.search(answer):
            now = datetime.now(timezone.utc)
            decision = agent._decision(str(uuid4()), [gate._r(C.QTY_AMBIGUOUS, gate.INFO, "Not ordered again, as you "
                                                              "said.", None, None)], [], now)
            return {"intent": "order", "question": None, "requested_date": entry.get("requested"), "order": None,
                    "decision": decision.model_dump(mode="json")}, text, requested
        if not conversation.YES.search(answer):
            return again("Order it again?", "Say yes or no."), text, requested
        return await _flow(text + " (again)", requested, buyer_id), text, requested
    # amount: only the asked item's amount and unit change; the stored parse, buyer and mandate stay
    request, n_item = entry["request"], entry["item"]
    item = request["items"][n_item]
    got = conversation.amount_in(answer)
    if got is None:
        return again(f"How much {item['query']}? Say the amount with a unit, e.g. '5 litres'.", "Say the amount with "
                     "a unit."), text, requested
    item["amount"], item["unit"] = got
    merged = f"{text}. {got[0]:g} {got[1]} {item['query']}"  # grounding finds amount + unit + product in one clause
    return await _flow(merged, requested, buyer_id, parsed=(request, True)), merged, requested


async def _flow(text: str, requested: date | None, buyer_id: str, covers: int | None = None,
                parsed: tuple[dict, bool] | None = None) -> dict:
    today = datetime.now(TZ).date()
    stated = date_from_text(text, today)  # deterministic, so the date guard can start with everything else
    guess = requested or stated or (today if urgent.URGENT.search(text) else None)
    # One parallel batch: intent check, order parse, steering and date guards (room3-speed; the parse is wasted only
    # when it turns out to be a menu, the guards only when the request stops at a question).
    t0 = time.monotonic()
    progress.phase("understanding")
    given_covers, given_parse = covers, parsed
    # Menu markers always route to the menu path (classify), so its parse starts now and the order parse is skipped
    # (room3-menu-speed: the unused order parse used to block the menu parse for ~8 s).
    menu_first = given_parse is None and bool(given_covers is not None or _COVERS.search(text) or _MENU_WORD.search(text))
    dishes = asyncio.create_task(menu.parse_menu(text, buyer_id)) if menu_first else None
    try:
        return await _route(text, requested, buyer_id, today, stated, guess, t0, given_covers, given_parse, dishes)
    finally:
        if dishes is not None and not dishes.done():
            dishes.cancel()  # the request stopped at a question


async def _route(text, requested, buyer_id, today, stated, guess, t0, given_covers, given_parse, dishes) -> dict:
    (intent, covers, _), parsed, steer, meant = await asyncio.gather(
        classify(text), agent.none() if dishes else agent._given(given_parse, lambda: agent.parse(text)),
        agent.steering(text), agent.date_intent(text, guess, today) if guess else agent.none())
    if given_covers is not None:  # a follow-up answered "for how many guests?"
        intent, covers = "menu", given_covers
    if given_parse is not None:  # a follow-up filled one amount: it stays an order
        intent = "order"
    t1 = time.monotonic()
    # An attack must never look like a normal clarification: instruction-like, authority or billing text is
    # answered with the injection reason before any date / guests / intent question (QA round 2).
    if (agent._INSTRUCTION.search(text) or agent._BILLING.search(text)
            or (steer is not None and steer >= agent.INJECTION_MAX)):
        return _ask(intent, covers, requested or stated, "request" if requested else "text" if stated else None,
                    "This request seems to try to steer the agent (instructions, approvals, billing or authority "
                    "claims). Nothing was ordered.", C.LOW_CONFIDENCE,
                    "Send just the products, amounts and date; rules change only through the Rules screen.")
    if intent == "unclear":  # off-topic first: "what's the weather like?" isn't a date question (QA round 2)
        return _ask(intent, covers, requested or stated, "request" if requested else "text" if stated else None,
                    "I can only help with ordering from Valio. What do you need?", C.QTY_AMBIGUOUS,
                    "Name the products and amounts, e.g. '20 kg butter for Monday', or paste a menu with the number "
                    "of guests.")
    if requested and stated and requested != stated:
        return _ask(intent, covers, requested, "request", f"Which delivery day: {stated:%A %d %B} (as written) or "
                    f"{requested:%A %d %B} (as selected)?", C.LOW_CONFIDENCE, "Pick one delivery date.")
    when, source = (requested, "request") if requested else (stated, "text") if stated else (None, None)
    if when is None and urgent.URGENT.search(text):  # "ASAP" / "now": the earliest day is today
        when, source = today, "text"
    if when is None:
        return _ask(intent, covers, None, None, "For which delivery day?", C.DATA_MISSING,
                    "Say the day, e.g. 'for Monday' or 'tomorrow'.", kind="date")
    if when < today:
        return _ask(intent, covers, when, source, f"{when:%A %d %B %Y} is in the past. Which delivery day?",
                    C.DATA_MISSING, "Pick a date from today on.")
    if (when - today).days > 60:
        return _ask(intent, covers, when, source, f"{when:%A %d %B %Y} is outside the 60-day ordering window. Which "
                    "delivery day?", C.DATA_MISSING, "Pick a date from today to 60 days ahead.")
    meta = {"intent": intent, "covers": covers, "requested_date": when.isoformat(), "date_source": source,
            "question": None, "urgent_options": None}
    if intent == "menu":
        if covers is None:  # never guessed: portions decide every quantity in the cart
            return _ask(intent, None, when, source, "For how many guests?", C.QTY_AMBIGUOUS,
                        "Add the number of guests, e.g. 'for 80 guests'.", kind="guests")
        body = await menu.propose(text, covers, when, buyer_id, dishes)
    else:
        body = await agent.run(text, when, buyer_id, pre={"parsed": parsed, "steer": steer,
                                                         "meant": meant if when == guess else None})
    # Suggestions only (walk-in, Click & Collect, next delivery): never an order the agent places.
    meta["urgent_options"] = urgent.urgent_options(text, buyer_id, when, datetime.now(TZ), body.get("lines", []))
    meta["timings_ms"] = {"understand": round((t1 - t0) * 1000), "total": round((time.monotonic() - t0) * 1000)}
    log.info("ask %s: understand %d ms, total %d ms", intent, meta["timings_ms"]["understand"], meta["timings_ms"]["total"])
    return meta | body
