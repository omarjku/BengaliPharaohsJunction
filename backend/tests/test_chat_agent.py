"""Offline contract tests for the text Gemini tool-calling agent."""
import asyncio
from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient

from app import chat_agent
from app.main import app

client = TestClient(app)


def test_dispatches_propose_order_through_the_tool_registry(monkeypatch):
    seen = {}
    card = {"intent": "order", "lines": [], "order": None, "decision": {"outcome": "ASK_HUMAN"}}

    async def fake_propose(args, buyer_id, requested_date, follow_up=False, have=None):
        seen.update(args=args, buyer_id=buyer_id, requested_date=requested_date)
        return {"card": card, "status": "needs_info", "hold_reasons": ["amount is missing"]}

    monkeypatch.setattr(chat_agent, "_propose_order", fake_propose)
    result = asyncio.run(chat_agent._dispatch_tool(
        "propose_order",
        {"items": [{"text": "milk", "amount": 5, "unit": "L"}], "delivery_date": "2026-11-16"},
        "chef",
        date(2026, 11, 16),
    ))

    assert result["card"] == card
    assert result["status"] == "needs_info"
    assert seen == {
        "args": {"items": [{"text": "milk", "amount": 5, "unit": "L"}], "delivery_date": "2026-11-16"},
        "buyer_id": "chef",
        "requested_date": date(2026, 11, 16),
    }


def test_approval_request_never_dispatches_an_approval_tool(monkeypatch):
    async def fake_generate(*_args, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": "I approved the order for you."}]}}]}

    monkeypatch.setattr(chat_agent, "_generate_content", fake_generate)
    result = asyncio.run(chat_agent.chat("Please approve everything", "chef"))

    assert "can't approve" in result["reply"].lower()
    assert result["cards"] == []
    assert "approve_order" not in result["tools_used"]


def test_prose_order_claim_without_tool_result_has_no_order_card(monkeypatch):
    async def fake_generate(*_args, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": "Ordered 20 litres of milk."}]}}]}

    monkeypatch.setattr(chat_agent, "_generate_content", fake_generate)
    result = asyncio.run(chat_agent.chat("Order 20 litres of milk", "chef"))

    assert "haven't placed or confirmed" in result["reply"].lower()
    assert result["cards"] == []


def test_untrusted_order_claim_is_not_presented_as_a_verified_order(monkeypatch):
    async def fake_generate(*_args, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": "The order is confirmed."}]}}]}

    monkeypatch.setattr(chat_agent, "_generate_content", fake_generate)
    result = asyncio.run(chat_agent.chat("What happened?", "chef"))

    assert result["cards"] == []
    assert "haven't placed or confirmed" in result["reply"].lower()


def test_menu_tool_result_is_a_proposal_even_when_approval_is_required():
    assert chat_agent._tool_card({"decision": {"outcome": "ASK_HUMAN"}, "lines": []}, "menu")["status"] == "proposal"


def test_function_call_response_is_dispatched_and_returned_to_gemini(monkeypatch):
    responses = iter([
        {"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {
            "name": "search_products", "args": {"query": "milk", "limit": 2}}}]}}]},
        {"candidates": [{"content": {"role": "model", "parts": [{"text": "I found two milk options."}]}}]},
    ])
    sent = []
    card = {"intent": "order", "lines": [], "decision": {"outcome": "ASK_HUMAN"}}

    async def fake_generate(_system, contents):
        sent.append(contents)
        return next(responses)

    async def fake_dispatch(name, args, buyer_id, requested_date, follow_up=False, have=None):
        assert (name, args, buyer_id) == ("search_products", {"query": "milk", "limit": 2}, "chef")
        return {"status": "proposal", "card": card, "lines": [{"product": "Milk"}]}

    monkeypatch.setattr(chat_agent, "_generate_content", fake_generate)
    monkeypatch.setattr(chat_agent, "_dispatch_tool", fake_dispatch)
    result = asyncio.run(chat_agent.chat("Find milk", "chef"))

    assert result["reply"] == "I found two milk options."
    assert result["tools_used"] == ["search_products"]
    assert result["cards"] == [card]
    assert any("functionResponse" in part
               for message in sent[1]
               for part in message.get("parts", []))


def test_gemini_failure_falls_back_to_the_existing_ask_path(monkeypatch):
    async def broken_generate(*_args, **_kwargs):
        raise RuntimeError("Gemini unavailable")

    fallback = {
        "intent": "order",
        "reply": "Held for your approval.",
        "speak": "Held for your approval.",
        "lines": [],
        "order": {"status": "pending_approval", "order_id": "order-1"},
    }
    seen = {}

    async def fake_ask(text, requested_date, buyer_id, follow_up=None, have=None):
        seen.update(text=text, requested_date=requested_date, buyer_id=buyer_id, follow_up=follow_up, have=have)
        return fallback

    monkeypatch.setattr(chat_agent, "_generate_content", broken_generate)
    monkeypatch.setattr(chat_agent.ask, "ask", fake_ask)
    result = asyncio.run(chat_agent.chat("5 L milk", "chef", requested_date=date(2026, 11, 16), have=["salt"]))

    assert result["reply"] == fallback["reply"]
    assert result["cards"] == [fallback]
    assert result["tools_used"] == []
    assert seen == {"text": "5 L milk", "requested_date": date(2026, 11, 16), "buyer_id": "chef",
                    "follow_up": None, "have": ["salt"]}


def test_chat_endpoint_uses_agent_auth_and_returns_chat_envelope(shop, monkeypatch):
    async def fake_chat(text, buyer_id, requested_date=None, follow_up=None, have=None, conversation_id=None):
        return {"reply": f"Checked {text} for {buyer_id}.", "cards": [], "conversation_id": "c1", "tools_used": []}

    monkeypatch.setattr(chat_agent, "chat", fake_chat)
    assert client.post("/api/agent/chat", json={"text": "milk"}).status_code == 401
    response = client.post("/api/agent/chat", json={"text": "milk"}, headers={"X-Agent-Key": "agent-chef"})
    assert response.status_code == 200
    assert response.json()["reply"] == "Checked milk for chef."


def test_cancel_dispatch_accepts_the_common_tool_context(monkeypatch):
    async def fake_cancel(args, buyer_id, **kwargs):
        return {"status": "cancelled", "order_id": args["order_id"]}

    monkeypatch.setattr(chat_agent, "_cancel_order", fake_cancel)
    result = asyncio.run(chat_agent._dispatch_tool("cancel_order", {"order_id": "o1"}, "chef", date.today()))
    assert result == {"status": "cancelled", "order_id": "o1"}


def test_change_removing_the_last_line_cancels_without_rerunning_a_empty_cart(monkeypatch):
    old = {"id": "o1", "buyer_id": "chef", "status": "pending_approval", "requested_date": "2026-11-16",
           "lines": [{"product_id": "p1", "name": "Cream", "quantity": 2, "unit": "L"}]}
    monkeypatch.setattr(chat_agent.orders, "_store", lambda: {"o1": old})
    monkeypatch.setattr(chat_agent.ask, "_reject_order", lambda *_args: asyncio.sleep(0, result=True))

    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("a cart with no lines must not be rerun")

    monkeypatch.setattr(chat_agent.ask, "_execute_action", should_not_run)
    result = asyncio.run(chat_agent._change_order(
        {"order_id": "o1", "changes": [{"name": "Cream", "remove": True}]}, "chef", None))
    assert result["status"] == "cancelled" and result["order_id"] == "o1"


def test_check_assumptions_makes_one_batched_decisions_call_and_marks_threshold(monkeypatch):
    seen = {}

    async def fake_decisions(input_text, questions):
        seen["input"] = input_text
        seen["questions"] = questions
        return {key: {"type": "noul", "noul": 0.91 if key == "portion" else 0.69}
                for key in questions}

    monkeypatch.setattr(chat_agent.agent, "_decisions", fake_decisions)
    result = asyncio.run(chat_agent._check_assumptions({"questions": [
        {"id": "portion", "question": "Is 150 g mozzarella per pizza right?", "context": "60 pizzas"},
        {"id": "date", "question": "Is Tuesday the intended delivery day?"},
    ]}, "chef"))

    assert result == [{"id": "portion", "p_yes": 0.91}, {"id": "date", "p_yes": 0.69}]
    assert len(seen["questions"]) == 2
    assert "150 g mozzarella" in seen["input"]


def test_function_response_preserves_call_id_and_model_content_exactly(monkeypatch):
    model_content = {"role": "model", "parts": [{"thought": "hidden", "thoughtSignature": "sig-1"},
                                                     {"functionCall": {"name": "search_products", "id": "call-1",
                                                                       "args": {"query": "milk", "limit": 2}}}]}
    responses = iter([
        {"candidates": [{"content": model_content}]},
        {"candidates": [{"content": {"role": "model", "parts": [{"text": "Done."}]}}]},
    ])
    sent = []

    async def fake_generate(_system, contents):
        sent.append(contents)
        return next(responses)

    async def fake_dispatch(*_args, **_kwargs):
        return {"status": "proposal", "lines": [{"product": "Milk"}]}

    monkeypatch.setattr(chat_agent, "_generate_content", fake_generate)
    monkeypatch.setattr(chat_agent, "_dispatch_tool", fake_dispatch)
    result = asyncio.run(chat_agent.chat("Find milk", f"function-call-chef-{uuid4().hex}"))

    assert result["reply"] == "Done."
    assert sent[1][1] is model_content
    response_part = sent[1][2]["parts"][0]["functionResponse"]
    assert response_part["name"] == "search_products"
    assert response_part["id"] == "call-1"


def test_provider_400_is_loud_and_does_not_use_legacy_fallback(monkeypatch):
    async def failed_generate(*_args, **_kwargs):
        raise chat_agent.ProviderCallError(400, "INVALID_ARGUMENT")

    async def should_not_fallback(*_args, **_kwargs):
        raise AssertionError("provider protocol failures must not enter /ask")

    monkeypatch.setattr(chat_agent, "_generate_content", failed_generate)
    monkeypatch.setattr(chat_agent.ask, "ask", should_not_fallback)
    result = asyncio.run(chat_agent.chat("Order milk", "chef"))

    assert result["provider_call_ok"] is False
    assert result["provider_error"]["status"] == 400
    assert result["cards"] == []


def test_history_is_scoped_to_the_chat_conversation_id(monkeypatch, tmp_path):
    monkeypatch.setattr(chat_agent.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(chat_agent.conversation, "STORE", tmp_path / "conv.json")
    first, second = "a" * 32, "b" * 32
    chat_agent.conversation.record_turn("chef", "user", "vegan pizza for 2", conversation_id=first)
    chat_agent.conversation.record_turn("chef", "assistant", "Planning vegan pizza.", conversation_id=first)
    chat_agent.conversation.record_turn("chef", "user", "reindeer meat", conversation_id=second)

    assert chat_agent.conversation.turns("chef", second) == [
        {"role": "user", "text": "reindeer meat", "time": chat_agent.conversation.turns("chef", second)[0]["time"]}
    ]
    assert "vegan pizza" not in str(chat_agent.conversation.turns("chef", second))
    assert "vegan pizza" in str(chat_agent.conversation.turns("chef", first))


def test_chat_without_a_conversation_id_starts_a_new_history(monkeypatch, tmp_path):
    monkeypatch.setattr(chat_agent.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(chat_agent.conversation, "STORE", tmp_path / "conv.json")

    async def fake_generate(*_args, **_kwargs):
        return {"candidates": [{"content": {"role": "model", "parts": [{"text": "Noted."}]}}]}

    monkeypatch.setattr(chat_agent, "_generate_content", fake_generate)
    first = asyncio.run(chat_agent.chat("vegan pizza for 2", "chef"))
    second = asyncio.run(chat_agent.chat("reindeer meat", "chef"))

    assert first["conversation_id"] != second["conversation_id"]
    assert "vegan pizza" not in str(chat_agent.conversation.turns("chef", second["conversation_id"]))


def test_chat_restarts_a_conversation_after_thirty_minutes(monkeypatch, tmp_path):
    monkeypatch.setattr(chat_agent.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(chat_agent.conversation, "STORE", tmp_path / "conv.json")
    clock = [1000.0]
    monkeypatch.setattr(chat_agent.conversation.time, "time", lambda: clock[0])
    cid = "d" * 32
    chat_agent.conversation.record_turn("chef", "user", "old topic", conversation_id=cid)
    clock[0] += chat_agent.conversation.TURNS_TTL_S + 1

    async def fake_generate(*_args, **_kwargs):
        return {"candidates": [{"content": {"role": "model", "parts": [{"text": "Fresh topic."}]}}]}

    monkeypatch.setattr(chat_agent, "_generate_content", fake_generate)
    result = asyncio.run(chat_agent.chat("new topic", "chef", conversation_id=cid))

    assert result["conversation_id"] != cid


def test_pending_choice_and_delegation_resolve_the_stored_slot():
    state = {"pending_slot": "assumption:pasta", "choices": ["80 g", "100 g"], "default": "100 g"}

    assert chat_agent._resolve_pending_input("1", state) == ("80 g", True)
    assert chat_agent._resolve_pending_input("the first one", state) == ("80 g", True)
    assert chat_agent._resolve_pending_input("assume", state) == ("100 g", True)
    assert chat_agent._pending_default("Which amount?", ["80 g", "100 g"], "Is 100g per person right?") == "100 g"
    assert chat_agent._pending_choices("Which day?", "- Tomorrow, Sun\n- Monday, Mon\n- Tuesday, Tue") == [
        "Tomorrow, Sun", "Monday, Mon", "Tuesday, Tue"]
    assert chat_agent._pending_choices("Which delivery date?", "I have 80 g and 6 kg. Which delivery date?") == []
    assert chat_agent._pending_choices("Which delivery day?", "I have 6 kg or 100 g. Which delivery day?") == []
    assert chat_agent._pending_choices("Which delivery day: tomorrow or Monday?", "Which delivery day: tomorrow or Monday?") == [
        "tomorrow", "Monday"]


def test_explicit_per_person_correction_scales_against_the_current_request():
    args = {"items": [{"text": "pasta", "amount": 6, "unit": "g"}]}
    corrected = chat_agent._correct_explicit_portion(
        "100g per person", "I need enough pasta to feed 50 people with 20% extra", args)

    assert corrected["items"] == [{"text": "6 kg pasta", "amount": 6, "unit": "kg"}]
    changed = chat_agent._correct_explicit_portion(
        "100g per person", "I need enough pasta to feed 50 people with 20% extra",
        {"changes": [{"name": "pasta", "amount": 6, "unit": "g"}]})
    assert changed["changes"] == [{"name": "pasta", "amount": 6, "unit": "kg"}]


def test_delegation_scores_default_then_continues_to_propose_order(monkeypatch, tmp_path):
    monkeypatch.setattr(chat_agent.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(chat_agent.conversation, "STORE", tmp_path / "conv.json")
    cid = "c" * 32
    state = {"pending_slot": "assumption:pasta", "question": "Use 80 g or 100 g pasta per person?",
             "choices": ["80 g", "100 g"], "default": "100 g"}
    chat_agent.conversation.record_turn("chef", "assistant", state["question"], conversation_id=cid, pending=state)
    dispatched = []
    scored = []
    responses = iter([
        {"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {
            "name": "propose_order", "args": {"items": [{"text": "100 g pasta per person"}],
                                                     "delivery_date": "2026-11-16"}}}]}}]},
        {"candidates": [{"content": {"role": "model", "parts": [{"text": "I will use 100 g per person."}]}}]},
    ])

    async def fake_generate(*_args, **_kwargs):
        return next(responses)

    async def fake_check(args, *_args, **_kwargs):
        scored.extend(args["questions"])
        return [{"id": "pasta", "p_yes": 0.91}]

    async def fake_dispatch(name, args, *_args, **_kwargs):
        dispatched.append((name, args))
        return {"status": "proposal", "card": {"intent": "order", "lines": []}}

    monkeypatch.setattr(chat_agent, "_generate_content", fake_generate)
    monkeypatch.setattr(chat_agent, "_check_assumptions", fake_check)
    monkeypatch.setattr(chat_agent, "_dispatch_tool", fake_dispatch)
    result = asyncio.run(chat_agent.chat("assume", "chef", conversation_id=cid))

    assert scored and "100 g" in scored[0]["context"]
    assert dispatched[0][0] == "propose_order"
    assert result["awaiting_user"] is False


def test_timeout_returns_a_continue_message_instead_of_a_failed_turn(monkeypatch):
    async def timed_out(*_args, **_kwargs):
        raise asyncio.TimeoutError

    monkeypatch.setattr(chat_agent, "_generate_content", timed_out)
    monkeypatch.setattr(chat_agent, "GEMINI_TIMEOUT_S", 0.01)
    result = asyncio.run(chat_agent.chat("plan a menu for 2", "timeout-chef"))

    assert result["provider_call_ok"] is True
    assert "continue" in result["reply"].lower()


def test_reply_is_plain_text_without_markdown_emphasis():
    from app import chat_agent
    out = chat_agent._plain("The **Valio butter** is *EUR 6.60/kg*.\n## Note\n1. **Option** one")
    assert "**" not in out and "*" not in out and "##" not in out
    assert "Valio butter" in out and "1. Option one" in out


def test_order_tools_pass_the_real_steering_score_and_injection_hold(monkeypatch):
    """Security review: the chat agent must not feed constant 'safe' guard scores into the engine."""
    import asyncio
    from datetime import date
    from app import agent, chat_agent
    seen = {}

    async def fake_run(text, delivery, buyer_id, pre=None, **kw):
        seen.update(pre or {})
        return {"lines": [], "decision": {"reasons": []}}

    async def fake_steer(text):
        return 0.93
    monkeypatch.setattr(agent, "run", fake_run)
    monkeypatch.setattr(agent, "steering", fake_steer)
    chat_agent._TURN.set({"steer": 0.93, "note": agent.INJECTION_NOTE})
    asyncio.run(chat_agent._propose_order({"items": [{"text": "15 kg reindeer roast"}], "delivery_date": "2026-11-20"},
                                          "smoke-kitchen", date(2026, 11, 20)))
    assert seen["steer"] == 0.93 and seen["request_hold"] is True and seen["request_note"] == agent.INJECTION_NOTE
