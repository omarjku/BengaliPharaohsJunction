"""Shared Gemini wrapper (reusable by later tasks). Agent A implements GeminiLLM.

Modes (LLM_MODE env var, or the `mode` argument):
- live:   cache hit -> return it; miss -> call Gemini (retry/backoff/fallback), store, return.
- record: always call Gemini and (over)write the cache entry. Used to record real fixtures.
- replay: read the cache only. A miss raises ReplayMiss. NEVER touches the network or the key.
Tests always run in replay, against fixtures in tests/fixtures/.

Cache entry = one JSON file `<cache_dir>/<cache_key>.json`:
  {"key": ..., "model": ..., "prompt": ..., "response": {...}, "synthetic": bool}
`synthetic: true` marks hand-written fixtures; recording overwrites them with real ones.
The key is sha256 over (prompt, schema, model), so a changed prompt or schema is a replay miss.

SECRETS: the API key is read from the environment only inside the live backend. It is never
logged, printed or put in an exception message. key_status() is the only thing that may be shown.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

# The one place that names models. Order = fallback order (first is tried first).
DEFAULT_MODELS: tuple[str, ...] = ("gemini-4-hydrogen",)
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / ".llm_cache"
KEY_ENV = "GEMINI_API_KEY"


class LLMMode(StrEnum):
    LIVE = "live"
    RECORD = "record"
    REPLAY = "replay"


class LLMError(Exception):
    """Base for wrapper failures. Messages must never contain the API key."""


class ReplayMiss(LLMError):
    """Replay mode found no cache entry for this (prompt, schema, model)."""


class RateLimited(LLMError):
    """A backend raises this on HTTP 429; the wrapper retries with exponential backoff."""


class LLMClient(Protocol):
    """What the compiler depends on. Tests use FakeLLM; production uses GeminiLLM."""

    def generate_structured(
        self, prompt: str, schema: dict[str, Any], model: str
    ) -> dict[str, Any]:
        """Return the model's answer parsed as a JSON object matching `schema`."""
        ...


# (prompt, schema, model) -> parsed JSON object. The real one calls Gemini; tests pass a fake.
Backend = Callable[[str, dict[str, Any], str], dict[str, Any]]


def cache_key(prompt: str, schema: dict[str, Any], model: str) -> str:
    payload = {"prompt": prompt, "schema": schema, "model": model}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def read_cache(cache_dir: Path, key: str) -> dict[str, Any] | None:
    path = Path(cache_dir) / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_cache(cache_dir: Path, key: str, entry: dict[str, Any]) -> Path:
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    path = Path(cache_dir) / f"{key}.json"
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def mode_from_env(default: LLMMode = LLMMode.LIVE) -> LLMMode:
    return LLMMode(os.environ.get("LLM_MODE", default.value).strip().lower())


def key_status() -> str:
    """The only key-related text that may ever be shown: presence and length, never the value."""
    value = os.environ.get(KEY_ENV, "")
    return f"{KEY_ENV}: present (length {len(value)})" if value else f"{KEY_ENV}: missing"


def _redact(text: str) -> str:
    """Remove the API key (and anything shaped like a Google key) from text before showing it."""
    key = os.environ.get(KEY_ENV, "")
    if key:
        text = text.replace(key, "[redacted]")
    return re.sub(r"AIza[0-9A-Za-z_\-]{20,}", "[redacted]", text)


def _failure_note(exc: BaseException) -> str:
    """Class name plus an integer status code only: never str(exc), which could echo a secret.

    Opt-in debugging: with LLM_DEBUG=1 a short message is added, with the key redacted."""
    code = getattr(exc, "code", None)
    if code is None:
        code = getattr(exc, "status_code", None)
    name = type(exc).__name__
    note = f"{name}({code})" if isinstance(code, int) and not isinstance(code, bool) else name
    if os.environ.get("LLM_DEBUG", "").strip().lower() in {"1", "true", "yes"}:
        note += ": " + _redact(" ".join(str(exc).split()))[:300]
    return note


class GeminiLLM:
    """LLMClient with modes, file cache, 429 retry with exponential backoff and model fallback.

    Retries: RateLimited -> sleep base_delay * 2**attempt, at most max_retries retries per model.
    Exhausted retries or any other backend Exception -> next model; all failed -> LLMError.
    """

    def __init__(
        self,
        mode: LLMMode | None = None,
        *,
        cache_dir: Path | None = None,
        models: tuple[str, ...] | None = None,
        backend: Backend | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_retries: int = 5,
        base_delay: float = 1.0,
    ) -> None:
        self.mode = mode or mode_from_env()
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.models = models or DEFAULT_MODELS
        self.backend = backend
        self.sleep = sleep
        self.max_retries = max_retries
        self.base_delay = base_delay

    def generate_structured(
        self, prompt: str, schema: dict[str, Any], model: str | None = None
    ) -> dict[str, Any]:
        models = [model] if model else list(self.models)
        if self.mode == LLMMode.REPLAY:
            for m in models:
                entry = read_cache(self.cache_dir, cache_key(prompt, schema, m))
                if entry is not None:
                    return entry["response"]
            key = cache_key(prompt, schema, models[0])[:12]
            raise ReplayMiss(
                f"replay miss: no cached response (key prefix {key}) for models {', '.join(models)}"
            )

        failures: list[str] = []
        for m in models:
            key = cache_key(prompt, schema, m)
            if self.mode == LLMMode.LIVE:
                entry = read_cache(self.cache_dir, key)
                if entry is not None:
                    return entry["response"]
            result = self._call_with_retries(prompt, schema, m, failures)
            if result is None:
                continue
            write_cache(
                self.cache_dir,
                key,
                {"key": key, "model": m, "prompt": prompt, "response": result, "synthetic": False},
            )
            return result
        raise LLMError("all models failed: " + "; ".join(failures))

    def _call_with_retries(
        self, prompt: str, schema: dict[str, Any], model: str, failures: list[str]
    ) -> dict[str, Any] | None:
        backend = self.backend or self._gemini_backend
        attempt = 0
        while True:
            try:
                result = backend(prompt, schema, model)
            except RateLimited:
                if attempt >= self.max_retries:
                    failures.append(f"{model}: RateLimited, retries exhausted")
                    return None
                self.sleep(self.base_delay * 2**attempt)
                attempt += 1
                continue
            except LLMError:
                raise  # config problem (e.g. missing key): not a per-model failure
            except Exception as exc:  # noqa: BLE001 - any backend failure means try next model
                failures.append(f"{model}: {_failure_note(exc)}")
                return None
            if not isinstance(result, dict):
                failures.append(f"{model}: non-object response")
                return None
            return result

    def _gemini_backend(self, prompt: str, schema: dict[str, Any], model: str) -> dict[str, Any]:
        # UNVERIFIED against the live API: first record run by the user will confirm.
        # Imports are lazy so replay/tests need neither the package, the key nor the network.
        key = os.environ.get(KEY_ENV, "")
        if not key:
            raise LLMError(f"{KEY_ENV} is not set")
        try:
            from google import genai
            from google.genai import errors, types
        except ImportError as exc:
            raise LLMError("google-genai is not installed") from exc
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=schema,  # plain JSON Schema dict, passed as given
            temperature=0,
        )
        # Keep a reference to the client for the whole call: a temporary one can be closed by the
        # garbage collector before the request is sent ("client has been closed" RuntimeError).
        client = genai.Client(api_key=key)
        try:
            response = client.models.generate_content(model=model, contents=prompt, config=config)
        except errors.APIError as exc:
            if getattr(exc, "code", None) == 429:
                raise RateLimited("HTTP 429") from None
            raise
        return json.loads(response.text)


def _find_repo_env() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".env").exists() or (parent / ".git").exists():
            return parent / ".env"
    return Path(".env")


def load_env_file(path: Path | None = None) -> None:
    """Put KEY=VALUE lines from a .env file into os.environ (never overriding values already
    set), without logging any value. Missing file = no-op."""
    env_path = Path(path) if path else _find_repo_env()
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, sep, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if not sep or not name:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(name, value)
