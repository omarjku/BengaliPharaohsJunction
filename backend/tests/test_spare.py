"""Kitchen loss: spare on menus (visible, packs first), a one-tap suggestion on direct orders, the kitchen's level."""
from datetime import datetime, timezone

from conftest import REQ
from fastapi.testclient import TestClient
from test_agent import ITEM, MILK, decisions, fake_match, run, shop1  # noqa: F401 - pytest fixtures + helpers
from test_menu import PORRIDGE

from app import agent, config, menu, profile
from app.main import app

c = TestClient(app, raise_server_exceptions=False)


def fake(monkeypatch, spare=None, dishes=(PORRIDGE,), items=ITEM):
    seen = []

    async def gemini(system, prompt, schema, *_):
        seen.append(schema)
        if schema is menu._MENU_SCHEMA:
            return {"dishes": list(dishes)}
        if schema is agent._SPARE_SCHEMA:
            return {"items": [{"ingredient": k, "spare_percent": p, "reason": r} for k, (p, r) in (spare or {}).items()]}
        if schema is agent._PARSE_SCHEMA:
            return {"summary": "x", "items": items}
        return None
    monkeypatch.setattr(agent, "_gemini", gemini)
    fake_match(monkeypatch, ["463335"])
    return seen


def post_menu(overrides=None, headers=None):
    body = {"menu_text": "Porridge with milk", "covers": 80, "requested_date": REQ.isoformat()}
    if overrides:
        body["overrides"] = overrides
    r = c.post("/api/agent/menu", json=body, headers=headers or {"X-Agent-Key": "agent-lk"})
    assert r.status_code == 200, r.text
    return r.json()


def test_rule1_menu_spare_is_visible_clamped_and_in_the_cart(shop1, monkeypatch):  # noqa: F811
    fake(monkeypatch, {"milk": (10, "Porridge can scorch; a spare batch is common")})
    body = post_menu()
    ing = body["ingredients"][0]
    assert (ing["needed_amount"], ing["spare_percent"], ing["spare_source"]) == (16.0, 10.0, "gemini")
    assert ing["spare_reason"].startswith("Porridge can scorch") and ing["spare_from_rounding"] == 0.0
    assert body["order_lines"] == [{"product_id": "463335", "quantity": 18}]  # 16 L + 10% = 17.6 → 18 packs of 1 L
    msg = [r["message"] for r in body["decision"]["reasons"] if "spare for kitchen loss" in r["message"]]
    assert msg == ["Includes about 12% spare for kitchen loss; 0% of it is pack rounding."]
    assert body["decision"]["outcome"] == "ASK_HUMAN" and "order" not in body  # a menu never orders by itself
    assert agent.spare_target((50, "x"), None)[0] == 10.0  # no kitchen level: Gemini's proposal, at most 10%
    assert agent.spare_target((50, "x"), "high")[0] == 20.0 and agent.spare_target((8, "x"), "low")[0] == 4.0


def test_rule2_pack_rounding_counts_first_never_double():
    ing = [{"query": "milk", "amount": 16.0, "unit": "L"}]
    ln = {"item": 0, "quantity": {"quantity": 2, "delivered": 20.0}, "quote": {"price": 10.0},
          "product": {"id": "p", "sales_unit": "KI"}, "line_total_cents": 2000}
    out = menu.add_spare(ing, [ln], {"milk": (10.0, "loss")}, None, {})
    assert ln["quantity"]["quantity"] == 2  # packs already give 25%: nothing more is bought
    assert ing[0]["spare_from_rounding"] == 25.0 and ing[0]["spare_percent"] == 10.0
    assert out[0].message == "Includes about 25% spare for kitchen loss; 25% of it is pack rounding."


def test_rule3_direct_orders_only_get_an_offer(shop1, monkeypatch):  # noqa: F811
    fake(monkeypatch, {"milk": (5, "Milk gets spilled at the coffee station")})
    plain = run()
    assert plain["spare_suggestion"] is None and plain["order"]["total_cents"] == 140000  # no level: nothing at all
    monkeypatch.setattr(agent, "spare_level", lambda buyer: "normal")
    body = run(MILK + " again")
    s = body["spare_suggestion"]
    assert s == {"percent": 5.0, "extra_quantity": 50.0, "unit": "L", "extra_sales_units": 50,
                 "extra_cost_cents": 7000, "reason": "Milk gets spilled at the coffee station"}
    chosen = [ln for ln in body["lines"] if ln["chosen"]][0]
    assert chosen["quantity"]["quantity"] == 1000  # the chef asked for 1000 L: nothing added silently


def test_rule4_kitchen_level_comes_from_the_profile(shop1, monkeypatch):  # noqa: F811
    assert agent.spare_level("lapland-kitchen") is None
    profile.store().add_memory("lapland-kitchen", kind=profile.MemoryKind.PREFERENCE_NOTE, key="spare_level",
                               text="Normal spare", value={"level": "none"}, source=profile.MemorySource.ONBOARDING,
                               now=datetime.now(timezone.utc), scope=profile.PreferenceScope.ALWAYS)
    assert agent.spare_level("lapland-kitchen") == "none"
    seen = fake(monkeypatch, {"milk": (10, "x")})
    body = post_menu()
    assert agent._SPARE_SCHEMA not in seen  # 'none': Gemini isn't even asked
    assert body["ingredients"][0]["spare_percent"] == 0.0 and body["order_lines"][0]["quantity"] == 16


def test_rule5_chef_sets_the_spare_with_the_approver_key(shop1, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "APPROVER_KEYS", config.APPROVER_KEYS + ",appr-lk=lapland-kitchen:Chef Aino")
    fake(monkeypatch, {"milk": (10, "x")})
    chef = post_menu([{"ingredient": "milk", "spare_percent": 0}],
                     {"X-Agent-Key": "agent-lk", "X-Approver-Key": "appr-lk"})
    assert chef["ingredients"][0]["spare_source"] == "chef" and chef["order_lines"][0]["quantity"] == 16
    fake(monkeypatch, {"milk": (10, "x")})
    agent_only = post_menu([{"ingredient": "milk", "spare_percent": 0}])
    assert agent_only["ingredients"][0]["spare_source"] == "gemini"
    assert any("can only be changed by the chef" in r["message"] for r in agent_only["decision"]["reasons"])
