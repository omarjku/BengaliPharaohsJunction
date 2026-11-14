"""Shared building blocks: closed vocabularies (enums) and the base model.

Money convention (all shapes): integer cents, and NET OF VAT, i.e. the customer price
excluding VAT. Spend limits are compared on that same net basis.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

CONTRACT_VERSION = "0.2"


class ContractModel(BaseModel):
    """Base for every shape: unknown fields are rejected (closed vocabulary)."""

    model_config = ConfigDict(extra="forbid")


class VersionedModel(ContractModel):
    """Base for the top-level shapes; carries the contract version."""

    contract_version: Literal["0.2"] = CONTRACT_VERSION


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
    """Closed list of checks a hard rule may express. Money values are net cents."""

    EXCLUDED_ALLERGEN = "excluded_allergen"
    REQUIRED_CLAIM = "required_claim"
    MAX_UNIT_PRICE_CENTS = "max_unit_price_cents"
    MIN_DELIVERY_RELIABILITY = "min_delivery_reliability"
    AUTO_APPROVE_LIMIT_CENTS = "auto_approve_limit_cents"


class Outcome(StrEnum):
    AUTO = "AUTO"
    ASK_HUMAN = "ASK_HUMAN"
    DECLINE = "DECLINE"


class Severity(StrEnum):
    """Per-reason severity. The Decision outcome is the highest severity present:
    DECLINE > ASK_HUMAN > INFO (INFO only = AUTO)."""

    INFO = "INFO"
    ASK_HUMAN = "ASK_HUMAN"
    DECLINE = "DECLINE"


class ReasonCode(StrEnum):
    # --- quantity and stock
    QTY_INVALID = "QTY_INVALID"
    QTY_AMBIGUOUS = "QTY_AMBIGUOUS"
    ASSUMPTION_CONFIRM = "ASSUMPTION_CONFIRM"
    QTY_SUSPICIOUS = "QTY_SUSPICIOUS"
    QTY_UNKNOWN = "QTY_UNKNOWN"
    STOCK_PARTIAL = "STOCK_PARTIAL"
    STOCK_NONE = "STOCK_NONE"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    # --- delivery, dates, data quality
    CUTOFF_PASSED = "CUTOFF_PASSED"
    UNDELIVERABLE = "UNDELIVERABLE"
    DATE_NOT_HONOURED = "DATE_NOT_HONOURED"
    LOW_RELIABILITY = "LOW_RELIABILITY"
    QUOTE_STALE = "QUOTE_STALE"
    PRICE_MISSING = "PRICE_MISSING"
    PRICE_CHANGED = "PRICE_CHANGED"
    UNKNOWN_PRODUCT = "UNKNOWN_PRODUCT"
    DATA_MISSING = "DATA_MISSING"
    # --- spend
    SPEND_OVER_LIMIT = "SPEND_OVER_LIMIT"
    LINE_OVER_CAP = "LINE_OVER_CAP"
    WEEKLY_BUDGET_EXCEEDED = "WEEKLY_BUDGET_EXCEEDED"
    # --- mandate and allergens
    ALLERGEN_CONTAINS = "ALLERGEN_CONTAINS"
    ALLERGEN_MAY_CONTAIN = "ALLERGEN_MAY_CONTAIN"
    ALLERGEN_DATA_MISSING = "ALLERGEN_DATA_MISSING"
    BLOCKLISTED = "BLOCKLISTED"
    MANDATE_MISSING = "MANDATE_MISSING"
    MANDATE_EXPIRED = "MANDATE_EXPIRED"
    MANDATE_INVALID = "MANDATE_INVALID"
    DEFAULT_MANDATE_APPLIED = "DEFAULT_MANDATE_APPLIED"
    LIMIT_CHANGE_ATTEMPT = "LIMIT_CHANGE_ATTEMPT"
    POLICY_DECLINE_UNKNOWN = "POLICY_DECLINE_UNKNOWN"
    # --- engine
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    ENGINE_ERROR = "ENGINE_ERROR"
    # --- menu to cart
    MENU_ASSUMPTIONS = "MENU_ASSUMPTIONS"  # a cart proposed from a menu rests on per-cover recipe guesses
    COVERAGE_LOW = "COVERAGE_LOW"  # fewer than 60% of menu ingredients are in the proposed cart
    # --- informational
    CONFIDENCE_OK = "CONFIDENCE_OK"  # INFO: the confidence check passed (LOW_CONFIDENCE is kept for asks)
    FRONT_DOOR = "FRONT_DOOR"  # INFO on the agent audit entry: the front door's verdict, order id and audit id
    PROFILE_DEFAULT = "PROFILE_DEFAULT"  # INFO: an assumption taken from the buyer's profile (e.g. gluten-free kitchen)


# D4: the only codes that may carry DECLINE severity (the mandate itself forbids it and
# no human action on this order can fix it).
HARD_CODES: frozenset[ReasonCode] = frozenset(
    {
        ReasonCode.ALLERGEN_CONTAINS,
        ReasonCode.BLOCKLISTED,
        ReasonCode.QTY_INVALID,
        ReasonCode.UNKNOWN_PRODUCT,
        ReasonCode.LIMIT_CHANGE_ATTEMPT,
        ReasonCode.POLICY_DECLINE_UNKNOWN,
    }
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


class AllergenStatus(StrEnum):
    CONTAINS = "CONTAINS"
    MAY_CONTAIN = "MAY_CONTAIN"
    FREE_FROM = "FREE_FROM"
