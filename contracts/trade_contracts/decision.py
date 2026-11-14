"""Decision: AUTO / ASK_HUMAN / DECLINE, always with reasons."""

from __future__ import annotations

from pydantic import AwareDatetime, Field, model_validator

from .common import HARD_RULE_CODES, ContractModel, Outcome, ReasonCode, VersionedModel


class Reason(ContractModel):
    code: ReasonCode
    message: str = Field(min_length=1, description="Plain language, shown to the chef.")
    product_id: str | None = None


class Alternative(ContractModel):
    product_id: str = Field(min_length=1)
    summary: str = Field(min_length=1, description="Why this is offered instead.")


class Decision(VersionedModel):
    request_id: str = Field(min_length=1)
    outcome: Outcome
    reasons: list[Reason] = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    alternatives: list[Alternative] = Field(default_factory=list)
    decided_at: AwareDatetime

    @model_validator(mode="after")
    def _outcome_matches_reasons(self) -> Decision:
        codes = {r.code for r in self.reasons}
        if self.outcome is Outcome.DECLINE and not (codes & HARD_RULE_CODES):
            raise ValueError("DECLINE needs a hard-rule reason; use ASK_HUMAN when unsure")
        if self.outcome is Outcome.AUTO and codes != {ReasonCode.WITHIN_MANDATE}:
            raise ValueError("AUTO may only carry the WITHIN_MANDATE reason")
        if self.outcome is not Outcome.AUTO and ReasonCode.WITHIN_MANDATE in codes:
            raise ValueError("WITHIN_MANDATE belongs to AUTO decisions only")
        return self
