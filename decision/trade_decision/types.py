"""Inputs that are not contract shapes. Plain dataclasses, so malformed values (NaN, None,
negative) can reach the rules and be answered with a reason instead of a crash."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from trade_contracts import Mandate, ProductFacts, PurchaseRequest, Quote

from .config import DecisionConfig


@dataclass(frozen=True)
class OrderLine:
    """One resolved order line (T05 has already turned the request into product ids).

    quantity: in sales units; may be None / NaN / <= 0 (that is QTY_INVALID, not a crash).
    unit: the unit the buyer asked in ("L", "KG", "PCS"); used for the unit-family check.
    expected_unit_price_cents: price the buyer/agent saw earlier; None = nothing to compare.
    """

    product_id: str
    quantity: float | None
    unit: str | None = None
    expected_unit_price_cents: int | None = None


@dataclass(frozen=True)
class RuleContext:
    """Everything a rule may read. Built once by the engine; rules are pure functions of it."""

    request: PurchaseRequest
    mandate: Mandate | None  # None = missing
    mandate_defaulted: bool  # True when the mandate was empty and defaults apply (D15)
    lines: tuple[OrderLine, ...]  # duplicates already merged
    quotes: dict[str, Quote]  # by product_id: ordered products AND alternative candidates
    facts: dict[str, ProductFacts]  # same
    now: datetime  # timezone-aware; the only clock
    config: DecisionConfig
    recent_spend_cents: int = 0  # spend in the weekly window incl. pending orders (case 32)
