from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from trade_contracts import (
    HARD_CODES,
    AuditEntry,
    Decision,
    Mandate,
    ProductFacts,
    PurchaseRequest,
    QuantityInfo,
    Quote,
    ReasonCode,
    RejectedOption,
)

NOW = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)


def reason(code="SPEND_OVER_LIMIT", severity="ASK_HUMAN", **extra):
    return {"code": code, "severity": severity, "message": "why", **extra}


def decision(outcome="ASK_HUMAN", reasons=None, **overrides):
    base = {
        "request_id": "r1",
        "outcome": outcome,
        "reasons": [reason()] if reasons is None else reasons,
        "rules_version": "t06-0.1",
        "decided_at": NOW,
    }
    return Decision(**{**base, **overrides})


def quote(**overrides):
    base = {
        "product_id": "p1",
        "unit_price_cents": 140,
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


def test_old_contract_version_is_rejected():
    with pytest.raises(ValidationError):
        quote(contract_version="0.1")


def test_request_needs_text_and_timezone_aware_time():
    ok = PurchaseRequest(id="r1", buyer_id="b", text="milk", created_at=NOW)
    assert ok.channel == "text" and ok.items == []
    with pytest.raises(ValidationError):
        PurchaseRequest(id="r1", buyer_id="b", text="", created_at=NOW)


# --- Quote: money in cents, known vs unknown quantity --------------------------------


def test_price_is_integer_cents():
    assert quote(unit_price_cents=140).unit_price_cents == 140
    with pytest.raises(ValidationError):
        quote(unit_price_cents=1.4)  # euros as a float must not slip in


def test_missing_price_is_allowed_but_must_be_explicit():
    assert quote(unit_price_cents=None).unit_price_cents is None
    base = quote().model_dump(mode="json")
    del base["unit_price_cents"]
    with pytest.raises(ValidationError):
        Quote.model_validate(base)


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


# --- Decision (D3, D4, D17, D22) ------------------------------------------------------


def test_hard_codes_are_the_d4_list():
    assert HARD_CODES == {
        ReasonCode.ALLERGEN_CONTAINS,
        ReasonCode.BLOCKLISTED,
        ReasonCode.QTY_INVALID,
        ReasonCode.UNKNOWN_PRODUCT,
        ReasonCode.LIMIT_CHANGE_ATTEMPT,
        ReasonCode.POLICY_DECLINE_UNKNOWN,
    }


def test_decline_severity_only_for_hard_codes():
    with pytest.raises(ValidationError):
        decision("DECLINE", [reason("CUTOFF_PASSED", "DECLINE")])


@pytest.mark.parametrize("code", sorted(HARD_CODES))
def test_decline_with_each_hard_code_is_ok(code):
    d = decision("DECLINE", [reason(code, "DECLINE")])
    assert d.outcome == "DECLINE"


def test_outcome_must_match_highest_severity():
    with pytest.raises(ValidationError):
        decision("AUTO", [reason()])  # an ASK reason cannot end in AUTO
    with pytest.raises(ValidationError):
        decision("ASK_HUMAN", [reason("BLOCKLISTED", "DECLINE")])


def test_ask_or_decline_without_reasons_is_rejected():
    for outcome in ("ASK_HUMAN", "DECLINE"):
        with pytest.raises(ValidationError):
            decision(outcome, [])


def test_auto_may_have_no_reasons_or_only_info():
    assert decision("AUTO", []).primary_reason is None
    info = reason("DEFAULT_MANDATE_APPLIED", "INFO")
    assert decision("AUTO", [info]).outcome == "AUTO"


def test_reasons_must_be_sorted_by_severity():
    low_first = [reason(), reason("BLOCKLISTED", "DECLINE")]
    with pytest.raises(ValidationError):
        decision("DECLINE", low_first)
    ok = decision("DECLINE", [reason("BLOCKLISTED", "DECLINE"), reason()])
    assert ok.outcome == "DECLINE"


def test_primary_reason_is_filled_from_first_reason():
    d = decision("DECLINE", [reason("BLOCKLISTED", "DECLINE"), reason()])
    assert d.primary_reason is not None and d.primary_reason.code == "BLOCKLISTED"


def test_primary_reason_must_equal_first_reason():
    wrong = reason("PRICE_MISSING")
    with pytest.raises(ValidationError):
        decision(primary_reason=wrong)


def test_reason_carries_facts_and_suggested_fix():
    r = decision(
        reasons=[reason(facts={"total_cents": 140000, "over": True}, suggested_fix="Reduce.")]
    ).reasons[0]
    assert r.facts["total_cents"] == 140000 and r.suggested_fix == "Reduce."


def test_at_most_three_alternatives():
    alts = [{"product_id": str(i), "summary": "s"} for i in range(4)]
    with pytest.raises(ValidationError):
        decision(alternatives=alts)


def test_rules_version_is_required():
    with pytest.raises(ValidationError):
        decision(rules_version="")


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_confidence_must_be_between_0_and_1(bad):
    with pytest.raises(ValidationError):
        decision(confidence=bad)


def test_confidence_may_be_null():
    assert decision(confidence=None).confidence is None


# --- Mandate -------------------------------------------------------------------------


def test_mandate_defaults():
    m = Mandate(id="m1", buyer_id="b")
    assert m.uncertainty_policy == "ask"
    assert m.hard_rules == [] and m.guidance == [] and m.open_questions == []
    assert m.blocklist == []
    assert m.per_line_cap_cents == 30000
    assert m.weekly_budget_cents is None and m.expires_at is None


def test_mandate_money_limits_must_be_positive_cents():
    with pytest.raises(ValidationError):
        Mandate(id="m1", buyer_id="b", per_line_cap_cents=0)
    with pytest.raises(ValidationError):
        Mandate(id="m1", buyer_id="b", weekly_budget_cents=-5)


def test_mandate_expiry_needs_timezone():
    with pytest.raises(ValidationError):
        Mandate(id="m1", buyer_id="b", expires_at=datetime(2026, 11, 16, 12, 0))


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
    with pytest.raises(ValidationError):  # the old euro-based names are gone
        Mandate(id="m1", buyer_id="b", hard_rules=[{"kind": "auto_approve_limit_eur", "value": 5}])


# --- ProductFacts ---------------------------------------------------------------------


def facts(**overrides):
    base = {"product_id": "463335", "sales_unit": "1 L carton"}
    return ProductFacts(**{**base, **overrides})


def test_product_facts_minimal_and_allergens():
    f = facts(allergens={"gluten": "FREE_FROM", "nuts": "MAY_CONTAIN", "milk": "CONTAINS"})
    assert f.name_en is None and f.category is None and f.reliability is None
    assert f.allergens["nuts"] == "MAY_CONTAIN"


def test_product_facts_rejects_bad_values():
    with pytest.raises(ValidationError):
        facts(allergens={"gluten": "PROBABLY_FINE"})
    with pytest.raises(ValidationError):
        facts(reliability=1.2)
    with pytest.raises(ValidationError):
        facts(min_order_qty=0)
    with pytest.raises(ValidationError):
        facts(pack_size=-1)
    with pytest.raises(ValidationError):
        facts(surprise=1)


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
        rejected_options=[{"product_id": "p2", "reasons": [reason("CUTOFF_PASSED")]}],
    )
    assert AuditEntry.model_validate_json(entry.model_dump_json()) == entry
