"""get_profile_context(): what the agent and the UI may use for ONE order, with the reasons. (Agent A)"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from trade_contracts import Preference
from trade_contracts.common import PreferenceScope

from .models import (
    ContextItem,
    Memory,
    MemoryKind,
    MemorySource,
    OrderRef,
    Overridden,
    PastOrders,
    ProfileContext,
    ProposedMandateChange,
)
from .onboarding import ONBOARDING_QUESTIONS
from .store import ProfileStore

_PROPOSABLE = (MemoryKind.ALLERGEN_AVOID, MemoryKind.SPEND_COMFORT)


def _sort_key(m: Memory) -> tuple[str, str, str]:
    return (m.kind.value, m.key, m.id)


def _rank(m: Memory) -> tuple[int, datetime, str]:
    return (1 if m.scope is PreferenceScope.THIS_ORDER else 0, m.created_at, m.id)


def _because(m: Memory) -> str:
    day = m.created_at.date().isoformat()
    if m.scope is PreferenceScope.THIS_ORDER:
        return f"this-order answer for order {m.order_id}"
    if m.source is MemorySource.ONBOARDING:
        return f"onboarding answer from {day}"
    return f"always-preference from {day}"


def get_profile_context(
    store: ProfileStore,
    buyer_id: str,
    order_id: str,
    now: datetime,
    *,
    past_orders: PastOrders | None = None,
    max_recent_orders: int = 5,
) -> ProfileContext:
    """Pure function of the event log, `now` and the read-only past orders.

    - items: each active memory with `used_because`, e.g. "always-preference from 2026-11-14" or
      "this-order answer for order ord-7".
    - conflicts (same kind + key, different value): narrower scope wins (this_order beats
      always); in the same scope the newer created_at wins. The loser goes to `overridden` with a
      reason naming the winner. The result must say which memory was used.
    - guidance: soft trade_contracts.Preference items built from the memories (scope kept as is).
      NEVER a HardRule, never a change to any mandate.
    - proposed_mandate_changes: for ALLERGEN_AVOID and SPEND_COMFORT memories only, an unconfirmed
      ProposedMandateChange (the human confirms it in the mandate, T09).
    - suggested_questions: open questions worth asking (e.g. onboarding answers still missing).
    - recent_orders: the buyer's last `max_recent_orders` orders by placed_at, via `past_orders`.
    - Output ordering is deterministic (sort by kind, key, memory id).
    """
    active = store.active_memories(buyer_id, order_id, now)
    order_of = {m.id: _sort_key(m) for m in active}

    groups: dict[tuple[str, str], list[Memory]] = defaultdict(list)
    for m in active:
        groups[(m.kind.value, m.key)].append(m)

    used: list[Memory] = []
    overridden: list[Overridden] = []
    notes: dict[str, list[str]] = defaultdict(list)
    for members in groups.values():
        winner = max(members, key=_rank)
        used.append(winner)
        for m in members:
            if m.id == winner.id:
                continue
            if m.value == winner.value:
                used.append(m)
                continue
            label = f"{m.kind.value}:{m.key}"
            if m.scope is not winner.scope:
                reason = f"{winner.scope.value} beats {m.scope.value} for {label}"
            else:
                reason = f"newer {winner.scope.value} answer beats older one for {label}"
            overridden.append(Overridden(memory_id=m.id, by_memory_id=winner.id, reason=reason))
            notes[winner.id].append(f"overrode {m.id} ({reason})")

    used.sort(key=_sort_key)
    overridden.sort(key=lambda o: order_of[o.memory_id])

    items = [
        ContextItem(
            memory=m,
            used_because=_because(m) + ("; " + "; ".join(notes[m.id]) if notes[m.id] else ""),
        )
        for m in used
    ]
    guidance = [Preference(text=m.text, scope=m.scope) for m in used]
    proposals = [
        ProposedMandateChange(
            memory_id=m.id,
            summary=(
                f"Make this a rule in your mandate: {m.text}. "
                "It stays a suggestion until you confirm it."
            ),
        )
        for m in used
        if m.kind in _PROPOSABLE
    ]

    have = {m.kind for m in active if m.scope is PreferenceScope.ALWAYS}
    questions = [q.question for q in ONBOARDING_QUESTIONS if q.kind not in have]

    recent: list[OrderRef] = []
    if past_orders is not None:
        mine = [o for o in past_orders.list_orders(buyer_id) if o.buyer_id == buyer_id]
        mine.sort(key=lambda o: (o.placed_at, o.order_id), reverse=True)
        recent = mine[: max(0, max_recent_orders)]

    return ProfileContext(
        buyer_id=buyer_id,
        order_id=order_id,
        as_of=now,
        items=items,
        overridden=overridden,
        guidance=guidance,
        suggested_questions=questions,
        proposed_mandate_changes=proposals,
        recent_orders=recent,
    )
