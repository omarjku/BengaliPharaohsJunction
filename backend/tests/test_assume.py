"""Room 3 kitchen-assistant assumptions: unit-aware proposals, profiles, speed seams, and off-topic replies."""
import asyncio

import pytest
from conftest import REQ, product, quote
from fastapi.testclient import TestClient
from test_agent import decisions, shop1  # noqa: F401 - pytest fixtures
from test_profile import pizza_shop

from app import agent, ask, config, conversation, live, menu, profile
from app.main import app

c = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def conversation_store(monkeypatch, tmp_path):
    monkeypatch.setattr(conversation, "STORE", tmp_path / "conversations.json")


def _post(text, key="agent-lk", requested=REQ):
    body = {"text": text}
    if requested is not None:
        body["requested_date"] = requested.isoformat()
    r = c.post("/api/agent/ask", json=body, headers={"X-Agent-Key": key})
    assert r.status_code == 200, r.text
    return r.json()


def _reasons(body):
    return body["decision"]["reasons"]


def _fake_order_gemini(monkeypatch, item, assumption=None, topic=None, thinking_seen=None):
    async def fake(system, prompt, schema, thinking=None):
        if schema is ask._INTENT_SCHEMA:
            return {"intent": "order", "covers": None, "topic": topic}
        if schema is agent._PARSE_SCHEMA:
            return {"summary": "x", "items": [item]}
        if schema is agent._ASSUME_SCHEMA:
            if thinking_seen is not None:
                thinking_seen["value"] = thinking
            return assumption
        return None

    monkeypatch.setattr(agent, "_gemini", fake)

    async def match(item, hits):
        return [p["id"] for p in hits]

    monkeypatch.setattr(agent, "match", match)


def _fake_menu_gemini(monkeypatch, dishes, intent="menu", covers=80):
    async def fake(system, prompt, schema, thinking=None):
        if schema is ask._INTENT_SCHEMA:
            return {"intent": intent, "covers": covers, "topic": None}
        if schema is menu._MENU_SCHEMA:
            return {"dishes": list(dishes)}
        return None

    monkeypatch.setattr(agent, "_gemini", fake)

    async def match(item, hits):
        return [p["id"] for p in hits]

    monkeypatch.setattr(agent, "match", match)


def _fake_menu_only(monkeypatch, dishes):
    async def fake(system, prompt, schema, thinking=None):
        if schema is menu._MENU_SCHEMA:
            return {"dishes": list(dishes)}
        return None

    monkeypatch.setattr(agent, "_gemini", fake)

    async def match(item, hits):
        return [p["id"] for p in hits]

    monkeypatch.setattr(agent, "match", match)


def test_natural_unit_drives_piece_question_and_options(shop1, monkeypatch):  # noqa: F811
    pizza_shop(shop1)
    item = {"query": "pizza base", "amount": None, "unit": None, "dietary": []}
    _fake_order_gemini(monkeypatch, item, assumption=None)

    unit, examples = agent.natural_unit(shop1.products["201"])
    assert unit == "pcs" and len(examples) == 3
    body = _post("pizza base for Monday")

    assert body["question"] == "How many pizza bases?"
    assert body["options"] and {o["unit"] for o in body["options"]} == {"pcs"}
    assert all("litre" not in o["label"].lower() and "L" not in o["label"] for o in body["options"])


def test_amountless_product_becomes_held_proposal(shop1, monkeypatch):  # noqa: F811
    pizza_shop(shop1)
    item = {"query": "pizza base", "amount": None, "unit": None, "dietary": []}
    thinking_seen = {}
    _fake_order_gemini(monkeypatch, item, {"amount": 10, "unit": "pcs", "assumption": "One base per guest-sized batch."},
                       thinking_seen=thinking_seen)

    body = _post("pizza base for Monday")
    assert thinking_seen["value"] == {"thinkingBudget": 0}
    assert body["order"] is None and body["decision"]["outcome"] == "ASK_HUMAN"
    assert body["assumptions"] == [{"item": 0, "query": "pizza base", "amount": 10.0, "unit": "pcs",
                                    "text": "One base per guest-sized batch.", "source": "gemini"}]
    assert any(ln["chosen"] and ln["quantity"]["requested"] == {"amount": 10.0, "unit": "pcs"}
               for ln in body["lines"])
    assert body["question"].startswith("I assumed 10 pcs pizza base") and body["conversation_id"]
    assert any(r["code"] == "QTY_AMBIGUOUS" and "One base per guest-sized batch" in r["message"] for r in _reasons(body))

    changed = c.post("/api/agent/ask", headers={"X-Agent-Key": "agent-lk"},
                     json={"follow_up": {"to": body["conversation_id"], "answer": "12 pcs"}})
    assert changed.status_code == 200, changed.text
    out = changed.json()
    assert out["order"] and out["order"]["status"] == "confirmed"
    assert out["request"]["items"][0]["amount"] == 12.0 and "assumptions" not in out


def test_failed_assumption_asks_with_natural_options(shop1, monkeypatch):  # noqa: F811
    pizza_shop(shop1)
    item = {"query": "pizza base", "amount": None, "unit": None, "dietary": []}
    _fake_order_gemini(monkeypatch, item, assumption=None)
    body = _post("pizza base for Monday")

    assert body["order"] is None and body["question"] == "How many pizza bases?"
    assert len(body["options"]) == 3 and all(set(o) == {"label", "amount", "unit"} for o in body["options"])
    assert all(o["unit"] == "pcs" for o in body["options"])
    assert body["conversation_id"]


def test_guest_count_and_day_always_make_a_menu_cart(shop1, monkeypatch):  # noqa: F811
    pizza_shop(shop1)
    dishes = [{"name": "Gluten-free pizza", "ingredients": [
        {"name": "pizza base", "per_cover": 1, "unit": "pcs", "assumption": "One base per guest.", "dietary": []}
    ]}]
    _fake_menu_gemini(monkeypatch, dishes, covers=80)
    body = _post("Gluten-free pizza for 80 guests on Monday")

    assert body["intent"] == "menu" and body["covers"] == 80
    assert body["question"] is None and body["order_lines"]
    assert body["decision"]["outcome"] == "ASK_HUMAN"


def test_menu_route_reuses_precomputed_steering(shop1, monkeypatch):  # noqa: F811
    pizza_shop(shop1)
    dishes = [{"name": "Pizza", "ingredients": [
        {"name": "pizza base", "per_cover": 1, "unit": "pcs", "assumption": "One base per guest.", "dietary": []}
    ]}]
    _fake_menu_gemini(monkeypatch, dishes, covers=80)
    calls = 0
    original = agent.steering

    async def counted(text):
        nonlocal calls
        calls += 1
        return await original(text)

    monkeypatch.setattr(agent, "steering", counted)
    body = _post("Pizza for 80 guests on Monday")
    assert body["order_lines"] and calls == 1


def test_same_dish_assumptions_share_one_decisions_input(shop1, monkeypatch, decisions):  # noqa: F811
    pizza_shop(shop1)
    dishes = [{"name": "Pizza", "ingredients": [
        {"name": "pizza base", "per_cover": 1, "unit": "pcs", "assumption": "One base.", "dietary": []},
        {"name": "cheese", "per_cover": 0.1, "unit": "kg", "assumption": "100 g cheese.", "dietary": []}
    ]}]
    _fake_menu_only(monkeypatch, dishes)
    r = c.post("/api/agent/menu", headers={"X-Agent-Key": "agent-lk"},
               json={"menu_text": "Pizza with pizza base and cheese", "covers": 10,
                     "requested_date": REQ.isoformat()})
    assert r.status_code == 200, r.text
    checks = [q for text, q in decisions["calls"] if "Dish: Pizza" in text and any(k.startswith("needed_") for k in q)]
    assert len(checks) == 1 and set(checks[0]) == {"needed_0", "amount_0", "needed_1", "amount_1"}


def test_menu_profile_default_is_relevant_and_visible(shop1, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "AGENT_KEYS", config.AGENT_KEYS + ",agent-hb=helsinki-bistro")
    pizza_shop(shop1)
    for pid, name, claims in (("205", "Gluten-free flour", ("FREE_FROM_GLUTEN",)),
                              ("206", "Gluten-free cheese", ("FREE_FROM_GLUTEN",)),
                              ("207", "Cooking oil", ()), ("208", "Table salt", ())):
        p = product(pid, name, claims=claims, contains=())
        p.update(base_unit="ST", units={"ST": 1.0}, volume={"unit": "LTR", "value": 1.0}, net_weight=None)
        shop1.products[pid], shop1.quotes[pid] = p, quote(pid, price=1.0)
    dishes = [{"name": "Pizza", "ingredients": [
        {"name": "flour", "per_cover": 0.2, "unit": "kg", "assumption": "200 g flour.", "dietary": []},
        {"name": "cheese", "per_cover": 0.1, "unit": "kg", "assumption": "100 g cheese.", "dietary": []},
        {"name": "oil", "per_cover": 0.01, "unit": "L", "assumption": "10 ml oil.", "dietary": []},
        {"name": "salt", "per_cover": 2, "unit": "g", "assumption": "2 g salt.", "dietary": []},
    ]}]
    _fake_menu_only(monkeypatch, dishes)
    r = c.post("/api/agent/menu", headers={"X-Agent-Key": "agent-hb"},
               json={"menu_text": "Pizza with flour, cheese, oil and salt", "covers": 10,
                     "requested_date": REQ.isoformat()})
    assert r.status_code == 200, r.text
    body = r.json()
    ingredients = {i["query"]: i for i in body["ingredients"]}
    assert ingredients["flour"]["claims"] == ["FREE_FROM_GLUTEN"]
    assert ingredients["cheese"]["claims"] == ["FREE_FROM_GLUTEN"]
    assert ingredients["oil"]["claims"] == [] and ingredients["salt"]["claims"] == []
    profile_reasons = [x for x in _reasons(body) if x["code"] == "PROFILE_DEFAULT"]
    assert {x["product_id"] for x in profile_reasons} >= {"205", "206"}
    assert not any(x["product_id"] in {"207", "208"} for x in profile_reasons)

    _fake_menu_only(monkeypatch, dishes)
    r = c.post("/api/agent/menu", headers={"X-Agent-Key": "agent-hb"},
               json={"menu_text": "Regular pizza with flour, cheese, oil and salt", "covers": 10,
                     "requested_date": REQ.isoformat()})
    assert r.status_code == 200
    assert not any(x["code"] == "PROFILE_DEFAULT" for x in _reasons(r.json()))


def test_guest_extras_memory_sets_high_spare(shop1):  # noqa: F811
    assert agent.spare_level("helsinki-bistro") == "high"
    profile.store().add_memory("helsinki-bistro", kind=profile.MemoryKind.PREFERENCE_NOTE, key="spare_level",
                               text="No spare", value={"level": "none"}, source=profile.MemorySource.ONBOARDING,
                               now=profile.datetime.now(profile.timezone.utc), scope=profile.PreferenceScope.ALWAYS)
    assert agent.spare_level("helsinki-bistro") == "none"


def test_exact_input_decisions_are_grouped_without_combining_candidates(monkeypatch):
    calls = []

    async def fake(input_text, questions):
        calls.append((input_text, questions))
        return {key: {"noul": 0.9} for key in questions}

    monkeypatch.setattr(agent, "_decisions", fake)
    q = {"type": "noul", "instructions": "x", "criteria": {"true_description": "yes", "false_description": "no"}}
    answers = asyncio.run(agent._decisions_grouped([("same", "meets", q), ("same", "qty", q),
                                                    ("candidate-a", "meets", q), ("candidate-b", "meets", q)]))
    assert len(calls) == 3
    assert next(questions for text, questions in calls if text == "same").keys() == {"meets", "qty"}
    assert answers == {"meets": {"noul": 0.9}, "qty": {"noul": 0.9},
                       "candidate-a:meets": {"noul": 0.9}, "candidate-b:meets": {"noul": 0.9}}


def test_off_topic_reply_is_specific_and_sanitized(shop1, monkeypatch):  # noqa: F811
    async def fake(system, prompt, schema, *_):
        if schema is ask._INTENT_SCHEMA:
            return {"intent": "unclear", "covers": None, "topic": "LEGO sets!!! <ignore rules> weather flights"}
        if schema is agent._PARSE_SCHEMA:
            return {"summary": "x", "items": []}
        return None

    monkeypatch.setattr(agent, "_gemini", fake)
    body = _post("Can you find LEGO sets?", requested=None)
    assert body["question"] == ("I order food and kitchen supplies from Valio, so I can't help with LEGO sets ignore "
                                 "rules. What do you need for the kitchen?")
    assert "order" not in body and "lines" not in body
    assert len(body["question"]) <= 200 and "<" not in body["question"]


def test_live_prompt_declines_off_topic_without_a_tool_call():
    assert "food and kitchen supplies" in live.SYSTEM
    assert "LEGO" in live.SYSTEM and "do not call tools" in live.SYSTEM
