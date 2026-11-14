"""Shared contracts v0.2 for the Trusted Trade Agents front door.

Money: integer cents, net of VAT (customer price excluding VAT).
"""

from .audit import AuditEntry, AuditInput, RejectedOption
from .common import (
    CONTRACT_VERSION,
    HARD_CODES,
    AllergenStatus,
    Outcome,
    ReasonCode,
    Severity,
)
from .decision import Alternative, Decision, Reason
from .mandate import HardRule, Mandate, OpenQuestion, Preference
from .money import eur_to_cents
from .product import ProductFacts
from .quote import CutOff, QuantityInfo, Quote
from .request import PurchaseRequest, RequestItem

# The top-level shapes that get a published JSON Schema.
SCHEMA_MODELS = {
    "PurchaseRequest": PurchaseRequest,
    "Mandate": Mandate,
    "Quote": Quote,
    "ProductFacts": ProductFacts,
    "Decision": Decision,
    "AuditEntry": AuditEntry,
}

__all__ = [
    "CONTRACT_VERSION",
    "HARD_CODES",
    "SCHEMA_MODELS",
    "AllergenStatus",
    "Alternative",
    "AuditEntry",
    "AuditInput",
    "CutOff",
    "Decision",
    "HardRule",
    "Mandate",
    "OpenQuestion",
    "Outcome",
    "Preference",
    "ProductFacts",
    "PurchaseRequest",
    "QuantityInfo",
    "Quote",
    "Reason",
    "ReasonCode",
    "RejectedOption",
    "RequestItem",
    "Severity",
    "eur_to_cents",
]
