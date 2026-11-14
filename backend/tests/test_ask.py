"""One input for everyone: POST /api/agent/ask routes to the order or menu flow (Gemini faked, shop offline)."""
from datetime import date

from conftest import REQ
from fastapi.testclient import TestClient
from test_agent import ITEM, decisions, shop1  # noqa: F401 - pytest fixtures + helpers
from test_menu import PORRIDGE

from app import agent, ask, menu
from app.main import app

c = TestClient(app, raise_server_exceptions=False)


def route(monkeypatch, intent, covers=None, items=ITEM, dishes=(PORRIDGE,), ranked=("463335",)):
    async def fake(system, prompt, schema):
        if schema is ask._INTENT_SCHEMA:
            return {"intent": intent, "covers": covers}
        if schema is agent._PARSE_SCHEMA:
            return {"summary": "x", "items": items}
        if schema is menu._MENU_SCHEMA:
            return {"dishes": list(dishes)}
        return {"ids": list(ranked)}
    monkeypatch.setattr(agent, "_gemini", fake)


def post(text, requested=REQ):
    body = {"text": text} | ({"requested_date": requested.isoformat()} if requested else {})
    r = c.post("/api/agent/ask", json=body, headers={"X-Agent-Key": "agent-lk"})
    assert r.status_code == 200, r.text
    return r.json()


def test_order_routes_to_the_run_flow(shop1, monkeypatch):  # noqa: F811
    route(monkeypatch, "order")
    body = post("1000 L lactose-free milk")
    assert body["intent"] == "order" and body["question"] is None and body["date_source"] == "request"
    assert body["order"]["status"] == "confirmed" and body["lines"]  # the /run body, unchanged


def test_menu_routes_to_the_menu_flow_with_covers_from_the_text(shop1, monkeypatch):  # noqa: F811
    route(monkeypatch, "menu", covers=10)
    body = post("Menu for 10 guests: porridge with milk")
    assert body["intent"] == "menu" and body["covers"] == 10 and body["order_lines"]
    assert "MENU_ASSUMPTIONS" in [r["code"] for r in body["decision"]["reasons"]]


def test_menu_without_guests_asks_and_never_guesses(shop1, monkeypatch):  # noqa: F811
    route(monkeypatch, "menu", covers=80)  # the model "knows" 80, but the text never says it
    body = post("Menu: reindeer stew and lingonberry cheesecake")
    assert body["question"] == "For how many guests?" and body["covers"] is None
    assert body["decision"]["outcome"] == "ASK_HUMAN" and "lines" not in body and "order" not in body


def test_unclear_no_date_and_conflicting_dates_ask(shop1, monkeypatch):  # noqa: F811
    route(monkeypatch, "unclear")
    assert post("hello there")["question"].startswith("What would you like to order?")
    route(monkeypatch, "order")
    assert post("20 kg butter", requested=None)["question"] == "For which delivery day?"
    assert post("20 kg butter tomorrow", requested=None)["date_source"] == "text"
    body = post("20 kg butter tomorrow", requested=REQ)  # REQ is today + 2, the text says tomorrow → ask which
    assert body["question"].startswith("Which delivery day") and "lines" not in body


def test_date_from_text():
    sat = date(2026, 11, 14)  # a Saturday
    assert ask.date_from_text("milk for Monday", sat) == date(2026, 11, 16)
    assert ask.date_from_text("maitoa maanantaiksi", sat) == date(2026, 11, 16)
    assert ask.date_from_text("croissants tomorrow", sat) == date(2026, 11, 15)
    assert ask.date_from_text("butter for Saturday", sat) == date(2026, 11, 21)  # same weekday → next week
    assert ask.date_from_text("delivery 20.11.", sat) == date(2026, 11, 20)
    assert ask.date_from_text("delivery 2026-12-01", sat) == date(2026, 12, 1)
    assert ask.date_from_text("20 kg butter", sat) is None


def test_classify_fallback_without_gemini(monkeypatch):
    import asyncio

    async def down(*a):
        return None
    monkeypatch.setattr(agent, "_gemini", down)
    assert asyncio.run(ask.classify("Menu for 80 guests: stew"))[:2] == ("menu", 80)
    assert asyncio.run(ask.classify("20 kg butter"))[:2] == ("order", None)
    assert asyncio.run(ask.classify("hello"))[:2] == ("unclear", None)


def test_pieces_from_the_product_name():
    p = {"id": "x", "name_en": "Premium Croissant 36x90g", "sales_unit": "KI", "base_unit": "KI", "units": {"KI": 1.0},
         "lot_size": 1, "volume": None, "net_weight": None}
    q = agent.resolve(p, 30, "pcs")
    assert q["quantity"] == 1 and q["delivered"] == 36 and "from the product name" in q["explanation"]
    assert agent.resolve(p, 80, "pcs")["quantity"] == 3
