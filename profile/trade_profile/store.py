"""Append-only JSONL event log per buyer; current state is derived by replaying it. (Agent A)

Layout: <root>/<safe buyer id>.jsonl, one ProfileEvent per line. No database.
Rules (Agent A implements, Agent B tests):
- A memory added without a scope is THIS_ORDER (never ALWAYS). Onboarding answers are ALWAYS.
- Adding an identical memory (same buyer, kind, key, value, scope, order_id) is a no-op.
- revoke / expire only append events; the memory is never used again.
- close_order() appends EXPIRE for that order's still-active THIS_ORDER memories.
- promote_to_always() requires by_human=True, else raises PermissionError. It never runs silently.
- forget_memory() erases the content of one memory (rewrite the log, keeping only a FORGET
  tombstone with the id); forget_profile() deletes the buyer's file.
- `now` is always passed in. No hidden clock, no randomness.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from trade_contracts.common import PreferenceScope

from .models import EventType, Memory, MemoryKind, MemorySource, ProfileEvent, Value

_SAFE = re.compile(r"[^A-Za-z0-9_.-]")


def log_path(root: Path, buyer_id: str) -> Path:
    """File for one buyer's log. Unsafe characters (path separators, '..') never escape `root`:
    an unsafe or empty id is replaced by a hash."""
    safe = _SAFE.sub("_", buyer_id)
    if not safe or safe.strip(".") == "" or safe != buyer_id:
        safe = "b_" + hashlib.sha256(buyer_id.encode("utf-8")).hexdigest()[:16]
    return Path(root) / f"{safe}.jsonl"


def memory_id_for(
    buyer_id: str,
    kind: MemoryKind,
    key: str,
    value: Mapping[str, object],
    scope: PreferenceScope,
    order_id: str | None,
) -> str:
    """Deterministic id from the content (so a duplicate memory gets the same id)."""
    blob = json.dumps(
        [buyer_id, kind.value, key, value, scope.value, order_id],
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "mem_" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


class ProfileStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # -- log io ---------------------------------------------------------------------------
    def _append(self, buyer_id: str, event: ProfileEvent) -> None:
        path = log_path(self.root, buyer_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(event.model_dump_json() + "\n")

    def events(self, buyer_id: str) -> list[ProfileEvent]:
        """The raw log, in order."""
        path = log_path(self.root, buyer_id)
        if not path.exists():
            return []
        out: list[ProfileEvent] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    out.append(ProfileEvent.model_validate_json(line))
        return out

    def _replay(self, buyer_id: str) -> tuple[dict[str, Memory], set[str]]:
        """Derive state: (id -> current Memory, ids that are active). Never stored."""
        mems: dict[str, Memory] = {}
        active: set[str] = set()
        for ev in self.events(buyer_id):
            if ev.type is EventType.ADD:
                if ev.memory is not None:
                    mems[ev.memory.id] = ev.memory
                    active.add(ev.memory.id)
            elif ev.memory_id is None:
                continue
            elif ev.type in (EventType.REVOKE, EventType.EXPIRE):
                active.discard(ev.memory_id)
            elif ev.type is EventType.PROMOTE:
                m = mems.get(ev.memory_id)
                if m is not None and ev.by_human:
                    mems[ev.memory_id] = m.model_copy(
                        update={"scope": PreferenceScope.ALWAYS, "order_id": None}
                    )
            elif ev.type is EventType.FORGET:
                mems.pop(ev.memory_id, None)
                active.discard(ev.memory_id)
        return mems, active

    # -- writes ---------------------------------------------------------------------------
    def add_memory(
        self,
        buyer_id: str,
        *,
        kind: MemoryKind,
        key: str,
        text: str,
        value: Value | None = None,
        source: MemorySource,
        now: datetime,
        scope: PreferenceScope = PreferenceScope.THIS_ORDER,
        order_id: str | None = None,
    ) -> Memory:
        if scope is PreferenceScope.THIS_ORDER and not order_id:
            raise ValueError("a this_order memory needs the order_id it belongs to")
        if scope is PreferenceScope.ALWAYS:
            order_id = None
        value = dict(value or {})
        mid = memory_id_for(buyer_id, kind, key, value, scope, order_id)
        mems, active = self._replay(buyer_id)
        if mid in active:
            return mems[mid]
        memory = Memory(
            id=mid,
            buyer_id=buyer_id,
            kind=kind,
            key=key,
            text=text,
            value=value,
            scope=scope,
            source=source,
            created_at=now,
            order_id=order_id,
        )
        self._append(
            buyer_id, ProfileEvent(type=EventType.ADD, buyer_id=buyer_id, at=now, memory=memory)
        )
        return memory

    def revoke(self, buyer_id: str, memory_id: str, now: datetime) -> None:
        mems, _ = self._replay(buyer_id)
        if memory_id not in mems:
            raise KeyError(memory_id)
        self._append(
            buyer_id,
            ProfileEvent(type=EventType.REVOKE, buyer_id=buyer_id, at=now, memory_id=memory_id),
        )

    def close_order(self, buyer_id: str, order_id: str, now: datetime) -> list[str]:
        """Expire the order's THIS_ORDER memories; return the expired memory ids."""
        mems, active = self._replay(buyer_id)
        ids = sorted(
            mid
            for mid in active
            if mems[mid].scope is PreferenceScope.THIS_ORDER and mems[mid].order_id == order_id
        )
        for mid in ids:
            self._append(
                buyer_id,
                ProfileEvent(
                    type=EventType.EXPIRE,
                    buyer_id=buyer_id,
                    at=now,
                    memory_id=mid,
                    order_id=order_id,
                ),
            )
        return ids

    def promote_to_always(
        self, buyer_id: str, memory_id: str, now: datetime, *, by_human: bool
    ) -> Memory:
        if not by_human:
            raise PermissionError("promoting a memory to always needs an explicit human action")
        mems, active = self._replay(buyer_id)
        if memory_id not in active:
            raise KeyError(memory_id)
        if mems[memory_id].scope is PreferenceScope.ALWAYS:
            return mems[memory_id]
        self._append(
            buyer_id,
            ProfileEvent(
                type=EventType.PROMOTE,
                buyer_id=buyer_id,
                at=now,
                memory_id=memory_id,
                by_human=True,
            ),
        )
        return self._replay(buyer_id)[0][memory_id]

    def forget_memory(self, buyer_id: str, memory_id: str, now: datetime) -> None:
        events = self.events(buyer_id)
        known = any(
            (e.memory is not None and e.memory.id == memory_id) or e.memory_id == memory_id
            for e in events
        )
        if not known:
            raise KeyError(memory_id)
        kept: list[ProfileEvent] = []
        for e in events:
            if e.memory is not None and e.memory.id == memory_id:
                kept.append(
                    ProfileEvent(
                        type=EventType.ADD, buyer_id=buyer_id, at=e.at, memory_id=memory_id
                    )
                )
            elif e.memory_id == memory_id and e.type is not EventType.FORGET:
                continue
            else:
                kept.append(e)
        if not any(e.type is EventType.FORGET and e.memory_id == memory_id for e in kept):
            kept.append(
                ProfileEvent(type=EventType.FORGET, buyer_id=buyer_id, at=now, memory_id=memory_id)
            )
        path = log_path(self.root, buyer_id)
        tmp = path.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as fh:
            for e in kept:
                fh.write(e.model_dump_json() + "\n")
        tmp.replace(path)

    def forget_profile(self, buyer_id: str) -> None:
        log_path(self.root, buyer_id).unlink(missing_ok=True)

    def record_onboarding(
        self, buyer_id: str, answers: Mapping[str, object], now: datetime
    ) -> list[Memory]:
        """Store answers keyed by onboarding.ONBOARDING_QUESTIONS ids as ALWAYS memories
        (allergens: one memory per allergen name). Unknown answer ids are ignored."""
        from .onboarding import ONBOARDING_QUESTIONS

        out: list[Memory] = []

        def put(kind: MemoryKind, key: str, text: str, value: Value) -> None:
            out.append(
                self.add_memory(
                    buyer_id,
                    kind=kind,
                    key=key,
                    text=text,
                    value=value,
                    source=MemorySource.ONBOARDING,
                    now=now,
                    scope=PreferenceScope.ALWAYS,
                )
            )

        for q in ONBOARDING_QUESTIONS:
            if q.id not in answers:
                continue
            raw = answers[q.id]
            if q.id == "allergens":
                names = [raw] if isinstance(raw, str) else list(raw)  # type: ignore[call-overload]
                for name in names:
                    n = str(name).strip().lower()
                    if n:
                        put(q.kind, n, f"Avoid {n}", {"name": n})
                continue
            if isinstance(raw, (list, tuple)):
                val: object = [str(x) for x in raw]
                shown = ", ".join(str(x) for x in raw)
            else:
                val = raw
                shown = str(raw)
            put(q.kind, q.key, f"{q.question} {shown}", {"answer": val})  # type: ignore[dict-item]
        return out

    def active_memories(self, buyer_id: str, order_id: str, now: datetime) -> list[Memory]:
        """Memories usable for `order_id` at `now`: ALWAYS ones not revoked/forgotten, plus
        THIS_ORDER ones that belong to this order and are not expired/revoked. Only this buyer's."""
        mems, active = self._replay(buyer_id)
        out = [
            m
            for mid, m in mems.items()
            if mid in active
            and m.buyer_id == buyer_id
            and m.created_at <= now
            and (m.scope is PreferenceScope.ALWAYS or m.order_id == order_id)
        ]
        return sorted(out, key=lambda m: (m.kind.value, m.key, m.id))
