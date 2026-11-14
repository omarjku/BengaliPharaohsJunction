"""PurchaseRequest: what the buyer asked for."""

from __future__ import annotations

from datetime import date

from pydantic import AwareDatetime, Field

from .common import Channel, ContractModel, VersionedModel


class RequestItem(ContractModel):
    name: str = Field(min_length=1, description="What the buyer called it, e.g. 'lactose-free milk'.")
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, description="e.g. 'L', 'KG', 'PCS'.")


class PurchaseRequest(VersionedModel):
    id: str = Field(min_length=1)
    buyer_id: str = Field(min_length=1)
    text: str = Field(min_length=1, description="The original words, kept for the audit trail.")
    channel: Channel = Channel.TEXT
    items: list[RequestItem] = Field(default_factory=list)
    needed_by: date | None = None
    created_at: AwareDatetime
