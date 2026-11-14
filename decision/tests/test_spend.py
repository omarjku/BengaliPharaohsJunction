"""Spend rows (cases 27-29, line cap, weekly budget case 32)."""

import pytest
from builders import codes, make_line, make_mandate, make_quote, run
from helpers_b import ASK, AUTO, check, reason

BIG_CAP = make_mandate(per_line_cap_cents=100000)


@pytest.mark.parametrize(
    ("price", "outcome"),
    [(50000, AUTO), (50001, ASK)],
    ids=["case-27-exactly-500.00", "case-27-500.01"],
)
def test_case_27_limit_boundary(price, outcome):
    d = run(lines=[make_line(quantity=1)], quotes=[make_quote(price_cents=price)], mandate=BIG_CAP)
    check(d, outcome, *(["SPEND_OVER_LIMIT"] if outcome == ASK else []))
    if outcome == ASK:
        assert reason(d, "SPEND_OVER_LIMIT").facts["total_cents"] == 50001
    else:
        assert "SPEND_OVER_LIMIT" not in codes(d)


def test_case_28_each_line_under_cap_sum_over_limit():
    lines = [make_line("P1", 290), make_line("P2", 290)]
    quotes = [make_quote(p, price_cents=100) for p in ("P1", "P2")]
    d = run(lines=lines, quotes=quotes)
    check(d, ASK, "SPEND_OVER_LIMIT")
    assert "LINE_OVER_CAP" not in codes(d)
    assert reason(d, "SPEND_OVER_LIMIT").facts["total_cents"] == 58000


def test_case_29_over_limit_facts():
    d = run(lines=[make_line(quantity=1000)], mandate=BIG_CAP)
    r = reason(d, "SPEND_OVER_LIMIT")
    assert r.facts["total_cents"] == 140000 and r.facts["limit_cents"] == 50000


def test_line_over_cap_only():
    d = run(lines=[make_line(quantity=310)], quotes=[make_quote(price_cents=100)])
    check(d, ASK, "LINE_OVER_CAP")
    assert "SPEND_OVER_LIMIT" not in codes(d)


def test_mandate_limit_overrides_default():
    d = run(mandate=make_mandate(limit_cents=10000))
    check(d, ASK, "SPEND_OVER_LIMIT")
    assert reason(d, "SPEND_OVER_LIMIT").facts["limit_cents"] == 10000


def _weekly(recent, **mandate_kw):
    return run(
        lines=[make_line(quantity=100)],
        quotes=[make_quote(price_cents=200)],
        mandate=make_mandate(**mandate_kw),
        recent_spend_cents=recent,
    )


def test_case_32_weekly_budget_exceeded():
    d = _weekly(90000, weekly_budget_cents=100000)
    check(d, ASK, "WEEKLY_BUDGET_EXCEEDED")
    values = reason(d, "WEEKLY_BUDGET_EXCEEDED").facts.values()
    assert 110000 in values and 100000 in values


def test_case_32_exactly_at_budget_is_allowed():
    check(_weekly(80000, weekly_budget_cents=100000), AUTO)


def test_case_32_no_budget_means_no_weekly_check():
    d = _weekly(900000)
    assert "WEEKLY_BUDGET_EXCEEDED" not in codes(d)
    check(d, AUTO)
