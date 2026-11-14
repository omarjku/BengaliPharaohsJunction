"""Building and ordering Reasons (D17, D22)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from trade_contracts import Reason, ReasonCode, Severity

from .texts import render

_SEVERITY_RANK = {Severity.DECLINE: 0, Severity.ASK_HUMAN: 1, Severity.INFO: 2}

# Rule priority inside the same severity (allergen before cut-off, and so on).
# Agent A orders this; codes not listed sort after the listed ones.
CODE_PRIORITY: tuple[ReasonCode, ...] = (
    # hard rules first
    ReasonCode.LIMIT_CHANGE_ATTEMPT,
    ReasonCode.ALLERGEN_CONTAINS,
    ReasonCode.BLOCKLISTED,
    ReasonCode.QTY_INVALID,
    ReasonCode.POLICY_DECLINE_UNKNOWN,
    ReasonCode.UNKNOWN_PRODUCT,
    # mandate and allergen uncertainty
    ReasonCode.MANDATE_MISSING,
    ReasonCode.MANDATE_EXPIRED,
    ReasonCode.MANDATE_INVALID,
    ReasonCode.ALLERGEN_MAY_CONTAIN,
    ReasonCode.ALLERGEN_DATA_MISSING,
    ReasonCode.DATA_MISSING,
    # quantity, units, delivery, stock
    ReasonCode.QTY_SUSPICIOUS,
    ReasonCode.QTY_AMBIGUOUS,
    ReasonCode.UNIT_MISMATCH,
    ReasonCode.CUTOFF_PASSED,
    ReasonCode.UNDELIVERABLE,
    ReasonCode.QTY_UNKNOWN,
    ReasonCode.STOCK_NONE,
    ReasonCode.STOCK_PARTIAL,
    ReasonCode.DATE_NOT_HONOURED,
    ReasonCode.QUOTE_STALE,
    ReasonCode.PRICE_MISSING,
    ReasonCode.PRICE_CHANGED,
    ReasonCode.LOW_RELIABILITY,
    # spend
    ReasonCode.SPEND_OVER_LIMIT,
    ReasonCode.LINE_OVER_CAP,
    ReasonCode.WEEKLY_BUDGET_EXCEEDED,
    # engine
    ReasonCode.LOW_CONFIDENCE,
    ReasonCode.ENGINE_ERROR,
    ReasonCode.DEFAULT_MANDATE_APPLIED,
)


def make_reason(
    code: ReasonCode,
    severity: Severity,
    facts: Mapping[str, str | int | float | bool | None] | None = None,
    product_id: str | None = None,
) -> Reason:
    """Reason with text and suggested_fix rendered from texts.TEMPLATES."""
    message, fix = render(code, facts)
    return Reason(
        code=code,
        severity=severity,
        message=message,
        facts=dict(facts or {}),
        suggested_fix=fix,
        product_id=product_id,
    )


def sort_reasons(reasons: Iterable[Reason]) -> list[Reason]:
    """Severity (DECLINE first), then rule priority, then product_id, then code (D17)."""
    priority = {code: i for i, code in enumerate(CODE_PRIORITY)}
    return sorted(
        reasons,
        key=lambda r: (
            _SEVERITY_RANK[r.severity],
            priority.get(r.code, len(priority)),
            r.product_id or "",
            r.code.value,
        ),
    )
