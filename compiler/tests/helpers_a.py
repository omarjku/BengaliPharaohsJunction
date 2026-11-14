"""Fake backends for the Gemini wrapper tests."""

from typing import Any


class ScriptedBackend:
    """Returns/raises scripted items in order; records (prompt, model) calls."""

    def __init__(self, *items: Any) -> None:
        self.items = list(items)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, prompt: str, schema: dict[str, Any], model: str) -> Any:
        self.calls.append((prompt, model))
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def forbidden_backend(prompt: str, schema: dict[str, Any], model: str) -> dict[str, Any]:
    raise AssertionError("backend must not be called")


class Sleeps:
    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)
