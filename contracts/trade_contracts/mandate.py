"""Mandate: the buyer's rules, compiled from plain language."""

from __future__ import annotations

from pydantic import Field

from .common import (
    ContractModel,
    PreferenceScope,
    RuleKind,
    UncertaintyPolicy,
    VersionedModel,
)


class HardRule(ContractModel):
    """A check that is either met or not. Breaking one justifies DECLINE
    (except AUTO_APPROVE_LIMIT_EUR, which only decides who signs off)."""

    kind: RuleKind
    value: str | float = Field(description="Allergen/claim name, or a number, depending on kind.")
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
