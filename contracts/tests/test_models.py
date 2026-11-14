from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from trade_contracts import (
    AuditEntry,
    Decision,
    Mandate,
    PurchaseRequest,
    QuantityInfo,
    Quote,
    RejectedOption,
)

NOW = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)


def reason(code="OVER_SPEND_LIMIT", message="why"):
    return {"code": code, "message": message}


def decision(**overrides):
    base = {
        "request_id": "r1",
        "outcome": "ASK_HUMAN",
        "reasons": [reason()],
        "decided_at": NOW,
    }
    return Decision(**{**base, **overrides})


def quote(**overrides):
    base = {
        "product_id": "p1",
        "unit_price_eur": 1.4,
        "unit": "1 L",
        "availability": "available",
        "quantity": {"known": True, "value": 10},
        "source": "mock",
        "fetched_at": NOW,
    }
    return Quote(**{**base, **overrides})


# --- closed vocabulary / strictness -------------------------------------------------


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        quote(surprise="x")


def test_naive_datetime_is_rejected():
    with pytest.raises(ValidationError):
        quote(fetched_at=datetime(2026, 11, 14, 9, 0))


def test_request_needs_text_and_timezone_aware_time():
    ok = PurchaseRequest(id="r1", buyer_id="b", text="milk", created_at=NOW)
    assert ok.channel == "text" and ok.items == []
    with pytest.raises(ValidationError):
        PurchaseRequest(id="r1", buyer_id="b", text="", created_at=NOW)


# --- Quote: known vs unknown quantity -----------------------------------------------


def test_unknown_quantity_has_no_value():
    assert QuantityInfo(known=False).value is None
    with pytest.raises(ValidationError):
        QuantityInfo(known=False, value=999999)


def test_known_quantity_needs_a_value():
    with pytest.raises(ValidationError):
        QuantityInfo(known=True)


def test_valid_until_must_be_after_fetch():
    with pytest.raises(ValidationError):
        quote(valid_until=NOW)


def test_negative_price_rejected():
    with pytest.raises(ValidationError):
        quote(unit_price_eur=-1)


# --- Decision rules (D6: never silently reject) --------------------------------------


def test_decline_needs_a_hard_rule_reason():
    with pytest.raises(ValidationError):
        decision(outcome="DECLINE", reasons=[reason("CUT_OFF_PASSED")])


@pytest.mark.parametrize("code", ["HARD_RULE_VIOLATED", "ALLERGEN_CONFLICT"])
def test_decline_with_hard_rule_reason_is_ok(code):
    assert decision(outcome="DECLINE", reasons=[reason(code)]).outcome == "DECLINE"


def test_every_decision_needs_a_reason():
    with pytest.raises(ValidationError):
        decision(reasons=[])


def test_auto_only_carries_within_mandate():
    assert decision(outcome="AUTO", reasons=[reason("WITHIN_MANDATE")]).outcome == "AUTO"
    with pytest.raises(ValidationError):
        decision(outcome="AUTO", reasons=[reason("OVER_SPEND_LIMIT")])


def test_within_mandate_not_allowed_on_ask_human():
    with pytest.raises(ValidationError):
        decision(outcome="ASK_HUMAN", reasons=[reason("WITHIN_MANDATE")])


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_confidence_must_be_between_0_and_1(bad):
    with pytest.raises(ValidationError):
        decision(confidence=bad)


def test_confidence_may_be_null():
    assert decision(confidence=None).confidence is None


# --- Mandate -------------------------------------------------------------------------


def test_mandate_defaults_to_ask_when_unsure():
    m = Mandate(id="m1", buyer_id="b")
    assert m.uncertainty_policy == "ask"
    assert m.hard_rules == [] and m.guidance == [] and m.open_questions == []


def test_preference_requires_a_scope():
    with pytest.raises(ValidationError):
        Mandate(id="m1", buyer_id="b", guidance=[{"text": "no wheat flour"}])


def test_preference_scope_this_order_and_always():
    m = Mandate(
        id="m1",
        buyer_id="b",
        guidance=[
            {"text": "no wheat flour today", "scope": "this_order"},
            {"text": "prefer Finnish", "scope": "always"},
        ],
    )
    assert [g.scope for g in m.guidance] == ["this_order", "always"]


def test_hard_rule_kind_is_a_closed_list():
    with pytest.raises(ValidationError):
        Mandate(id="m1", buyer_id="b", hard_rules=[{"kind": "make_it_cheap", "value": 1}])


# --- Audit ---------------------------------------------------------------------------


def test_rejected_option_needs_reasons():
    with pytest.raises(ValidationError):
        RejectedOption(product_id="p2", reasons=[])


def test_audit_entry_round_trips_through_json():
    entry = AuditEntry(
        id="a1",
        timestamp=NOW,
        actor="buyer_agent",
        input={"request": PurchaseRequest(id="r1", buyer_id="b", text="milk", created_at=NOW)},
        decision=decision(),
        rejected_options=[{"product_id": "p2", "reasons": [reason("CUT_OFF_PASSED")]}],
    )
    assert AuditEntry.model_validate_json(entry.model_dump_json()) == entry
