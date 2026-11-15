"""The chat agent must see the WHOLE conversation on every turn (fake model, no network)."""
import asyncio
import json

from app import chat_agent

CID = "c" * 32


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(chat_agent.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(chat_agent.conversation, "STORE", tmp_path / "conv.json")
    seen = []

    async def fake_generate(system, contents):
        seen.append((system, json.loads(json.dumps(contents))))
        return {"candidates": [{"content": {"role": "model", "parts": [{"text": f"Noted {len(seen)}."}]}}]}

    monkeypatch.setattr(chat_agent, "_generate_content", fake_generate)
    return seen


def _texts(contents):
    return [part["text"] for message in contents for part in message["parts"] if "text" in part]


def test_every_turn_carries_turn_one_facts_and_all_prior_turns(monkeypatch, tmp_path):
    seen = _setup(monkeypatch, tmp_path)
    messages = ["We are a peanut-free kitchen, deliveries only on Tuesdays."] + [f"unrelated question number {i}" for i in range(1, 9)]
    for message in messages:
        asyncio.run(chat_agent.chat(message, "chef", conversation_id=CID))
    asyncio.run(chat_agent.chat("What did I tell you about deliveries?", "chef", conversation_id=CID))
    system, contents = seen[-1]
    texts = _texts(contents)
    assert contents[0]["role"] == "user" and "peanut-free kitchen" in texts[0]
    for message in messages:  # every earlier chef message, in order, plus the model's replies between them
        assert message in texts
    assert [t for t in texts if t.startswith("Noted")] == [f"Noted {i}." for i in range(1, 10)]
    assert texts[-1] == "What did I tell you about deliveries?"
    assert {m["role"] for m in contents} == {"user", "model"}
    assert "whole conversation" in system and "Never say you cannot" in system


def test_tool_results_stay_in_the_history_not_just_the_text(monkeypatch, tmp_path):
    seen = _setup(monkeypatch, tmp_path)
    c = chat_agent.conversation
    c.record_turn("chef", "user", "order oat milk", conversation_id=CID)
    c.record_turn("chef", "assistant", json.dumps({"tool": "propose_order", "result": {"status": "pending_approval",
                  "items": [{"name": "Oatly Barista 1 l"}]}}), conversation_id=CID, kind="tool")
    c.record_turn("chef", "assistant", "Held for your approval.", conversation_id=CID)
    asyncio.run(chat_agent.chat("order the same product again", "chef", conversation_id=CID))
    assert any("Oatly Barista 1 l" in t for t in _texts(seen[-1][1]))


def test_long_conversation_is_summarised_but_keeps_every_chef_message(monkeypatch, tmp_path):
    seen = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(chat_agent, "HISTORY_BUDGET_CHARS", 600)
    c = chat_agent.conversation
    c.record_turn("chef", "user", "Our kitchen is peanut-free and we only take deliveries on Tuesdays.", conversation_id=CID)
    c.record_turn("chef", "assistant", "Understood.", conversation_id=CID)
    c.record_turn("chef", "assistant", json.dumps({"tool": "propose_order", "result": {"items": [{"name": "Valio whole milk 1 l"}]}}),
                  conversation_id=CID, kind="tool")
    for i in range(30):
        c.record_turn("chef", "user", f"filler question {i} " + "x" * 80, conversation_id=CID)
        c.record_turn("chef", "assistant", f"filler answer {i} " + "y" * 80, conversation_id=CID)
    asyncio.run(chat_agent.chat("what did I tell you about deliveries?", "chef", conversation_id=CID))
    system, contents = seen[-1]
    assert contents[0]["role"] == "user"
    assert "<earlier_conversation>" in system
    notes = system.rsplit("<earlier_conversation>", 1)[1]
    assert "peanut-free" in notes and "only take deliveries on Tuesdays" in notes
    assert "filler question 0" in notes and "filler question 29" in " ".join(_texts(contents))
    assert sum(len(t) for t in _texts(contents)) < 600 + 400  # the verbatim part obeys the budget


def test_a_chat_thread_keeps_early_turns_while_active_and_expires_when_idle(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    clock = [1000.0]
    monkeypatch.setattr(chat_agent.conversation.time, "time", lambda: clock[0])
    c = chat_agent.conversation
    c.record_turn("chef", "user", "first fact", conversation_id=CID)
    for _ in range(40):  # an active hour: no gap reaches the 30-minute idle limit
        clock[0] += 90
        c.record_turn("chef", "user", "more", conversation_id=CID)
    rows = c.turns("chef", CID)
    assert rows[0]["text"] == "first fact" and len(rows) == 41
    clock[0] += c.TURNS_TTL_S + 1
    assert c.turns("chef", CID) == [] and c.is_stale("chef", CID) is False


def test_legacy_buyer_context_is_still_bounded(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    for i in range(25):
        chat_agent.conversation.record_turn("chef", "user", f"t{i}")
    assert len(chat_agent.conversation.turns("chef")) == chat_agent.conversation.MAX_TURNS
