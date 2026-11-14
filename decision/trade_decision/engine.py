"""decide(): pure, deterministic, fail-closed."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from trade_contracts import (
    Alternative,
    Decision,
    Mandate,
    Outcome,
    ProductFacts,
    PurchaseRequest,
    Quote,
    Reason,
    ReasonCode,
    Severity,
)

from .alternatives import NO_SAFE_ALTERNATIVE, find_alternatives
from .config import RULES_VERSION, DecisionConfig, load_config
from .merge import merge_lines
from .reasons import make_reason, sort_reasons
from .rules import RULES
from .types import OrderLine, RuleContext

_ALT_CODES = frozenset(
    {
        ReasonCode.STOCK_PARTIAL,
        ReasonCode.STOCK_NONE,
        ReasonCode.QTY_UNKNOWN,
        ReasonCode.CUTOFF_PASSED,
        ReasonCode.UNDELIVERABLE,
        ReasonCode.UNKNOWN_PRODUCT,
    }
)
_OUTCOME = {
    Severity.INFO: Outcome.AUTO,
    Severity.ASK_HUMAN: Outcome.ASK_HUMAN,
    Severity.DECLINE: Outcome.DECLINE,
}


def decide(
    request: PurchaseRequest,
    mandate: Mandate | None,
    lines: Sequence[OrderLine],
    quotes: Sequence[Quote],
    facts: Sequence[ProductFacts],
    *,
    now: datetime,
    confidence: float | None = None,
    config: DecisionConfig | None = None,
    recent_spend_cents: int = 0,
) -> Decision:
    """Decide one order. No clock, no randomness: same inputs give the same Decision.

    Any exception or malformed input returns ASK_HUMAN with ENGINE_ERROR; never AUTO (D18).
    `quotes` and `facts` hold the ordered products AND the alternative candidates.
    """
    safe_now = _safe_now(now)  # before the try: the fallback itself needs a valid timestamp
    if not isinstance(now, datetime):  # no usable clock value: never evaluate against a guess
        return _fail_closed(request, safe_now, TypeError("now is not a datetime"))
    try:
        cfg = config or load_config()
        return _decide(
            request, mandate, lines, quotes, facts, safe_now, confidence, cfg, recent_spend_cents
        )
    except Exception as exc:  # noqa: BLE001 - fail closed on anything
        return _fail_closed(request, safe_now, exc)


_SENTINEL_NOW = datetime(1970, 1, 1, tzinfo=UTC)  # only used when `now` is not a datetime at all


def _safe_now(now: object) -> datetime:
    """A timezone-aware datetime from whatever was passed: naive means Helsinki; junk means a
    fixed sentinel (no hidden clock). Never raises."""
    if not isinstance(now, datetime):
        return _SENTINEL_NOW
    if now.tzinfo is not None:
        return now
    try:
        return now.replace(tzinfo=ZoneInfo("Europe/Helsinki"))
    except Exception:  # noqa: BLE001 - tzdata missing
        return now.replace(tzinfo=UTC)


def _index(items: Sequence) -> tuple[dict, set[str]]:
    """By product_id. Identical duplicates collapse; DIFFERENT duplicates are reported as
    conflicts (the later copy stays in the dict, but ordered products among them ask)."""
    out: dict = {}
    conflicts: set[str] = set()
    for item in items:
        prior = out.get(item.product_id)
        if prior is not None and prior != item:
            conflicts.add(item.product_id)
        out[item.product_id] = item
    return out, conflicts


def _decide(
    request: PurchaseRequest,
    mandate: Mandate | None,
    lines: Sequence[OrderLine],
    quotes: Sequence[Quote],
    facts: Sequence[ProductFacts],
    now: datetime,
    confidence: float | None,
    config: DecisionConfig,
    recent_spend_cents: int,
) -> Decision:
    """Agent A implements. Steps:
    1. effective mandate (None -> missing; empty -> defaults + INFO DEFAULT_MANDATE_APPLIED)
    2. merge_lines; index quotes/facts by product_id; build RuleContext
    3. run every rule in rules.RULES and collect ALL reasons
    4. attach alternatives (alternatives.find_alternatives, max 3) where a line is blocked
       by stock / cut-off / undeliverable / unknown product
    5. D26: confidence below config.low_confidence_threshold downgrades AUTO to ASK_HUMAN
       (LOW_CONFIDENCE); never upgrades ASK/DECLINE; None leaves everything unchanged
    6. reasons.sort_reasons; outcome = highest severity (INFO only = AUTO); build the Decision
       with rules_version=RULES_VERSION, confidence passed through, primary_reason auto-filled
    """
    now_tz = now if now.tzinfo else now.replace(tzinfo=ZoneInfo(config.timezone))
    quotes_by_id, quote_conflicts = _index(quotes)
    facts_by_id, facts_conflicts = _index(facts)
    defaulted = mandate is not None and not mandate.hard_rules
    merged = merge_lines(lines)
    ctx = RuleContext(
        request=request,
        mandate=mandate,
        mandate_defaulted=defaulted,
        lines=merged,
        quotes=quotes_by_id,
        facts=facts_by_id,
        now=now_tz,
        config=config,
        recent_spend_cents=max(0, recent_spend_cents),  # a negative figure must not widen budgets
        conflicts=frozenset(quote_conflicts | facts_conflicts),
    )

    reasons: list[Reason] = []
    for rule in RULES:
        reasons.extend(rule(ctx))

    alternatives: list[Alternative] = []
    seen: set[str] = set()
    cache: dict[str, list[Alternative]] = {}
    attached: list[Reason] = []
    for reason in sort_reasons(reasons):
        if reason.code in _ALT_CODES and reason.product_id:
            pid = reason.product_id
            if pid not in cache:
                cache[pid] = find_alternatives(ctx, pid)
            if cache[pid]:
                for alt in cache[pid]:
                    if alt.product_id not in seen and len(alternatives) < config.max_alternatives:
                        seen.add(alt.product_id)
                        alternatives.append(alt)
            else:
                reason = reason.model_copy(update={"suggested_fix": NO_SAFE_ALTERNATIVE})
        attached.append(reason)
    reasons = attached

    if (
        confidence is not None
        and confidence < config.low_confidence_threshold
        and all(r.severity is Severity.INFO for r in reasons)
    ):
        reasons.append(
            make_reason(
                ReasonCode.LOW_CONFIDENCE,
                Severity.ASK_HUMAN,
                {"confidence": confidence, "threshold": config.low_confidence_threshold},
            )
        )

    reasons = sort_reasons(reasons)
    outcome = _OUTCOME[reasons[0].severity] if reasons else Outcome.AUTO
    return Decision(
        request_id=request.id,
        outcome=outcome,
        reasons=reasons,
        confidence=confidence,
        alternatives=alternatives,
        rules_version=RULES_VERSION,
        decided_at=now_tz,
    )


def _fail_closed(request: object, now: datetime, exc: Exception) -> Decision:
    request_id = getattr(request, "id", None)
    if not isinstance(request_id, str) or not request_id:
        request_id = "unknown"
    reason = make_reason(
        ReasonCode.ENGINE_ERROR,
        Severity.ASK_HUMAN,
        {"error_type": type(exc).__name__},
    )
    return Decision(
        request_id=request_id,
        outcome=Outcome.ASK_HUMAN,
        reasons=[reason],
        rules_version=RULES_VERSION,
        decided_at=now,
    )
