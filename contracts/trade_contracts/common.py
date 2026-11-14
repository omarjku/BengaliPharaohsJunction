"""Shared building blocks: closed vocabularies (enums) and the base model."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

CONTRACT_VERSION = "0.1"


class ContractModel(BaseModel):
    """Base for every shape: unknown fields are rejected (closed vocabulary)."""

    model_config = ConfigDict(extra="forbid")


class VersionedModel(ContractModel):
    """Base for the five top-level shapes; carries the contract version."""

    contract_version: Literal["0.1"] = CONTRACT_VERSION


class Channel(StrEnum):
    TEXT = "text"
    VOICE = "voice"
    PHOTO = "photo"
    MENU = "menu"


class UncertaintyPolicy(StrEnum):
    """What the agent does when it cannot verify something."""

    ASK = "ask"
    DECLINE = "decline"
    APPROVE = "approve"


class PreferenceScope(StrEnum):
    """How long a preference lasts (D5: don't over-generalise)."""

    THIS_ORDER = "this_order"
    ALWAYS = "always"


class RuleKind(StrEnum):
    """Closed list of checks a hard rule may express."""

    EXCLUDED_ALLERGEN = "excluded_allergen"
    REQUIRED_CLAIM = "required_claim"
    MAX_UNIT_PRICE_EUR = "max_unit_price_eur"
    MIN_DELIVERY_RELIABILITY = "min_delivery_reliability"
    AUTO_APPROVE_LIMIT_EUR = "auto_approve_limit_eur"


class Outcome(StrEnum):
    AUTO = "AUTO"
    ASK_HUMAN = "ASK_HUMAN"
    DECLINE = "DECLINE"


class ReasonCode(StrEnum):
    # Uncertain or unverifiable -> a human decides (D6: never silently reject)
    CUT_OFF_PASSED = "CUT_OFF_PASSED"
    QUANTITY_UNKNOWN = "QUANTITY_UNKNOWN"
    PARTIAL_STOCK = "PARTIAL_STOCK"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_DELIVERABLE = "NOT_DELIVERABLE"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    OVER_SPEND_LIMIT = "OVER_SPEND_LIMIT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    SUBSTITUTION_OUTSIDE_PREFERENCES = "SUBSTITUTION_OUTSIDE_PREFERENCES"
    # A rule the buyer set was clearly broken -> the only reasons that justify DECLINE
    HARD_RULE_VIOLATED = "HARD_RULE_VIOLATED"
    ALLERGEN_CONFLICT = "ALLERGEN_CONFLICT"
    # Everything checked out
    WITHIN_MANDATE = "WITHIN_MANDATE"


HARD_RULE_CODES: frozenset[ReasonCode] = frozenset(
    {ReasonCode.HARD_RULE_VIOLATED, ReasonCode.ALLERGEN_CONFLICT}
)


class Availability(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class QuoteSource(StrEnum):
    VALIO_API = "valio_api"
    VALIO_FRONT_DOOR = "valio_front_door"
    MOCK = "mock"
