"""T06.1: fixes from Omar's review of the merged decision step, plus the real-data stock sentinel."""

from datetime import timedelta

import pytest
from builders import (
    NOW,
    codes,
    make_facts,
    make_line,
    make_mandate,
    make_quote,
    make_request,
    run,
)
from helpers_b import ASK, AUTO, check
from trade_contracts import CutOff, HardRule, QuantityInfo
from trade_contracts.common import RuleKind

from trade_decision import decide

# --- item 1: anything that is not AVAILABLE can never be AUTO --------------------------------


def test_unavailable_with_a_normal_stock_number_is_never_auto():
    q = make_quote(availability="unavailable", stock=5000)  # sales-blocked but "5000 in stock"
    check(run(quotes=[q]), ASK, "UNDELIVERABLE")


@pytest.mark.parametrize("status", ["unknown", "partial"])
def test_unknown_or_partial_availability_asks_even_with_enough_stock(status):
    check(run(quotes=[make_quote(availability=status, stock=5000)]), ASK, "DATA_MISSING")


def test_available_with_enough_stock_is_still_auto():
    check(run(), AUTO)


# --- item 2: the fail-closed fallback cannot raise --------------------------------------------


def test_naive_now_is_treated_as_helsinki_and_decides_normally():
    naive = NOW.replace(tzinfo=None)
    d = decide(make_request(), make_mandate(), [make_line()], [make_quote()], [make_facts()], now=naive)
    assert d.outcome == "AUTO" and d.decided_at.tzinfo is not None


def test_naive_now_with_a_failing_check_still_returns_a_decision():
    naive = NOW.replace(tzinfo=None)
    d = decide(None, None, None, [], [], now=naive)  # type: ignore[arg-type]
    assert d.outcome == "ASK_HUMAN" and codes(d) == ["ENGINE_ERROR"] and d.decided_at.tzinfo


@pytest.mark.parametrize("junk", [None, "2026-11-14", 12345])
def test_unusable_now_fails_closed_with_a_valid_timestamp(junk):
    d = decide(make_request(), make_mandate(), [make_line()], [make_quote()], [make_facts()], now=junk)
    assert d.outcome == "ASK_HUMAN" and codes(d) == ["ENGINE_ERROR"]
    assert d.decided_at.year == 1970  # the fixed sentinel, not a hidden clock


def test_broken_config_object_fails_closed_inside_the_try():
    d = decide(
        make_request(), make_mandate(), [make_line()], [make_quote()], [make_facts()],
        now=NOW, config=object(),  # type: ignore[arg-type]
    )  # fmt: skip
    assert d.outcome == "ASK_HUMAN" and codes(d) == ["ENGINE_ERROR"]


# --- item 3: ordinary chef text is not a "limit change attempt" -------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "keep it within budget",
        "no need to change the spending limit",
        "please set the delivery for Monday",
        "raise the quantity to 200 L",
    ],
)
def test_ordinary_text_is_not_a_limit_change_attempt(text):
    d = run(request=make_request(text=text))
    assert "LIMIT_CHANGE_ATTEMPT" not in codes(d)
    check(d, AUTO)


# --- item 4: conflicting duplicate data asks --------------------------------------------------


def test_conflicting_duplicate_quotes_ask_a_human():
    quotes = [make_quote(price_cents=140), make_quote(price_cents=150)]
    check(run(quotes=quotes), ASK, "DATA_MISSING")


def test_conflicting_duplicate_facts_ask_a_human():
    facts = [make_facts(reliability=0.95), make_facts(reliability=0.50)]
    check(run(facts=facts), ASK, "DATA_MISSING")


def test_identical_duplicates_are_fine():
    check(run(quotes=[make_quote(), make_quote()], facts=[make_facts(), make_facts()]), AUTO)


# --- item 11: only the exact placeholder 999999 means "unknown quantity" -----------------------


def test_eila_style_huge_stock_is_plenty_not_unknown():
    q = make_quote(quantity=QuantityInfo(known=True, value=9_999_999_999))
    d = run(lines=[make_line(quantity=100)], quotes=[q])
    assert "QTY_UNKNOWN" not in codes(d)
    check(d, AUTO)


@pytest.mark.parametrize(
    "quantity",
    [QuantityInfo(known=False), QuantityInfo(known=True, value=999999)],
    ids=["known-false", "known-999999"],
)
def test_the_999999_placeholder_still_asks(quantity):
    check(run(quotes=[make_quote(quantity=quantity)]), ASK, "QTY_UNKNOWN")


def test_huge_stock_is_not_offered_or_blocked_wrongly_for_alternatives():
    # a candidate with huge known stock is a valid alternative for a blocked product
    blocked = make_quote(availability="unavailable", stock=5000)
    alt_q = make_quote("ALT1", quantity=QuantityInfo(known=True, value=9_999_999_999))
    d = run(quotes=[blocked, alt_q], facts=[make_facts(), make_facts("ALT1")])
    assert [a.product_id for a in d.alternatives] == ["ALT1"]


# --- item 5: a reliability rule with no record asks -------------------------------------------


def test_reliability_rule_with_no_record_asks_even_on_a_cheap_order():
    rule = HardRule(kind=RuleKind.MIN_DELIVERY_RELIABILITY, value=0.9)
    mandate = make_mandate(hard_rules=[rule])
    d = run(mandate=mandate, facts=[make_facts(reliability=None)])
    check(d, ASK, "LOW_RELIABILITY")


def test_no_reliability_record_and_no_rule_stays_ok_on_a_cheap_order():
    check(run(facts=[make_facts(reliability=None)]), AUTO)


# --- item 6: the cut-off passed flag counts as well as the clock ------------------------------


def test_cutoff_passed_flag_is_honoured_even_if_the_clock_says_open():
    future = NOW + timedelta(days=1)
    q = make_quote(cut_off=CutOff(closing_time=future, passed=True))
    check(run(quotes=[q]), ASK, "CUTOFF_PASSED")


# --- item 10: a negative recent spend cannot widen the weekly budget --------------------------


def test_negative_recent_spend_is_clamped_to_zero():
    mandate = make_mandate(weekly_budget_cents=10000)  # the 14000 order exceeds it
    d = run(mandate=mandate, recent_spend_cents=-500000)
    assert "WEEKLY_BUDGET_EXCEEDED" in codes(d)

