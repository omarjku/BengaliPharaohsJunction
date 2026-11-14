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
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

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


@dataclass
class GateResult:
    status: str  # "confirmed" | "pending_approval" | "refused": the door's verdict
    decision: Decision
    rejected_options: list[RejectedOption]
    quotes: list[Quote]
    lines: list[dict]
    total_cents: int


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
    return r.severity is DECLINE or r.code in NOT_APPROVABLE or "hard_rule" in r.facts


def _sorted(rs: list[Reason]) -> list[Reason]:
    return sorted(rs, key=lambda r: -_RANK[r.severity])


async def _alternatives(rejected: list[str], skip: set[str], requested: date, m: Mandate, excluded: set[str],
                        now: datetime) -> tuple[list[Alternative], list[RejectedOption]]:
    """Same category + same dietary claims, minus excluded allergens; re-quoted so we only offer orderable ones."""
    need = {str(c).strip().upper() for c in _rules(m, RuleKind.REQUIRED_CLAIM)}
    cands: dict[str, str] = {}  # candidate id -> the rejected product it replaces
    for pid in rejected:
        cat = catalogue.get(pid)
        if not cat:
            continue
        claims = sorted((set(cat["claims"]) & DIETARY_CLAIMS) | need)
        hits = cat["substitutes"] + [p["id"] for p in catalogue.search("", claims, sorted(excluded), False, cat["category"], 8)]
        for c in hits:
            if c not in skip and c not in m.blocklist and len(cands) < 10:
                cands.setdefault(c, pid)
    if not cands:
        return [], []
    try:  # cached quotes are fine here: an alternative is only a suggestion, re-gated with fresh quotes when ordered
        quotes = {q["product_id"]: q for q in await valio.get_quotes(list(cands), requested.isoformat())}
    except Exception:
        log.exception("alternatives lookup failed")  # the order's own verdict stands; just no alternatives
        return [], []
    ok, bad = [], []
    for c, replaces in cands.items():
        q = quotes.get(c)
        rs, _ = check_line(c, None, q, requested, m, excluded, now)
        if [r for r in rs if r.severity is not INFO]:
            bad.append(RejectedOption(product_id=c, reasons=_sorted(rs)))
        else:
            ok.append((q.get("comparison_price") or float("inf"), c, replaces, q))
    alts = []
    for _, c, replaces, q in sorted(ok, key=lambda x: (x[0], x[1]))[:MAX_ALTERNATIVES]:
        cat = catalogue.get(c)
        amount = "unknown amount" if not q["quantity_known"] else f"{_qty(q['available_amount'])} {q['sales_unit']} available"
        alts.append(Alternative(product_id=c, summary=(
            f"Instead of {replaces}: {cat.get('name_en') or cat.get('name_fi')}, same category and dietary claims, "
            f"orderable for {requested} (cut-off {q['order_cutoff']}), {eur(eur_to_cents(q['price']))} per "
            f"{q['sales_unit']} net, {amount}.")))
    return alts, bad


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

    reasons = _sorted(line_rs + order_rs)
    alts, bad_alts = await _alternatives([ro.product_id for ro in rejected], set(ids), requested, m, excluded, now) \
        if rejected else ([], [])
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
    return GateResult(status, decision, rejected + bad_alts, contract_quotes, info, total)
