"""Test builders for the profile tests (shared by both agents)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from trade_contracts.common import PreferenceScope

from trade_profile import MemoryKind, MemorySource, OrderRef, ProfileStore
from trade_profile.models import OrderLineRef

HELSINKI = ZoneInfo("Europe/Helsinki")
NOW = datetime(2026, 11, 14, 9, 0, tzinfo=HELSINKI)
LATER = NOW + timedelta(days=2)
BUYER = "lapland-demo"
OTHER_BUYER = "other-buyer"


def make_store(root: Path) -> ProfileStore:
    return ProfileStore(root)


def add(
    store: ProfileStore,
    *,
    buyer: str = BUYER,
    kind: MemoryKind = MemoryKind.ALLERGEN_AVOID,
    key: str = "wheat",
    text: str = "No wheat flour",
    value: dict | None = None,
    source: MemorySource = MemorySource.ANSWERED_QUESTION,
    now: datetime = NOW,
    scope: PreferenceScope | None = None,  # None = rely on the store default (this_order)
    order_id: str | None = "ord-1",
):
    kwargs = {"kind": kind, "key": key, "text": text, "value": value or {"name": key},
              "source": source, "now": now, "order_id": order_id}  # fmt: skip
    if scope is not None:
        kwargs["scope"] = scope
        if scope is PreferenceScope.ALWAYS:
            kwargs["order_id"] = None
    return store.add_memory(buyer, **kwargs)


class FakePastOrders:
    """Read-only past orders for tests."""

    def __init__(self, *orders: OrderRef) -> None:
        self.orders = list(orders)

    def list_orders(self, buyer_id: str) -> list[OrderRef]:
        return [o for o in self.orders if o.buyer_id == buyer_id]


def make_order(order_id: str = "ord-0", buyer: str = BUYER, days_ago: int = 3, total: int = 12000):
    return OrderRef(
        order_id=order_id,
        buyer_id=buyer,
        placed_at=NOW - timedelta(days=days_ago),
        lines=[OrderLineRef(product_id="463335", quantity=100, unit="L")],
        total_cents=total,
    )
