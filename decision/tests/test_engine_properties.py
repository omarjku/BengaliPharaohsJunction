"""Engine properties: determinism, fail-closed, confidence (D26), no input mutation."""

import copy

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
from helpers_b import ASK, AUTO, DECLINE, check
from trade_contracts import Decision

from trade_decision import decide


def test_case_54_same_inputs_equal_decision():
    a, b = run(), run()
    assert a == b and a.model_dump_json() == b.model_dump_json()


def test_case_54_determinism_with_violations():
    kw = {"lines": [make_line(quantity=1000)], "quotes": [make_quote(stock=51)]}
    assert run(**kw) == run(**kw)


def test_fail_closed_lines_none():
    d = decide(make_request(), make_mandate(), None, [], [], now=NOW)  # type: ignore[arg-type]
    check(d, ASK, "ENGINE_ERROR")


def test_fail_closed_request_none():
    d = decide(None, make_mandate(), [make_line()], [make_quote()], [make_facts()], now=NOW)  # type: ignore[arg-type]
    check(d, ASK, "ENGINE_ERROR")
    assert d.outcome.value != AUTO


def test_fail_closed_garbage_quotes():
    d = decide(make_request(), make_mandate(), [make_line()], [object()], [object()], now=NOW)  # type: ignore[list-item]
    assert d.outcome.value != AUTO


def test_d26_confidence_none_leaves_auto():
    check(run(confidence=None), AUTO)


@pytest.mark.parametrize("conf", [0.99, 0.8, 1.0], ids=["high", "at-threshold", "one"])
def test_d26_confident_auto_stays_auto(conf):
    d = run(confidence=conf)
    check(d, AUTO)
    assert d.confidence == conf


@pytest.mark.parametrize("conf", [0.79, 0.5, 0.0], ids=["just-below", "half", "zero"])
def test_d26_low_confidence_downgrades_auto(conf):
    d = run(confidence=conf)
    check(d, ASK, "LOW_CONFIDENCE")
    assert d.confidence == conf


def test_d26_high_confidence_never_upgrades_ask():
    d = run(lines=[make_line(quantity=1000)], quotes=[make_quote(price_cents=10, stock=51)],
            confidence=1.0)
    check(d, ASK, "STOCK_PARTIAL")


def test_d26_high_confidence_never_upgrades_decline():
    d = run(mandate=make_mandate(blocklist=("463335",)), confidence=1.0)
    check(d, DECLINE, "BLOCKLISTED")


def test_d26_low_confidence_never_softens_decline():
    d = run(mandate=make_mandate(blocklist=("463335",)), confidence=0.1)
    check(d, DECLINE, "BLOCKLISTED")


def test_decide_does_not_mutate_inputs():
    request, mandate = make_request(), make_mandate(excluded_allergens=("gluten",))
    lines = [make_line(quantity=200), make_line(quantity=300)]
    quotes, facts = [make_quote()], [make_facts()]
    before = copy.deepcopy((request, mandate, lines, quotes, facts))
    run(lines=lines, quotes=quotes, facts=facts, mandate=mandate, request=request)
    assert (request, mandate, lines, quotes, facts) == before


def test_returns_valid_decision_with_version_and_clock():
    d = run()
    assert isinstance(d, Decision) and d.rules_version and d.decided_at == NOW
    assert d.request_id == "req-1"
    assert "ENGINE_ERROR" not in codes(d)
