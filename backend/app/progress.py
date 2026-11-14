"""Progress phases for the streaming endpoint (POST /api/agent/ask/stream). A no-op unless a sink is set, so the
normal JSON routes pay nothing. The agent calls phase() at a few points; the route turns them into SSE events."""
from contextvars import ContextVar
from typing import Callable

_sink: ContextVar[Callable[[dict], None] | None] = ContextVar("progress_sink", default=None)

TEXTS = {"understanding": "Reading your request…", "searching": "Searching Valio's catalogue…",
         "stock": "Checking Valio stock and prices…", "judging": "Asking Gemini to double-check each match…",
         "planning": "Turning the menu into ingredients…", "ordering": "Placing the order at Valio's front door…"}


def phase(name: str, text: str | None = None) -> None:
    if (sink := _sink.get()) is not None:
        sink({"phase": name, "text": text or TEXTS.get(name, name)})


def set_sink(sink: Callable[[dict], None]) -> None:
    _sink.set(sink)
