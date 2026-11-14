"""Mandate and allergen rows (cases 34, 37-41, D12, D15, D16, D17 ordering)."""

from datetime import timedelta

import pytest
from builders import NOW, codes, make_facts, make_line, make_mandate, make_quote, run
from helpers_b import ASK, AUTO, DECLINE, check, reason

GLUTEN = {"excluded_allergens": ("gluten",)}


def _facts(gluten):
    allergens = {"peanut": "FREE_FROM", "tree nuts": "FREE_FROM"}
    if gluten is not None:
        allergens["gluten"] = gluten
    return make_facts(allergens=allergens)


@pytest.mark.parametrize(
    ("status", "outcome", "code"),
    [
        ("CONTAINS", DECLINE, "ALLERGEN_CONTAINS"),
        ("MAY_CONTAIN", ASK, "ALLERGEN_MAY_CONTAIN"),
        (None, ASK, "ALLERGEN_DATA_MISSING"),
        ("FREE_FROM", AUTO, None),
    ],
    ids=["case-34-contains", "case-34-may-contain", "case-34-missing", "case-34-free-from"],
)
def test_case_34_gluten_rule(status, outcome, code):
    d = run(facts=[_facts(status)], mandate=make_mandate(**GLUTEN))
    check(d, outcome, *([code] if code else []))


def test_allergen_not_excluded_is_ignored():
    d = run(facts=[_facts("CONTAINS")], mandate=make_mandate())
    check(d, AUTO)


def test_case_39_category_missing_asks():
    d = run(facts=[make_facts(category=None)], mandate=make_mandate(**GLUTEN))
    check(d, ASK, "DATA_MISSING")


def test_case_40_approve_policy_never_loosens_allergen():
    m = make_mandate(uncertainty_policy="approve", **GLUTEN)
    d = run(facts=[_facts("MAY_CONTAIN")], mandate=m)
    check(d, ASK, "ALLERGEN_MAY_CONTAIN")


def test_case_41_decline_policy_on_missing_allergen_data():
    m = make_mandate(uncertainty_policy="decline", **GLUTEN)
    check(run(facts=[_facts(None)], mandate=m), DECLINE, "POLICY_DECLINE_UNKNOWN")


def test_blocklisted_product_declines():
    check(run(mandate=make_mandate(blocklist=("463335",))), DECLINE, "BLOCKLISTED")


def test_other_product_blocklisted_does_not_matter():
    check(run(mandate=make_mandate(blocklist=("111",))), AUTO)


def test_d16_missing_mandate_asks_never_auto():
    check(run(mandate=None), ASK, "MANDATE_MISSING")


def test_d16_expired_mandate_asks():
    m = make_mandate(expires_at=NOW - timedelta(seconds=1))
    check(run(mandate=m), ASK, "MANDATE_EXPIRED")


def test_mandate_not_yet_expired_is_fine():
    check(run(mandate=make_mandate(expires_at=NOW + timedelta(days=1))), AUTO)


def test_d15_empty_mandate_applies_defaults_info_only():
    d = run(mandate=make_mandate(limit_cents=None))
    check(d, AUTO, "DEFAULT_MANDATE_APPLIED")
    assert reason(d, "DEFAULT_MANDATE_APPLIED").severity.value == "INFO"


def test_d15_empty_mandate_still_enforces_500_limit():
    d = run(
        lines=[make_line(quantity=1)],
        quotes=[make_quote(price_cents=60000)],
        mandate=make_mandate(limit_cents=None, per_line_cap_cents=100000),
    )
    check(d, ASK, "SPEND_OVER_LIMIT", "DEFAULT_MANDATE_APPLIED")


def test_d15_empty_mandate_still_checks_cutoff():
    q = make_quote(closing_time=NOW - timedelta(hours=1))
    d = run(quotes=[q], mandate=make_mandate(limit_cents=None))
    check(d, ASK, "CUTOFF_PASSED", "DEFAULT_MANDATE_APPLIED")


def test_cases_37_allergen_contains_and_cutoff_passed_list_both():
    q = make_quote(closing_time=NOW - timedelta(hours=1))
    d = run(quotes=[q], facts=[_facts("CONTAINS")], mandate=make_mandate(**GLUTEN))
    check(d, DECLINE, "ALLERGEN_CONTAINS", "CUTOFF_PASSED")
    assert codes(d).index("ALLERGEN_CONTAINS") < codes(d).index("CUTOFF_PASSED")


def test_case_38_three_rules_broken_all_listed():
    q = make_quote(closing_time=NOW - timedelta(hours=1))
    d = run(
        quotes=[q],
        facts=[_facts("CONTAINS")],
        mandate=make_mandate(blocklist=("463335",), **GLUTEN),
    )
    check(d, DECLINE, "ALLERGEN_CONTAINS", "BLOCKLISTED", "CUTOFF_PASSED")
    assert codes(d).index("CUTOFF_PASSED") == len(codes(d)) - 1 or "INFO" in {
        r.severity.value for r in d.reasons
    }


def test_d17_primary_reason_is_first_and_severity_sorted():
    q = make_quote(closing_time=NOW - timedelta(hours=1), price_cents=None)
    d = run(quotes=[q], facts=[_facts("CONTAINS")], mandate=make_mandate(**GLUTEN))
    assert d.primary_reason == d.reasons[0]
    ranks = {"DECLINE": 0, "ASK_HUMAN": 1, "INFO": 2}
    order = [ranks[r.severity.value] for r in d.reasons]
    assert order == sorted(order)


def test_d17_same_code_sorted_by_product_id():
    lines = [make_line("B2", 10), make_line("A1", 10)]
    closed = NOW - timedelta(hours=1)
    quotes = [make_quote(p, closing_time=closed) for p in ("B2", "A1")]
    d = run(lines=lines, quotes=quotes)
    cutoffs = [r.product_id for r in d.reasons if r.code.value == "CUTOFF_PASSED"]
    assert cutoffs == ["A1", "B2"]
