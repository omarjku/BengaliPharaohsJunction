"""Mandate: the buyer's rules, compiled from plain language.

All money is integer cents, NET OF VAT (customer price excluding VAT); spend limits are
compared on that net basis.
"""

from __future__ import annotations

from pydantic import AwareDatetime, Field

from .common import (
    ContractModel,
    PreferenceScope,
    RuleKind,
    UncertaintyPolicy,
    VersionedModel,
)


class HardRule(ContractModel):
    """A check that is either met or not. Breaking one is a hard violation
    (except AUTO_APPROVE_LIMIT_CENTS, which only decides who signs off)."""

    kind: RuleKind
    value: str | float = Field(
        description="Allergen/claim name, or a number (cents for *_cents kinds), depending on kind."
    )
    scope: PreferenceScope = PreferenceScope.ALWAYS
    source_text: str | None = Field(default=None, description="The buyer's own words.")


class Preference(ContractModel):
    """Soft guidance that is not a clean check; shapes ranking, never blocks."""

    text: str = Field(min_length=1)
    scope: PreferenceScope


class OpenQuestion(ContractModel):
    """Something the compiler could not resolve; asked, not guessed."""

    question: str = Field(min_length=1)
    why: str | None = None


class Mandate(VersionedModel):
    id: str = Field(min_length=1)
    buyer_id: str = Field(min_length=1)
    hard_rules: list[HardRule] = Field(default_factory=list)
    uncertainty_policy: UncertaintyPolicy = UncertaintyPolicy.ASK
    guidance: list[Preference] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    blocklist: list[str] = Field(
        default_factory=list, description="Product ids that may never be ordered."
    )
    per_line_cap_cents: int = Field(
        default=30000, gt=0, description="Max net cents for one order line (default EUR 300)."
    )
    weekly_budget_cents: int | None = Field(
        default=None, gt=0, description="Optional net-cents budget for a rolling 7 days."
    )
    expires_at: AwareDatetime | None = Field(
        default=None, description="After this the mandate is expired (decisions ask a human)."
    )
