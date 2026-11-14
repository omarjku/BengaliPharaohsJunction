import os
import subprocess
import sys

import pytest
from helpers_a import ScriptedBackend, Sleeps, forbidden_backend

from trade_compiler.llm import (
    GeminiLLM,
    LLMError,
    LLMMode,
    RateLimited,
    ReplayMiss,
    cache_key,
    load_env_file,
    read_cache,
    write_cache,
)

S = {"type": "object"}


def make(tmp_path, mode, backend, models=("m1",), **kw):
    return GeminiLLM(mode, cache_dir=tmp_path, models=models, backend=backend, **kw)


def seed(tmp_path, prompt, model, response, synthetic=True):
    k = cache_key(prompt, S, model)
    write_cache(tmp_path, k, {"key": k, "model": model, "prompt": prompt,
                              "response": response, "synthetic": synthetic})


def test_replay_hit_never_calls_backend(tmp_path):
    seed(tmp_path, "p", "m1", {"a": 1})
    assert make(tmp_path, LLMMode.REPLAY, forbidden_backend).generate_structured("p", S) == {"a": 1}


def test_replay_miss_raises_and_hides_prompt(tmp_path):
    llm = make(tmp_path, LLMMode.REPLAY, forbidden_backend, models=("m1", "m2"))
    with pytest.raises(ReplayMiss) as ei:
        llm.generate_structured("full confidential prompt text", S)
    text = str(ei.value)
    assert "replay miss" in text and "m1" in text and "m2" in text
    assert "confidential" not in text


def test_replay_falls_through_models_in_cache(tmp_path):
    seed(tmp_path, "p", "m2", {"b": 2})
    llm = make(tmp_path, LLMMode.REPLAY, forbidden_backend, models=("m1", "m2"))
    assert llm.generate_structured("p", S) == {"b": 2}


def test_live_miss_calls_once_then_cache(tmp_path):
    be = ScriptedBackend({"x": 1})
    llm = make(tmp_path, LLMMode.LIVE, be)
    assert llm.generate_structured("p", S) == {"x": 1}
    assert llm.generate_structured("p", S) == {"x": 1}
    assert len(be.calls) == 1
    entry = read_cache(tmp_path, cache_key("p", S, "m1"))
    assert entry["synthetic"] is False and entry["model"] == "m1"


def test_live_fallback_across_models_via_cache(tmp_path):
    be = ScriptedBackend(RuntimeError("model gone"), {"y": 2})
    llm = make(tmp_path, LLMMode.LIVE, be, models=("m1", "m2"))
    assert llm.generate_structured("p", S) == {"y": 2}
    assert [m for _, m in be.calls] == ["m1", "m2"]
    assert read_cache(tmp_path, cache_key("p", S, "m2")) is not None
    assert read_cache(tmp_path, cache_key("p", S, "m1")) is None
    again = make(tmp_path, LLMMode.LIVE, forbidden_backend, models=("m1", "m2"))
    assert again.generate_structured("p", S) == {"y": 2}


def test_record_always_calls_and_overwrites_synthetic(tmp_path):
    seed(tmp_path, "p", "m1", {"old": True}, synthetic=True)
    be = ScriptedBackend({"new": True})
    assert make(tmp_path, LLMMode.RECORD, be).generate_structured("p", S) == {"new": True}
    entry = read_cache(tmp_path, cache_key("p", S, "m1"))
    assert entry["response"] == {"new": True} and entry["synthetic"] is False
    assert len(be.calls) == 1


def test_429_retry_sleeps_1_2_4(tmp_path):
    sl = Sleeps()
    be = ScriptedBackend(RateLimited(), RateLimited(), RateLimited(), {"ok": 1})
    assert make(tmp_path, LLMMode.LIVE, be, sleep=sl).generate_structured("p", S) == {"ok": 1}
    assert sl.delays == [1, 2, 4] and len(be.calls) == 4


def test_retries_exhausted_then_next_model(tmp_path):
    sl = Sleeps()
    be = ScriptedBackend(RateLimited(), RateLimited(), RateLimited(), {"ok": 2})
    llm = make(tmp_path, LLMMode.LIVE, be, models=("m1", "m2"), sleep=sl, max_retries=2)
    assert llm.generate_structured("p", S) == {"ok": 2}
    assert sl.delays == [1, 2]
    assert [m for _, m in be.calls] == ["m1", "m1", "m1", "m2"]


def test_all_models_failing_raises_llm_error(tmp_path):
    be = ScriptedBackend(RuntimeError("a"), ValueError("b"))
    llm = make(tmp_path, LLMMode.LIVE, be, models=("m1", "m2"))
    with pytest.raises(LLMError):
        llm.generate_structured("p", S)


def test_non_dict_result_is_a_model_failure(tmp_path):
    be = ScriptedBackend(["not a dict"], {"ok": 3})
    llm = make(tmp_path, LLMMode.LIVE, be, models=("m1", "m2"))
    assert llm.generate_structured("p", S) == {"ok": 3}


def test_backend_error_text_never_leaks(tmp_path):
    class Boom(Exception):
        code = 500

    be = ScriptedBackend(Boom("key=SECRETKEY123"))
    with pytest.raises(LLMError) as ei:
        make(tmp_path, LLMMode.LIVE, be).generate_structured("p", S)
    assert "SECRETKEY123" not in str(ei.value) and "SECRETKEY123" not in repr(ei.value)
    assert "Boom" in str(ei.value) and "500" in str(ei.value)


def test_missing_key_message_has_no_value(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMError) as ei:
        make(tmp_path, LLMMode.LIVE, None).generate_structured("p", S)
    assert "GEMINI_API_KEY is not set" in str(ei.value)


def test_mode_from_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MODE", "replay")
    assert GeminiLLM(cache_dir=tmp_path).mode is LLMMode.REPLAY


def test_load_env_file(tmp_path, monkeypatch):
    for n in ("TEST_ONLY_VAR", "TEST_ONLY_Q", "TEST_ONLY_EXP"):
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setenv("TEST_ONLY_SET", "keep")
    f = tmp_path / ".env"
    f.write_text(
        "# comment\n\nTEST_ONLY_VAR=plain\nTEST_ONLY_Q=\"quoted val\"\n"
        "export TEST_ONLY_EXP='x y'\nTEST_ONLY_SET=override\n",
        encoding="utf-8",
    )
    load_env_file(f)
    assert os.environ["TEST_ONLY_VAR"] == "plain"
    assert os.environ["TEST_ONLY_Q"] == "quoted val"
    assert os.environ["TEST_ONLY_EXP"] == "x y"
    assert os.environ["TEST_ONLY_SET"] == "keep"
    load_env_file(tmp_path / "missing.env")
    for n in ("TEST_ONLY_VAR", "TEST_ONLY_Q", "TEST_ONLY_EXP"):
        monkeypatch.delitem(os.environ, n)


def test_module_imports_without_google_genai():
    code = (
        "import sys; sys.modules['google']=None; sys.modules['google.genai']=None; "
        "import trade_compiler.llm"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr[-300:]
