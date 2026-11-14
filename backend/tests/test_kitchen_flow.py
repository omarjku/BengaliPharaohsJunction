"""Kitchen history defaults for event/week planning requests."""
import asyncio
from datetime import date

import pytest

from app import agent, ask, menu
from app import conversation


FRIDAY = date(2026, 11, 20)


@pytest.fixture(autouse=True)
def isolated_conversations(monkeypatch, tmp_path):
    monkeypatch.setattr(conversation, "STORE", tmp_path / "conversations.json")


def _context():
    return {
        "covers": {"avg_per_weekday": {"mon": 10, "tue": 20, "wed": None, "thu": 30,
                                        "fri": 80, "sat": 40, "sun": None}},
        "leftovers_recent": [{"date": "2026-11-13", "item": "salmon", "amount": 2, "unit": "kg"}],
    }


def _stub_flow(monkeypatch, context):
    seen = {}

    monkeypatch.setattr(ask, "kitchen_context", lambda buyer_id: context, raising=False)

    async def fake_classify(_text):
        return "menu", None, False, None

    async def fake_given(value, _make):
        return value

    async def fake_menu(menu_text, covers, requested, buyer_id, dishes_task=None, **kwargs):
        seen.update(menu_text=menu_text, covers=covers, requested=requested, buyer_id=buyer_id, kwargs=kwargs)
        return {"cart_total_cents": 1234, "lines": [], "assumptions": [], "decision": {"reasons": []}}

    async def fake_parse(_text, _buyer_id):
        return []

    monkeypatch.setattr(ask, "classify", fake_classify)
    monkeypatch.setattr(agent, "_given", fake_given)
    monkeypatch.setattr(agent, "steering", lambda _text: asyncio.sleep(0, result=None))
    monkeypatch.setattr(agent, "date_intent", lambda *_args: asyncio.sleep(0, result=None))
    monkeypatch.setattr(menu, "parse_menu", fake_parse)
    monkeypatch.setattr(menu, "propose", fake_menu)
    return seen


def test_friday_context_builds_menu_cart_and_mentions_leftovers(monkeypatch):
    seen = _stub_flow(monkeypatch, _context())

    body = asyncio.run(ask.ask("what do we need for Friday", FRIDAY, "chef"))

    assert seen["covers"] == 80
    assert body["covers"] == 80 and body["covers_source"] == "kitchen"
    assert body["covers_assumption"] == "Using 80 covers: your usual Friday."
    assert body["kitchen_leftovers"] == _context()["leftovers_recent"]
    assert "leftover" in body["speak"].lower() and "not subtracted" in body["speak"].lower()


def test_next_week_context_sums_available_weekday_averages(monkeypatch):
    seen = _stub_flow(monkeypatch, _context())

    body = asyncio.run(ask.ask("food for next week", None, "chef"))

    assert seen["covers"] == 180
    assert body["covers"] == 180 and body["covers_source"] == "kitchen"
    assert "Using 180 covers" in body["covers_assumption"]


def test_context_without_usable_covers_keeps_guest_question(monkeypatch):
    _stub_flow(monkeypatch, {"covers": {"avg_per_weekday": {}}, "leftovers_recent": []})

    body = asyncio.run(ask.ask("what do we need for Friday", FRIDAY, "chef"))

    assert body["question"] == "For how many guests?"
    assert body["covers"] is None and "covers_source" not in body


def test_week_without_context_keeps_guest_question(monkeypatch):
    _stub_flow(monkeypatch, {"covers": {"avg_per_weekday": {}}, "leftovers_recent": []})

    body = asyncio.run(ask.ask("food for next week", None, "chef"))

    assert body["question"] == "For how many guests?"


def test_explicit_guest_count_overrides_kitchen_default(monkeypatch):
    seen = _stub_flow(monkeypatch, _context())

    body = asyncio.run(ask._flow("what do we need for Friday", FRIDAY, "chef", covers=100))

    assert seen["covers"] == 100
    assert body["covers"] == 100 and "covers_source" not in body
