"""The 6 golden fixtures that sell the demo (T06 doc, section D)."""

from datetime import datetime

from builders import HELSINKI, NOW, make_facts, make_line, make_mandate, make_quote, run
from helpers_b import ASK, AUTO, DECLINE, candidate, check, order_with, reason
from trade_contracts import QuantityInfo


def test_463335_over_spend_limit():
    d = run(lines=[make_line(quantity=1000)], mandate=make_mandate(per_line_cap_cents=200000))
    check(d, ASK, "SPEND_OVER_LIMIT")
    r = reason(d, "SPEND_OVER_LIMIT")
    assert r.facts["total_cents"] == 140000 and r.facts["limit_cents"] == 50000


def test_463038_cutoff_passed_unknown_qty():
    closed = datetime(2026, 11, 12, 15, 0, tzinfo=HELSINKI)
    quote = make_quote("463038", closing_time=closed, stock=None)
    d = order_with([candidate("ALT1")], line=make_line("463038"), order_quote=quote)
    check(d, ASK, "CUTOFF_PASSED")
    assert d.alternatives


def test_terminal_999999_unknown_flag():
    check(run(quotes=[make_quote(stock=None)]), ASK, "QTY_UNKNOWN")


def test_terminal_999999_known_value():
    q = make_quote(quantity=QuantityInfo(known=True, value=999999))
    check(run(quotes=[q]), ASK, "QTY_UNKNOWN")


def test_51_of_1000_partial_stock():
    d = run(lines=[make_line(quantity=1000)], quotes=[make_quote(price_cents=10, stock=51)])
    check(d, ASK, "STOCK_PARTIAL")
    r = reason(d, "STOCK_PARTIAL")
    assert r.facts["available"] == 51 and r.facts["requested"] == 1000


def test_allergen_contains_declines():
    facts = make_facts(allergens={"gluten": "CONTAINS", "peanut": "FREE_FROM"})
    d = run(facts=[facts], mandate=make_mandate(excluded_allergens=("gluten",)))
    check(d, DECLINE, "ALLERGEN_CONTAINS")


def test_clean_order_is_auto():
    d = run()
    check(d, AUTO)
    assert all(r.severity.value == "INFO" for r in d.reasons)
    assert d.decided_at == NOW
