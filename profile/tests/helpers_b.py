"""Small helpers for Agent B tests."""

from __future__ import annotations

from datetime import datetime

from builders import BUYER, NOW
from trade_contracts.common import PreferenceScope

from trade_profile import ProfileContext, get_profile_context

ALWAYS = PreferenceScope.ALWAYS
THIS = PreferenceScope.THIS_ORDER


def ctx(store, order_id="ord-1", buyer=BUYER, now: datetime = NOW, **kw) -> ProfileContext:
    return get_profile_context(store, buyer, order_id, now, **kw)


def item_ids(context: ProfileContext) -> set[str]:
    return {i.memory.id for i in context.items}
