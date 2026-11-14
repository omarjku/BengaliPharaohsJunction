"""Skeleton smoke tests only (not the store or the context)."""

import pytest
from builders import NOW
from pydantic import ValidationError
from trade_contracts.common import PreferenceScope

from trade_profile import ONBOARDING_QUESTIONS, Memory, MemoryKind, MemorySource, log_path
from trade_profile import models as models_module
from trade_profile.store import memory_id_for


def _memory(**kw):
    base = {"id": "m1", "buyer_id": "b", "kind": MemoryKind.ALLERGEN_AVOID, "key": "wheat",
            "text": "No wheat", "scope": PreferenceScope.THIS_ORDER,
            "source": MemorySource.ANSWERED_QUESTION, "created_at": NOW, "order_id": "ord-1"}  # fmt: skip
    return Memory(**{**base, **kw})


def test_this_order_memory_needs_an_order_and_always_must_not_have_one():
    assert _memory().order_id == "ord-1"
    with pytest.raises(ValidationError):
        _memory(order_id=None)
    with pytest.raises(ValidationError):
        _memory(scope=PreferenceScope.ALWAYS)  # always + order_id
    assert _memory(scope=PreferenceScope.ALWAYS, order_id=None).scope == "always"


def test_memory_id_is_deterministic_and_content_based():
    args = ("b", MemoryKind.ALLERGEN_AVOID, "wheat", {"name": "wheat"}, PreferenceScope.ALWAYS, None)
    assert memory_id_for(*args) == memory_id_for(*args)
    other = ("b", MemoryKind.ALLERGEN_AVOID, "milk", {"name": "wheat"}, PreferenceScope.ALWAYS, None)
    assert memory_id_for(*args) != memory_id_for(*other)


@pytest.mark.parametrize("bad", ["../evil", "a/b", "..", "", "x\\y", "C:\\boot"])
def test_log_path_never_escapes_the_root(tmp_path, bad):
    path = log_path(tmp_path, bad)
    assert path.parent == tmp_path and path.suffix == ".jsonl"
    assert ".." not in path.name or path.name.startswith("b_")


def test_five_onboarding_questions():
    assert len(ONBOARDING_QUESTIONS) == 5
    assert {q.kind for q in ONBOARDING_QUESTIONS} >= {MemoryKind.ALLERGEN_AVOID}


def test_models_module_never_builds_hard_rules():
    # the profile package must not even import the rule types
    assert not hasattr(models_module, "HardRule") and not hasattr(models_module, "Mandate")
