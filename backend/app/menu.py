"""T15 menu → cart: the chef pastes a menu and the number of covers; the agent proposes a cart and never orders.

Gemini turns dishes into ingredients with a per-cover amount and a one-line assumption. Code scales them to covers,
merges identical ingredients across dishes (normalised to L / kg / pcs), and runs each through the same per-item
pipeline as /api/agent/run (catalogue, Gemini rank, live Valio quotes, quantity, gate checks, Decisions confidence,
mandate limits, reliability floor, Finnish preference). Recipe quantities are guesses, so the Decision is always
ASK_HUMAN with MENU_ASSUMPTIONS; the chef confirms by posting `order_lines` to POST /api/orders, which re-checks it.
"""
import asyncio
import math
import re
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from uuid import uuid4

from trade_contracts import AuditEntry, AuditInput, Mandate, PurchaseRequest, Reason, RequestItem
from trade_contracts import ReasonCode as C
from trade_contracts.common import Channel, RuleKind

from . import agent, catalogue, gate, mandates, orders, quantity, valio

MAX_INGREDIENTS = 20
# Per-cover amounts above these are flagged, not trusted: 1 kg of potato per plate is a misread, not a recipe.
PER_COVER_MAX = {"volume": 1.0, "weight": 1.0, "count": 6}  # L, kg, pieces
BASE_UNIT = {"volume": "L", "weight": "kg", "count": "pcs"}
ASK, INFO = gate.ASK, gate.INFO

MENU_PROMPT = agent.UNTRUSTED + """
You plan purchasing for a professional restaurant kitchen. For each dish on the menu, list the main ingredients the
kitchen buys from a food wholesaler. For each ingredient:
- name: 1-3 English words, the way a wholesaler lists it (e.g. "potato", "whipping cream", "reindeer meat").
- per_cover: the amount for ONE portion, and unit: one of L, dl, cl, ml, kg, g, pcs.
- assumption: one short sentence a chef can check, e.g. "Mashed potatoes: 200 g potato per portion".
- dietary: only constraints the menu itself states for that dish.
Skip water, salt, pepper and other trace seasonings. Use the dish names as written on the menu."""

_MENU_SCHEMA = {"type": "object", "required": ["dishes"], "properties": {"dishes": {"type": "array", "items": {
    "type": "object", "required": ["name", "ingredients"], "properties": {
        "name": {"type": "string"},
        "ingredients": {"type": "array", "items": {"type": "object",
                                                    "required": ["name", "per_cover", "unit", "assumption", "dietary"],
            "properties": {"name": {"type": "string"}, "per_cover": {"type": "number"}, "unit": {"type": "string"},
                           "assumption": {"type": "string"},
                           "dietary": {"type": "array", "items": {"type": "string", "enum": list(agent.DIETARY)}}}}}}}}}}


def dish_tags(menu_text: str, dish: str) -> list[str]:
    """Dietary words written in the dish's own line of the menu (lines split on ; . and newlines, not 'and': dish
    names contain it). Deterministic, so a parse that drops 'lactose-free' can't make it disappear."""
    words = re.findall(r"[\wäöå]+", dish.lower())
    return list(dict.fromkeys(tag for line in re.split(r"[;\n]|\.\s", menu_text) if agent._words_in(words, line)
                              for word, tag in agent._WORDS.items() if word in line.lower()))


def apply_dietary(menu_text: str, dishes: list[dict]) -> list[Reason]:
    """Security guard (sibling of the request flow's): stated dietary needs are enforced or asked, never dropped.
    Allergen exclusions ('nut-free') go on every ingredient of that dish; a claim ('lactose-free') that no ingredient
    of the dish carries is asked (putting it on the potatoes would just find nothing)."""
    problems, owned = [], set()
    for d in dishes:
        tags = dish_tags(menu_text, d["name"])
        owned |= set(tags)
        for t in (t for t in tags if agent.DIETARY[t][1]):  # allergen exclusions: enforce on every ingredient
            for ing in d["ingredients"]:
                ing["dietary"] = list(dict.fromkeys(list(ing.get("dietary") or []) + [t]))
        for t in (t for t in tags if agent.DIETARY[t][0]):  # claims: some ingredient must carry it
            if not any(t in (ing.get("dietary") or []) for ing in d["ingredients"]):
                problems.append(gate._r(C.LOW_CONFIDENCE, ASK, f"The menu says {t.replace('_', '-')} for "
                                        f"{d['name']}, but no ingredient in the cart carries that need.", None,
                                        "Check which ingredients must be " + t.replace("_", "-") + "."))
    lost = sorted({tag for word, tag in agent._WORDS.items() if word in menu_text.lower()} - owned)
    if lost:
        problems.append(gate._r(C.LOW_CONFIDENCE, ASK, f"The menu says {', '.join(t.replace('_', '-') for t in lost)}"
                                " but it isn't clear which dish that applies to.", None,
                                "Put the dietary word on the dish's own line."))
    return problems


def _key(name: str) -> str:
    """'Potatoes' and 'potato', 'lingonberries' and 'lingonberry' merge; word order doesn't matter."""
    return " ".join(sorted({agent._singular(w) for w in re.findall(r"[\wäöå]+", name.lower())}))


def scale(dishes: list[dict], covers: int) -> tuple[list[dict], list[dict], list[Reason]]:
    """Dishes → (merged ingredients scaled to covers, assumptions, problems). Pure function."""
    merged: dict[tuple[str, str], dict] = {}
    assumptions, problems = [], []
    for dish in dishes:
        for ing in dish["ingredients"]:
            name, unit = str(ing.get("name") or "").strip(), str(ing.get("unit") or "").lower()
            try:
                per = float(ing.get("per_cover"))
            except (TypeError, ValueError):
                per = math.nan
            assumptions.append({"ingredient": name, "dish": dish["name"], "per_cover": per if math.isfinite(per) else None,
                                "unit": ing.get("unit"), "text": str(ing.get("assumption") or "")})
            if not name or unit not in quantity.MEASURES or not math.isfinite(per) or per <= 0:
                problems.append(gate._r(C.QTY_AMBIGUOUS, ASK, f"Couldn't read a usable amount for '{name or '?'}' in "
                                        f"{dish['name']} ({ing.get('per_cover')} {ing.get('unit')} per cover); it is "
                                        "left out of the cart.", None, "Add it by hand, or restate the dish."))
                continue
            dim, size = quantity.MEASURES[unit]
            per_base = Fraction(str(per)) * size  # exact: 3 x 200 g is 0.6 kg, not 0.6000000000000001
            if per_base > 10 * PER_COVER_MAX[dim]:  # absurd (e.g. 1e308): left out, never scaled into a crash
                problems.append(gate._r(C.QTY_SUSPICIOUS, ASK, f"{per:g} {ing['unit']} of {name} per cover for "
                                        f"{dish['name']} can't be right; it is left out of the cart.", None,
                                        "Check the per-cover amount and add it by hand."))
                continue
            if per_base > PER_COVER_MAX[dim]:
                problems.append(gate._r(C.QTY_SUSPICIOUS, ASK, f"{per:g} {ing['unit']} of {name} per cover for "
                                        f"{dish['name']} looks too much.", None, "Check the per-cover amount.",
                                        per_cover=per, unit=ing["unit"]))
            m = merged.setdefault((_key(name), dim), {"query": name, "base": Fraction(0), "dim": dim, "dishes": [],
                                                       "tags": []})
            m["base"] += per_base * covers
            m["dishes"] += [dish["name"]] if dish["name"] not in m["dishes"] else []
            m["tags"] += ing.get("dietary") or []  # union: the strictest dish wins for a shared ingredient
    ingredients = []
    for m in merged.values():
        amount = math.ceil(m["base"] * 1000) / 1000  # round UP to 3 decimals: never under-order a booked service
        it = agent._item(m["query"], amount, BASE_UNIT[m["dim"]], m["tags"])
        ingredients.append(it | {"dishes": m["dishes"]})
    return ingredients, assumptions, problems


ASSUMPTION_MIN = 0.5  # weaker of 'needed' / 'amount reasonable' below this → flagged (backend/eval/guards_eval.py)


async def check_assumption(dish: str, ingredient: str, per_cover, unit, text: str) -> float | None:
    """Gemini Decisions guard per (dish, ingredient): is it needed, and is the per-portion amount reasonable?
    One call, two questions about the same assumption; the weaker answer. A low score only flags it for the chef."""
    answers = await agent._decisions(
        f"{agent.UNTRUSTED}\nA professional restaurant kitchen plans a dish.\n"
        f"{agent._wrap(f'Dish: {dish}. Ingredient: {ingredient}, {per_cover} {unit} per portion. {text}')}", {
            "needed": {"type": "noul", "instructions": "Is this ingredient normally needed for this dish?",
                       "criteria": {"true_description": "Yes, a usual ingredient of this dish.",
                                    "false_description": "No, it doesn't belong in this dish."}},
            "amount": {"type": "noul", "instructions": "Is this per-portion amount reasonable for this dish?",
                       "criteria": {"true_description": "Yes, a normal restaurant portion amount.",
                                    "false_description": "No, clearly too much or too little for one portion."}}})
    if not answers:
        return None
    ys = [agent._yes(answers[k]) for k in ("needed", "amount")]
    return None if None in ys else min(ys)


async def parse_menu(menu_text: str) -> list[dict] | None:
    out = await agent._gemini(MENU_PROMPT, agent._wrap(menu_text), _MENU_SCHEMA)
    if not out or not isinstance(out.get("dishes"), list):
        return None
    return [{"name": str(d.get("name") or "").strip(), "ingredients": [dict(i) for i in d.get("ingredients") or []
                                                                         if isinstance(i, dict)]}
            for d in out["dishes"] if isinstance(d, dict) and str(d.get("name") or "").strip()]


async def propose(menu_text: str, covers: int, requested: date, buyer_id: str) -> dict:
    run_id, now = str(uuid4()), datetime.now(timezone.utc)
    mandate = mandates.get(buyer_id)
    m = mandate or Mandate(id="none", buyer_id=buyer_id)
    reasons: list[Reason] = [gate._r(
        C.MENU_ASSUMPTIONS, ASK, f"This cart is a proposal for {covers} covers: the quantities rest on per-cover recipe "
        "assumptions (listed with the cart). Nothing is ordered until you confirm.", None,
        "Check the assumptions and the lines, then order the cart.", covers=covers)]
    if not mandate:
        reasons.append(gate._r(C.MANDATE_MISSING, ASK, f"No mandate is on file for buyer '{buyer_id}'.", None,
                               "Set up a mandate for this buyer, then retry."))
    if agent._INSTRUCTION.search(menu_text):
        reasons.append(gate._r(C.LOW_CONFIDENCE, ASK, "The menu contains instruction-like text (e.g. 'ignore', "
                               "'return only'), which may be an attempt to steer the agent.", None,
                               "Check where the menu came from before ordering anything from this cart."))
    excluded = set().union(*(gate._allergen_codes(str(v)) for v in gate._rules(m, RuleKind.EXCLUDED_ALLERGEN)))

    dishes, steer = await asyncio.gather(parse_menu(menu_text), agent.steering(menu_text))
    if steer is not None and steer >= agent.INJECTION_MAX:
        reasons.append(gate._r(C.LOW_CONFIDENCE, ASK, "This menu seems to try to change limits, delivery, invoicing or "
                               f"approvals, or claims special authority (Gemini Decisions: {agent._pct(steer)}).", None,
                               "Check where the menu came from before ordering anything from this cart.",
                               steering=steer))
    if dishes is None:  # no fallback: turning dishes into ingredients is the language job itself
        reasons.append(gate._r(C.ENGINE_ERROR, ASK, "Gemini couldn't read the menu, so no cart was proposed.", None,
                               "Retry in a moment, or order the ingredients with a normal request."))
        dishes = []
    kept, seen = [], set()
    lines_ = re.split(r"[;\n]|\.\s", menu_text)
    for d in dishes:  # injection guard: a dish must be on ONE line of the menu the chef pasted, and only once
        words = re.findall(r"[\wäöå]+", d["name"].lower())
        if _key(d["name"]) in seen:
            reasons.append(gate._r(C.QTY_AMBIGUOUS, ASK, f"The dish '{d['name']}' came back twice; it is counted once.",
                                   None, "Check the menu text."))
        elif any(agent._words_in(words, line) for line in lines_):
            kept.append(d)
            seen.add(_key(d["name"]))
        else:
            reasons.append(gate._r(C.LOW_CONFIDENCE, ASK, f"The dish '{d['name']}' isn't on the menu you sent; its "
                                   "ingredients were left out.", None, "Check the menu text."))
    reasons += apply_dietary(menu_text, kept)
    ingredients, assumptions, problems = scale(kept, covers)
    reasons += problems
    if len(ingredients) > MAX_INGREDIENTS:
        reasons.append(gate._r(C.LOW_CONFIDENCE, ASK, f"The menu needs {len(ingredients)} ingredients; the agent "
                               f"prices {MAX_INGREDIENTS} per proposal (the rest are left out).", None,
                               "Split the menu into smaller parts."))
        ingredients = ingredients[:MAX_INGREDIENTS]
    items = ingredients  # agent.canonical() tells the judge which dishes each ingredient is for

    res, checks = await asyncio.gather(  # pricing and the assumption checks run side by side
        agent._pipeline(menu_text, items, requested, buyer_id, m, excluded, now, reasons, True),
        asyncio.gather(*(check_assumption(a["dish"], a["ingredient"], a["per_cover"], a["unit"], a["text"])
                         for a in assumptions)))
    for a, y in zip(assumptions, checks):
        a["check"], a["flagged"] = y, y is not None and y < ASSUMPTION_MIN
        if a["flagged"]:
            reasons.append(gate._r(C.LOW_CONFIDENCE, ASK, f"Check this assumption: {a['per_cover']} {a['unit']} of "
                                   f"{a['ingredient']} per portion for {a['dish']} (Gemini Decisions: {agent._pct(y)} "
                                   "that it belongs and the amount is reasonable).", None,
                                   "Correct the amount or remove the ingredient before ordering.", check=y))
    lines, chosen = res["lines"], res["chosen"]
    for ln in lines:
        ln["dishes"] = ingredients[ln["item"]]["dishes"]
        ln.pop("_weakest", None)
    qty: dict[str, float] = {}
    price: dict[str, int] = {}
    for ln in chosen:  # the chef confirms the whole cart, so two ingredients on one product become one order line
        qty[ln["product"]["id"]] = qty.get(ln["product"]["id"], 0) + ln["quantity"]["quantity"]
        price[ln["product"]["id"]] = gate.eur_to_cents(ln["quote"]["price"])
    for pid in [p for p, q in qty.items() if q > gate.MAX_LINE_QTY]:  # never hand the UI a line the door rejects
        reasons.append(gate._r(C.QTY_SUSPICIOUS, ASK, f"{gate._qty(qty.pop(pid))} units of "
                               f"{agent._name(catalogue.get(pid) or {'id': pid})} is over the "
                               f"{gate._qty(gate.MAX_LINE_QTY)} per-line limit; it is left out of the order lines.",
                               pid, "Check the amounts for that ingredient."))
    confs = [ln["confidence"] for ln in chosen]
    confidence = min(confs) if confs and None not in confs else None
    decision = agent._decision(run_id, reasons, res["alternatives"], now, confidence)

    contract_quotes = [cq.model_copy(update={"product_name": agent._name(catalogue.get(pid) or {"id": pid})})
                       for pid, q in res["quotes"].items() if (cq := valio.to_contract_quote(q))]
    entry = AuditEntry(id=str(uuid4()), timestamp=now, actor=agent.ACTOR, decision=decision,
                       rejected_options=res["rejected"], input=AuditInput(
                           mandate=mandate, quotes=contract_quotes, request=PurchaseRequest(
                               id=run_id, buyer_id=buyer_id, text=f"Menu for {covers} covers: {menu_text}",
                               channel=Channel.MENU, created_at=now, needed_by=requested,
                               items=[RequestItem(name=i["query"], quantity=i["amount"], unit=i["unit"])
                                      for i in ingredients])))
    orders._append_audit(entry)
    return {"menu": {"dishes": [{"name": d["name"], "ingredients": [
                {"name": i.get("name"), "per_cover": i.get("per_cover"), "unit": i.get("unit"),
                 "assumption": i.get("assumption")} for i in d["ingredients"]]} for d in kept]},
            "assumptions": assumptions, "ingredients": ingredients, "lines": lines,
            # computed like the front door will (unit price x summed quantity), so the chef sees what they'll pay
            "cart_total_cents": sum(int((Decimal(price[p]) * Decimal(str(q))).quantize(Decimal(1), ROUND_HALF_UP))
                                    for p, q in qty.items()),
            "order_lines": [{"product_id": p, "quantity": q} for p, q in qty.items()],
            "decision": decision.model_dump(mode="json"), "audit_id": entry.id}
