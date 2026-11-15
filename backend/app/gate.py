"""Valio's front door (D2): re-checks every incoming order against HARD rules with fresh Valio quotes.

Soft judgement (confidence, preferences, Gemini) is the buyer agent's job (T06), not the door's.
Never silently reject (D6): every problem comes back as a contract `Reason` with a suggested fix,
plus orderable alternatives where we can find them cheaply.

Contract tension (contracts v0.2): only HARD_CODES may carry DECLINE severity, so e.g. a passed cut-off
is ASK_HUMAN in the `Decision`. But no human sign-off can make Valio deliver past its cut-off, so the
door's own `status` refuses orders with a NOT_APPROVABLE reason: the human is told why and what to change.
"""
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from trade_contracts import (Alternative, Decision, Mandate, Quote, Reason, ReasonCode as C, RejectedOption, Severity,
                             eur_to_cents)
from trade_contracts.common import RuleKind, UncertaintyPolicy

from . import catalogue, quantity, valio

RULES_VERSION = "t07-front-door-0.2"
HELSINKI = ZoneInfo("Europe/Helsinki")
log = logging.getLogger(__name__)
ASK, DECLINE, INFO = Severity.ASK_HUMAN, Severity.DECLINE, Severity.INFO
_RANK = {INFO: 0, ASK: 1, DECLINE: 2}

# Mandate hard rules with no reason code in contracts v0.2. Until Zoha adds CLAIM_MISSING / UNIT_PRICE_OVER_MAX,
# they borrow the closest code and carry facts["hard_rule"]; either way they are refused (see _blocking).
CLAIM_MISSING = getattr(C, "CLAIM_MISSING", C.DATA_MISSING)
UNIT_PRICE_OVER_MAX = getattr(C, "UNIT_PRICE_OVER_MAX", C.LINE_OVER_CAP)
# Valio physically can't deliver the line as ordered, or the mandate forbids it: the order has to change,
# a signature can't fix it.
NOT_APPROVABLE = frozenset({C.CUTOFF_PASSED, C.UNDELIVERABLE, C.STOCK_NONE, C.STOCK_PARTIAL, C.PRICE_MISSING,
                            C.MANDATE_MISSING, CLAIM_MISSING, UNIT_PRICE_OVER_MAX} - {C.DATA_MISSING, C.LINE_OVER_CAP})
NUMERIC_RULES = (RuleKind.MAX_UNIT_PRICE_CENTS, RuleKind.MIN_DELIVERY_RELIABILITY, RuleKind.AUTO_APPROVE_LIMIT_CENTS)
# Claims worth keeping when looking for a substitute (dietary needs, not marketing claims like LOW_SODIUM_SALT).
DIETARY_CLAIMS = {"FREE_FROM_LACTOSE", "FREE_FROM_GLUTEN", "VEGAN", "VEGETARIAN", "FREE_FROM_MILK"}
MAX_ALTERNATIVES = 3
TIERS = ("best", "better", "good")
OTHER_KIND = "alternative"  # below "good": a different kind of product (horseradish for onion), offered only as a hint
_TIER_ORDER = {**{t: i for i, t in enumerate(TIERS)}, OTHER_KIND: len(TIERS)}
# Words that say nothing about what a product IS (sizes, packaging, processing, marketing); the rest of a name, in
# English and Finnish, is what "same kind" compares. Brands are dropped per product.
_GENERIC_WORDS = {
    "pcs", "kpl", "pack", "bag", "box", "bottle", "can", "tin", "jar", "case", "tray", "carton", "single", "packed",
    "frozen", "raw", "fresh", "fully", "baked", "ready", "small", "large", "big", "mini", "whole", "half", "sliced",
    "organic", "free", "gluten", "lactose", "low", "fat", "light", "sugar", "salt", "salted", "unsalted", "finnish",
    "kotimainen", "luomu", "pakaste", "pakasteena", "and", "with", "for", "the", "uht", "pro", "valio", "pcd", "aimo",
    "gluteeniton", "laktoositon", "rasvaton", "kevyt", "kpl", "litre", "litra", "kilo", "gram", "grams"}
# Sales units counted by weight or volume may be fractional; every other Valio unit (ST, KI, PAK, BAG, …) is a piece.
MEASURE_UNITS = {"KG", "KGM", "G", "GRM", "L", "LTR", "DL", "CL", "ML"}
# When allergen data doesn't settle an excluded allergen, the product NAME (en + fi) is checked for these words.
# Kept small on purpose: a hit refuses. "…free", "…vapaa" and Finnish -ton/-tön/-ttom-/-ttöm- forms are negations;
# plant "milks" (coconut, oat, soy, almond, rice) and buckwheat are excluded.
ALLERGEN_WORDS = {
    "AP": (r"pea ?nut", r"ground ?nut", r"maapähkin"),
    "AN": (r"hazelnut", r"walnut", r"cashew", r"pecan", r"pistachio", r"macadamia", r"almond", r"\bnuts?\b",
           r"pähkinä", r"manteli"),
    "AM": (r"(?<!coconut )(?<!oat )(?<!soy )(?<!almond )(?<!rice )\bmilk", r"\bcheese", r"yog(h)?urt",
           r"(?<!kookos)(?<!kaura)(?<!soija)(?<!manteli)maito", r"juusto", r"jogurt"),
    "AW": (r"(?<!buck)wheat", r"gluten", r"\brye\b", r"barley", r"spelt", r"vehnä", r"gluteeni", r"\bruis", r"ohra"),
    "AE": (r"\beggs?\b", r"kananmun"),
    "AF": (r"\bfish", r"salmon", r"\btuna", r"\blohi", r"\bkala"),
    "AY": (r"\bsoy", r"soija"),
    "AS": (r"sesam", r"seesam"),
}
# What a product IS beyond allergen safety (SU-02): a substitute lacking one of these that the original has is
# offered only as a demoted "good" option that says what differs, never "best", and never used to fill a split.
NUTRITION_CLAIMS = {"FREE_FROM_FAT", "LOW_FAT", "LOW_LACTOSE", "FREE_FROM_EGGS", "FREE_FROM_SOY", "FREE_FROM_WHEAT",
                    "NO_ADDED_SUGARS", "FREE_FROM_SWEETENERS", "FREE_FROM_ARTIFICIAL_SWEETENERS", "LOW_SODIUM_SALT",
                    "FREE_FROM_SODIUM_SALT", "HIGH_PROTEIN", "HIGH_FIBRE"}
ORGANIC_LABELS = {"EU_ORGANIC_FARMING", "KRAV_MARK", "SOIL_ASSOCIATION_ORGANIC_SYMBOL"}
MAX_ORDER_LINES, MAX_LINE_QTY = 50, 100_000  # = the /api/orders route limits (main.py), so a proposal can be re-posted
DEPOSIT_NOTE = "returnable packaging deposit charged by Valio; not priced by the mock API"


@dataclass
class GateResult:
    status: str  # "confirmed" | "pending_approval" | "refused": the door's verdict
    decision: Decision
    rejected_options: list[RejectedOption]
    quotes: list[Quote]
    lines: list[dict]
    total_cents: int
    # Up to 3 allergen-safe substitutes per refused line, best first: {product_id, replaces, tier (best|better|good),
    # why_safe, name, unit, unit_price_cents, reliability, origin, available}.
    substitutes: list[dict] = field(default_factory=list)
    # When every refused line is only short on stock: the same order with each short line split across the product
    # and its best same-unit substitute. A proposal for the human (never AUTO); re-POST its lines to order it.
    # {lines: [{product_id, quantity, unit, unit_price_cents, line_total_cents, name, replaces?}], total_cents, summary,
    #  order_lines: [{product_id, quantity}] (the body's `lines` to re-POST, verbatim)}
    alternative_order: dict | None = None
    mandate_version: str | None = None  # the version of the buyer's mandate this was judged under (mandates.version)


def eur(cents: int) -> str:
    return f"EUR {cents / 100:,.2f}"


def _qty(x: float) -> str:
    return f"{x:,.2f}".rstrip("0").rstrip(".")


def _r(code: C, severity: Severity, message: str, pid: str | None = None, fix: str | None = None, **facts) -> Reason:
    product = catalogue.get(pid) if pid else None
    return Reason(code=code, severity=severity, message=quantity.humanize_text(message, product), facts=facts,
                  suggested_fix=quantity.humanize_text(fix, product) if fix else fix, product_id=pid)


def _unknown(policy: UncertaintyPolicy, code: C, message: str, pid: str | None, fix: str, **facts) -> Reason:
    """Something we can't verify: the mandate's uncertainty policy decides (ask / decline / approve)."""
    if policy is UncertaintyPolicy.DECLINE:
        return _r(C.POLICY_DECLINE_UNKNOWN, DECLINE, message + " Your mandate says to decline what can't be verified.",
                  pid, fix, unknown=code.value, **facts)
    return _r(code, INFO if policy is UncertaintyPolicy.APPROVE else ASK, message, pid, fix, **facts)


def _allergen_codes(value: str) -> set[str]:
    """Mandate allergen value ("AP", "peanut", "milk") → GS1 codes in the catalogue. Empty = can't interpret."""
    v = value.strip()
    if re.fullmatch(r"[A-Za-z]{2}", v):
        return {v.upper()} & catalogue.ALLERGEN_NAMES.keys()  # an unknown code ("ZZ") is MANDATE_INVALID, not ignored
    word = v.lower().rstrip("s")
    return {c for c, name in catalogue.ALLERGEN_NAMES.items() if word and word in name}


def _rules(m: Mandate, kind: RuleKind) -> list:
    return [r.value for r in m.hard_rules if r.kind is kind]


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _nums(m: Mandate, kind: RuleKind) -> list[float]:
    """Valid numeric rule values; check() reports the invalid ones as MANDATE_INVALID."""
    return [f for v in _rules(m, kind) if (f := _num(v)) is not None]


def _name_says(cat: dict, code: str) -> str | None:
    """The allergen word a product's name carries (en or fi), unless negated ("peanut-free", "gluteeniton")."""
    name = " ".join(filter(None, (cat.get("name_en"), cat.get("name_fi")))).lower()
    for pattern in ALLERGEN_WORDS.get(code, ()):
        for m in re.finditer(pattern, name):
            rest = name[m.end():]
            word_end = re.match(r"\w*", rest).group(0)
            if re.search(r"t(o|ö)n|tt(o|ö)m", word_end) or re.match(r"\w*(\s+(and|&|ja)\s+\w+)?[\s-]*(free|vapaa)", rest):
                continue
            return m.group(0).strip()
    return None


def _cutoff_passed(q: dict, now: datetime) -> bool:
    # Re-check against the clock: quotes are cached up to valio.CACHE_TTL_S, the flag may be that old.
    return "cutoff_passed" in q["flags"] or bool(q["order_cutoff"] and datetime.fromisoformat(q["order_cutoff"]) <= now)


def check_line(pid: str, qty: float | None, q: dict | None, requested: date, m: Mandate, excluded: set[str],
               now: datetime, approved_price: int | None = None) -> tuple[list[Reason], dict]:
    """All hard checks for one product. qty=None checks a candidate alternative (no quantity yet)."""
    rs: list[Reason] = []
    cat = catalogue.get(pid)
    name = (cat or {}).get("name_en") or (cat or {}).get("name_fi") or pid
    info = {"product_id": pid, "name": name, "quantity": qty, "unit": None, "unit_price_cents": None,
            "line_total_cents": None, "deposit": None}
    if pid in m.blocklist:
        rs.append(_r(C.BLOCKLISTED, DECLINE, f"{name} is on your blocklist.", pid, "Pick another product."))
    if cat is None or q is None or "unknown_product" in q["flags"]:
        rs.append(_r(C.UNKNOWN_PRODUCT, DECLINE, f"Product {pid} is not in Valio's catalogue.", pid,
                     "Check the product id."))
        return rs, info
    info["unit"] = q["sales_unit"] or cat.get("sales_unit")
    unit = info["unit"] or "unit"
    if cat.get("deposits"):
        info["deposit"] = DEPOSIT_NOTE

    if "undeliverable" in q["flags"]:
        rs.append(_r(C.UNDELIVERABLE, ASK, f"{name} can't be delivered right now (no delivery schedule).", pid,
                     "Pick an alternative."))
    if "sales_block" in q["flags"]:
        rs.append(_r(C.UNDELIVERABLE, ASK, f"{name} is under a sales block at Valio.", pid, "Pick an alternative.",
                     sales_block=True))
    if q["order_cutoff"] and _cutoff_passed(q, now):
        rs.append(_r(C.CUTOFF_PASSED, ASK, f"The order cut-off for {name} ({q['order_cutoff']}) has passed, "
                     f"so it can't be ordered for {requested}.", pid,
                     "Pick an alternative that can still arrive, or a later delivery date.", closing_time=q["order_cutoff"]))
    avail = q["available_amount"]
    if "out_of_stock" in q["flags"]:
        rs.append(_r(C.STOCK_NONE, ASK, f"{name} is out of stock.", pid, "Pick an alternative.", available=0))
    elif "quantity_unknown" in q["flags"]:
        rs.append(_r(C.QTY_UNKNOWN, INFO, "Valio doesn't report stock for this product; it can still be ordered.", pid,
                     "Continue with the order; the other rules still apply.", quantity_unknown=True))
    elif qty is not None and avail is not None and avail < qty:
        rs.append(_r(C.STOCK_PARTIAL, ASK, f"Only {_qty(avail)} {unit} of {name} available, {_qty(qty)} ordered.",
                     pid, f"Reduce to {_qty(avail)} and cover the rest with an alternative.", available=avail, requested=qty))
    if q["available_date"] and q["available_date"][:10] > requested.isoformat():
        rs.append(_r(C.DATE_NOT_HONOURED, ASK, f"{name} arrives {q['available_date'][:10]}, not {requested}.", pid,
                     "Accept the later date or pick an alternative.", available_date=q["available_date"][:10]))
    if q["sales_unit"] and cat.get("sales_unit") and q["sales_unit"] != cat["sales_unit"]:
        rs.append(_r(C.UNIT_MISMATCH, ASK, f"Valio sells {name} per {q['sales_unit']} today, the catalogue says "
                     f"{cat['sales_unit']}; the quantity is counted in {q['sales_unit']}.", pid,
                     "Confirm the quantity in the sales unit.", api_unit=q["sales_unit"], catalogue_unit=cat["sales_unit"]))
    lot = cat.get("lot_size")
    effective_lot = max(Decimal(str(lot)), Decimal(1)) if lot else None
    if qty is not None and qty > MAX_LINE_QTY:  # every path (route, agent, menu, MCP) goes through here
        rs.append(_r(C.QTY_INVALID, DECLINE, f"{_qty(qty)} {unit} of {name} is over the {_qty(MAX_LINE_QTY)} per-line "
                     "maximum.", pid, "Check the quantity; split a genuinely huge order with Valio.",
                     requested=qty, max_quantity=MAX_LINE_QTY))
    elif qty is not None and info["unit"] and info["unit"].upper() not in MEASURE_UNITS and qty != int(qty):
        rs.append(_r(C.QTY_INVALID, DECLINE, f"{name} is sold per {unit}, so it can't be ordered as {_qty(qty)}; "
                     "only whole units are delivered.", pid, f"Round to {math.ceil(qty)}.", requested=qty,
                     suggested_quantity=math.ceil(qty)))
    elif qty is not None and effective_lot and Decimal(str(qty)) % effective_lot != 0:
        if Decimal(str(lot)) < 1:
            rs.append(_r(C.QTY_INVALID, DECLINE, f"{name} is sold in whole {unit} units; {_qty(qty)} isn't one.",
                         pid, f"Round to {math.ceil(qty)}.", lot_size=lot, effective_lot_size=1, requested=qty))
        else:
            rs.append(_r(C.QTY_INVALID, DECLINE, f"{name} is sold in multiples of {_qty(lot)} {unit}; {_qty(qty)} isn't one.",
                         pid, f"Order a multiple of {_qty(lot)}.", lot_size=lot, requested=qty))

    if q["price"] is None:
        rs.append(_r(C.PRICE_MISSING, ASK, f"Valio returned no price for {name}, so it can't be ordered at a fixed price.",
                     pid, "Pick an alternative."))
    else:
        unit_cents = eur_to_cents(q["price"])
        info["unit_price_cents"] = unit_cents
        if approved_price is not None and unit_cents != approved_price:
            rs.append(_r(C.PRICE_CHANGED, ASK, f"The price of {name} changed from {eur(approved_price)} to "
                         f"{eur(unit_cents)} per {unit} since it was approved.", pid, "Approve the new price or reject.",
                         old_unit_price_cents=approved_price, unit_price_cents=unit_cents))
        for cap in _nums(m, RuleKind.MAX_UNIT_PRICE_CENTS):
            if unit_cents > cap:
                rs.append(_r(UNIT_PRICE_OVER_MAX, ASK, f"{name} costs {eur(unit_cents)} per {unit}, above your "
                             f"{eur(int(cap))} maximum unit price.", pid, "Pick a cheaper alternative.",
                             hard_rule=RuleKind.MAX_UNIT_PRICE_CENTS.value, unit_price_cents=unit_cents, max_cents=cap))
        if qty is not None:
            total = int((Decimal(unit_cents) * Decimal(str(qty))).quantize(Decimal(1), rounding=ROUND_HALF_UP))
            info["line_total_cents"] = total
            if total < 1:
                rs.append(_r(C.QTY_INVALID, DECLINE, f"The {name} line comes to {eur(total)}; an order line must be "
                             "at least 1 cent.", pid, "Order a larger quantity.", line_total_cents=total, requested=qty))
            if total > m.per_line_cap_cents:
                rs.append(_r(C.LINE_OVER_CAP, ASK, f"The {name} line is {eur(total)} (net of VAT), above your "
                             f"{eur(m.per_line_cap_cents)} per-line cap.", pid, "Approve, or reduce the quantity.",
                             line_total_cents=total, cap_cents=m.per_line_cap_cents))

    for claim in sorted({str(v).strip().upper() for v in _rules(m, RuleKind.REQUIRED_CLAIM)}):
        if claim not in (cat.get("claims") or []):
            rs.append(_r(CLAIM_MISSING, ASK, f"{name} isn't labelled {claim}, which your mandate requires.", pid,
                         f"Pick an alternative labelled {claim}.", hard_rule=RuleKind.REQUIRED_CLAIM.value,
                         required_claim=claim))

    al = cat.get("allergens") or {}
    data_missing = cat.get("allergen_data") == "missing" or not any(al.get(key) for key in ("contains", "may_contain", "free_from", "undeclared"))
    contains = set(al.get("contains") or [])
    may_contain = set(al.get("may_contain") or [])
    free_from = set(al.get("free_from") or [])
    undeclared = set(al.get("undeclared") or [])
    if data_missing:
        undeclared |= set(catalogue.ALLERGEN_NAMES)
    inferred = set(al.get("inferred") or [])
    for code in sorted(excluded):
        word = _name_says(cat, code) if code not in contains else None
        if code in contains:
            rs.append(_r(C.ALLERGEN_CONTAINS, DECLINE, f"{name} contains {catalogue.ALLERGEN_NAMES.get(code, code)}, "
                         "which your mandate excludes.", pid, "Pick an alternative without it.", allergen=code))
        elif data_missing and code in inferred:
            rs.append(_unknown(m.uncertainty_policy, C.ALLERGEN_DATA_MISSING, f"{name} appears to contain "
                               f"{catalogue.ALLERGEN_NAMES.get(code, code)} from its name, but Valio lists no "
                               "allergen data, so your rule can't be verified.", pid,
                               "Check the label, or pick a product with allergen data.", allergen=code,
                               source="product_name", inferred=True))
        elif word:  # allergen data doesn't list it, but the name does: refuse, no signature can override that
            rs.append(_r(C.ALLERGEN_CONTAINS, DECLINE, f"Name says {word}; your rules exclude "
                         f"{catalogue.ALLERGEN_NAMES.get(code, code)} ({name}).", pid,
                         "Pick an alternative whose label rules it out.", allergen=code, source="product_name", word=word))
        elif code in may_contain:  # (name hits were refused above)
            rs.append(_r(C.ALLERGEN_MAY_CONTAIN, ASK, f"{name} may contain {catalogue.ALLERGEN_NAMES.get(code, code)}.",
                         pid, "Approve if traces are acceptable, or pick an alternative.", allergen=code))
        elif code in undeclared:
            rs.append(_unknown(m.uncertainty_policy, C.ALLERGEN_DATA_MISSING, f"{name} has no allergen data for "
                               f"{catalogue.ALLERGEN_NAMES.get(code, code)}, so your rule can't be verified.", pid,
                               "Check the label, or pick a product with allergen data.", allergen=code))
        elif code not in free_from and not contains:
            rs.append(_unknown(m.uncertainty_policy, C.ALLERGEN_DATA_MISSING, f"{name} has no allergen data for "
                               f"{catalogue.ALLERGEN_NAMES.get(code, code)}, so your rule can't be verified.", pid,
                               "Check the label, or pick a product with allergen data.", allergen=code))

    for floor in _nums(m, RuleKind.MIN_DELIVERY_RELIABILITY):
        rel = cat.get("delivery_reliability")
        if rel is None:
            rs.append(_unknown(m.uncertainty_policy, C.DATA_MISSING, f"No delivery-reliability data for {name}.", pid,
                               "Accept, or pick a product with a reliability record.", min_reliability=floor))
        elif rel < floor:
            rs.append(_r(C.LOW_RELIABILITY, ASK, f"{name} is delivered on time {rel:.0%} of the time, below your "
                         f"{floor:.0%}.", pid, "Approve, or pick a more reliable product.",
                         reliability=rel, min_reliability=floor))
    return rs, info


def _blocking(r: Reason) -> bool:
    return r.severity is DECLINE or r.code in NOT_APPROVABLE or "hard_rule" in r.facts or bool(r.facts.get("not_approvable"))


def _sorted(rs: list[Reason]) -> list[Reason]:
    return sorted(rs, key=lambda r: -_RANK[r.severity])


def _score(q: dict, cat: dict) -> float:
    """Lower is better: net comparison price, made dearer by poor delivery reliability, cheaper if Finnish.
    ponytail: hand-set weights (Finnish origin worth 10% of price, each 10 points of on-time below 100% costs 5%,
    unknown reliability counted as 90%); learn them from the buyer's past picks when there are some."""
    price = q.get("comparison_price") or q.get("price") or float("inf")
    rel = cat.get("delivery_reliability")
    return price * (1 + 0.5 * (1 - (0.9 if rel is None else rel))) * (0.9 if cat.get("origin") == "fi" else 1)


def _why_safe(cat: dict, replaced: dict, excluded: set[str], need: set[str]) -> str:
    keep = sorted((set(replaced.get("claims") or []) & DIETARY_CLAIMS) | need)
    parts = [f"same category ({cat.get('category')}) as {replaced.get('name_en') or replaced['id']}"]
    if excluded:
        names = ", ".join(catalogue.ALLERGEN_NAMES.get(a, a) for a in sorted(excluded))
        parts.append(f"labelled neither containing nor 'may contain' {names}")
    if keep:
        parts.append("keeps " + ", ".join(keep))
    return "; ".join(parts) + "."


async def _alternatives(rejected: list[str], skip: set[str], requested: date, m: Mandate, excluded: set[str],
                        now: datetime) -> tuple[list[Alternative], list[RejectedOption], list[dict], dict[str, dict]]:
    """Allergen-safe substitutes for refused products. Hard filter: same category, the buyer's excluded allergens
    neither CONTAINED nor MAY_CONTAINED (and allergen data present), required + dietary claims kept, orderable on a
    re-quote (check_line with no concerns at all). Then ranked by _score into best / better / good.
    Returns (contract alternatives, rejected candidates, substitutes, {candidate id: quote})."""
    need = {str(c).strip().upper() for c in _rules(m, RuleKind.REQUIRED_CLAIM)}
    cands: dict[str, str] = {}  # candidate id -> the rejected product it replaces
    for pid in rejected:
        cat = catalogue.get(pid)
        if not cat:
            continue
        claims = sorted((set(cat["claims"]) & DIETARY_CLAIMS) | need)
        hits = cat["substitutes"] + [p["id"] for p in catalogue.search("", claims, sorted(excluded), True, cat["category"], 8)]
        for c in hits:
            if c not in skip and c not in m.blocklist and len(cands) < 10:
                cands.setdefault(c, pid)
    if not cands:
        return [], [], [], {}
    try:  # cached quotes are fine here: an alternative is only a suggestion, re-gated with fresh quotes when ordered
        quotes = {q["product_id"]: q for q in await valio.get_quotes(list(cands), requested.isoformat())}
    except Exception:
        log.exception("alternatives lookup failed")  # the order's own verdict stands; just no alternatives
        return [], [], [], {}
    ok, bad = {}, []
    for c, replaces in cands.items():
        q, cat, old = quotes.get(c), catalogue.get(c) or {}, catalogue.get(replaces)
        rs, _ = check_line(c, None, q, requested, m, excluded, now)
        claims = set(cat.get("claims") or [])
        lost = sorted(((set(old["claims"]) & DIETARY_CLAIMS) | need) - claims)
        if not cat.get("category") or cat.get("category") != old.get("category"):  # unknown ≠ same
            rs.append(_r(C.DATA_MISSING, ASK, f"{cat.get('name_en') or c} is not known to be in the same category.", c,
                         "Not offered as a substitute.", category=cat.get("category")))
        al = cat.get("allergens") or {}
        declared = set(al.get("contains") or []) | set(al.get("may_contain") or [])  # name guesses never count as a declaration
        missing = cat.get("allergen_data") == "missing" or not (declared or al.get("free_from"))
        unknown = [a for a in sorted(excluded) if missing or a in (al.get("undeclared") or []) or
                   (not declared and a not in (al.get("free_from") or []))]
        if unknown:  # a substitute must be KNOWN safe, whatever the uncertainty policy says about the order itself
            rs.append(_r(C.ALLERGEN_DATA_MISSING, ASK, f"{cat.get('name_en') or c} has no allergen declaration covering "
                         f"{', '.join(unknown)}.", c, "Not offered as a substitute.", allergens=", ".join(unknown)))
        if q and q.get("price") is not None and eur_to_cents(q["price"]) < 1:
            rs.append(_r(C.PRICE_MISSING, ASK, f"{cat.get('name_en') or c} has no usable price.", c,
                         "Not offered as a substitute.", unit_price_cents=eur_to_cents(q["price"])))
        if lost:
            rs.append(_r(C.DATA_MISSING, ASK, f"{cat.get('name_en') or c} lacks {', '.join(lost)}.", c,
                         "Not offered as a substitute.", missing_claims=", ".join(lost)))
        differs = _differs(old, cat)
        added_allergens = [d.removeprefix("also contains ") for d in differs if d.startswith("also contains ")]
        if added_allergens:
            rs.append(_r(C.ALLERGEN_CONTAINS, ASK,
                         f"{cat.get('name_en') or c} adds allergens ({'; '.join(added_allergens)}) compared with "
                         f"{old.get('name_en') or replaces}.", c, "Not offered as a substitute.",
                         added_allergens=", ".join(added_allergens)))
        if not _same_kind_for_alternative(old, cat):
            rs.append(_r(C.DATA_MISSING, ASK, f"{cat.get('name_en') or c} is not a similar kind of product.", c,
                         "Not offered as a substitute."))
        if [r for r in rs if r.severity is not INFO]:
            bad.append(RejectedOption(product_id=c, reasons=_sorted(rs)))
        else:
            ok.setdefault(replaces, []).append((bool(_differs(old, cat)), _score(q, cat), c, q))
    alts, subs = [], []
    for replaces, ranked in ok.items():
        old = catalogue.get(replaces)
        for i, (_, _, c, q) in enumerate(sorted(ranked, key=lambda x: (x[0], x[1], x[2]))[:len(TIERS)]):
            cat = catalogue.get(c)
            differs = _differs(old, cat)
            tier = "good" if differs else TIERS[i]
            name = cat.get("name_en") or cat.get("name_fi") or c
            spoken_unit = quantity.human_unit(cat, q["sales_unit"])
            amount = "unknown amount" if not q["quantity_known"] else f"{_qty(q['available_amount'])} {spoken_unit} available"
            why = _why_safe(cat, old, excluded, need) + (f" Differs: {'; '.join(differs)}." if differs else "")
            subs.append({"product_id": c, "replaces": replaces, "tier": tier, "why_safe": why, "name": name,
                         "differs": differs,
                         "unit": q["sales_unit"], "unit_price_cents": eur_to_cents(q["price"]),
                         "reliability": cat.get("delivery_reliability"), "origin": cat.get("origin"),
                         "available": q["available_amount"] if q["quantity_known"] else None})
            alts.append((tier, Alternative(product_id=c, summary=(
                f"{tier.upper()} instead of {replaces}: {name}. Safe: {why} Orderable for {requested} (cut-off "
                f"{q['order_cutoff']}), {eur(eur_to_cents(q['price']))} per {spoken_unit} net, {amount}."))))
    alts.sort(key=lambda x: _TIER_ORDER[x[0]])  # the contract allows 3: best first across refused lines
    return [a for _, a in alts[:MAX_ALTERNATIVES]], bad, subs, quotes


def _kind_words(cat: dict) -> set[str]:
    text = " ".join(filter(None, (cat.get("name_en"), cat.get("name_fi")))).lower()
    brand = set(re.findall(r"[a-zäöå]{3,}", (cat.get("brand") or "").lower()))
    words = {w[:-1] if len(w) > 4 and w.endswith("s") else w for w in re.findall(r"[a-zäöå]{3,}", text)}
    return words - _GENERIC_WORDS - brand


def same_kind(old: dict, cat: dict) -> bool:
    """Is the candidate the same KIND of product (blackbox test #9: horseradish for onion, Nutella for peanut butter,
    a rice pasty for bread rolls)? Valio's own substitute list says yes; otherwise the names must share a product
    word (cube / cubes, English or Finnish). No shared word = a different product: never guessed to be the same.
    ponytail: a shared word is a coarse test ("rice cakes" vs "basmati rice" pass); the agent's Gemini acceptability
    judgement on substitutes catches those. A head-noun rule was stricter but split "milk drink" from "milk"."""
    if cat.get("id") in (old.get("substitutes") or []):
        return True
    return bool(_kind_words(old) & _kind_words(cat))


_CROSS_TYPE_WORDS = {"peanut", "maapähkin", "ham", "kinkku", "bacon", "pekoni", "salad", "salaatti",
                     "seasoning", "mauste"}


def _same_kind_for_alternative(old: dict, cat: dict) -> bool:
    """Strict offer check: same-category candidates also need a similar product name and food type."""
    old_words, candidate_words = _kind_words(old), _kind_words(cat)
    if not old_words & candidate_words:
        return False
    introduced = candidate_words - old_words
    return not introduced & _CROSS_TYPE_WORDS


def _differs(old: dict, cat: dict) -> list[str]:
    """What the candidate is that the original isn't, in words for the chef: allergens it ADDS (any of the 15
    named ones, excluded by the mandate or not: QA round 2 N4, e.g. Nugatti for peanut butter), then nutrition
    claims / organic it lacks. Any entry demotes a substitute: never "best", never a split fill."""
    candidate_allergens = set((cat.get("allergens") or {}).get("contains") or []) | set((cat.get("allergens") or {}).get("inferred") or [])
    old_allergens = set((old.get("allergens") or {}).get("contains") or []) | set((old.get("allergens") or {}).get("inferred") or [])
    added = sorted(candidate_allergens & catalogue.ALLERGEN_NAMES.keys() - old_allergens)
    out = ["also contains " + ", ".join(catalogue.ALLERGEN_NAMES[a] for a in added)] if added else []
    lost = sorted((set(old.get("claims") or []) & NUTRITION_CLAIMS) - set(cat.get("claims") or []))
    out += [f"not {c}" for c in lost]
    if set(old.get("labels") or []) & ORGANIC_LABELS and not set(cat.get("labels") or []) & ORGANIC_LABELS:
        out.append("not organic")
    return out


def _step(cat: dict, unit: str | None):
    """Smallest orderable amount: the lot size, but at least one whole unit for piece-type sales units."""
    lot = cat.get("lot_size")
    return lot if unit and unit.upper() in MEASURE_UNITS else max(lot or 0, 1)


def _lot(qty: Decimal, lot, rounding) -> Decimal:
    if not lot:
        return qty
    lot = Decimal(str(lot))
    return (qty / lot).to_integral_value(rounding=rounding) * lot


def _split(pid: str, qty: float, quotes: dict, subs: list[dict], sub_quotes: dict, requested: date, m: Mandate,
           excluded: set[str], now: datetime) -> list[dict] | None:
    """A line short on stock → what's there of it + the rest from the best same-unit substitute, each part passing
    check_line with nothing blocking. None when no such split exists."""
    q, cat = quotes.get(pid), catalogue.get(pid) or {}
    have = _lot(Decimal(str(q["available_amount"] or 0)), _step(cat, q["sales_unit"] or cat.get("sales_unit")), ROUND_FLOOR)
    if have <= 0 or have >= Decimal(str(qty)):
        return None
    a_rs, a = check_line(pid, float(have), q, requested, m, excluded, now)
    if any(_blocking(r) for r in a_rs):
        return None
    for s in (s for s in subs if s["replaces"] == pid and not s["differs"]):  # a split fill must keep the claims
        scat = catalogue.get(s["product_id"]) or {}
        rest = _lot(Decimal(str(qty)) - have, _step(scat, s["unit"] or scat.get("sales_unit")), ROUND_CEILING)
        if rest > MAX_LINE_QTY:
            continue
        b_rs, b = check_line(s["product_id"], float(rest), sub_quotes.get(s["product_id"]), requested, m, excluded, now)
        if a["unit"] and a["unit"] == b["unit"] and not any(_blocking(r) for r in b_rs):  # resolved units, known + equal
            return [a, dict(b, replaces=pid, tier=s["tier"])]
    return None


def _alternative_order(lines: list, info: list[dict], rejected: list[str], quotes: dict, subs: list[dict],
                       sub_quotes: dict, requested: date, m: Mandate, excluded: set[str],
                       now: datetime) -> dict | None:
    """The whole order again with every refused line split; only if every refused line can be (else no proposal)."""
    out, splits = [], []
    for ln, li in zip(lines, info):
        if ln.product_id not in rejected:
            out.append(li)
            continue
        parts = _split(ln.product_id, ln.quantity, quotes, subs, sub_quotes, requested, m, excluded, now)
        if not parts:
            return None
        out += parts
        splits.append(f"{_qty(parts[0]['quantity'])} {quantity.human_unit(catalogue.get(parts[0]['product_id']) or {}, parts[0]['unit'])} "
                      f"of {parts[0]['name']} + {_qty(parts[1]['quantity'])} "
                      f"{quantity.human_unit(catalogue.get(parts[1]['product_id']) or {}, parts[1]['unit'])} "
                      f"of {parts[1]['name']} ({parts[1]['tier']} substitute)")
    if len(out) > MAX_ORDER_LINES:
        return None
    keep = ("product_id", "name", "quantity", "unit", "unit_price_cents", "line_total_cents", "replaces")
    total = sum(li["line_total_cents"] or 0 for li in out)
    return {"lines": [{k: li[k] for k in keep if k in li} for li in out], "total_cents": total,
            "order_lines": [{"product_id": li["product_id"], "quantity": li["quantity"]} for li in out],  # POST as is
            "summary": "Split across products: " + "; ".join(splits) + f". New total {eur(total)} net; "
                       "needs your approval, then order these lines."}


def _no_mandate(lines: list, request_id: str, now: datetime) -> GateResult:
    """No stored mandate = nobody has said what this buyer may order: refuse without asking Valio anything."""
    return _unanswered(lines, request_id, now, _r(
        C.MANDATE_MISSING, ASK, "No mandate is on file for this buyer, so nothing can be ordered on its behalf.",
        None, "Set up the buyer's mandate with Valio, then order again."))


def engine_error(lines: list, request_id: str, now: datetime) -> GateResult:
    """Valio couldn't be asked (down, timeout, 5xx, broken JSON): nothing decided, nothing ordered; for the audit."""
    return _unanswered(lines, request_id, now, _r(
        C.ENGINE_ERROR, ASK, "Valio's price and availability check failed, so nothing was decided or ordered.",
        None, "Retry shortly."))


def _unanswered(lines: list, request_id: str, now: datetime, r: Reason) -> GateResult:
    info = [{"product_id": ln.product_id, "name": (catalogue.get(ln.product_id) or {}).get("name_en") or ln.product_id,
             "quantity": ln.quantity, "unit": None, "unit_price_cents": None, "line_total_cents": None} for ln in lines]
    decision = Decision(request_id=request_id, outcome="ASK_HUMAN", reasons=[r], alternatives=[],
                        rules_version=RULES_VERSION, decided_at=now)
    return GateResult("refused", decision, [], [], info, 0)


async def check(lines: list, requested: date, m: Mandate | None, request_id: str, spent_7d_cents: int = 0,
                approved_prices: dict[str, int] | None = None, now: datetime | None = None,
                forced_reasons: list[Reason] | None = None) -> GateResult:
    """Run every hard check on an order. `lines` items have .product_id and .quantity (sales units).
    `m` is the buyer's STORED mandate (mandates.py), never one from the client; None → refused, MANDATE_MISSING.
    Quotes are fetched here, server-side; nothing the client says about price or stock is trusted."""
    now = now or datetime.now(timezone.utc)
    if m is None:
        return _no_mandate(lines, request_id, now)
    ids = [ln.product_id for ln in lines]
    quotes = {q["product_id"]: q for q in await valio.get_quotes(ids, requested.isoformat(), fresh=True)}

    order_rs: list[Reason] = []
    for rule in m.hard_rules:
        if rule.kind in NUMERIC_RULES and _num(rule.value) is None:
            order_rs.append(_r(C.MANDATE_INVALID, ASK, f"Your {rule.kind.value} rule has a value that isn't a number "
                               f"('{str(rule.value)[:40]}'), so it can't be checked.", None,
                               "Fix the rule in the mandate.", rule_kind=rule.kind.value, rule_value=str(rule.value)[:40]))
    excluded: set[str] = set()
    for v in _rules(m, RuleKind.EXCLUDED_ALLERGEN):
        codes = _allergen_codes(str(v))
        excluded |= codes
        if not codes:
            order_rs.append(_r(C.MANDATE_INVALID, ASK, f"Can't map the excluded allergen '{v}' to Valio's allergen data.",
                               None, "Restate it as a GS1 allergen code (e.g. AP = peanuts).", rule_value=str(v)))
    local_today = now.astimezone(HELSINKI).date() if now.tzinfo else now.date()
    if requested < local_today:  # routes reject this too; the gate must hold whoever calls it
        order_rs.append(_r(C.DATE_NOT_HONOURED, ASK, f"The delivery date {requested} is in the past.", None,
                           "Pick a delivery date from today on.", requested_date=requested.isoformat(), not_approvable=True))
    if m.expires_at and m.expires_at <= now:
        order_rs.append(_r(C.MANDATE_EXPIRED, ASK, f"Your mandate expired at {m.expires_at.isoformat()}.", None,
                           "Approve this order by hand, or renew the mandate.", expires_at=m.expires_at.isoformat()))

    rejected, info, line_rs = [], [], []
    for ln in lines:
        rs, li = check_line(ln.product_id, ln.quantity, quotes.get(ln.product_id), requested, m, excluded, now,
                            (approved_prices or {}).get(ln.product_id))
        info.append(li)
        line_rs += rs
        if any(_blocking(r) for r in rs):
            rejected.append(RejectedOption(product_id=ln.product_id, reasons=_sorted(rs)))

    total = sum(li["line_total_cents"] or 0 for li in info)
    limits = [int(v) for v in _nums(m, RuleKind.AUTO_APPROVE_LIMIT_CENTS)]
    if limits and total > min(limits):
        order_rs.append(_r(C.SPEND_OVER_LIMIT, ASK, f"This order is {eur(total)} (net of VAT), above your "
                           f"{eur(min(limits))} auto-approve limit.", None,
                           "Approve, reduce the quantity to fit the limit, or reject.", total_cents=total, limit_cents=min(limits)))
    if m.weekly_budget_cents and spent_7d_cents + total > m.weekly_budget_cents:
        order_rs.append(_r(C.WEEKLY_BUDGET_EXCEEDED, ASK, f"With this order, the last 7 days come to "
                           f"{eur(spent_7d_cents + total)}, above your {eur(m.weekly_budget_cents)} weekly budget.", None,
                           "Approve, or wait / reduce the order.", spent_7d_cents=spent_7d_cents, total_cents=total,
                           budget_cents=m.weekly_budget_cents))
    order_rs.extend(forced_reasons or [])

    alts, bad_alts, subs, sub_quotes = await _alternatives([ro.product_id for ro in rejected], set(ids), requested, m,
                                                           excluded, now) if rejected else ([], [], [], {})
    alt_order = None
    if rejected and all({r.code for r in ro.reasons if _blocking(r)} == {C.STOCK_PARTIAL} for ro in rejected):
        alt_order = _alternative_order(lines, info, [ro.product_id for ro in rejected], quotes, subs, sub_quotes,
                                       requested, m, excluded, now)
    if alt_order:  # say exactly how to fix the short line(s), still for a human to approve
        line_rs = [r.model_copy(update={"suggested_fix": alt_order["summary"]}) if r.code is C.STOCK_PARTIAL else r
                   for r in line_rs]
    reasons = _sorted(line_rs + order_rs)
    status = ("refused" if any(_blocking(r) for r in reasons)
              else "pending_approval" if any(r.severity is ASK for r in reasons) else "confirmed")
    outcome = {DECLINE: "DECLINE", ASK: "ASK_HUMAN", INFO: "AUTO"}[reasons[0].severity] if reasons else "AUTO"
    decision = Decision(request_id=request_id, outcome=outcome, reasons=reasons, alternatives=alts,
                        rules_version=RULES_VERSION, decided_at=now)
    contract_quotes = []
    for q in quotes.values():
        if cq := valio.to_contract_quote(q):
            cat = catalogue.get(q["product_id"]) or {}
            contract_quotes.append(cq.model_copy(update={"product_name": cat.get("name_en") or cat.get("name_fi")}))
    return GateResult(status, decision, rejected + bad_alts, contract_quotes, info, total, subs, alt_order, m.id)
