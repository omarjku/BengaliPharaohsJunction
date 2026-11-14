import asyncio
import copy
from datetime import date
from types import SimpleNamespace

from app import ask, auth, chat_agent, mandates, orders, signing
from conftest import REQ, store_mandate


CONFIRMED_MESSAGE = "This order is already confirmed; cancel or change it on screen (needs your approval)."


def _place(qty: float) -> dict:
    principal = auth.Principal("chef", "chef", "agent-chef")

    async def place():
        token = auth.CURRENT_AGENT.set(principal)
        try:
            return await orders.place("chef", REQ, [SimpleNamespace(product_id="463335", quantity=qty)],
                                      mandates.get("chef"))
        finally:
            auth.CURRENT_AGENT.reset(token)

    return asyncio.run(place())


def _agent_order(order_id: str) -> dict:
    return orders._store()[order_id]


def test_agent_withdraws_its_own_pending_order_without_human_signoff(shop):
    store_mandate({"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9,
                   "hard_rules": [{"kind": "auto_approve_limit_cents", "value": 100}]})
    placed = _place(1000)
    order = _agent_order(placed["order_id"])

    assert order["status"] == "pending_approval"
    assert asyncio.run(ask._reject_order(order, "chef")) is True
    assert order["status"] == "rejected"
    assert order["signed_off_by"] is None
    audit = orders.audit_log("chef", 20)[-1]
    assert audit["actor"] == "agent:agent-chef:withdrawn_by_agent"
    assert audit["front_door"]["action"] == "withdrawn_by_agent"
    assert audit["front_door"]["signed_off_by"] is None
    assert "signed_statement" in audit["front_door"] and "signature" in audit["front_door"]
    assert signing.verify(audit["front_door"]["signed_statement"], audit["front_door"]["signature"])


def test_different_agent_cannot_withdraw_the_pending_order(shop):
    store_mandate({"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9,
                   "hard_rules": [{"kind": "auto_approve_limit_cents", "value": 100}]})
    placed = _place(1000)
    order = _agent_order(placed["order_id"])
    before = copy.deepcopy(order)
    token = auth.CURRENT_AGENT.set(auth.Principal("chef", "chef", "agent-other"))
    try:
        assert asyncio.run(ask._reject_order(order, "chef")) is False
    finally:
        auth.CURRENT_AGENT.reset(token)
    assert order == before


def test_agent_cancel_of_confirmed_order_is_refused_and_unchanged(shop):
    store_mandate({"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9,
                   "hard_rules": [{"kind": "auto_approve_limit_cents", "value": 100000}]})
    placed = _place(1)
    order = _agent_order(placed["order_id"])
    before = copy.deepcopy(order)

    result = asyncio.run(ask._cancel_named_order("cancel the order", "chef", {"order_id": order["id"]}))

    assert result["reply"] == CONFIRMED_MESSAGE
    assert order == before


def test_agent_change_of_confirmed_order_creates_no_new_order(shop, monkeypatch):
    store_mandate({"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9,
                   "hard_rules": [{"kind": "auto_approve_limit_cents", "value": 100000}]})
    placed = _place(1)
    order = _agent_order(placed["order_id"])
    before = copy.deepcopy(order)
    monkeypatch.setattr(ask.agent, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("confirmed order must not be rerun")))

    result = asyncio.run(ask._execute_action(
        {"intent": "change_cart", "slots": {"items": [{"name": "Eila milk 1 l", "amount": 2, "unit": "ST"}]}},
        "make it 2 ST", REQ, "chef", date.today(), "gemini", 0.0,
        {"order_id": order["id"], "requested_date": order["requested_date"], "order": order}))

    assert result["reply"] == CONFIRMED_MESSAGE
    assert order == before
    assert len(orders._store()) == 1


def test_chat_cancel_and_change_tools_refuse_confirmed_order(shop, monkeypatch):
    store_mandate({"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9,
                   "hard_rules": [{"kind": "auto_approve_limit_cents", "value": 100000}]})
    placed = _place(1)
    order = _agent_order(placed["order_id"])
    before = copy.deepcopy(order)
    monkeypatch.setattr(chat_agent, "_turn_guard", lambda *_args, **_kwargs: asyncio.sleep(0, result={"steer": 0.0}))
    monkeypatch.setattr(chat_agent.ask.agent, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("confirmed order must not be rerun")))

    cancelled = asyncio.run(chat_agent._cancel_order({"order_id": order["id"]}, "chef"))
    changed = asyncio.run(chat_agent._change_order(
        {"order_id": order["id"], "changes": [{"name": "Eila milk 1 l", "amount": 2, "unit": "ST"}]},
        "chef", REQ))

    assert cancelled["hold_reasons"] == [CONFIRMED_MESSAGE]
    assert changed["hold_reasons"] == [CONFIRMED_MESSAGE]
    assert order == before
