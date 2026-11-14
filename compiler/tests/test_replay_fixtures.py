"""Compile the fixture sentences through the real wrapper in REPLAY mode (no network, no key)."""

import pytest
from builders import FIXTURES, SENTENCES
from trade_contracts.common import PreferenceScope, RuleKind, UncertaintyPolicy

from trade_compiler import GeminiLLM, LLMMode, compile_mandate


@pytest.fixture
def llm():
    return GeminiLLM(mode=LLMMode.REPLAY, cache_dir=FIXTURES)


def run(llm, name):
    return compile_mandate(SENTENCES[name], PreferenceScope.ALWAYS, llm=llm)


def test_replay_allergens(llm):
    res = run(llm, "allergens")
    assert not res.used_fallback
    values = [r.value for r in res.mandate.hard_rules if r.kind == RuleKind.EXCLUDED_ALLERGEN]
    assert values == ["peanut", "gluten"]


def test_replay_limit(llm):
    res = run(llm, "limit")
    (rule,) = res.mandate.hard_rules
    assert rule.kind == RuleKind.AUTO_APPROVE_LIMIT_CENTS and rule.value == 50000
    assert res.loosened == ()


def test_replay_finnish(llm):
    res = run(llm, "finnish")
    assert res.mandate.hard_rules == [] and res.mandate.guidance and res.open_questions


def test_replay_ask(llm):
    res = run(llm, "ask")
    assert res.mandate.uncertainty_policy == UncertaintyPolicy.ASK and not res.mandate.hard_rules


def test_replay_ambiguous(llm):
    res = run(llm, "ambiguous")
    assert res.mandate.hard_rules == [] and res.open_questions


def test_replay_injection(llm):
    res = run(llm, "injection")
    assert res.injection_flagged and res.mandate.hard_rules == []
    assert res.mandate.uncertainty_policy == UncertaintyPolicy.ASK and res.loosened == ()
