"""Buyer profile: Zoha's trade_profile package, used as it is. A profile is guidance, never a rule.

- Standing dietary needs (a business_type memory whose value has "dietary", e.g. a gluten-free kitchen) become
  PREFERRED claims on each item when the buyer's text states no diet: labelled products win when they exist, and
  the line says why ("Gluten-free, because your profile says ..."). The buyer's own words always beat the profile.
- Usual products (usual_product memories + this buyer's confirmed front-door orders) break near-ties only:
  "You usually order this". Never past the confidence threshold or the front door's limits.
- context(): the read-only view for GET /api/profile.
Seeds come from profile_seed.json in the repo (helsinki-bistro only); the event log lives under DATA_DIR/profiles.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from trade_contracts.common import PreferenceScope
from trade_profile import MemoryKind, MemorySource, OrderRef, ProfileStore, get_profile_context
from trade_profile.models import OrderLineRef

from . import config, orders

SEED = Path(__file__).with_name("profile_seed.json")
SEEDED_AT = datetime(2026, 11, 13, 9, tzinfo=timezone.utc)
_STORE: list = [None, None]  # [root, store]: rebuilt if DATA_DIR changes (tests)


def store() -> ProfileStore:
    root = config.DATA_DIR / "profiles"
    if _STORE[0] != root:
        s = ProfileStore(root)
        for buyer, mems in json.loads(SEED.read_text()).items():  # idempotent: same memory → same id, added once
            for m in mems:
                s.add_memory(buyer, kind=MemoryKind(m["kind"]), key=m["key"], text=m["text"], value=m.get("value"),
                             source=MemorySource.ONBOARDING, now=SEEDED_AT, scope=PreferenceScope.ALWAYS)
        _STORE[:] = [root, s]
    return _STORE[1]


class _PastOrders:
    """Read-only view of the front door's confirmed orders (orders.py stays the source)."""
    def list_orders(self, buyer_id: str) -> list[OrderRef]:
        return [OrderRef(order_id=o["id"], buyer_id=buyer_id, placed_at=o["created_at"], total_cents=o["total_cents"],
                         lines=[OrderLineRef(product_id=ln["product_id"], quantity=ln["quantity"], unit=ln.get("unit"))
                                for ln in o.get("lines", [])])
                for o in list(orders._store().values())
                if o.get("buyer_id") == buyer_id and o.get("status") == "confirmed" and o.get("created_at")]


def _memories(buyer_id: str) -> list:
    return store().active_memories(buyer_id, "-", datetime.now(timezone.utc))


def dietary(buyer_id: str) -> list[tuple[str, str]]:
    """[(tag, why)] the kitchen always needs, e.g. ("gluten_free", "your profile says: Our kitchen is gluten-free")."""
    return [(tag, f"your profile says: {m.text}") for m in _memories(buyer_id)
            for tag in (m.value.get("dietary") or []) if isinstance(tag, str)]


def usual(buyer_id: str) -> set[str]:
    """Product ids this buyer usually orders: profile memories plus confirmed orders. Only for buyers WITH a profile:
    a buyer without one (lapland-kitchen, the demo arc) keeps today's choices whatever was ordered before."""
    mems = _memories(buyer_id)
    if not mems:
        return set()
    ids = {str(m.value["product_id"]) for m in mems if m.kind is MemoryKind.USUAL_PRODUCT and m.value.get("product_id")}
    return ids | {ln.product_id for o in _PastOrders().list_orders(buyer_id) for ln in o.lines}


def context(buyer_id: str) -> dict:
    ctx = get_profile_context(store(), buyer_id, "-", datetime.now(timezone.utc), past_orders=_PastOrders())
    return {"buyer_id": buyer_id,
            "dietary": [{"tag": t, "label": t.replace("_", "-"), "because": why} for t, why in dietary(buyer_id)],
            "usual_product_ids": sorted(usual(buyer_id)),
            "memories": [{"kind": i.memory.kind.value, "key": i.memory.key, "text": i.memory.text,
                          "used_because": i.used_because} for i in ctx.items],
            "suggested_questions": ctx.suggested_questions,
            "recent_orders": [o.model_dump(mode="json") for o in ctx.recent_orders]}
