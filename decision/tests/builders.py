"""Test builders: every default describes a CLEAN order (100 L of milk, EUR 140 net, plenty of
stock, cut-off tomorrow, allergen data present), so a test overrides only what it is about."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from trade_contracts import (
    Decision,
    HardRule,
    Mandate,
    ProductFacts,
    PurchaseRequest,
    QuantityInfo,
    Quote,
)
from trade_contracts.common import RuleKind
from trade_contracts.quote import CutOff

from trade_decision import OrderLine, decide

HELSINKI = ZoneInfo("Europe/Helsinki")
NOW = datetime(2026, 11, 14, 9, 0, tzinfo=HELSINKI)  # Saturday morning
MONDAY = date(2026, 11, 16)
PID = "463335"
DEFAULT = object()  # sentinel: "build the default mandate" (None means a MISSING mandate)


def make_request(**kw) -> PurchaseRequest:
    base = {
        "id": "req-1",
        "buyer_id": "lapland-demo",
        "text": "100 L lactose-free milk by Monday",
        "needed_by": MONDAY,
        "created_at": NOW,
    }
    return PurchaseRequest(**{**base, **kw})


def make_line(product_id: str = PID, quantity: float | None = 100, unit: str | None = "L", **kw):
    return OrderLine(product_id=product_id, quantity=quantity, unit=unit, **kw)


def make_quote(
    product_id: str = PID,
    price_cents: int | None = 140,
    stock: int | None = 5000,  # None = unknown quantity (Terminal 999999)
    closing_time: datetime | None = None,  # default: tomorrow 17:00
    available_date: date | None = MONDAY,
    availability: str = "available",
    **kw,
) -> Quote:
    closing = closing_time or datetime(2026, 11, 15, 17, 0, tzinfo=HELSINKI)
    base = {
        "product_id": product_id,
        "product_name": f"Product {product_id}",
        "unit_price_cents": price_cents,
        "unit": "1 L carton",
        "availability": availability,
        "quantity": QuantityInfo(known=stock is not None, value=stock),
        "available_date": available_date,
        "source": "mock",
        "fetched_at": NOW - timedelta(minutes=1),
        "cut_off": CutOff(closing_time=closing, passed=closing <= NOW),
    }
    return Quote(**{**base, **kw})


def make_facts(product_id: str = PID, **kw) -> ProductFacts:
    base = {
        "product_id": product_id,
        "name_en": f"Product {product_id}",
        "category": "Milk drinks",
        "allergens": {"gluten": "FREE_FROM", "peanut": "FREE_FROM", "tree nuts": "FREE_FROM"},
        "reliability": 0.95,
        "min_order_qty": 1,
        "sales_unit": "1 L carton",
        "pack_size": 1,
    }
    return ProductFacts(**{**base, **kw})


def make_mandate(
    limit_cents: int | None = 50000,
    excluded_allergens: tuple[str, ...] = (),
    blocklist: tuple[str, ...] = (),
    per_line_cap_cents: int = 30000,
    **kw,
) -> Mandate:
    rules = [HardRule(kind=RuleKind.EXCLUDED_ALLERGEN, value=a) for a in excluded_allergens]
    if limit_cents is not None:
        rules.append(HardRule(kind=RuleKind.AUTO_APPROVE_LIMIT_CENTS, value=limit_cents))
    base = {
        "id": "m1",
        "buyer_id": "lapland-demo",
        "hard_rules": rules,
        "blocklist": list(blocklist),
        "per_line_cap_cents": per_line_cap_cents,
    }
    return Mandate(**{**base, **kw})


def run(lines=None, quotes=None, facts=None, mandate=DEFAULT, request=None, **kw) -> Decision:
    """Call decide() with clean defaults. Quotes/facts default to one clean entry per line."""
    lines = lines if lines is not None else [make_line()]
    quotes = quotes if quotes is not None else [make_quote(ln.product_id) for ln in lines]
    facts = facts if facts is not None else [make_facts(ln.product_id) for ln in lines]
    mandate = make_mandate() if mandate is DEFAULT else mandate
    return decide(request or make_request(), mandate, lines, quotes, facts, now=NOW, **kw)


def codes(decision: Decision) -> list[str]:
    return [r.code.value for r in decision.reasons]
