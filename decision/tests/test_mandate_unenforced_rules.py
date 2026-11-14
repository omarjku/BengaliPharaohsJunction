"""A mandate rule the engine cannot check must never be silently dropped: a human is asked."""

import pytest
from builders import codes, make_mandate, run
from helpers_b import ASK, AUTO, check, reason
from trade_contracts import HardRule
from trade_contracts.common import RuleKind


def rule(kind: RuleKind, value) -> HardRule:
    return HardRule(kind=kind, value=value)


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        pytest.param(RuleKind.REQUIRED_CLAIM, "FREE_FROM_LACTOSE", id="required-claim"),
        pytest.param(RuleKind.MAX_UNIT_PRICE_CENTS, 200, id="max-unit-price"),
    ],
)
def test_unenforced_rule_kind_asks_a_human(kind, value):
    d = run(mandate=make_mandate(hard_rules=[rule(kind, value)]))
    check(d, ASK, "MANDATE_INVALID")
    assert kind.value in reason(d, "MANDATE_INVALID").facts["rule_kinds"]


def test_both_unenforced_kinds_give_one_reason_listing_both():
    d = run(
        mandate=make_mandate(
            hard_rules=[
                rule(RuleKind.REQUIRED_CLAIM, "VEGAN"),
                rule(RuleKind.MAX_UNIT_PRICE_CENTS, 200),
            ]
        )
    )
    assert codes(d).count("MANDATE_INVALID") == 1
    kinds = reason(d, "MANDATE_INVALID").facts["rule_kinds"]
    assert "required_claim" in kinds and "max_unit_price_cents" in kinds


def test_enforced_kinds_do_not_trigger_it():
    d = run(
        mandate=make_mandate(
            hard_rules=[
                rule(RuleKind.EXCLUDED_ALLERGEN, "gluten"),
                rule(RuleKind.AUTO_APPROVE_LIMIT_CENTS, 50000),
                rule(RuleKind.MIN_DELIVERY_RELIABILITY, 0.9),
            ]
        )
    )
    check(d, AUTO)
    assert "MANDATE_INVALID" not in codes(d)
