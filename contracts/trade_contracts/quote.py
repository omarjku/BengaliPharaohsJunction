"""Quote: Valio's answer for one product, with how much to trust it."""

from __future__ import annotations

from datetime import date

from pydantic import AwareDatetime, Field, model_validator

from .common import Availability, ContractModel, QuoteSource, VersionedModel


class QuantityInfo(ContractModel):
    """Available quantity. `known=False` means unknown, NOT unlimited
    (the mock API reports Terminal stock as 999999)."""

    known: bool
    value: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _value_matches_known(self) -> QuantityInfo:
        if self.known and self.value is None:
            raise ValueError("known quantity needs a value")
        if not self.known and self.value is not None:
            raise ValueError("unknown quantity must not carry a value")
        return self


class CutOff(ContractModel):
    closing_time: AwareDatetime
    passed: bool


class Quote(VersionedModel):
    product_id: str = Field(min_length=1)
    product_name: str | None = None
    unit_price_eur: float = Field(ge=0)
    unit: str = Field(min_length=1, description="Sales unit, e.g. '1 L carton'.")
    availability: Availability
    quantity: QuantityInfo
    available_date: date | None = None
    source: QuoteSource
    fetched_at: AwareDatetime = Field(description="Freshness: when this was read.")
    valid_until: AwareDatetime | None = None
    cut_off: CutOff | None = None

    @model_validator(mode="after")
    def _valid_until_after_fetch(self) -> Quote:
        if self.valid_until is not None and self.valid_until <= self.fetched_at:
            raise ValueError("valid_until must be after fetched_at")
        return self
