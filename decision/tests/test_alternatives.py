"""Alternatives (D21): filter, rank, cap at 3, labels, and the "none found" message."""

from datetime import timedelta

import pytest
from builders import NOW, make_mandate, make_quote
from helpers_b import ASK, candidate, check, order_with, reason

OUT_OF_STOCK = make_quote(stock=0)
GLUTEN = make_mandate(excluded_allergens=("gluten",))


def _alt_ids(d):
    return [a.product_id for a in d.alternatives]


def test_max_three_alternatives():
    cands = [candidate(f"ALT{i}", price=100 + i) for i in range(5)]
    d = order_with(cands, order_quote=OUT_OF_STOCK)
    check(d, ASK, "STOCK_NONE")
    assert len(d.alternatives) == 3


def test_allergen_unsafe_candidate_filtered_out():
    bad = candidate("BAD", allergens={"gluten": "CONTAINS"})
    good = candidate("GOOD", allergens={"gluten": "FREE_FROM"})
    d = order_with([bad, good], order_quote=OUT_OF_STOCK, mandate=GLUTEN)
    assert _alt_ids(d) == ["GOOD"]


def test_cutoff_passed_candidate_filtered_out():
    late = candidate("LATE", closing_time=NOW - timedelta(hours=1))
    good = candidate("GOOD")
    d = order_with([late, good], order_quote=OUT_OF_STOCK)
    assert _alt_ids(d) == ["GOOD"]


def test_insufficient_stock_candidate_filtered_out():
    small = candidate("SMALL", stock=10)
    good = candidate("GOOD")
    d = order_with([small, good], order_quote=OUT_OF_STOCK)
    assert _alt_ids(d) == ["GOOD"]


def test_unknown_quantity_candidate_filtered_out():
    d = order_with([candidate("UNK", stock=None), candidate("GOOD")], order_quote=OUT_OF_STOCK)
    assert _alt_ids(d) == ["GOOD"]


def test_ranked_by_reliability_then_price():
    cands = [
        candidate("A", price=200, reliability=0.99),
        candidate("B", price=100, reliability=0.90),
        candidate("C", price=150, reliability=0.99),
    ]
    d = order_with(cands, order_quote=OUT_OF_STOCK)
    assert _alt_ids(d) == ["C", "A", "B"]


def test_summary_labels_best_match_and_cheaper():
    cands = [candidate("A", price=150, reliability=0.99), candidate("B", price=100, reliability=0.9)]
    d = order_with(cands, order_quote=OUT_OF_STOCK)
    assert d.alternatives
    assert "Best match" in d.alternatives[0].summary
    assert any("Cheaper" in a.summary for a in d.alternatives)


@pytest.mark.parametrize(
    "pool",
    [
        [],
        [candidate("BAD", allergens={"gluten": "CONTAINS"})],
        [candidate("SMALL", stock=10)],
    ],
    ids=["no-candidates", "all-allergen-unsafe", "all-too-small"],
)
def test_none_safe_gives_no_alternatives_and_says_so(pool):
    d = order_with(pool, order_quote=OUT_OF_STOCK, mandate=GLUTEN)
    check(d, ASK, "STOCK_NONE")
    assert d.alternatives == []
    assert "No safe alternative found" in (reason(d, "STOCK_NONE").suggested_fix or "")


@pytest.mark.skip(reason="needs origin field in ProductFacts")
def test_local_label_for_finnish_origin():
    raise AssertionError
