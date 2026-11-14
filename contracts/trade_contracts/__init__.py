"""Shared contracts v0 for the Trusted Trade Agents front door."""

from .audit import AuditEntry, AuditInput, RejectedOption
from .common import CONTRACT_VERSION, HARD_RULE_CODES, Outcome, ReasonCode
from .decision import Alternative, Decision, Reason
from .mandate import HardRule, Mandate, OpenQuestion, Preference
from .quote import CutOff, QuantityInfo, Quote
from .request import PurchaseRequest, RequestItem

# The five top-level shapes that get a published JSON Schema.
SCHEMA_MODELS = {
    "PurchaseRequest": PurchaseRequest,
    "Mandate": Mandate,
    "Quote": Quote,
    "Decision": Decision,
    "AuditEntry": AuditEntry,
}

__all__ = [
    "CONTRACT_VERSION",
    "HARD_RULE_CODES",
    "SCHEMA_MODELS",
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
    "PurchaseRequest",
    "QuantityInfo",
    "Quote",
    "Reason",
    "ReasonCode",
    "RejectedOption",
    "RequestItem",
]
