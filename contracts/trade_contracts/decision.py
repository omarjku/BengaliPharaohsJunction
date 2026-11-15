"""Decision: AUTO / ASK_HUMAN / DECLINE, with every reason that applied."""

from __future__ import annotations

from pydantic import AwareDatetime, Field, model_validator

from .common import HARD_CODES, ContractModel, Outcome, ReasonCode, Severity, VersionedModel

# Facts are small numbers/strings the chef-facing text is built from. Money is net cents.
FactValue = str | int | float | bool | None

_RANK = {Severity.INFO: 0, Severity.ASK_HUMAN: 1, Severity.DECLINE: 2}
_OUTCOME_FOR = {
    Severity.INFO: Outcome.AUTO,
    Severity.ASK_HUMAN: Outcome.ASK_HUMAN,
    Severity.DECLINE: Outcome.DECLINE,
}


class Reason(ContractModel):
    code: ReasonCode
    severity: Severity
    message: str = Field(min_length=1, description="Plain language, shown to the chef.")
    facts: dict[str, FactValue] = Field(
        default_factory=dict, description="The numbers behind the message (money in net cents)."
    )
    suggested_fix: str | None = Field(default=None, description="What the human can do about it.")
    product_id: str | None = None

    @model_validator(mode="after")
    def _decline_only_for_hard_codes(self) -> Reason:
        if self.severity is Severity.DECLINE and self.code not in HARD_CODES:
            raise ValueError(f"{self.code} may not carry DECLINE severity; use ASK_HUMAN")
        return self


class Alternative(ContractModel):
    item: int | None = Field(default=None, ge=0, description="Request item index this alternative belongs to.")
    product_id: str = Field(min_length=1)
    summary: str = Field(min_length=1, description="Why this is offered instead.")


class Decision(VersionedModel):
    request_id: str = Field(min_length=1)
    outcome: Outcome
    reasons: list[Reason] = Field(
        default_factory=list, description="All reasons, highest severity first."
    )
    primary_reason: Reason | None = Field(
        default=None, description="reasons[0]; filled in automatically; null only when no reasons."
    )
    confidence: float | None = Field(default=None, ge=0, le=1)
    alternatives: list[Alternative] = Field(default_factory=list, max_length=3)
    rules_version: str = Field(min_length=1)
    decided_at: AwareDatetime

    @model_validator(mode="after")
    def _consistent(self) -> Decision:
        ranks = [_RANK[r.severity] for r in self.reasons]
        if ranks != sorted(ranks, reverse=True):
            raise ValueError("reasons must be sorted by severity, highest first")
        expected = _OUTCOME_FOR[self.reasons[0].severity] if self.reasons else Outcome.AUTO
        if self.outcome is not expected:
            raise ValueError(f"outcome {self.outcome} does not match reasons (expected {expected})")
        first = self.reasons[0] if self.reasons else None
        if self.primary_reason is None:
            self.primary_reason = first
        elif self.primary_reason != first:
            raise ValueError("primary_reason must equal reasons[0]")
        return self
