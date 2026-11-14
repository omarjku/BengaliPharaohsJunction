"""The rules. Each rule is a pure function RuleContext -> list[Reason] (empty = no finding).

Rules never raise on bad data; they answer with a reason. Unknown data is never OK and never
bad: it is ASK_HUMAN ("we can't confirm X"). DECLINE is only for trade_contracts.HARD_CODES.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from trade_contracts import Reason, ReasonCode, Severity
from trade_contracts.common import AllergenStatus, Availability, RuleKind, UncertaintyPolicy

from .merge import valid_quantity
from .reasons import make_reason
from .types import OrderLine, RuleContext

Rule = Callable[[RuleContext], list[Reason]]

DEFAULT_PER_LINE_CAP_CENTS = 30000

# Rule kinds the engine cannot check yet (no claims data in ProductFacts; no unit-price check).
# They are never silently skipped: check_mandate asks a human instead.
_UNENFORCED_KINDS = frozenset({RuleKind.REQUIRED_CLAIM, RuleKind.MAX_UNIT_PRICE_CENTS})

# ----------------------------------------------------------------------------- helpers


def _num(x: float) -> int | float:
    """Integral floats shown as ints (stable, readable facts)."""
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return x


def _name(ctx: RuleContext, pid: str) -> str:
    q = ctx.quotes.get(pid)
    f = ctx.facts.get(pid)
    for candidate in (
        f.name_en if f else None,
        q.product_name if q else None,
        f.name_fi if f else None,
    ):
        if candidate:
            return candidate
    return pid


def _aware(ctx: RuleContext) -> datetime:
    now = ctx.now
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo(ctx.config.timezone))
    return now


def _line_total_cents(line: OrderLine, price: int | None) -> int | None:
    if not valid_quantity(line.quantity):
        return None
    if isinstance(price, bool) or not isinstance(price, int) or price <= 0:
        return None
    total = Decimal(repr(line.quantity)) * Decimal(price)
    return int(total.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _line_totals(ctx: RuleContext) -> list[tuple[OrderLine, int]]:
    out = []
    for line in ctx.lines:
        q = ctx.quotes.get(line.product_id)
        if q is None:
            continue
        total = _line_total_cents(line, q.unit_price_cents)
        if total is not None:
            out.append((line, total))
    return out


def _order_total(ctx: RuleContext) -> int:
    return sum(t for _, t in _line_totals(ctx))


def _limit_values(ctx: RuleContext) -> tuple[list[int], bool]:
    """(valid limits, any_invalid) from AUTO_APPROVE_LIMIT_CENTS rules."""
    valid: list[int] = []
    invalid = False
    if ctx.mandate is None:
        return valid, invalid
    for rule in ctx.mandate.hard_rules:
        if rule.kind is not RuleKind.AUTO_APPROVE_LIMIT_CENTS:
            continue
        v = rule.value
        if isinstance(v, bool | str) or not math.isfinite(v) or v <= 0:
            invalid = True
            continue
        valid.append(int(v))
    return valid, invalid


def order_limit_cents(ctx: RuleContext) -> int:
    """Per-order limit: the mandate rule (the lowest, if several), else the config default."""
    valid, _ = _limit_values(ctx)
    return min(valid) if valid else ctx.config.default_order_limit_cents


def _per_line_cap(ctx: RuleContext) -> int:
    return ctx.mandate.per_line_cap_cents if ctx.mandate else DEFAULT_PER_LINE_CAP_CENTS


def _min_reliability(ctx: RuleContext) -> float:
    base = ctx.config.min_reliability
    if ctx.mandate is not None:
        for rule in ctx.mandate.hard_rules:
            v = rule.value
            if (
                rule.kind is RuleKind.MIN_DELIVERY_RELIABILITY
                and not isinstance(v, str | bool)
                and math.isfinite(v)
                and v > base
            ):
                base = float(v)
    return base


def _excluded_allergens(ctx: RuleContext) -> list[str]:
    if ctx.mandate is None:
        return []
    seen: list[str] = []
    for rule in ctx.mandate.hard_rules:
        if rule.kind is RuleKind.EXCLUDED_ALLERGEN:
            name = str(rule.value).strip().lower()
            if name and name not in seen:
                seen.append(name)
    return seen


def _allergen_status(allergens: dict, name: str) -> AllergenStatus | None:
    for key, status in allergens.items():
        if str(key).strip().lower() == name:
            return status
    return None


_VOLUME = {"l", "litre", "litres", "liter", "liters", "ml", "dl", "cl"}
_MASS = {"kg", "g", "gram", "grams", "kilo", "kilos", "kilogram", "kilograms", "mg"}
_COUNT = {
    "pcs", "pc", "piece", "pieces", "ct", "count", "st", "kpl", "each",
    "carton", "cartons", "case", "cases", "box", "boxes", "pack", "packs",
}  # fmt: skip


def unit_family(text: str | None) -> str | None:
    """'volume' / 'mass' / 'count' from free unit text; None when it cannot be told."""
    if not text:
        return None
    tokens = set(re.findall(r"[a-zåäö]+", text.lower()))
    if tokens & _VOLUME:
        return "volume"
    if tokens & _MASS:
        return "mass"
    if tokens & _COUNT:
        return "count"
    return None


# ----------------------------------------------------------------------------- rules


def check_mandate(ctx: RuleContext) -> list[Reason]:
    """D15/D16, cases 42, 47: missing / expired / unreadable mandate -> ASK; defaulted -> INFO;
    (T06.1: no text-based limit-change detection; the mandate cannot be changed from a request)."""
    out: list[Reason] = []
    mandate = ctx.mandate
    if mandate is None:
        out.append(make_reason(ReasonCode.MANDATE_MISSING, Severity.ASK_HUMAN))
    else:
        now = _aware(ctx)
        if mandate.expires_at is not None and now > mandate.expires_at:
            local = mandate.expires_at.astimezone(ZoneInfo(ctx.config.timezone))
            out.append(
                make_reason(
                    ReasonCode.MANDATE_EXPIRED,
                    Severity.ASK_HUMAN,
                    {
                        "expires_at": mandate.expires_at.isoformat(),
                        "expired_at": local.strftime("%a %d %b %H:%M"),
                    },
                )
            )
        valid, invalid = _limit_values(ctx)
        if invalid:
            out.append(
                make_reason(
                    ReasonCode.MANDATE_INVALID,
                    Severity.ASK_HUMAN,
                    {"detail": "Can't read the auto-approve limit in your rules, so I can't apply it."},
                )
            )
        elif len(set(valid)) > 1:
            out.append(
                make_reason(
                    ReasonCode.MANDATE_INVALID,
                    Severity.ASK_HUMAN,
                    {
                        "detail": "Your rules give conflicting auto-approve limits; "
                        "I used the lowest.",
                        "limits": ",".join(str(v) for v in sorted(set(valid))),
                    },
                )
            )
        unchecked = sorted({r.kind.value for r in mandate.hard_rules if r.kind in _UNENFORCED_KINDS})
        if unchecked:
            # Never drop a rule the buyer wrote: if we cannot check it, a person must.
            out.append(
                make_reason(
                    ReasonCode.MANDATE_INVALID,
                    Severity.ASK_HUMAN,
                    {
                        "detail": "Your rules include "
                        + ", ".join(k.replace("_", " ") for k in unchecked)
                        + ", which this check cannot verify yet, so a person must check.",
                        "rule_kinds": ",".join(unchecked),
                    },
                )
            )
        if mandate.open_questions:
            out.append(
                make_reason(
                    ReasonCode.MANDATE_INVALID,
                    Severity.ASK_HUMAN,
                    {
                        "detail": "Some of your rules could not be read and are still open "
                        f"questions ({len(mandate.open_questions)}).",
                        "open_questions": len(mandate.open_questions),
                    },
                )
            )
        if ctx.mandate_defaulted:
            out.append(
                make_reason(
                    ReasonCode.DEFAULT_MANDATE_APPLIED,
                    Severity.INFO,
                    {"limit_cents": order_limit_cents(ctx)},
                )
            )
    return out


def check_quantity(ctx: RuleContext) -> list[Reason]:
    """Cases 1-3, 8, 15, D7: invalid (None/NaN/<=0/empty order) -> DECLINE QTY_INVALID;
    typo-sized request -> QTY_SUSPICIOUS (ASK)."""
    out: list[Reason] = []
    if not ctx.lines:
        return [make_reason(ReasonCode.QTY_INVALID, Severity.DECLINE, {"lines": 0})]
    for line in ctx.lines:
        if not valid_quantity(line.quantity):
            shown = None if line.quantity is None or not isinstance(line.quantity, int | float) else (
                str(line.quantity)
            )
            out.append(
                make_reason(
                    ReasonCode.QTY_INVALID,
                    Severity.DECLINE,
                    {"quantity": shown, "product": _name(ctx, line.product_id)},
                    line.product_id,
                )
            )
        elif line.quantity >= ctx.config.suspicious_quantity:  # type: ignore[operator]
            out.append(
                make_reason(
                    ReasonCode.QTY_SUSPICIOUS,
                    Severity.ASK_HUMAN,
                    {
                        "quantity": _num(line.quantity),  # type: ignore[arg-type]
                        "threshold": _num(ctx.config.suspicious_quantity),
                        "product": _name(ctx, line.product_id),
                    },
                    line.product_id,
                )
            )
    return out


def check_product(ctx: RuleContext) -> list[Reason]:
    """Case 25, 39: no quote AND no facts for a line's product -> DECLINE UNKNOWN_PRODUCT
    (attach alternatives); only one of them missing -> DATA_MISSING (ASK)."""
    out: list[Reason] = []
    for line in ctx.lines:
        pid = line.product_id
        has_q = pid in ctx.quotes
        has_f = pid in ctx.facts
        if not has_q and not has_f:
            out.append(
                make_reason(
                    ReasonCode.UNKNOWN_PRODUCT, Severity.DECLINE, {"product_id": pid}, pid
                )
            )
        elif has_f and ctx.facts[pid].category is None and _excluded_allergens(ctx):
            out.append(
                make_reason(
                    ReasonCode.DATA_MISSING,
                    Severity.ASK_HUMAN,
                    {"missing": "category", "product": _name(ctx, pid)},
                    pid,
                )
            )
            if not has_q:
                out.append(
                    make_reason(
                        ReasonCode.DATA_MISSING,
                        Severity.ASK_HUMAN,
                        {"missing": "quote", "product": _name(ctx, pid)},
                        pid,
                    )
                )
        elif has_q != has_f:
            out.append(
                make_reason(
                    ReasonCode.DATA_MISSING,
                    Severity.ASK_HUMAN,
                    {
                        "missing": "product facts" if has_q else "quote",
                        "product": _name(ctx, pid),
                    },
                    pid,
                )
            )
    return out


def check_data_conflicts(ctx: RuleContext) -> list[Reason]:
    """T06.1: a product that appears twice in quotes or facts with different content cannot be
    trusted (the engine keeps one copy); ordered products among them ask a human."""
    out: list[Reason] = []
    for pid in sorted({line.product_id for line in ctx.lines} & ctx.conflicts):
        out.append(
            make_reason(
                ReasonCode.DATA_MISSING,
                Severity.ASK_HUMAN,
                {"missing": "consistent data", "product": _name(ctx, pid), "conflict": True},
                pid,
            )
        )
    return out


def check_blocklist(ctx: RuleContext) -> list[Reason]:
    """D4/D5: product on mandate.blocklist -> DECLINE BLOCKLISTED."""
    if ctx.mandate is None:
        return []
    blocked = set(ctx.mandate.blocklist)
    return [
        make_reason(
            ReasonCode.BLOCKLISTED,
            Severity.DECLINE,
            {"product": _name(ctx, line.product_id)},
            line.product_id,
        )
        for line in ctx.lines
        if line.product_id in blocked
    ]


def check_allergens(ctx: RuleContext) -> list[Reason]:
    """D12, cases 34, 37, 40, 41: CONTAINS -> DECLINE; MAY_CONTAIN -> ASK; missing data with
    exclusions -> ASK (DECLINE POLICY_DECLINE_UNKNOWN if uncertainty_policy == decline);
    policy 'approve' never loosens an allergen rule."""
    out: list[Reason] = []
    excluded = _excluded_allergens(ctx)
    if not excluded or ctx.mandate is None:
        return out
    decline_unknown = ctx.mandate.uncertainty_policy is UncertaintyPolicy.DECLINE
    for line in ctx.lines:
        facts = ctx.facts.get(line.product_id)
        if facts is None:
            continue  # check_product already reports the missing data
        product = _name(ctx, line.product_id)
        for allergen in excluded:
            status = _allergen_status(facts.allergens, allergen)
            base = {"allergen": allergen, "product": product}
            if status is AllergenStatus.CONTAINS:
                out.append(
                    make_reason(
                        ReasonCode.ALLERGEN_CONTAINS, Severity.DECLINE, base, line.product_id
                    )
                )
            elif status is AllergenStatus.MAY_CONTAIN:
                out.append(
                    make_reason(
                        ReasonCode.ALLERGEN_MAY_CONTAIN,
                        Severity.ASK_HUMAN,
                        base,
                        line.product_id,
                    )
                )
            elif status is AllergenStatus.FREE_FROM:
                continue
            elif decline_unknown:
                out.append(
                    make_reason(
                        ReasonCode.POLICY_DECLINE_UNKNOWN, Severity.DECLINE, base, line.product_id
                    )
                )
            else:
                out.append(
                    make_reason(
                        ReasonCode.ALLERGEN_DATA_MISSING,
                        Severity.ASK_HUMAN,
                        base,
                        line.product_id,
                    )
                )
    return out


def check_price(ctx: RuleContext) -> list[Reason]:
    """D11, cases 23, 24: price None/<=0 -> ASK PRICE_MISSING; moved > tolerance vs
    expected_unit_price_cents -> ASK PRICE_CHANGED."""
    out: list[Reason] = []
    for line in ctx.lines:
        quote = ctx.quotes.get(line.product_id)
        if quote is None:
            continue
        price = quote.unit_price_cents
        product = _name(ctx, line.product_id)
        if price is None or price <= 0:
            out.append(
                make_reason(
                    ReasonCode.PRICE_MISSING,
                    Severity.ASK_HUMAN,
                    {"product": product, "price_cents": price},
                    line.product_id,
                )
            )
            continue
        expected = line.expected_unit_price_cents
        if isinstance(expected, int) and not isinstance(expected, bool) and expected > 0:
            change = abs(price - expected) * 100 / expected
            if change > ctx.config.price_change_tolerance_pct:
                signed = (price - expected) * 100 / expected
                out.append(
                    make_reason(
                        ReasonCode.PRICE_CHANGED,
                        Severity.ASK_HUMAN,
                        {
                            "product": product,
                            "expected_cents": expected,
                            "price_cents": price,
                            "change_pct": round(signed, 1),
                            "tolerance_pct": ctx.config.price_change_tolerance_pct,
                        },
                        line.product_id,
                    )
                )
    return out


def check_units(ctx: RuleContext) -> list[Reason]:
    """Case 12, 13: unit family of line.unit vs facts.sales_unit (volume/mass/count) differs ->
    ASK UNIT_MISMATCH (only when both families are known); below min_order_qty -> ASK."""
    out: list[Reason] = []
    for line in ctx.lines:
        facts = ctx.facts.get(line.product_id)
        if facts is None:
            continue
        product = _name(ctx, line.product_id)
        want = unit_family(line.unit)
        have = unit_family(facts.sales_unit)
        if want is not None and have is not None and want != have:
            out.append(
                make_reason(
                    ReasonCode.UNIT_MISMATCH,
                    Severity.ASK_HUMAN,
                    {
                        "product": product,
                        "requested_unit": line.unit,
                        "sales_unit": facts.sales_unit,
                        "requested_family": want,
                        "sales_family": have,
                    },
                    line.product_id,
                )
            )
        if (
            facts.min_order_qty is not None
            and valid_quantity(line.quantity)
            and line.quantity < facts.min_order_qty  # type: ignore[operator]
        ):
            out.append(
                make_reason(
                    ReasonCode.QTY_AMBIGUOUS,
                    Severity.ASK_HUMAN,
                    {
                        "product": product,
                        "quantity": _num(line.quantity),  # type: ignore[arg-type]
                        "min_order_qty": _num(facts.min_order_qty),
                    },
                    line.product_id,
                )
            )
    return out


def _qty_unknown(ctx: RuleContext, quote) -> bool:
    info = quote.quantity
    return (
        not info.known
        or info.value is None
        or info.value in ctx.config.unknown_quantity_sentinels
    )


def check_stock(ctx: RuleContext) -> list[Reason]:
    """D7, D8, cases 4-8: unknown qty (known=False, None or the exact placeholder 999999) -> QTY_UNKNOWN;
    0 < available < requested -> STOCK_PARTIAL; available == 0 -> STOCK_NONE. All ASK,
    always with alternatives. Compare against the MERGED line quantity."""
    out: list[Reason] = []
    for line in ctx.lines:
        quote = ctx.quotes.get(line.product_id)
        if quote is None or not valid_quantity(line.quantity):
            continue
        product = _name(ctx, line.product_id)
        requested = _num(line.quantity)  # type: ignore[arg-type]
        if _qty_unknown(ctx, quote):
            if quote.availability is Availability.UNAVAILABLE:
                continue  # reported as UNDELIVERABLE by check_delivery
            out.append(
                make_reason(
                    ReasonCode.QTY_UNKNOWN,
                    Severity.ASK_HUMAN,
                    {
                        "product": product,
                        "requested": requested,
                        "reported_value": quote.quantity.value,
                        "known": quote.quantity.known,
                    },
                    line.product_id,
                )
            )
            continue
        available = quote.quantity.value or 0
        if available == 0:
            out.append(
                make_reason(
                    ReasonCode.STOCK_NONE,
                    Severity.ASK_HUMAN,
                    {"product": product, "requested": requested, "available": 0},
                    line.product_id,
                )
            )
        elif available < line.quantity:  # type: ignore[operator]
            coverage = available / line.quantity  # type: ignore[operator]
            out.append(
                make_reason(
                    ReasonCode.STOCK_PARTIAL,
                    Severity.ASK_HUMAN,
                    {
                        "product": product,
                        "requested": requested,
                        "available": available,
                        "coverage_pct": round(coverage * 100, 1),
                        "preselect_partial": coverage >= ctx.config.partial_preselect_coverage,
                    },
                    line.product_id,
                )
            )
    return out


def check_cutoff(ctx: RuleContext) -> list[Reason]:
    """D9, case 16-17: compare quote.cut_off.closing_time to ctx.now in config.timezone
    (passed = the flag OR the clock); reached = passed -> ASK CUTOFF_PASSED with alternatives."""
    out: list[Reason] = []
    tz = ZoneInfo(ctx.config.timezone)
    now = _aware(ctx).astimezone(tz)
    for line in ctx.lines:
        quote = ctx.quotes.get(line.product_id)
        if quote is None or quote.cut_off is None:
            continue
        closing = quote.cut_off.closing_time.astimezone(tz)
        if now >= closing or quote.cut_off.passed:
            out.append(
                make_reason(
                    ReasonCode.CUTOFF_PASSED,
                    Severity.ASK_HUMAN,
                    {
                        "product": _name(ctx, line.product_id),
                        "closing": closing.strftime("%A %H:%M"),
                        "closing_time": closing.isoformat(),
                    },
                    line.product_id,
                )
            )
    return out


def check_delivery(ctx: RuleContext) -> list[Reason]:
    """D10, D13, D14, cases 18-22: UNDELIVERABLE (availability UNAVAILABLE, whatever the stock
    number says; any other non-AVAILABLE status asks too), DATE_NOT_HONOURED (INFO always; ASK when the
    available_date is later than request.needed_by), LOW_RELIABILITY (< min_reliability; missing
    record only ASK above reliability_missing_ask_above_cents), QUOTE_STALE."""
    out: list[Reason] = []
    now = _aware(ctx)
    total = _order_total(ctx)
    min_rel = _min_reliability(ctx)
    rel_rule = ctx.mandate is not None and any(
        r.kind is RuleKind.MIN_DELIVERY_RELIABILITY for r in ctx.mandate.hard_rules
    )
    needed = ctx.request.needed_by
    for line in ctx.lines:
        pid = line.product_id
        quote = ctx.quotes.get(pid)
        facts = ctx.facts.get(pid)
        product = _name(ctx, pid)
        if quote is not None:
            if quote.availability is Availability.UNAVAILABLE:
                # sales-blocked / undeliverable: never AUTO, even with a normal-looking stock number
                out.append(
                    make_reason(ReasonCode.UNDELIVERABLE, Severity.ASK_HUMAN, {"product": product}, pid)
                )
            elif quote.availability is not Availability.AVAILABLE:
                out.append(
                    make_reason(
                        ReasonCode.DATA_MISSING,
                        Severity.ASK_HUMAN,
                        {
                            "missing": "confirmed availability",
                            "product": product,
                            "availability": quote.availability.value,
                        },
                        pid,
                    )
                )
            avail_date = quote.available_date
            if avail_date is not None and needed is not None and avail_date != needed:
                late = avail_date > needed
                out.append(
                    make_reason(
                        ReasonCode.DATE_NOT_HONOURED,
                        Severity.ASK_HUMAN if late else Severity.INFO,
                        {
                            "product": product,
                            "available_date": avail_date.isoformat(),
                            "needed_by": needed.isoformat(),
                        },
                        pid,
                    )
                )
            age = (now - quote.fetched_at).total_seconds()
            expired = quote.valid_until is not None and now > quote.valid_until
            if age > ctx.config.quote_max_age_seconds or expired:
                out.append(
                    make_reason(
                        ReasonCode.QUOTE_STALE,
                        Severity.ASK_HUMAN,
                        {
                            "product": product,
                            "age_minutes": int(age // 60),
                            "max_age_seconds": ctx.config.quote_max_age_seconds,
                            "past_valid_until": expired,
                        },
                        pid,
                    )
                )
        if facts is not None:
            score = facts.reliability
            if score is None:
                if rel_rule or total > ctx.config.reliability_missing_ask_above_cents:
                    out.append(
                        make_reason(
                            ReasonCode.LOW_RELIABILITY,
                            Severity.ASK_HUMAN,
                            {
                                "detail": f"No delivery track record for {product}, and "
                                + (
                                    "your rules require a minimum reliability."
                                    if rel_rule
                                    else "this order is large enough to matter."
                                ),
                                "reliability": None,
                                "order_total_cents": total,
                            },
                            pid,
                        )
                    )
            elif score < min_rel:
                out.append(
                    make_reason(
                        ReasonCode.LOW_RELIABILITY,
                        Severity.ASK_HUMAN,
                        {
                            "detail": f"{product} delivers on time {score:.0%} of the time, "
                            f"below your {min_rel:.0%} minimum.",
                            "reliability": score,
                            "min_reliability": min_rel,
                        },
                        pid,
                    )
                )
    return out


def check_spend(ctx: RuleContext) -> list[Reason]:
    """D1, D2, cases 27-29, 32: net-of-VAT line total > mandate.per_line_cap_cents -> LINE_OVER_CAP;
    order total > order limit (mandate AUTO_APPROVE_LIMIT_CENTS rule, else config default) ->
    SPEND_OVER_LIMIT; recent_spend_cents + total > weekly_budget_cents -> WEEKLY_BUDGET_EXCEEDED.
    Integer cents only; exactly at the limit is allowed."""
    out: list[Reason] = []
    totals = _line_totals(ctx)
    cap = _per_line_cap(ctx)
    for line, lt in totals:
        if lt > cap:
            out.append(
                make_reason(
                    ReasonCode.LINE_OVER_CAP,
                    Severity.ASK_HUMAN,
                    {
                        "product": _name(ctx, line.product_id),
                        "line_total_cents": lt,
                        "cap_cents": cap,
                        "over_cents": lt - cap,
                    },
                    line.product_id,
                )
            )
    total = sum(t for _, t in totals)
    limit = order_limit_cents(ctx)
    if total > limit:
        out.append(
            make_reason(
                ReasonCode.SPEND_OVER_LIMIT,
                Severity.ASK_HUMAN,
                {"total_cents": total, "limit_cents": limit, "over_cents": total - limit},
            )
        )
    budget = ctx.mandate.weekly_budget_cents if ctx.mandate else None
    if budget is not None:
        recent = ctx.recent_spend_cents
        projected = recent + total
        if projected > budget:
            out.append(
                make_reason(
                    ReasonCode.WEEKLY_BUDGET_EXCEEDED,
                    Severity.ASK_HUMAN,
                    {
                        "recent_cents": recent,
                        "total_cents": total,
                        "projected_cents": projected,
                        "budget_cents": budget,
                    },
                )
            )
    return out


# Evaluation order = rule priority for ties. The engine runs every rule (all reasons are kept).
RULES: tuple[Rule, ...] = (
    check_mandate,
    check_quantity,
    check_product,
    check_data_conflicts,
    check_blocklist,
    check_allergens,
    check_price,
    check_units,
    check_stock,
    check_cutoff,
    check_delivery,
    check_spend,
)
