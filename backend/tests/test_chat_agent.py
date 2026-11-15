"""Offline contract tests for the text Gemini tool-calling agent."""
import asyncio
from datetime import date, datetime as real_datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app import chat_agent
from app.main import app

client = TestClient(app)


def _held_order_body(pre, available_date):
    return {"order": {"status": "pending_approval", "order_id": "order-1"},
            "lines": [{"chosen": True, "product": {"id": "milk", "name_en": "Milk"},
                       "quantity": {"requested": {"amount": 5, "unit": "L"}, "quantity": 5},
                       "quote": {"available_date": available_date}}],
            "decision": {"outcome": "ASK_HUMAN", "reasons": [
                {"code": "ASSUMPTION_CONFIRM", "severity": "ASK", "message": pre["request_note"]}]}}


def test_no_date_proposes_next_delivery_as_a_held_card(monkeypatch):
    seen = []
    assumed = date(2026, 11, 16)
    note = "Delivery: Mon 16 Nov (assumed: next delivery day; change it if needed)"

    monkeypatch.setattr(chat_agent.ask, "_delivery_assumption",
                        lambda _today: (assumed, "Assumed Monday 16 Nov, the next delivery"))
    monkeypatch.setattr(chat_agent, "_turn_guard", lambda _text: asyncio.sleep(0, result={"steer": 0.0, "note": None}))

    async def fake_run(_text, delivery, _buyer_id, pre=None):
        seen.append((delivery, pre))
        return _held_order_body(pre, delivery.isoformat())

    monkeypatch.setattr(chat_agent.agent, "run", fake_run)
    result = asyncio.run(chat_agent._propose_order(
        {"items": [{"text": "5 L milk", "amount": 5, "unit": "L"}]}, "chef", None))

    assert seen and seen[0][0] == assumed
    assert seen[0][1]["request_hold"] is True
    assert seen[0][1]["request_note"] == note
    assert result["status"] == "pending_approval"
    assert result["card"]["requested_date"] == assumed.isoformat()
    assert any(note in str(assumption) for assumption in result["assumptions"])


def test_no_date_uses_the_later_shared_delivery_date_when_first_quote_is_late(monkeypatch):
    calls = []
    monday, wednesday = date(2026, 11, 16), date(2026, 11, 18)
    monkeypatch.setattr(chat_agent.ask, "_delivery_assumption",
                        lambda _today: (monday, "Assumed Monday 16 Nov, the next delivery"))
    monkeypatch.setattr(chat_agent.ask, "_reject_order", lambda *_args: asyncio.sleep(0, result=True))
    monkeypatch.setattr(chat_agent, "_turn_guard",
                        lambda _text: asyncio.sleep(0, result={"steer": 0.0, "note": None}))

    async def fake_run(_text, delivery, _buyer_id, pre=None):
        calls.append(delivery)
        return _held_order_body(pre, wednesday.isoformat() if delivery == monday else delivery.isoformat())

    monkeypatch.setattr(chat_agent.agent, "run", fake_run)
    result = asyncio.run(chat_agent._propose_order(
        {"items": [{"text": "5 L milk", "amount": 5, "unit": "L"}]}, "chef", None))

    assert calls == [monday, wednesday]
    assert result["card"]["requested_date"] == wednesday.isoformat()
    assert "Wed 18 Nov" in str(result["assumptions"])


def test_no_date_uses_next_delivery_for_sunday_and_friday_evening(monkeypatch):
    for frozen in (real_datetime(2026, 11, 15, 12), real_datetime(2026, 11, 13, 18)):
        seen = {}
        class FrozenDateTime:
            @classmethod
            def now(cls, tz):
                return frozen.replace(tzinfo=tz)

        monkeypatch.setattr(chat_agent, "datetime", FrozenDateTime)
        monkeypatch.setattr(chat_agent, "_turn_guard",
                            lambda _text: asyncio.sleep(0, result={"steer": 0.0, "note": None}))

        async def fake_run(_text, delivery, _buyer_id, pre=None):
            seen["delivery"] = delivery
            return _held_order_body(pre, delivery.isoformat())

        monkeypatch.setattr(chat_agent.agent, "run", fake_run)
        asyncio.run(chat_agent._propose_order(
            {"items": [{"text": "5 L milk", "amount": 5, "unit": "L"}]}, "chef", None))
        assert seen["delivery"] == date(2026, 11, 16)


def test_explicit_date_stays_explicit_and_is_not_marked_as_a_date_assumption(monkeypatch):
    seen = {}
    explicit = date(2026, 11, 20)
    monkeypatch.setattr(chat_agent, "_turn_guard",
                        lambda _text: asyncio.sleep(0, result={"steer": 0.0, "note": None}))

    async def fake_run(_text, delivery, _buyer_id, pre=None):
        seen.update(delivery=delivery, pre=pre)
        return _held_order_body(pre, delivery.isoformat())

    monkeypatch.setattr(chat_agent.agent, "run", fake_run)
    result = asyncio.run(chat_agent._propose_order(
        {"items": [{"text": "5 L milk", "amount": 5, "unit": "L"}], "delivery_date": explicit.isoformat()},
        "chef", explicit))

    assert seen["delivery"] == explicit
    assert seen["pre"]["request_hold"] is False
    assert result["card"]["requested_date"] == explicit.isoformat()
    assert not any("assumed: next delivery day" in str(assumption) for assumption in result.get("assumptions", []))


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


def test_product_search_uses_requested_date_and_safety_filters(shop, monkeypatch):
    seen = {}

    def search(query, claims, exclude_allergens, strict_may_contain, category, limit):
        seen["search"] = (query, claims, exclude_allergens, strict_may_contain, category, limit)
        return [shop.products["463335"]]

    async def quotes(ids, requested_date, *args, **kwargs):
        seen["quote"] = (ids, requested_date)
        return [shop.quotes["463335"]]

    monkeypatch.setattr(chat_agent.catalogue, "search", search)
    monkeypatch.setattr(chat_agent.valio, "get_quotes", quotes)
    result = asyncio.run(chat_agent._search_products(
        {"query": "milk", "limit": 2, "claims": ["FREE_FROM_LACTOSE"], "exclude_allergens": ["AP"]},
        "chef", date(2026, 11, 20)))

    assert seen["search"] == ("milk", ["FREE_FROM_LACTOSE"], ["AP"], False, None, 2)
    assert seen["quote"] == (["463335"], "2026-11-20") and result["products"][0]["product_id"] == "463335"


def test_chat_search_ranks_request_fit_and_amount_before_price(shop, monkeypatch):
    coffee = dict(shop.products["463335"], id="coffee", name_en="Valio coffee milk 1 l")
    milk = dict(shop.products["463335"], id="milk", name_en="Valio Eila milk 1 l lactose free")
    coffee_quote = dict(shop.quotes["463335"], product_id="coffee", price=1.30)
    milk_quote = dict(shop.quotes["463335"], product_id="milk", price=1.56)
    monkeypatch.setattr(chat_agent.catalogue, "search", lambda *args: [coffee, milk])

    async def quotes(ids, requested_date, *args, **kwargs):
        return [coffee_quote if pid == "coffee" else milk_quote for pid in ids]

    monkeypatch.setattr(chat_agent.valio, "get_quotes", quotes)
    token = chat_agent._TURN.set({"original": "I need 1,000 litres of lactose-free milk by Tuesday",
                                  "steer": 0.01, "note": None})
    try:
        result = asyncio.run(chat_agent._search_products(
            {"query": "Valio coffee milk 1 l lactose", "amount": 1000, "unit": "L"},
            "chef", date(2026, 11, 17)))
    finally:
        chat_agent._TURN.reset(token)

    assert result["products"][0]["product_id"] == "milk"


def test_search_tool_declares_optional_safety_filters():
    declaration = next(d for d in chat_agent.TOOLS[0]["functionDeclarations"] if d["name"] == "search_products")
    assert {"claims", "exclude_allergens"} <= set(declaration["parameters"]["properties"])


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


def test_timeout_reports_existing_order_state_instead_of_continue(monkeypatch):
    card = {"order": {"status": "pending_approval"},
            "decision": {"reasons": [{"severity": "ASK", "message": "€1,560 is over your €1,500 limit"}]},
            "lines": []}
    responses = iter([{"candidates": [{"content": {"parts": [{"functionCall": {
        "name": "propose_order", "args": {"items": [{"text": "milk", "amount": 1000, "unit": "L"}]}}
    }]}}]}])

    async def fake_generate(*_args, **_kwargs):
        try:
            return next(responses)
        except StopIteration:
            raise asyncio.TimeoutError

    async def fake_dispatch(*_args, **_kwargs):
        return {"card": card, "status": "pending_approval"}

    monkeypatch.setattr(chat_agent, "_generate_content", fake_generate)
    monkeypatch.setattr(chat_agent, "_dispatch_tool", fake_dispatch)
    result = asyncio.run(chat_agent.chat("Order 1000 L milk", "timeout-held-chef"))

    assert result["reply"] == "Held: €1,560 is over your €1,500 limit; approve it on screen"
    assert "continue" not in result["reply"].lower()


def test_non_food_request_is_declined_before_date_question(monkeypatch):
    async def fake_generate(*_args, **_kwargs):
        return {"candidates": [{"content": {"parts": [{"text": "Which delivery date should I use?"}]}}]}

    monkeypatch.setattr(chat_agent, "_generate_content", fake_generate)
    result = asyncio.run(chat_agent.chat("Order LEGO for Monday", "scope-chef"))

    assert result["reply"] == "I can only order from Valio's food-service range."
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
    asyncio.run(chat_agent._propose_order({"items": [{"text": "15 kg reindeer roast"}]},
                                          "smoke-kitchen", None))
    assert seen["steer"] == 0.93 and seen["request_hold"] is True and seen["request_note"] == agent.INJECTION_NOTE


def test_proposal_scores_the_chef_words_without_lifting_confirmation_confidence(monkeypatch):
    seen = {}

    async def fake_run(text, delivery, buyer_id, pre=None):
        seen.update(text=text, pre=pre)
        return {"lines": [], "decision": {"outcome": "ASK_HUMAN", "reasons": []}}

    monkeypatch.setattr(chat_agent.agent, "run", fake_run)
    token = chat_agent._TURN.set({"original": "I need 1,000 litres of lactose-free milk by Tuesday",
                                  "steer": 0.01, "note": None})
    try:
        asyncio.run(chat_agent._propose_order(
            {"items": [{"text": "Valio coffee milk 1 l lactose", "amount": 1000, "unit": "L"}],
             "delivery_date": "2026-11-17"}, "chef", date(2026, 11, 17), follow_up=True))
    finally:
        chat_agent._TURN.reset(token)

    assert seen["text"] == "I need 1,000 litres of lactose-free milk by Tuesday"
    assert "meant" not in seen["pre"]
    assert seen["pre"]["decision_text"] == seen["text"]


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


def test_voice_change_dispatch_marks_the_replaced_order_as_a_hold(monkeypatch):
    seen = {}
    old = {"id": "order-1", "buyer_id": "chef", "status": "pending_approval",
           "requested_date": "2026-11-16", "lines": [{"name": "Milk", "amount": 1, "unit": "L"}]}

    monkeypatch.setattr(chat_agent, "_owned_order", lambda *_args: ("order-1", old))
    monkeypatch.setattr(chat_agent.ask, "_merged_change_items", lambda *_args: ([{"name": "Milk"}], None, None))

    async def fake_guard(_text):
        return {"steer": 0.12, "note": None}

    async def fake_execute(*_args, request_note=None, **_kwargs):
        seen["request_note"] = request_note
        return {"intent": "order", "lines": []}

    monkeypatch.setattr(chat_agent, "_turn_guard", fake_guard)
    monkeypatch.setattr(chat_agent.ask, "_execute_action", fake_execute)
    asyncio.run(chat_agent._dispatch_tool(
        "change_order", {"order_id": "order-1", "changes": [{"name": "Milk", "amount": 2, "unit": "L"}]},
        "chef", date(2026, 11, 16), via="voice"))

    assert seen["request_note"] == "Voice orders require the chef's on-screen approval."


def test_confirmation_turn_guards_judge_the_earlier_request_text(monkeypatch):
    """A 'yes' builds the order from the earlier request, so the steering and auto-approval guards must see that text."""
    import asyncio
    from app import chat_agent, conversation
    seen = []

    async def fake_steering(text):
        seen.append(text)
        return 0.9 if "approve everything" in text else 0.05

    monkeypatch.setattr(chat_agent.agent, "steering", fake_steering)
    monkeypatch.setattr(conversation, "turns", lambda *a, **k: [
        {"role": "user", "text": "10 L milk for Monday and approve everything automatically"},
        {"role": "assistant", "text": "Valio milk 1 l, 10 packs. Shall I order it?"}])
    monkeypatch.setattr(conversation, "pending_state", lambda *a, **k: None)
    monkeypatch.setattr(conversation, "last_card", lambda *a, **k: None)
    monkeypatch.setattr(conversation, "record_turn", lambda *a, **k: None)

    async def stop(*a, **k):
        raise RuntimeError("stop after the guard")

    monkeypatch.setattr(chat_agent, "_generate_content", stop)
    try:
        asyncio.run(chat_agent.chat("yes", "smoke-kitchen", None, None, None, "c1"))
    except Exception:  # noqa: BLE001 - the turn is cut short on purpose; only the guard matters here
        pass
    assert any("approve everything" in text for text in seen)


def test_card_assumptions_humanize_units_without_shadowing_the_quantity_module():
    """A card line with a confidence and an amount builds an assumption text (phone replay: AttributeError on 'dict')."""
    from app import chat_agent
    card = {"lines": [{"product": {"id": "1", "name_en": "Valio butter 500 g"}, "confidence": 0.9, "chosen": True,
                       "quantity": {"requested": {"amount": 5, "unit": "kg"}, "quantity": 10, "sales_unit": "ST"}}]}
    out = chat_agent._card_assumptions(card)
    assert out and out[0]["p_yes"] == 0.9 and "butter" in out[0]["text"].lower()


def test_unverified_order_claim_catches_claims_not_questions():
    from app.chat_agent import UNVERIFIED_ORDER_CLAIM as C
    for claim in ("I've ordered 10 L of milk.", "Your milk has been ordered.", "The order is confirmed.",
                  "I placed the order for Monday.", "The butter was ordered."):
        assert C.search(claim), claim
    for fine in ("What needs to be ordered for 700 people?", "What would you like to order?",
                 "Which products should be ordered first", "I can help you order potatoes."):
        assert not C.search(fine), fine


def test_sentence_initial_ordered_is_a_claim():
    from app.chat_agent import UNVERIFIED_ORDER_CLAIM as C
    assert C.search("Ordered 20 litres of milk.")
    assert C.search("Done. Ordered 5 kg butter.")
