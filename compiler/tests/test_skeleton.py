"""Skeleton smoke tests only (not the wrapper or the compiler): keys, cache helpers, secrets."""

import pytest
from builders import FakeLLM, write_fixture

from trade_compiler.llm import (
    DEFAULT_MODELS,
    KEY_ENV,
    LLMMode,
    cache_key,
    key_status,
    mode_from_env,
    read_cache,
)
from trade_compiler.schema import CompilerOutput

SCHEMA = {"type": "object"}


def test_cache_key_is_stable_and_depends_on_every_part():
    base = cache_key("p", SCHEMA, "m")
    assert base == cache_key("p", SCHEMA, "m")
    assert len({base, cache_key("p2", SCHEMA, "m"), cache_key("p", {"a": 1}, "m"),
                cache_key("p", SCHEMA, "m2")}) == 4


def test_write_fixture_round_trips_under_the_lookup_key(tmp_path):
    write_fixture(tmp_path, "p", SCHEMA, "m", {"ok": True})
    entry = read_cache(tmp_path, cache_key("p", SCHEMA, "m"))
    assert entry["response"] == {"ok": True} and entry["synthetic"] is True
    assert read_cache(tmp_path, cache_key("other", SCHEMA, "m")) is None


def test_fake_llm_returns_then_raises_in_order():
    fake = FakeLLM({"a": 1}, RuntimeError("boom"))
    assert fake.generate_structured("p", SCHEMA, "m") == {"a": 1}
    with pytest.raises(RuntimeError):
        fake.generate_structured("p", SCHEMA, "m")
    assert len(fake.calls) == 2


def test_key_status_never_shows_the_value(monkeypatch):
    monkeypatch.setenv(KEY_ENV, "super-secret-value")
    shown = key_status()
    assert shown == "GEMINI_API_KEY: present (length 18)" and "secret" not in shown
    monkeypatch.delenv(KEY_ENV)
    assert key_status() == "GEMINI_API_KEY: missing"


def test_mode_from_env(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "Replay")
    assert mode_from_env() is LLMMode.REPLAY
    monkeypatch.delenv("LLM_MODE")
    assert mode_from_env() is LLMMode.LIVE


def test_defaults_and_compiler_output_schema_are_usable():
    assert DEFAULT_MODELS
    schema = CompilerOutput.model_json_schema()
    assert "excluded_allergens" in schema["properties"]
    assert CompilerOutput().excluded_allergens == []
