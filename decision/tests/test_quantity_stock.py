"""Quantity, stock and unit rows (cases 1-8, 12, 13, 15, 30)."""

import pytest
from builders import codes, make_facts, make_line, make_mandate, make_quote, run
from helpers_b import ASK, AUTO, DECLINE, candidate, check, order_with, reason
from trade_contracts import QuantityInfo

CHEAP = {"price_cents": 10}


@pytest.mark.parametrize(
    "qty",
    [0, -5, float("nan"), None],
    ids=["case-01-zero", "case-01-negative", "case-01-nan", "case-01-null"],
)
def test_invalid_quantity_declines(qty):
    check(run(lines=[make_line(quantity=qty)]), DECLINE, "QTY_INVALID")


def test_case_01_empty_order_declines():
    check(run(lines=[], quotes=[], facts=[]), DECLINE, "QTY_INVALID")


@pytest.mark.parametrize("qty", [999999, 1e9], ids=["case-03-999999", "case-03-1e9"])
def test_case_03_absurd_request_asks(qty):
    d = run(lines=[make_line(quantity=qty)], quotes=[make_quote(price_cents=1, stock=None)])
    check(d, ASK, "QTY_SUSPICIOUS")


def test_case_15_huge_qty_near_zero_price_asks():
    d = run(lines=[make_line(quantity=500000)], quotes=[make_quote(price_cents=1, stock=None)])
    assert d.outcome.value == ASK


def test_case_04_stock_equals_request_is_auto():
    d = run(lines=[make_line(quantity=1000)], quotes=[make_quote(stock=1000, **CHEAP)])
    check(d, AUTO)


def test_case_05_stock_one_short_asks():
    d = run(lines=[make_line(quantity=1000)], quotes=[make_quote(stock=999, **CHEAP)])
    check(d, ASK, "STOCK_PARTIAL")
    r = reason(d, "STOCK_PARTIAL")
    assert r.facts["available"] == 999 and r.facts["requested"] == 1000


def test_case_06_partial_even_at_99_percent_asks():
    d = run(lines=[make_line(quantity=1000)], quotes=[make_quote(stock=990, **CHEAP)])
    check(d, ASK, "STOCK_PARTIAL")


@pytest.mark.parametrize("with_alternative", [True, False], ids=["case-07-alts", "case-07-none"])
def test_case_07_zero_stock_asks_never_silent(with_alternative):
    cands = [candidate("ALT1")] if with_alternative else []
    d = order_with(cands, order_quote=make_quote(stock=0))
    check(d, ASK, "STOCK_NONE")
    assert bool(d.alternatives) is with_alternative
    if not with_alternative:
        assert "No safe alternative found" in (reason(d, "STOCK_NONE").suggested_fix or "")


def test_case_08_terminal_sentinel_small_request():
    d = run(lines=[make_line(quantity=10)], quotes=[make_quote(stock=None)])
    check(d, ASK, "QTY_UNKNOWN")


def test_case_08_known_999999_small_request():
    q = make_quote(quantity=QuantityInfo(known=True, value=999999))
    check(run(lines=[make_line(quantity=10)], quotes=[q]), ASK, "QTY_UNKNOWN")


def test_case_08_only_the_exact_placeholder_999999_is_unknown():
    # T06.1 (real Valio data): Eila reports 9,999,999,999 as plenty; only 999999 means unknown.
    placeholder = make_quote(quantity=QuantityInfo(known=True, value=999999))
    check(run(quotes=[placeholder]), ASK, "QTY_UNKNOWN")
    plenty = make_quote(quantity=QuantityInfo(known=True, value=100000))
    assert "QTY_UNKNOWN" not in codes(run(quotes=[plenty]))


def test_case_12_unit_mismatch_l_vs_kg():
    d = run(
        lines=[make_line(unit="L")],
        facts=[make_facts(sales_unit="1 kg bag")],
        quotes=[make_quote(unit="1 kg bag")],
    )
    check(d, ASK, "UNIT_MISMATCH")


def test_case_12_same_unit_family_is_clean():
    check(run(lines=[make_line(unit="L")]), AUTO)


def test_case_13_below_minimum_order_asks():
    d = run(lines=[make_line(quantity=10)], facts=[make_facts(min_order_qty=24)])
    assert d.outcome.value == ASK


def test_case_30_duplicate_lines_merged_before_stock_check():
    lines = [make_line(quantity=200), make_line(quantity=300)]
    d = run(lines=lines, quotes=[make_quote(stock=400, **CHEAP)], facts=[make_facts()])
    check(d, ASK, "STOCK_PARTIAL")
    r = reason(d, "STOCK_PARTIAL")
    assert r.facts["requested"] == 500 and r.facts["available"] == 400


def test_case_30_duplicate_lines_merged_before_total_check():
    lines = [make_line(quantity=200), make_line(quantity=300)]
    d = run(
        lines=lines,
        quotes=[make_quote(price_cents=101)],
        facts=[make_facts()],
        mandate=make_mandate(per_line_cap_cents=60000),
    )
    check(d, ASK, "SPEND_OVER_LIMIT")
    assert reason(d, "SPEND_OVER_LIMIT").facts["total_cents"] == 50500


def test_case_30_merged_under_limit_is_auto():
    lines = [make_line(quantity=200), make_line(quantity=300)]
    d = run(
        lines=lines,
        quotes=[make_quote(price_cents=100)],
        facts=[make_facts()],
        mandate=make_mandate(per_line_cap_cents=60000),
    )
    check(d, AUTO)
