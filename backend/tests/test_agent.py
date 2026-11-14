"""M1 buyer agent end to end: POST /api/agent/run on the offline shop (conftest.py), Gemini faked."""
import pytest
from conftest import REQ
from fastapi.testclient import TestClient

from app import agent, valio
from app.main import app

c = TestClient(app, raise_server_exceptions=False)
MILK = "1000 L lactose-free milk for Monday"


@pytest.fixture
def shop1(shop):
    """The gate fixture plus the unit data quantity.resolve needs: 1 L per ST, 10 ST per KI."""
    for p in shop.products.values():
        p.update(base_unit="ST", units={"ST": 1.0, "KI": 10.0}, volume={"unit": "LTR", "value": 1.0}, net_weight=None)
    return shop


def gemini(monkeypatch, items=None, ranked=None):
    """Fake Gemini: parse → items, rank → ranked ids (None = Gemini down for that call)."""
    calls = []

    async def fake(prompt, schema):
        calls.append(prompt)
        if schema is agent._PARSE_SCHEMA:
            return None if items is None else {"summary": "Lactose-free milk for Monday", "items": items}
        return None if ranked is None else {"ids": ranked}
    monkeypatch.setattr(agent, "_gemini", fake)
    return calls


def run(text=MILK, buyer="lapland-kitchen"):
    r = c.post("/api/agent/run", json={"text": text, "requested_date": REQ.isoformat(), "buyer_id": buyer})
    assert r.status_code == 200, r.text
    return r.json()


def codes(body):
    return [r["code"] for r in body["decision"]["reasons"]]


def audit(buyer="lapland-kitchen"):
    return c.get("/api/audit", params={"buyer_id": buyer}).json()


ITEM = [{"query": "milk", "amount": 1000, "unit": "L", "dietary": ["lactose_free"]}]


def test_milk_end_to_end_orders_through_front_door(shop1, monkeypatch):
    calls = gemini(monkeypatch, ITEM, ranked=["462775", "463335", "999"])  # 999 isn't a search hit: ignored
    body = run()
    assert body["request"]["items"] == [{"query": "milk", "amount": 1000.0, "unit": "L",
                                         "claims": ["FREE_FROM_LACTOSE"], "exclude_allergens": []}]
    assert [ln["product"]["id"] for ln in body["lines"]] == ["462775", "463335"]
    arla, eila = body["lines"]
    assert not arla["chosen"] and "Only 51" in arla["why"]  # partial stock → the next match is chosen
    assert eila["chosen"] and eila["quantity"]["quantity"] == 1000 and eila["line_total_cents"] == 140000
    assert eila["quote"]["price"] == 1.4 and "1,000 L" in eila["why"]
    assert body["order"]["status"] == "confirmed" and body["decision"]["outcome"] == "AUTO"
    assert body["order"]["lines"][0]["quantity"] == 1000 and body["audit_id"] == body["order"]["audit_id"]
    agent_entry, door_entry = audit()
    assert agent_entry["actor"] == "buyer_agent" and agent_entry["input"]["request"]["text"] == MILK
    assert agent_entry["input"]["mandate"]["id"] == "lapland-kitchen-2026-11"
    assert agent_entry["rejected_options"][0]["product_id"] == "462775"
    assert door_entry["actor"] == "valio_front_door" and door_entry["id"] == body["audit_id"]
    assert len(calls) == 2


def test_over_auto_limit_is_held_by_the_front_door(shop1, monkeypatch):
    gemini(monkeypatch, [dict(ITEM[0], amount=2000)], ranked=["463335"])
    body = run("2000 L lactose-free milk for Monday")
    assert body["order"]["status"] == "pending_approval" and body["decision"]["outcome"] == "ASK_HUMAN"
    assert {"SPEND_OVER_LIMIT", "LINE_OVER_CAP"} <= set(codes(body))
    gemini(monkeypatch, [dict(ITEM[0], amount=2000)], ranked=["463335", "476240"])
    body = run("2000 L lactose-free milk for Monday")  # the agent's other match is offered to the approver
    assert [a["product_id"] for a in body["decision"]["alternatives"]] == ["476240"]


def test_gemini_down_uses_fallback_parser_and_search_order(shop1, monkeypatch):
    gemini(monkeypatch, items=None, ranked=None)
    body = run()
    assert body["request"]["summary"].startswith("[fallback parser")
    assert body["request"]["items"][0]["query"] == "milk" and body["request"]["items"][0]["amount"] == 1000
    assert body["order"]["status"] == "confirmed" and "LOW_CONFIDENCE" in codes(body)
    assert sum(ln["chosen"] for ln in body["lines"]) == 1


def test_trap_cutoff_passed_and_terminal_asks_human_without_ordering(shop1, monkeypatch):
    gemini(monkeypatch, ITEM, ranked=["463038"])  # Terminal: closingTime already passed, stock 999999 = unknown
    body = run()
    assert body["order"] is None and body["decision"]["outcome"] == "ASK_HUMAN"
    assert {"CUTOFF_PASSED", "QTY_UNKNOWN"} <= set(codes(body))
    assert body["lines"][0]["chosen"] is False and body["audit_id"]
    assert body["decision"]["alternatives"]  # orderable substitutes, found and re-quoted by the door's finder
    [entry] = audit()
    assert entry["id"] == body["audit_id"] and entry["rejected_options"][0]["product_id"] == "463038"


def test_missing_amount_asks_instead_of_guessing(shop1, monkeypatch):
    gemini(monkeypatch, [dict(ITEM[0], amount=None, unit=None)], ranked=["463335"])
    body = run("lactose-free milk for Monday")
    assert body["order"] is None and codes(body) == ["QTY_AMBIGUOUS"]


def test_no_match_and_unknown_buyer(shop1, monkeypatch):
    gemini(monkeypatch, ITEM, ranked=[])
    body = run(buyer="nobody")
    assert body["order"] is None and {"UNKNOWN_PRODUCT", "MANDATE_MISSING"} <= set(codes(body))


def test_valio_down_is_a_decision_not_a_500(shop1, monkeypatch):
    gemini(monkeypatch, ITEM, ranked=["463335"])

    async def boom(*a, **k):
        raise RuntimeError("upstream")
    monkeypatch.setattr(valio, "get_quotes", boom)
    body = run()
    assert body["order"] is None and codes(body) == ["ENGINE_ERROR"]


def test_fallback_parse():
    items = agent.fallback_parse("1,000 L lactose-free milk for Monday, 20 kg butter and 12 kpl gluten-free buns")
    assert [(i["query"], i["amount"], i["unit"]) for i in items] == [
        ("milk", 1000.0, "L"), ("butter", 20.0, "kg"), ("buns", 12.0, "pcs")]
    assert items[0]["claims"] == ["FREE_FROM_LACTOSE"] and items[2]["claims"] == ["FREE_FROM_GLUTEN"]
    assert agent.fallback_parse("some dairy-free cream")[0] == {
        "query": "some cream", "amount": None, "unit": None, "claims": [], "exclude_allergens": ["AM"]}


def test_client_cannot_send_a_mandate(shop1):
    r = c.post("/api/agent/run", json={"text": MILK, "requested_date": REQ.isoformat(), "buyer_id": "lapland-kitchen",
                                       "mandate": {"id": "x", "buyer_id": "lapland-kitchen"}})
    assert r.status_code == 422
