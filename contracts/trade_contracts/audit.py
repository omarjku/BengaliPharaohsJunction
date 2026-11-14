"""AuditEntry: one human-readable, append-only record of what happened and why."""

from __future__ import annotations

from pydantic import AwareDatetime, Field

from .common import ContractModel, VersionedModel
from .decision import Decision, Reason
from .mandate import Mandate
from .quote import Quote
from .request import PurchaseRequest


class AuditInput(ContractModel):
    request: PurchaseRequest
    mandate: Mandate | None = None
    quotes: list[Quote] = Field(default_factory=list)


class RejectedOption(ContractModel):
    product_id: str = Field(min_length=1)
    reasons: list[Reason] = Field(min_length=1)


class AuditEntry(VersionedModel):
    id: str = Field(min_length=1)
    timestamp: AwareDatetime
    actor: str = Field(min_length=1, description="e.g. 'buyer_agent', 'valio_front_door', 'human:<name>'.")
    input: AuditInput
    decision: Decision
    rejected_options: list[RejectedOption] = Field(default_factory=list)
