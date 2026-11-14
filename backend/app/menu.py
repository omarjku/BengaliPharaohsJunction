"""T15 menu → cart: the chef pastes a menu and the number of covers; the agent proposes a cart and never orders.

Gemini turns dishes into ingredients with a per-cover amount and a one-line assumption. Code scales them to covers,
merges identical ingredients across dishes (normalised to L / kg / pcs), and runs each through the same per-item
pipeline as /api/agent/run (catalogue, Gemini rank, live Valio quotes, quantity, gate checks, Decisions confidence,
mandate limits, reliability floor, Finnish preference). Recipe quantities are guesses, so the Decision is always
ASK_HUMAN with MENU_ASSUMPTIONS; the chef confirms by posting `order_lines` to POST /api/orders, which re-checks it.
"""
import asyncio
from contextvars import ContextVar
import math
import re
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from uuid import uuid4

from trade_contracts import AuditEntry, AuditInput, Mandate, PurchaseRequest, Reason, RequestItem
from trade_contracts import ReasonCode as C
from trade_contracts.common import Channel, RuleKind

from . import agent, catalogue, gate, mandates, orders, profile, progress, quantity, valio

MAX_INGREDIENTS = 20
MAX_DISHES, MAX_PER_DISH = 12, 15  # bound what a (possibly steered) menu parse can make the agent check and price
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
- dietary: only constraints the menu itself states for that dish, and only on the ingredients that need a special
  product to meet them (gluten-free cake: the flour, not the butter, sugar or eggs, which are naturally gluten-free).
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
    plain = [w for w in words if not any(w in d for d in agent._WORDS)]  # the dish's own name, without diet words
    tags = []
    for line in re.split(r"[;\n]|\.\s", menu_text):
        if not agent._words_in(words, line):
            continue
        low, seg = line.lower(), line.lower()
        # Two dishes on one line ("lactose-free mash and gluten-free cake"): only the words just before and in this
        # dish's name count (black-box E4: the two dishes' diet labels were swapped).
        hits = [m for w in plain for m in re.finditer(rf"(?<![\wäöå]){re.escape(w)}", low)]
        if hits:
            first, last = min(m.start() for m in hits), max(m.end() for m in hits)
            cuts = [0] + [m.end() for m in re.finditer(r",|:| and | ja | with ", low[:first])]
            start = cuts.pop()
            while cuts:  # "nut-free, lactose-free cheesecake": a chunk of only diet words still belongs to the dish
                chunk = low[cuts[-1]:start]
                rest = chunk
                for word in agent._WORDS:
                    rest = rest.replace(word, " ")
                if not re.search(r"[a-zäöå]", re.sub(r"\b(and|ja)\b|[,:]", " ", rest)):
                    start = cuts.pop()
                else:
                    break
            seg = low[start:last]
        tags += [tag for word, tag in agent._WORDS.items() if word in seg]
    return list(dict.fromkeys(tags))


def apply_dietary(menu_text: str, dishes: list[dict]) -> list[Reason]:
    """Attach a dish's diet context to every ingredient; suitability decides which lines need a claim."""
    problems, owned = [], set()
    for d in dishes:
        tags = dish_tags(menu_text, d["name"])
        owned |= set(tags)
        for ing in d["ingredients"]:
            ing["dietary"] = list(dict.fromkeys(list(ing.get("dietary") or []) + tags))
    lost = sorted({tag for word, tag in agent._WORDS.items() if word in menu_text.lower()} - owned)
    if lost:
        problems.append(gate._r(C.LOW_CONFIDENCE, ASK, f"The menu says {', '.join(t.replace('_', '-') for t in lost)}"
                                " but it isn't clear which dish that applies to.", None,
                                "Put the dietary word on the dish's own line."))
    return problems


_PROFILE_SPECIAL = {
    "gluten_free": {"flour", "wheat", "rye", "barley", "oat", "bread", "pizza", "dough", "base", "crust",
                     "pasta", "noodle", "cake", "pastry", "biscuit", "cracker", "cheese", "mozzarella"},
    "lactose_free": {"milk", "cream", "cheese", "mozzarella", "butter", "yogurt", "yoghurt", "whey", "dairy",
                      "custard", "ice"},
    "vegan": {"meat", "beef", "pork", "chicken", "fish", "salmon", "milk", "cream", "cheese", "butter", "egg",
              "mayonnaise", "yogurt", "honey", "sausage"},
    "vegetarian": {"meat", "beef", "pork", "chicken", "fish", "salmon", "sausage", "bacon"},
    "milk_free": {"milk", "cream", "cheese", "mozzarella", "butter", "yogurt", "whey", "dairy", "custard"},
    "egg_free": {"egg", "mayonnaise", "pasta", "cake", "biscuit"},
    "nut_free": {"nut", "almond", "hazelnut", "walnut", "cashew", "peanut", "pistachio"},
    "peanut_free": {"peanut"}, "soy_free": {"soy"}, "fish_free": {"fish", "salmon", "tuna"},
}


def _profile_relevant(query: str, tag: str) -> bool:
    words = {agent._singular(w) for w in re.findall(r"[\wäöå]+", query.lower())}
    special = _PROFILE_SPECIAL.get(tag, set())
    return bool(words & special)


def apply_profile_defaults(menu_text: str, dishes: list[dict], ingredients: list[dict], buyer_id: str) -> None:
    """Mark only menu ingredients that need a special product for the kitchen's standing profile diets."""
    standing = profile.dietary(buyer_id)
    for ing in ingredients:
        ing["_profile_checked"] = True
        tags = set()
        for dish_name in ing.get("dishes") or []:
            words = re.findall(r"[\wäöå]+", dish_name.lower())
            owned = dish_tags(menu_text, dish_name)
            override = any(agent._PLAIN.search(line.lower()) and agent._words_in(words, line)
                           for line in re.split(r"[;\n]|\.\s", menu_text))
            if override:
                continue
            tags |= {tag for tag, _ in standing if tag not in owned and _profile_relevant(ing["query"], tag)}
        if tags:
            ing["prefer_claims"] = sorted({claim for tag in tags for claim in agent.DIETARY[tag][0]})
            ing["profile_why"] = "; ".join(dict.fromkeys(why for tag, why in standing if tag in tags))


def _key(name: str) -> str:
    """'Potatoes' and 'potato', 'lingonberries' and 'lingonberry' merge; word order doesn't matter."""
    return " ".join(sorted({agent._singular(w) for w in re.findall(r"[\wäöå]+", name.lower())}))


HAVE: ContextVar[list[str] | None] = ContextVar("have", default=None)  # /api/agent/ask's per-request pantry list
_GENERIC = {"wheat", "plain", "all", "purpose", "caster", "granulated", "white", "table", "sea", "fine", "coarse",
            "unsalted", "fresh", "cooking", "extra", "virgin", "ground", "dried", "baking", "regular", "normal"}


def pantry(buyer_id: str, have: list[str] | None) -> list[tuple[str, str]]:
    """[(words, source)] the kitchen says it has: its profile staples ('kitchen') and this request's list
    ('this_order'). No list → [] → nothing changes."""
    out = [(str(w)[:60], "this_order") for w in have or [] if str(w).strip()]
    for m in profile._memories(buyer_id):
        if m.kind.value == "preference_note" and m.key == "staples":
            out += [(str(w)[:60], "kitchen") for w in (m.value.get("items") or []) if str(w).strip()]
    return out[:60]


def have_match(ing: dict, have: list[tuple[str, str]]) -> dict | None:
    """Does the kitchen already have this ingredient? Deterministic, never a guess: 'wheat flour' ~ 'flour', 'oil' ~
    'olive oil', but 'salmon fillet' is not 'salmon'. A diet or allergen need is only met if the have-words say it."""
    words = {agent._singular(w) for w in re.findall(r"[\wäöå]+", ing["query"].lower())}
    for text, source in have:
        low = text.lower()
        if (ing.get("claims") or ing.get("exclude_allergens")) and not any(w in low for w in agent._WORDS):
            continue
        hw = {agent._singular(w) for w in re.findall(r"[\wäöå]+", low)} - {w for w in agent._WORDS for w in w.split()}
        hw -= {"free", "gluten", "lactose"}
        if hw and (words <= hw or (hw <= words and words - hw <= _GENERIC)):
            return {"source": source, "matched": text}
    return None


def add_spare(ingredients: list[dict], chosen: list[dict], props: dict, level: str | None,
              chef: dict[str, float]) -> list[Reason]:
    """Kitchen loss on a menu cart, visibly: per ingredient Gemini's proposal (or the chef's), scaled by the kitchen's
    spare level and clamped; pack rounding counts as spare FIRST, so it is never bought twice. The cart's lines (and
    so every total the front door checks) include the spare."""
    by_item = {ln["item"]: ln for ln in chosen}
    needed_cost = plain_cost = final_cost = 0.0
    for n, ing in enumerate(ingredients):
        needed, key = ing["amount"], agent._spare_key(ing["query"])
        if key in chef:
            pct, why, src = min(max(float(chef[key]), 0.0), agent.SPARE_MAX), "Set by the chef.", "chef"
        else:
            pct, why, src = agent.spare_target(props.get(key), level)
        ln = by_item.get(n)
        rnd = agent.rounding_spare(needed, ln["quantity"]) if ln else 0.0
        ing.update(needed_amount=needed, spare_percent=round(pct, 1), spare_reason=why, spare_source=src,
                   spare_from_rounding=rnd, amount_with_spare=math.ceil(needed * (1 + pct / 100) * 1000) / 1000)
        if not ln or not ln.get("quote") or ln["quote"].get("price") is None:
            continue
        price = gate.eur_to_cents(ln["quote"]["price"])
        plain = price * ln["quantity"]["quantity"]
        if rnd < pct:  # packs don't cover it: top up to the spare (never more)
            more = agent.resolve(ln["product"], needed * (1 + pct / 100), ing["unit"])
            if more.get("quantity") is not None and more["quantity"] > ln["quantity"]["quantity"]:
                ln["quantity"] = more | {"explanation": f"{more['explanation']} Includes {pct:g}% spare: {why}"}
                ln["line_total_cents"] = round(price * more["quantity"])
        final = price * ln["quantity"]["quantity"]
        if delivered := ln["quantity"].get("delivered"):
            needed_cost += final * needed / delivered
            plain_cost += plain
            final_cost += final
        ln["spare"] = {k: ing[k] for k in ("needed_amount", "spare_percent", "spare_reason", "spare_source",
                                           "spare_from_rounding")}
    if not (final_cost and needed_cost) or final_cost - needed_cost < 0.005 * needed_cost:  # nothing worth saying
        return []
    total = (final_cost - needed_cost) / needed_cost * 100
    packs = max(0.0, (plain_cost - needed_cost) / needed_cost * 100)
    return [gate._r(C.MENU_ASSUMPTIONS, gate.INFO, f"Includes about {total:.0f}% spare for kitchen loss; {packs:.0f}% of "
                    "it is pack rounding.", None, None, spare_percent=round(total, 1), from_rounding=round(packs, 1))]


def apply_overrides(dishes: list[dict], overrides: list[dict] | None, by_chef: bool = False) -> list[Reason]:
    """The chef's own portions, on top of Gemini's reading: deterministic, so the cart rescales the same way every
    time. Matches an ingredient by name (plural- and order-tolerant), in one dish or, without `dish`, in every dish."""
    problems = []
    for o in overrides or []:
        hit = False
        for d in dishes:
            if o.get("dish") and _key(o["dish"]) != _key(d["name"]):
                continue
            for ing in d["ingredients"]:
                if _key(str(ing.get("name") or "")) == _key(o["ingredient"]):
                    hit = True
                    if o.get("per_cover") is None:  # a spare-only change: applied after pricing (propose)
                        continue
                    # only an approver-key request is the chef; an agent's change is still checked by Gemini
                    ing.update(per_cover=o["per_cover"], unit=o["unit"], set_by="chef" if by_chef else "agent",
                               assumption=f"{d['name']}: {o['per_cover']:g} {o['unit']} {ing.get('name')} per portion "
                                          + ("(set by the chef)" if by_chef else "(changed by the agent)"))
        if not hit:
            problems.append(gate._r(C.QTY_AMBIGUOUS, gate.INFO, f"No ingredient '{o['ingredient']}' in this menu"
                                    + (f" for {o['dish']}" if o.get("dish") else "") + "; that portion change was "
                                    "not applied.", None, "Check the ingredient name."))
        if o.get("spare_percent") is not None and not by_chef:
            problems.append(gate._r(C.QTY_AMBIGUOUS, gate.INFO, f"The spare for '{o['ingredient']}' can only be changed "
                                    "by the chef (approver key); Gemini's proposal was kept.", None, None))
    return problems


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
                                "unit": ing.get("unit"), "text": str(ing.get("assumption") or ""),
                                "set_by": ing.get("set_by") or "gemini"})
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
        it = agent._item(m["query"], amount, BASE_UNIT[m["dim"]], [])
        it["dietary"] = list(dict.fromkeys(m["tags"]))
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


async def check_assumptions(assumptions: list[dict]) -> list[float | None]:
    """Check all assumptions for one dish in one Decisions input, keeping dishes separate for calibration."""
    results: list[float | None] = [None] * len(assumptions)
    groups: dict[str, list[tuple[int, dict]]] = {}
    for n, assumption in enumerate(assumptions):
        if assumption["set_by"] != "chef":
            groups.setdefault(assumption["dish"], []).append((n, assumption))

    async def check_group(dish: str, group: list[tuple[int, dict]]) -> None:
        rows = "\n".join(f"Ingredient {n}: {a['ingredient']}, {a['per_cover']} {a['unit']} per portion. {a['text']}"
                          for n, a in group)
        questions = {}
        for n, _ in group:
            questions[f"needed_{n}"] = {
                "type": "noul", "instructions": "Is this ingredient normally needed for this dish?",
                "criteria": {"true_description": "Yes, a usual ingredient of this dish.",
                             "false_description": "No, it doesn't belong in this dish."}}
            questions[f"amount_{n}"] = {
                "type": "noul", "instructions": "Is this per-portion amount reasonable for this dish?",
                "criteria": {"true_description": "Yes, a normal restaurant portion amount.",
                             "false_description": "No, clearly too much or too little for one portion."}}
        input_text = (f"{agent.UNTRUSTED}\nA professional restaurant kitchen plans a dish.\n"
                      f"{agent._wrap(f'Dish: {dish}.\n{rows}')}")
        answers = await agent._decisions_grouped([(input_text, key, question) for key, question in questions.items()])
        if not answers:
            return
        for n, _ in group:
            ys = [agent._yes(answers.get(f"needed_{n}")), agent._yes(answers.get(f"amount_{n}"))]
            results[n] = None if None in ys else min(ys)

    await asyncio.gather(*(check_group(dish, group) for dish, group in groups.items()))
    return results


async def parse_menu(menu_text: str, buyer_id: str | None = None) -> list[dict] | None:
    # The kitchen's standing needs (buyer profile) shape the recipe: a gluten-free kitchen's pizza uses gluten-free
    # flour, not wheat flour. Only when the menu itself says nothing about diet; it comes from our own data, never
    # from the buyer's text.
    system = MENU_PROMPT
    low = menu_text.lower()
    if buyer_id and not any(w in low for w in agent._WORDS) and not agent._PLAIN.search(low):
        if needs := [t.replace("_", "-") for t, _ in profile.dietary(buyer_id)]:
            system += (f"\nThis kitchen's standing dietary needs (from its profile): {', '.join(needs)}. Choose "
                       "ingredients that fit them (e.g. gluten-free flour instead of wheat flour).")
    # thinkingBudget 0: 4.8-6.1 s instead of 6.8-8.0 s, same ingredients (measured, room3-menu-speed); every
    # assumption is still checked by Gemini Decisions afterwards
    out = await agent._gemini(system, agent._wrap(menu_text), _MENU_SCHEMA, {"thinkingBudget": 0})
    if not out or not isinstance(out.get("dishes"), list):
        return None
    return [{"name": str(d.get("name") or "").strip(), "ingredients": [dict(i) for i in d.get("ingredients") or []
                                                                         if isinstance(i, dict)][:MAX_PER_DISH]}
            for d in out["dishes"] if isinstance(d, dict) and str(d.get("name") or "").strip()][:MAX_DISHES]


_STEER_UNSET = object()


async def propose(menu_text: str, covers: int, requested: date, buyer_id: str, dishes_task=None,
                  overrides: list[dict] | None = None, by_chef: bool = False, have: list[str] | None = None,
                  steer_score: float | None | object = _STEER_UNSET) -> dict:
    """`dishes_task`: parse_menu(menu_text) already started by the caller (ask._flow starts it at t=0)."""
    agent.start_budget(agent.DECISIONS_PER_MENU)
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

    progress.phase("planning")
    if steer_score is _STEER_UNSET:
        dishes, steer = await asyncio.gather(dishes_task or parse_menu(menu_text, buyer_id), agent.steering(menu_text))
    else:
        dishes, steer = await (dishes_task or parse_menu(menu_text, buyer_id)), steer_score
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
    reasons += apply_overrides(kept, overrides, by_chef)
    ingredients, assumptions, problems = scale(kept, covers)
    apply_profile_defaults(menu_text, kept, ingredients, buyer_id)
    reasons += problems
    if len(ingredients) > MAX_INGREDIENTS:
        reasons.append(gate._r(C.LOW_CONFIDENCE, ASK, f"The menu needs {len(ingredients)} ingredients; the agent "
                               f"prices {MAX_INGREDIENTS} per proposal (the rest are left out).", None,
                               "Split the menu into smaller parts."))
        ingredients = ingredients[:MAX_INGREDIENTS]
    items = ingredients  # agent.canonical() tells the judge which dishes each ingredient is for
    level = agent.spare_level(buyer_id)
    spare_task = asyncio.create_task(agent.spare_proposals(ingredients, menu_text) if level != "none" else agent.empty())
    res, checks = await asyncio.gather(  # pricing and the assumption checks run side by side
        agent._pipeline(menu_text, items, requested, buyer_id, m, excluded, now, reasons, True),
        check_assumptions(assumptions[:MAX_DISHES * MAX_PER_DISH]))
    for a, y in zip(assumptions, checks):
        a["check"], a["flagged"] = y, y is not None and y < ASSUMPTION_MIN
        if a["flagged"]:
            reasons.append(gate._r(C.LOW_CONFIDENCE, ASK, f"Check this assumption: {a['per_cover']} {a['unit']} of "
                                   f"{a['ingredient']} per portion for {a['dish']} (Gemini Decisions: {agent._pct(y)} "
                                   "that it belongs and the amount is reasonable).", None,
                                   "Correct the amount or remove the ingredient before ordering.", check=y))
    lines, chosen = res["lines"], res["chosen"]
    for ingredient in ingredients:
        ingredient["diet_checks"] = []
    for line in lines:
        if line.get("chosen"):
            ingredients[line["item"]]["diet_checks"] = list(line.get("diet_checks") or [])
    for ln in lines:
        ln["dishes"] = ingredients[ln["item"]]["dishes"]
        ln.pop("_weakest", None)
    chef_spare = {agent._spare_key(o["ingredient"]): o["spare_percent"] for o in overrides or []
                  if by_chef and o.get("spare_percent") is not None}
    reasons += add_spare(ingredients, chosen, await spare_task, level, chef_spare)
    qty: dict[str, float] = {}
    price: dict[str, int] = {}
    # A line with a doubt (low confidence, odd quantity, unlabelled, ...) never goes into order_lines silently (black-box
    # #7: an 80 kg egg line reached the door and was held only by chance): it is listed under check_lines instead.
    check = [ln for ln in chosen if ln["item"] in res["failed_items"]]
    for ln in check:
        ln["check"] = True
    if check:
        reasons.append(gate._r(C.LOW_CONFIDENCE, ASK, "Left out of the order lines until you check them: "
                               + "; ".join(agent._name(ln["product"]) for ln in check) + ". Add them back once the "
                               "doubt on each line is cleared.", None, "Check those lines, then add them to the order."))
    chosen = [ln for ln in chosen if not ln.get("check")]
    # Pantry: what the kitchen says it has stays visible (marked have) but out of the order and the total.
    kitchen_has = pantry(buyer_id, have if have is not None else HAVE.get())
    back = {_key(o["ingredient"]) for o in overrides or [] if o.get("include")}
    left = []
    for n, ing in enumerate(ingredients):
        if kitchen_has and _key(ing["query"]) not in back and (got := have_match(ing, kitchen_has)):
            ing["have"] = got
            left.append(ing["query"])
    for ln in res["chosen"]:  # every priced line, the doubted ones too: what the kitchen has needs no check
        if ingredients[ln["item"]].get("have"):
            ln["have"] = ingredients[ln["item"]]["have"]
            ln.pop("check", None)
    chosen = [ln for ln in chosen if not ln.get("have")]
    for ing in ingredients:
        ing.pop("_profile_checked", None)
    if any(ln.get("have") for ln in check):  # re-say the "check them" sentence without what the kitchen has
        check = [ln for ln in check if not ln.get("have")]
        reasons[:] = [r for r in reasons if not r.message.startswith("Left out of the order lines until you check")]
        if check:
            reasons.append(gate._r(C.LOW_CONFIDENCE, ASK, "Left out of the order lines until you check them: "
                                   + "; ".join(agent._name(ln["product"]) for ln in check) + ". Add them back once the "
                                   "doubt on each line is cleared.", None, "Check those lines, then add them to the order."))
    if left:
        reasons.append(gate._r(C.MENU_ASSUMPTIONS, gate.INFO, "Left out because you have it: " + ", ".join(left)
                               + ". Add one back if you're short.", None, "Add it back with include.",
                               left_out=", ".join(left)))
    for ln in chosen:  # the chef confirms the whole cart, so two ingredients on one product become one order line
        qty[ln["product"]["id"]] = qty.get(ln["product"]["id"], 0) + ln["quantity"]["quantity"]
        price[ln["product"]["id"]] = gate.eur_to_cents(ln["quote"]["price"])
    for pid in [p for p, q in qty.items() if q > gate.MAX_LINE_QTY]:  # never hand the UI a line the door rejects
        reasons.append(gate._r(C.QTY_SUSPICIOUS, ASK, f"{gate._qty(qty.pop(pid))} units of "
                               f"{agent._name(catalogue.get(pid) or {'id': pid})} is over the "
                               f"{gate._qty(gate.MAX_LINE_QTY)} per-line limit; it is left out of the order lines.",
                               pid, "Check the amounts for that ingredient."))
    cart_total = sum(int((Decimal(price[p]) * Decimal(str(q))).quantize(Decimal(1), ROUND_HALF_UP))
                     for p, q in qty.items())
    in_cart = {ln["item"] for ln in chosen if ln["product"]["id"] in qty}
    checked_items = {ln["item"] for ln in check}
    check_lines = [{"product_id": ln["product"]["id"], "quantity": ln["quantity"]["quantity"],
                    "name": agent._name(ln["product"])} for ln in check]
    candidate_checks = []
    candidate_check_totals = []
    missing = []
    for n, ing in enumerate(ingredients):
        if n in in_cart or ing.get("have"):
            continue
        candidates_for_item = [ln for ln in lines if ln.get("item") == n and ln.get("product")]
        if candidates_for_item:
            if n in checked_items:
                continue
            best = next((ln for ln in candidates_for_item if ln.get("chosen")), candidates_for_item[0])
            checked_items.add(n)
            candidate_checks.append({"status": "check", "ingredient": ing["query"],
                                     "product_id": best["product"]["id"],
                                     "quantity": best.get("quantity") and best["quantity"].get("quantity"),
                                     "name": agent._name(best["product"]), "reason": best.get("why")})
            candidate_check_totals.append(best.get("line_total_cents") or 0)
        else:
            missing.append(ing["query"])
    if candidate_checks:
        reasons.append(gate._r(C.LOW_CONFIDENCE, ASK, "Left out of the order lines until you check them: "
                               + "; ".join(line["name"] for line in candidate_checks) + ". Add them back once the "
                               "doubt on each line is cleared.", None, "Check those lines, then add them to the order."))
    check_total = sum(ln.get("line_total_cents") or 0 for ln in check)
    check_total += sum(candidate_check_totals)
    check_lines += candidate_checks
    check_lines += [{"status": "not_found", "ingredient": name, "product_id": None, "quantity": None,
                     "name": name, "reason": "No product was found in the catalogue."} for name in missing]
    check_count = len(checked_items)
    needs_look = check_count + len(missing)
    coverage = {"ingredients": len(ingredients), "in_cart": len(in_cart), "to_check": check_count,
                "check_total_cents": check_total, "not_found": missing,
                "have": len(left), "needs_look": needs_look}
    if ingredients and len(in_cart) / len(ingredients) < 0.6:
        coverage_note = (f"I found {len(in_cart)} of {len(ingredients)} ingredients; {needs_look} need your look."
                         if needs_look else
                         f"I found {len(in_cart)} of {len(ingredients)} ingredients; the rest are already in your kitchen.")
        reasons.append(gate._r(
            C.COVERAGE_LOW, ASK, coverage_note + (f" Not found: {', '.join(missing)}." if missing else ""),
            None, "Check the missing and held ingredients before ordering.",
            in_cart=len(in_cart), ingredients=len(ingredients), needs_look=needs_look, not_found=", ".join(missing)))
    if check_count or missing:  # the headline total must never look like the whole menu when it isn't
        reasons.append(gate._r(C.MENU_ASSUMPTIONS, gate.INFO, f"EUR {cart_total / 100:,.2f} covers {len(in_cart)} of "
                f"{len(ingredients)} ingredients" + (f"; {check_count} need your look (about EUR "
                               f"{coverage['check_total_cents'] / 100:,.2f})" if check_count else "")
                               + (f"; no product found yet for {', '.join(missing)}" if missing else "") + ".",
                               None, "Check the held lines, then add them to the order.",
                               in_cart=len(in_cart), to_check=check_count))
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
            "cart_total_cents": cart_total, "cart_coverage": coverage, "not_found": missing,
            "order_lines": [{"product_id": p, "quantity": q} for p, q in qty.items()],
            "check_lines": check_lines,
            "decision": decision.model_dump(mode="json"), "audit_id": entry.id}
