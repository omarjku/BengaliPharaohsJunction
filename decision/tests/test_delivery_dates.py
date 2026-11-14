"""Delivery, dates and data-quality rows (cases 16, 17, 19-25, price rows D11)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from builders import (
    HELSINKI,
    NOW,
    codes,
    make_facts,
    make_line,
    make_quote,
    make_request,
    run,
)
from helpers_b import ASK, AUTO, DECLINE, candidate, check, order_with, reason
from trade_contracts import CutOff


def test_case_16_cutoff_passed_asks_with_alternatives():
    q = make_quote(closing_time=NOW - timedelta(hours=1))
    d = order_with([candidate("ALT1")], order_quote=q)
    check(d, ASK, "CUTOFF_PASSED")
    assert [a.product_id for a in d.alternatives] == ["ALT1"]


def test_case_16_does_not_trust_the_passed_flag():
    q = make_quote(cut_off=CutOff(closing_time=NOW - timedelta(hours=1), passed=False))
    check(run(quotes=[q]), ASK, "CUTOFF_PASSED")


@pytest.mark.parametrize(
    ("closing", "expect_ask"),
    [
        (NOW, True),
        (NOW - timedelta(minutes=1), True),
        (NOW + timedelta(minutes=1), False),
        (NOW.astimezone(UTC), True),
        ((NOW + timedelta(minutes=1)).astimezone(UTC), False),
        (datetime(2026, 11, 14, 8, 59, tzinfo=HELSINKI), True),
    ],
    ids=[
        "case-17-equal",
        "case-17-minute-before",
        "case-17-minute-after",
        "case-17-equal-utc",
        "case-17-minute-after-utc",
        "case-17-helsinki-0859",
    ],
)
def test_case_17_cutoff_boundary(closing, expect_ask):
    q = make_quote(cut_off=CutOff(closing_time=closing, passed=False))
    d = run(quotes=[q])
    assert ("CUTOFF_PASSED" in codes(d)) is expect_ask
    assert d.outcome.value == (ASK if expect_ask else AUTO)


def test_case_19_no_note_when_valio_date_matches_the_request():
    d = run()  # available_date == needed_by: the date was honoured, so no note
    check(d, AUTO)
    assert "DATE_NOT_HONOURED" not in codes(d)


def test_case_19_info_note_when_valio_date_differs_but_is_not_later():
    d = run(
        quotes=[make_quote(available_date=date(2026, 11, 15))],  # a day EARLIER than needed_by
        request=make_request(needed_by=date(2026, 11, 16)),
    )
    check(d, AUTO, "DATE_NOT_HONOURED")
    assert reason(d, "DATE_NOT_HONOURED").severity.value == "INFO"


def test_case_19_available_later_than_needed_by_asks():
    d = run(
        quotes=[make_quote(available_date=date(2026, 11, 16))],
        request=make_request(needed_by=date(2026, 11, 15)),
    )
    check(d, ASK, "DATE_NOT_HONOURED")


def test_case_20_undeliverable_asks_with_alternatives():
    q = make_quote(availability="unavailable", stock=None)
    d = order_with([candidate("ALT1")], order_quote=q)
    check(d, ASK, "UNDELIVERABLE")
    assert d.alternatives


@pytest.mark.parametrize(
    ("reliability", "qty", "outcome", "code"),
    [
        (None, 100, AUTO, None),
        (None, 200, ASK, "LOW_RELIABILITY"),
        (0.79, 100, ASK, "LOW_RELIABILITY"),
        (0.8, 100, AUTO, None),
    ],
    ids=[
        "case-21-missing-cheap",
        "case-21-missing-above-200",
        "case-21-score-0.79",
        "case-21-score-0.80",
    ],
)
def test_case_21_reliability(reliability, qty, outcome, code):
    d = run(lines=[make_line(quantity=qty)], facts=[make_facts(reliability=reliability)])
    check(d, outcome, *([code] if code else []))
    if code is None:
        assert "LOW_RELIABILITY" not in codes(d)


def test_case_22_stale_quote_asks():
    q = make_quote(fetched_at=NOW - timedelta(hours=2))
    check(run(quotes=[q]), ASK, "QUOTE_STALE")


@pytest.mark.parametrize(
    "price", [None, 0, -5], ids=["case-24-none", "case-24-zero", "case-24-negative"]
)
def test_case_24_price_missing_asks(price):
    check(run(quotes=[make_quote(price_cents=price)]), ASK, "PRICE_MISSING")


@pytest.mark.parametrize(
    ("expected", "quoted", "changed"),
    [(140, 140, False), (140, 144, False), (140, 147, False), (140, 150, True), (200, 140, True)],
    ids=["same", "within-3pct", "exactly-5pct", "case-23-rose-7pct", "case-23-dropped-30pct"],
)
def test_case_23_price_change_tolerance(expected, quoted, changed):
    d = run(
        lines=[make_line(expected_unit_price_cents=expected)],
        quotes=[make_quote(price_cents=quoted)],
    )
    assert ("PRICE_CHANGED" in codes(d)) is changed
    assert d.outcome.value == (ASK if changed else AUTO)


def test_case_25_unknown_product_declines():
    d = run(lines=[make_line("999000")], quotes=[], facts=[])
    check(d, DECLINE, "UNKNOWN_PRODUCT")


def test_case_25_unknown_product_still_carries_alternatives():
    q, f = candidate("ALT1")
    d = run(lines=[make_line("999000")], quotes=[q], facts=[f])
    check(d, DECLINE, "UNKNOWN_PRODUCT")
    assert [a.product_id for a in d.alternatives] == ["ALT1"]
