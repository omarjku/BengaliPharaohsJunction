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

from trade_contracts import (Alternative, Decision, Mandate, Quote, Reason, ReasonCode as C, RejectedOption, Severity,
                             eur_to_cents)
from trade_contracts.common import RuleKind, UncertaintyPolicy

from . import catalogue, valio

RULES_VERSION = "t07-front-door-0.2"
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
    # {lines: [{product_id, quantity, unit, unit_price_cents, line_total_cents, name, replaces?}], total_cents, summary}
    alternative_order: dict | None = None


def eur(cents: int) -> str:
    return f"EUR {cents / 100:,.2f}"


def _qty(x: float) -> str:
    return f"{x:,.2f}".rstrip("0").rstrip(".")


def _r(code: C, severity: Severity, message: str, pid: str | None = None, fix: str | None = None, **facts) -> Reason:
    return Reason(code=code, severity=severity, message=message, facts=facts, suggested_fix=fix, product_id=pid)


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


def _cutoff_passed(q: dict, now: datetime) -> bool:
    # Re-check against the clock: quotes are cached up to valio.CACHE_TTL_S, the flag may be that old.
    return "cutoff_passed" in q["flags"] or bool(q["order_cutoff"] and datetime.fromisoformat(q["order_cutoff"]) <= now)


def check_line(pid: str, qty: float | None, q: dict | None, requested: date, m: Mandate, excluded: set[str],
               now: datetime, approved_price: int | None = None) -> tuple[list[Reason], dict]:
    """All hard checks for one product. qty=None checks a candidate alternative (no quantity yet)."""
    rs: list[Reason] = []
    cat = catalogue.get(pid)
    name = (cat or {}).get("name_en") or (cat or {}).get("name_fi") or pid
    info = {"product_id": pid, "name": name, "quantity": qty, "unit": None, "unit_price_cents": None, "line_total_cents": None}
    if pid in m.blocklist:
        rs.append(_r(C.BLOCKLISTED, DECLINE, f"{name} is on your blocklist.", pid, "Pick another product."))
    if cat is None or q is None or "unknown_product" in q["flags"]:
        rs.append(_r(C.UNKNOWN_PRODUCT, DECLINE, f"Product {pid} is not in Valio's catalogue.", pid,
                     "Check the product id."))
        return rs, info
    info["unit"] = q["sales_unit"] or cat.get("sales_unit")
    unit = info["unit"] or "unit"

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
        rs.append(_unknown(m.uncertainty_policy, C.QTY_UNKNOWN,
                           f"Valio can't confirm how much {name} is available (Terminal product, stock reported as 999999 = unknown).",
                           pid, "Accept the risk that Valio may deliver less, or pick a stocked alternative."))
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
    if qty is not None and lot and Decimal(str(qty)) % Decimal(str(lot)) != 0:
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
    for code in sorted(excluded):
        if code in al.get("contains", []):
            rs.append(_r(C.ALLERGEN_CONTAINS, DECLINE, f"{name} contains {catalogue.ALLERGEN_NAMES.get(code, code)}, "
                         "which your mandate excludes.", pid, "Pick an alternative without it.", allergen=code))
        elif code in al.get("may_contain", []):
            rs.append(_r(C.ALLERGEN_MAY_CONTAIN, ASK, f"{name} may contain {catalogue.ALLERGEN_NAMES.get(code, code)}.",
                         pid, "Approve if traces are acceptable, or pick an alternative.", allergen=code))
    if excluded and not any(al.get(k) for k in ("contains", "may_contain", "free_from")):
        rs.append(_unknown(m.uncertainty_policy, C.ALLERGEN_DATA_MISSING, f"{name} has no allergen data, so your "
                           "allergen rules can't be verified.", pid, "Check the label, or pick a product with allergen data."))

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
        if cat and cat.get("category") != old.get("category"):
            rs.append(_r(C.DATA_MISSING, ASK, f"{cat.get('name_en') or c} is in another category.", c,
                         "Not offered as a substitute.", category=cat.get("category")))
        if lost:
            rs.append(_r(C.DATA_MISSING, ASK, f"{cat.get('name_en') or c} lacks {', '.join(lost)}.", c,
                         "Not offered as a substitute.", missing_claims=", ".join(lost)))
        if [r for r in rs if r.severity is not INFO]:
            bad.append(RejectedOption(product_id=c, reasons=_sorted(rs)))
        else:
            ok.setdefault(replaces, []).append((_score(q, cat), c, q))
    alts, subs = [], []
    for replaces, ranked in ok.items():
        old = catalogue.get(replaces)
        for tier, (_, c, q) in zip(TIERS, sorted(ranked, key=lambda x: (x[0], x[1]))):
            cat = catalogue.get(c)
            name = cat.get("name_en") or cat.get("name_fi") or c
            amount = "unknown amount" if not q["quantity_known"] else f"{_qty(q['available_amount'])} {q['sales_unit']} available"
            why = _why_safe(cat, old, excluded, need)
            subs.append({"product_id": c, "replaces": replaces, "tier": tier, "why_safe": why, "name": name,
                         "unit": q["sales_unit"], "unit_price_cents": eur_to_cents(q["price"]),
                         "reliability": cat.get("delivery_reliability"), "origin": cat.get("origin"),
                         "available": q["available_amount"] if q["quantity_known"] else None})
            alts.append((tier, Alternative(product_id=c, summary=(
                f"{tier.upper()} instead of {replaces}: {name}. Safe: {why} Orderable for {requested} (cut-off "
                f"{q['order_cutoff']}), {eur(eur_to_cents(q['price']))} per {q['sales_unit']} net, {amount}."))))
    alts.sort(key=lambda x: TIERS.index(x[0]))  # the contract allows 3: best first across refused lines
    return [a for _, a in alts[:MAX_ALTERNATIVES]], bad, subs, quotes


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
    have = _lot(Decimal(str(q["available_amount"] or 0)), cat.get("lot_size"), ROUND_FLOOR)
    if have <= 0 or have >= Decimal(str(qty)):
        return None
    a_rs, a = check_line(pid, float(have), q, requested, m, excluded, now)
    if any(_blocking(r) for r in a_rs):
        return None
    for s in (s for s in subs if s["replaces"] == pid and s["unit"] == q["sales_unit"]):
        rest = _lot(Decimal(str(qty)) - have, (catalogue.get(s["product_id"]) or {}).get("lot_size"), ROUND_CEILING)
        b_rs, b = check_line(s["product_id"], float(rest), sub_quotes.get(s["product_id"]), requested, m, excluded, now)
        if not any(_blocking(r) for r in b_rs):
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
        splits.append(f"{_qty(parts[0]['quantity'])} {parts[0]['unit']} of {parts[0]['name']} + "
                      f"{_qty(parts[1]['quantity'])} {parts[1]['unit']} of {parts[1]['name']} ({parts[1]['tier']} substitute)")
    keep = ("product_id", "name", "quantity", "unit", "unit_price_cents", "line_total_cents", "replaces")
    total = sum(li["line_total_cents"] or 0 for li in out)
    return {"lines": [{k: li[k] for k in keep if k in li} for li in out], "total_cents": total,
            "summary": "Split across products: " + "; ".join(splits) + f". New total {eur(total)} net; "
                       "needs your approval, then order these lines."}


def _no_mandate(lines: list, request_id: str, now: datetime) -> GateResult:
    """No stored mandate = nobody has said what this buyer may order: refuse without asking Valio anything."""
    r = _r(C.MANDATE_MISSING, ASK, "No mandate is on file for this buyer, so nothing can be ordered on its behalf.",
           None, "Set up the buyer's mandate with Valio, then order again.")
    info = [{"product_id": ln.product_id, "name": (catalogue.get(ln.product_id) or {}).get("name_en") or ln.product_id,
             "quantity": ln.quantity, "unit": None, "unit_price_cents": None, "line_total_cents": None} for ln in lines]
    decision = Decision(request_id=request_id, outcome="ASK_HUMAN", reasons=[r], alternatives=[],
                        rules_version=RULES_VERSION, decided_at=now)
    return GateResult("refused", decision, [], [], info, 0)


async def check(lines: list, requested: date, m: Mandate | None, request_id: str, spent_7d_cents: int = 0,
                approved_prices: dict[str, int] | None = None, now: datetime | None = None) -> GateResult:
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
    if requested < now.date():  # routes reject this too; the gate must hold whoever calls it
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
    return GateResult(status, decision, rejected + bad_alts, contract_quotes, info, total, subs, alt_order)
