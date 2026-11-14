"""Profile shapes. SAFETY RULE: this package never builds a HardRule or edits a Mandate.

A profile only feeds GUIDANCE and question suggestions. A remembered answer that names an
allergen or a limit may be PROPOSED as a mandate change (ProposedMandateChange, always
unconfirmed); only the human, through the confirmed Mandate (T09), can make it a rule.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from trade_contracts import Preference
from trade_contracts.common import PreferenceScope

# Structured value of a memory: small, flat, JSON-friendly (data minimisation).
Value = dict[str, str | int | float | bool | list[str] | None]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MemoryKind(StrEnum):
    """Closed list of what the agent may remember (business and ordering preferences only)."""

    BUSINESS_TYPE = "business_type"
    DELIVERY_DAYS = "delivery_days"
    ALLERGEN_AVOID = "allergen_avoid"  # key = allergen name
    SPEND_COMFORT = "spend_comfort"  # key = "order_total"
    LOCAL_PREFERENCE = "local_preference"  # key = "origin"
    USUAL_PRODUCT = "usual_product"  # key = the phrase, e.g. "1000 L milk"
    PREFERENCE_NOTE = "preference_note"  # free guidance


class MemorySource(StrEnum):
    ONBOARDING = "onboarding"
    ANSWERED_QUESTION = "answered_question"
    CHOSEN_ALTERNATIVE = "chosen_alternative"


class Memory(_Closed):
    """One remembered thing. Immutable facts; its status is derived from the event log."""

    id: str = Field(min_length=1)
    buyer_id: str = Field(min_length=1)
    kind: MemoryKind
    key: str = Field(min_length=1, description="Conflict key within a kind, e.g. 'peanut'.")
    text: str = Field(min_length=1, description="Plain words, shown to the human.")
    value: Value = Field(default_factory=dict)
    scope: PreferenceScope
    source: MemorySource
    created_at: AwareDatetime
    order_id: str | None = Field(
        default=None, description="Required for this_order memories: the order they belong to."
    )

    @model_validator(mode="after")
    def _scope_matches_order(self) -> Memory:
        if self.scope is PreferenceScope.THIS_ORDER and not self.order_id:
            raise ValueError("a this_order memory needs the order_id it belongs to")
        if self.scope is PreferenceScope.ALWAYS and self.order_id:
            raise ValueError("an always memory must not carry an order_id")
        return self


class EventType(StrEnum):
    ADD = "add"
    REVOKE = "revoke"  # the human withdrew it; kept in the log, never used again
    EXPIRE = "expire"  # its order was closed (this_order memories)
    PROMOTE = "promote"  # this_order -> always, only by an explicit human action
    FORGET = "forget"  # content erased; only the id and the fact it was forgotten remain


class ProfileEvent(_Closed):
    """One line of the append-only JSONL log for a buyer."""

    type: EventType
    buyer_id: str
    at: AwareDatetime
    memory: Memory | None = None  # ADD only
    memory_id: str | None = None  # REVOKE / EXPIRE / PROMOTE / FORGET
    order_id: str | None = None  # EXPIRE: the order that was closed
    by_human: bool = False  # PROMOTE must have True


class OrderLineRef(_Closed):
    product_id: str
    quantity: float
    unit: str | None = None


class OrderRef(_Closed):
    """A past order, by reference. Read-only: the order record / audit log stays the source."""

    order_id: str
    buyer_id: str
    placed_at: AwareDatetime
    lines: list[OrderLineRef] = Field(default_factory=list)
    total_cents: int  # net of VAT


class PastOrders(Protocol):
    """Read-only view of order history (the real one adapts the front door's audit log)."""

    def list_orders(self, buyer_id: str) -> list[OrderRef]: ...


class ContextItem(_Closed):
    memory: Memory
    used_because: str  # e.g. "always-preference from 2026-11-14"


class Overridden(_Closed):
    memory_id: str
    by_memory_id: str
    reason: str  # e.g. "this_order beats always for allergen_avoid:wheat"


class ProposedMandateChange(_Closed):
    """A remembered answer that looks like a rule. NEVER applied: the human must confirm it in
    the mandate (T09). `confirmed` is always False here."""

    memory_id: str
    summary: str
    confirmed: Literal[False] = False


class ProfileContext(_Closed):
    buyer_id: str
    order_id: str
    as_of: AwareDatetime
    items: list[ContextItem] = Field(default_factory=list)
    overridden: list[Overridden] = Field(default_factory=list)
    guidance: list[Preference] = Field(default_factory=list)  # soft, never a gate
    suggested_questions: list[str] = Field(default_factory=list)
    proposed_mandate_changes: list[ProposedMandateChange] = Field(default_factory=list)
    recent_orders: list[OrderRef] = Field(default_factory=list)


__all__ = [
    "ContextItem",
    "EventType",
    "Memory",
    "MemoryKind",
    "MemorySource",
    "OrderLineRef",
    "OrderRef",
    "Overridden",
    "PastOrders",
    "ProfileContext",
    "ProfileEvent",
    "ProposedMandateChange",
    "Value",
    "date",
]
