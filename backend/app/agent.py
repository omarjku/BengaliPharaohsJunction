"""Milestone 1 buyer agent: chef's text → catalogue → Valio quote → quantity → decision → front-door order → audit.

Gemini does the two language jobs: turning the text into items, and judging which catalogue hits really ARE the
thing asked for (keyword search ranks "milk ice cream" next to milk). Everything with money, stock or rules is
deterministic and reuses the front door's own checks (gate.check_line), so agent and door agree (D2).
Without a key, or when Gemini fails, a simple parser and plain search order take over and the answer says so.
Problems the door can't see (no matching product, a quantity that needs confirming) stop the run before any order
and come back as an ASK_HUMAN / DECLINE Decision with reasons (D6). The door's own concerns (spend limits, cut-offs)
come back from the door, which holds the order for sign-off or refuses it.
"""
import asyncio
import json
import logging
import re
from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
from fastapi import HTTPException
from trade_contracts import (Alternative, AuditEntry, AuditInput, Decision, Mandate, PurchaseRequest, Reason,
                             RejectedOption, RequestItem)
from trade_contracts import ReasonCode as C
from trade_contracts.common import RuleKind

from . import catalogue, config, gate, mandates, orders, quantity, valio

RULES_VERSION = "m1-buyer-agent-0.1"
ACTOR = "buyer_agent"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_TIMEOUT_S = 15
SEARCH_LIMIT = 20  # catalogue hits shown to Gemini
QUOTE_TOP = 5  # candidates per item actually quoted at Valio (no catalogue sweeps)
ASK, DECLINE, INFO = gate.ASK, gate.DECLINE, gate.INFO

# Dietary tag (closed list Gemini must pick from) → (claims that must be present, GS1 allergens to exclude).
# Lactose-free milk still CONTAINS milk (AM): lactose is a claim, "dairy-free" is the allergen.
DIETARY = {
    "lactose_free": (["FREE_FROM_LACTOSE"], []), "gluten_free": (["FREE_FROM_GLUTEN"], []),
    "vegan": (["VEGAN"], []), "vegetarian": (["VEGETARIAN"], []), "milk_free": ([], ["AM"]),
    "egg_free": ([], ["AE"]), "nut_free": ([], ["AN", "AP"]), "peanut_free": ([], ["AP"]),
    "soy_free": ([], ["AY"]), "fish_free": ([], ["AF"]),
}
_WORDS = {"lactose-free": "lactose_free", "lactose free": "lactose_free", "gluten-free": "gluten_free",
          "gluten free": "gluten_free", "vegan": "vegan", "vegetarian": "vegetarian", "dairy-free": "milk_free",
          "dairy free": "milk_free", "milk-free": "milk_free", "egg-free": "egg_free", "nut-free": "nut_free",
          "peanut-free": "peanut_free", "soy-free": "soy_free", "fish-free": "fish_free"}

log = logging.getLogger(__name__)

PARSE_PROMPT = """You turn a restaurant buyer's purchase request into line items for a food wholesaler's catalogue search.
For each product asked for:
- query: 1-3 English words naming the product the way a wholesaler lists it (e.g. "milk", "cream", "butter").
  No quantities, no dietary words, no brand unless the buyer named one.
- amount and unit exactly as the buyer stated them. unit is one of L, dl, cl, ml, kg, g, pcs. If the buyer gave no
  amount or no unit, use null: never invent one.
- dietary: only constraints the buyer actually stated.
summary: one short sentence restating the request.
Request: """

RANK_PROMPT = """A restaurant buyer asked a food wholesaler for: {query}{diet}.
Their full request: "{text}"
Below are catalogue products found by keyword search. Return the ids of the products that ARE what the buyer asked
for, best match first (a product merely made from it is not a match: milk ice cream is not milk). Return an empty
list if none match.
{products}"""

_PARSE_SCHEMA = {"type": "object", "required": ["summary", "items"], "properties": {
    "summary": {"type": "string"},
    "items": {"type": "array", "items": {"type": "object", "required": ["query", "amount", "unit", "dietary"],
        "properties": {"query": {"type": "string"}, "amount": {"type": "number", "nullable": True},
                       "unit": {"type": "string", "nullable": True},
                       "dietary": {"type": "array", "items": {"type": "string", "enum": list(DIETARY)}}}}}}}
_RANK_SCHEMA = {"type": "object", "required": ["ids"], "properties": {"ids": {"type": "array", "items": {"type": "string"}}}}


async def _gemini(prompt: str, schema: dict) -> dict | None:
    """One structured-output call. None on no key / any failure (never raises, never logs the key)."""
    if not config.GEMINI_API_KEY:
        return None
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema, "temperature": 0}}
    try:
        async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT_S) as http:
            r = await http.post(f"{GEMINI_URL}/{config.GEMINI_MODEL}:generateContent",
                                headers={"x-goog-api-key": config.GEMINI_API_KEY}, json=body)
            r.raise_for_status()
            parts = r.json()["candidates"][0]["content"]["parts"]
            return json.loads("".join(p.get("text", "") for p in parts if not p.get("thought")))
    except Exception as e:  # noqa: BLE001 - any failure means "use the fallback"
        log.warning("Gemini call failed (%s); using fallback", type(e).__name__)
        return None


def _item(query: str, amount, unit, tags) -> dict:
    tags = [t for t in dict.fromkeys(tags) if t in DIETARY]
    try:
        amount = float(amount) if amount is not None and float(amount) > 0 else None
    except (TypeError, ValueError):
        amount = None
    return {"query": query.strip(), "amount": amount, "unit": unit or None,
            "claims": sorted({c for t in tags for c in DIETARY[t][0]}),
            "exclude_allergens": sorted({a for t in tags for a in DIETARY[t][1]})}


_AMOUNT = re.compile(r"(\d[\d,.]*)\s*(l|dl|cl|ml|kg|g|pcs|kpl)?\b\s*(?:of\s+)?(.*)", re.I)


def fallback_parse(text: str) -> list[dict]:
    """Deterministic: '1000 L lactose-free milk for Monday, 20 kg butter' → items. Amount/unit only if written."""
    items = []
    for chunk in re.split(r",(?!\d)|;|\n|\band\b", text):
        chunk = re.sub(r"\b(for|by|on|delivered)\b.*$", "", chunk, flags=re.I).strip()
        low = chunk.lower()
        tags = [tag for word, tag in _WORDS.items() if word in low]
        for word in _WORDS:
            chunk = re.sub(re.escape(word), " ", chunk, flags=re.I)
        m = _AMOUNT.match(chunk.strip())
        amount = unit = None
        if m:
            n = m[1].rstrip(".,")
            n = n.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", n) else n.replace(",", ".")
            amount, unit, chunk = float(n), m[2] and ("pcs" if m[2].lower() == "kpl" else m[2]), m[3]
        query = " ".join(chunk.split())
        if query:
            items.append(_item(query, amount, unit, tags))
    return items


async def parse(text: str) -> tuple[dict, bool]:
    """→ ({summary, items}, used_gemini)."""
    out = await _gemini(PARSE_PROMPT + text, _PARSE_SCHEMA)
    if out and out.get("items"):
        items = [_item(i.get("query") or "", i.get("amount"), i.get("unit"), i.get("dietary") or [])
                 for i in out["items"]]
        if items := [i for i in items if i["query"]]:
            return {"summary": out.get("summary") or text, "items": items}, True
    return {"summary": f"[fallback parser, Gemini unavailable] {text}", "items": fallback_parse(text)}, False


async def candidates(text: str, item: dict, excluded: set[str]) -> tuple[list[str], bool]:
    """Catalogue hits for one item (claims + allergen filters), narrowed and ordered by Gemini. → (ids, used_gemini)."""
    excl = sorted(set(item["exclude_allergens"]) | excluded)
    hits = catalogue.search(item["query"], item["claims"], excl, False, None, SEARCH_LIMIT)
    if not hits and len(item["query"].split()) > 1:  # "whole milk" not found → try the head noun
        hits = catalogue.search(item["query"].split()[-1], item["claims"], excl, False, None, SEARCH_LIMIT)
    if not hits:
        return [], True
    listing = "\n".join(json.dumps({"id": p["id"], "name": p["name_en"] or p["name_fi"], "brand": p["brand"]},
                                   ensure_ascii=False) for p in hits)
    diet = f" ({', '.join(item['claims'] + ['no ' + a for a in item['exclude_allergens']])})" \
        if item["claims"] or item["exclude_allergens"] else ""
    out = await _gemini(RANK_PROMPT.format(query=item["query"], diet=diet, text=text, products=listing), _RANK_SCHEMA)
    if out is None or not isinstance(out.get("ids"), list):
        return [p["id"] for p in hits[:QUOTE_TOP]], False
    known = {p["id"] for p in hits}
    return [i for i in dict.fromkeys(map(str, out["ids"])) if i in known][:QUOTE_TOP], True


def _unit_ok(unit: str | None) -> bool:
    return bool(unit) and (unit.lower() in quantity.MEASURES or bool(re.fullmatch(r"[A-Z]{2,4}", unit)))


def _decision(request_id: str, reasons: list[Reason], alternatives: list[Alternative], now: datetime) -> Decision:
    rs = gate._sorted(reasons)
    outcome = {DECLINE: "DECLINE", ASK: "ASK_HUMAN", INFO: "AUTO"}[rs[0].severity] if rs else "AUTO"
    return Decision(request_id=request_id, outcome=outcome, reasons=rs, alternatives=alternatives[:3],
                    rules_version=RULES_VERSION, decided_at=now)


def _name(p: dict) -> str:
    return p.get("name_en") or p.get("name_fi") or p["id"]


def _offer(line: dict) -> str:
    qty, q = line["quantity"], line["quote"]
    return (f"{gate._qty(qty['quantity'])} {qty['sales_unit']} at {gate.eur(gate.eur_to_cents(q['price']))} "
            f"= {gate.eur(line['line_total_cents'])} net")


async def run(text: str, requested: date, buyer_id: str) -> dict:
    run_id, now = str(uuid4()), datetime.now(timezone.utc)
    mandate = mandates.get(buyer_id)
    m = mandate or Mandate(id="none", buyer_id=buyer_id)  # checks still run; nothing is ordered without a mandate
    reasons: list[Reason] = []  # problems the front door can't see; any non-INFO one stops the order
    if not mandate:
        reasons.append(gate._r(C.MANDATE_MISSING, ASK, f"No mandate is on file for buyer '{buyer_id}', so the agent "
                               "may not order on its own.", None, "Set up a mandate for this buyer, then retry."))
    excluded = set().union(*(gate._allergen_codes(str(v)) for v in gate._rules(m, RuleKind.EXCLUDED_ALLERGEN)))

    request, parsed_by_gemini = await parse(text)
    if not parsed_by_gemini:
        reasons.append(gate._r(C.LOW_CONFIDENCE, INFO, "Gemini was unavailable, so the request was read by the simple "
                               "fallback parser; check the items.", None, "Check the items, or retry later."))
    if not request["items"]:
        reasons.append(gate._r(C.QTY_AMBIGUOUS, ASK, "No product could be read from the request.", None,
                               "Say what to order and how much, e.g. '1000 L lactose-free milk'."))

    found = await asyncio.gather(*(candidates(text, it, excluded) for it in request["items"]))
    if not all(by_gemini for _, by_gemini in found) and parsed_by_gemini:
        reasons.append(gate._r(C.LOW_CONFIDENCE, INFO, "Gemini couldn't rank the catalogue matches; plain keyword "
                               "order was used.", None, "Check the chosen products."))
    ids = list(dict.fromkeys(pid for cands, _ in found for pid in cands))
    quotes: dict[str, dict] = {}
    try:
        quotes = {q["product_id"]: q for q in await valio.get_quotes(ids, requested.isoformat())} if ids else {}
    except Exception:  # noqa: BLE001 - upstream details stay in the server log
        log.exception("Valio quote failed")
        reasons.append(gate._r(C.ENGINE_ERROR, ASK, "Valio's price and availability check failed; nothing was "
                               "ordered.", None, "Retry in a moment."))
        found = []

    lines, checked, alternatives, chosen = [], [], [], []
    for n, (it, (cands, _)) in enumerate(zip(request["items"], found)):
        amount_ok = it["amount"] is not None and _unit_ok(it["unit"])
        scored = []
        for rank, pid in enumerate(cands):
            p, q = catalogue.get(pid), quotes.get(pid)
            qty = quantity.resolve(p, it["amount"], it["unit"]) if amount_ok else None
            rs, info = gate.check_line(pid, qty and qty["quantity"], q, requested, m, excluded, now)
            line = {"item": n, "product": p, "quote": q, "quantity": qty, "line_total_cents": info["line_total_cents"],
                    "why": "", "chosen": False}
            lines.append(line)
            checked.append((line, rs))
            blocking = [r for r in rs if gate._blocking(r)]
            viable = not blocking and qty is not None and qty["quantity"] is not None
            asks = [r for r in rs if r.severity is not INFO]
            line["why"] = " ".join(r.message for r in asks) or (
                f"Matches '{it['query']}' and is orderable for {requested}." if q else "No quote from Valio.")
            scored.append(((not viable, bool(qty and qty["needs_confirmation"]), len(asks), rank), line, asks))

        label = f"'{it['query']}'" + (f" ({', '.join(it['claims'] + ['no ' + a for a in it['exclude_allergens']])})"
                                      if it["claims"] or it["exclude_allergens"] else "")
        if not cands:
            reasons.append(gate._r(C.UNKNOWN_PRODUCT, ASK, f"No product in Valio's catalogue matches {label}.", None,
                                   "Rephrase the product, or name it more precisely."))
            continue
        if not amount_ok:
            reasons.append(gate._r(C.QTY_AMBIGUOUS, ASK, f"How much {it['query']}? The request gives no amount and "
                                   "unit the agent can convert (L, dl, cl, ml, kg, g, pcs).", None,
                                   f"Say the amount, e.g. '20 L {it['query']}'."))
            continue
        scored.sort(key=lambda s: s[0])
        (not_viable, _, _, _), best, best_asks = scored[0]
        if not_viable:  # every candidate is blocked: bring the best one's traps to the human
            if best["quantity"]["quantity"] is None:
                reasons.append(gate._r(C.QTY_AMBIGUOUS, ASK, best["quantity"]["explanation"], best["product"]["id"],
                                       "Confirm the quantity in sales units."))
            reasons += best_asks
            try:  # J4: substitutes from the front door's own finder (same category + dietary claims, re-quoted)
                alternatives += (await gate._alternatives(cands, set(ids), requested, m, excluded, now))[0]
            except Exception:  # noqa: BLE001 - no substitutes is still a valid answer
                log.exception("substitute search failed")
            continue
        best["chosen"] = True
        chosen.append(best)
        best["why"] = (f"Best match for {label}: {_name(best['product'])}, {_offer(best)}, orderable for {requested}. "
                       + best["quantity"]["explanation"] + (" " + best["why"] if best_asks else ""))
        if best["quantity"]["needs_confirmation"]:
            reasons.append(gate._r(C.QTY_AMBIGUOUS, ASK, best["quantity"]["explanation"], best["product"]["id"],
                                   "Confirm the quantity in sales units."))
        for key, line, _ in scored[1:]:
            if not key[0]:
                alternatives.append(Alternative(product_id=line["product"]["id"], summary=(
                    f"Also matches {label}: {_name(line['product'])}, {_offer(line)}.")))

    rejected = [RejectedOption(product_id=line["product"]["id"], reasons=gate._sorted(rs)) for line, rs in checked
                if not line["chosen"] and any(r.severity is not INFO for r in rs)]
    contract_quotes = [cq.model_copy(update={"product_name": _name(catalogue.get(pid) or {"id": pid})})
                       for pid, q in quotes.items() if (cq := valio.to_contract_quote(q))]

    def audit(decision: Decision) -> str:
        entry = AuditEntry(
            id=str(uuid4()), timestamp=datetime.now(timezone.utc), actor=ACTOR, decision=decision,
            rejected_options=rejected, input=AuditInput(mandate=mandate, quotes=contract_quotes, request=PurchaseRequest(
                id=run_id, buyer_id=buyer_id, text=text, created_at=now, needed_by=requested,
                items=[RequestItem(name=i["query"], quantity=i["amount"], unit=i["unit"]) for i in request["items"]])))
        orders._append_audit(entry)
        return entry.id

    decision = _decision(run_id, reasons, alternatives, now)
    order, audit_id = None, audit(decision)  # the agent's own decision is logged before the door sees anything
    if chosen and decision.outcome == "AUTO" and mandate:
        qty_by_pid: dict[str, float] = {}
        for line in chosen:  # two items resolving to one product become one order line
            pid = line["product"]["id"]
            qty_by_pid[pid] = qty_by_pid.get(pid, 0) + line["quantity"]["quantity"]
        try:
            order = await orders.place(buyer_id, requested, [SimpleNamespace(product_id=p, quantity=q)
                                                             for p, q in qty_by_pid.items()], mandate)
        except HTTPException as e:
            reasons.append(gate._r(C.ENGINE_ERROR, ASK, f"The front door couldn't take the order: {e.detail}", None,
                                   "Retry in a moment."))
            decision = _decision(run_id, reasons, alternatives, now)
            audit_id = audit(decision)
        else:
            door = Decision.model_validate(order["decision"])
            # The door's verdict wins; the agent's INFO notes (e.g. fallback parser) ride along at the end, and the
            # agent's other matches are offered when the door has no alternatives of its own.
            decision = Decision(**door.model_dump(exclude={"reasons", "primary_reason", "alternatives"}),
                                reasons=door.reasons + [r for r in reasons if r.severity is INFO],
                                alternatives=door.alternatives or alternatives[:3])
            audit_id = order["audit_id"]
    return {"request": request, "lines": lines, "decision": decision.model_dump(mode="json"), "order": order,
            "audit_id": audit_id}
