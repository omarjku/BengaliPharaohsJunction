"""LLM_DEBUG shows a short, key-redacted backend message; off by default nothing leaks."""

import pytest

from trade_compiler.llm import KEY_ENV, GeminiLLM, LLMError, LLMMode

SCHEMA = {"type": "object"}


def _failing_llm(tmp_path):
    def backend(prompt, schema, model):
        raise RuntimeError("bad request key=SECRETKEY123 and more detail")

    return GeminiLLM(
        LLMMode.LIVE,
        cache_dir=tmp_path,
        models=("m1",),
        backend=backend,
        sleep=lambda s: None,
    )


def test_debug_off_shows_only_the_class_name(tmp_path, monkeypatch):
    monkeypatch.setenv(KEY_ENV, "SECRETKEY123")
    monkeypatch.delenv("LLM_DEBUG", raising=False)
    with pytest.raises(LLMError) as err:
        _failing_llm(tmp_path).generate_structured("p", SCHEMA)
    assert "RuntimeError" in str(err.value)
    assert "bad request" not in str(err.value) and "SECRETKEY123" not in str(err.value)


def test_debug_on_shows_the_message_with_the_key_redacted(tmp_path, monkeypatch):
    monkeypatch.setenv(KEY_ENV, "SECRETKEY123")
    monkeypatch.setenv("LLM_DEBUG", "1")
    with pytest.raises(LLMError) as err:
        _failing_llm(tmp_path).generate_structured("p", SCHEMA)
    text = str(err.value)
    assert "bad request" in text and "[redacted]" in text and "SECRETKEY123" not in text


def test_debug_redacts_google_shaped_keys_even_if_not_the_env_key(tmp_path, monkeypatch):
    monkeypatch.setenv(KEY_ENV, "something-else")
    monkeypatch.setenv("LLM_DEBUG", "1")

    def backend(prompt, schema, model):
        raise RuntimeError("url ?key=AIzaSyA1234567890abcdefghijklmnopqrstu failed")

    llm = GeminiLLM(
        LLMMode.LIVE, cache_dir=tmp_path, models=("m1",), backend=backend, sleep=lambda s: None
    )
    with pytest.raises(LLMError) as err:
        llm.generate_structured("p", SCHEMA)
    assert "AIza" not in str(err.value) and "[redacted]" in str(err.value)
