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
    async def fake_chat(text, buyer_id, requested_date=None, follow_up=None, have=None):
        return {"reply": f"Checked {text} for {buyer_id}.", "cards": [], "conversation_id": "c1", "tools_used": []}

    monkeypatch.setattr(chat_agent, "chat", fake_chat)
    assert client.post("/api/agent/chat", json={"text": "milk"}).status_code == 401
    response = client.post("/api/agent/chat", json={"text": "milk"}, headers={"X-Agent-Key": "agent-chef"})
    assert response.status_code == 200
    assert response.json()["reply"] == "Checked milk for chef."
    assert response.json()["confidence_threshold"] == 0.8


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


def test_voice_dispatch_marks_every_order_as_an_assumption_hold(monkeypatch):
    seen = {}

    async def fake_guard(_text):
        return {"steer": 0.12, "note": None}

    async def fake_run(_text, _delivery, _buyer_id, pre=None):
        seen.update(pre or {})
        return {"lines": [], "decision": {"outcome": "ASK_HUMAN", "reasons": []}}

    monkeypatch.setattr(chat_agent, "_turn_guard", fake_guard)
    monkeypatch.setattr(chat_agent.agent, "run", fake_run)
    asyncio.run(chat_agent._dispatch_tool(
        "propose_order", {"items": [{"text": "butter", "amount": 25, "unit": "kg"}],
                           "delivery_date": "2026-11-16"}, "chef", date(2026, 11, 16), via="voice"))
    assert seen["request_hold"] is True
    assert seen["request_note"] == "Voice orders require the chef's on-screen approval."
