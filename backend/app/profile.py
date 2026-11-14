"""Buyer profile: Zoha's trade_profile package, used as it is. A profile is guidance, never a rule.

- Standing dietary needs (a business_type memory whose value has "dietary", e.g. a gluten-free kitchen) become
  PREFERRED claims on each item when the buyer's text states no diet: labelled products win when they exist, and
  the line says why ("Gluten-free, because your profile says ..."). The buyer's own words always beat the profile.
- Usual products (usual_product memories + this buyer's confirmed front-door orders) break near-ties only:
  "You usually order this". Never past the confidence threshold or the front door's limits.
- context(): the view for GET /api/profile; revoke() and remember() are the chef's edits (approver key).
- "This order only" memories belong to today's orders (Helsinki date): they stop applying tomorrow by themselves.
Seeds come from profile_seed.json in the repo (helsinki-bistro only); the event log lives under DATA_DIR/profiles.
A revoked seed stays revoked (the loader never re-adds a memory the log has seen); reset(buyer) restores the seeds.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from trade_contracts.common import PreferenceScope
from trade_profile import (MemoryKind, MemorySource, OrderRef, ProfileStore, get_profile_context, log_path,
                           memory_id_for)
from trade_profile.models import OrderLineRef

from . import catalogue, config, orders

SEED = Path(__file__).with_name("profile_seed.json")
SEEDED_AT = datetime(2026, 11, 13, 9, tzinfo=timezone.utc)
_STORE: list = [None, None]  # [root, store]: rebuilt if DATA_DIR changes (tests)


def store() -> ProfileStore:
    root = config.DATA_DIR / "profiles"
    if _STORE[0] != root:
        s = ProfileStore(root)
        for buyer, mems in json.loads(SEED.read_text()).items():
            seen = {e.memory.id if e.memory else e.memory_id for e in s.events(buyer)}
            for m in mems:  # added once; a seed the chef revoked is never re-added on restart
                kind, value = MemoryKind(m["kind"]), m.get("value") or {}
                if memory_id_for(buyer, kind, m["key"], value, PreferenceScope.ALWAYS, None) in seen:
                    continue
                s.add_memory(buyer, kind=kind, key=m["key"], text=m["text"], value=value,
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


def _order_id() -> str:
    """'This order only' = today's orders (Helsinki date)."""
    return "today-" + datetime.now(ZoneInfo("Europe/Helsinki")).date().isoformat()


def _memories(buyer_id: str) -> list:
    return store().active_memories(buyer_id, _order_id(), datetime.now(timezone.utc))


def _view(m, why: str | None) -> dict:
    return {"id": m.id, "kind": m.kind.value, "key": m.key, "text": m.text, "scope": m.scope.value,
            "source": m.source.value, "created_at": m.created_at.isoformat(), "used_because": why,
            "product_id": m.value.get("product_id")}


def revoke(buyer_id: str, memory_id: str) -> None:
    """Forget one active memory of THIS buyer. KeyError if it isn't one (unknown, already revoked, another buyer's)."""
    if memory_id not in {m.id for m in _memories(buyer_id)}:
        raise KeyError(memory_id)
    store().revoke(buyer_id, memory_id, datetime.now(timezone.utc))


def remember(buyer_id: str, product_id: str, scope: str, text: str | None) -> dict:
    """'Remember this': a usual product the chef chose (e.g. the pricier caviar guests like). ValueError if the product
    isn't in the catalogue. It only breaks near-ties: never past the confidence threshold or the door's limits."""
    p = catalogue.get(product_id)
    if not p:
        raise ValueError(f"No product {product_id} in the catalogue.")
    sc = PreferenceScope(scope)
    name = p.get("name_en") or p.get("name_fi") or product_id
    m = store().add_memory(buyer_id, kind=MemoryKind.USUAL_PRODUCT, key=product_id,
                           text=(text or "").strip()[:200] or f"Usually order {name}", value={"product_id": product_id},
                           source=MemorySource.CHOSEN_ALTERNATIVE, now=datetime.now(timezone.utc), scope=sc,
                           order_id=_order_id() if sc is PreferenceScope.THIS_ORDER else None)
    return _view(m, "you asked to remember it")


def reset(buyer_id: str | None) -> None:
    """Demo reset: archive the buyer's profile log (or all of them), so the seeds come back. Nothing is deleted."""
    root = config.DATA_DIR / "profiles"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for f in root.glob("*.jsonl") if root.exists() else []:
        if buyer_id is None or f == log_path(root, buyer_id):
            dest = config.DATA_DIR / "archive" / f"{stamp}-profiles"
            dest.mkdir(parents=True, exist_ok=True)
            os.replace(f, dest / f.name)
    _STORE[:] = [None, None]  # re-seed on next use


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
    ctx = get_profile_context(store(), buyer_id, _order_id(), datetime.now(timezone.utc), past_orders=_PastOrders())
    why = {i.memory.id: i.used_because for i in ctx.items} | {o.memory_id: f"not used: {o.reason}" for o in ctx.overridden}
    return {"buyer_id": buyer_id,
            "dietary": [{"tag": t, "label": t.replace("_", "-"), "because": why} for t, why in dietary(buyer_id)],
            "usual_product_ids": sorted(usual(buyer_id)),
            "memories": [_view(m, why.get(m.id)) for m in _memories(buyer_id)],  # every active one, with why
            "suggested_questions": ctx.suggested_questions,
            "recent_orders": [o.model_dump(mode="json") for o in ctx.recent_orders]}
