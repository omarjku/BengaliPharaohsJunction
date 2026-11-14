"""Zoha's redesign: the memory panel (list, forget), 'remember this', and editable menu portions."""
from conftest import REQ
from fastapi.testclient import TestClient
from test_agent import decisions, shop1  # noqa: F401 - pytest fixtures
from test_menu import PORRIDGE, fake_gemini

from app import config, profile
from app.main import app

c = TestClient(app, raise_server_exceptions=False)
HB, LK = {"X-Approver-Key": "appr-hb"}, {"X-Approver-Key": "appr-lk"}


def keys(monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", config.AGENT_KEYS + ",agent-hb=helsinki-bistro")
    monkeypatch.setattr(config, "APPROVER_KEYS", config.APPROVER_KEYS
                        + ",appr-hb=helsinki-bistro:Chef Mikko,appr-lk=lapland-kitchen:Chef Aino")


def memories(headers={"X-Agent-Key": "agent-hb"}):
    return c.get("/api/profile", headers=headers).json()["memories"]


def test_memory_panel_lists_and_forgets_and_seeds_stay_forgotten(shop1, monkeypatch):  # noqa: F811
    keys(monkeypatch)
    mems = memories()
    gf = next(m for m in mems if m["kind"] == "business_type")
    assert set(gf) >= {"id", "kind", "text", "scope", "source", "used_because"}
    assert gf["scope"] == "always" and gf["source"] == "onboarding" and gf["used_because"].startswith("onboarding")
    assert c.delete(f"/api/profile/memories/{gf['id']}", headers={"X-Agent-Key": "agent-hb"}).status_code == 401
    assert c.delete(f"/api/profile/memories/{gf['id']}", headers=LK).status_code == 404  # another buyer's
    assert c.delete("/api/profile/memories/mem_000000000000", headers=HB).status_code == 404
    r = c.delete(f"/api/profile/memories/{gf['id']}", headers=HB)
    assert r.status_code == 200 and r.json()["dietary"] == []
    profile._STORE[:] = [None, None]  # a restart: the seed loader runs again
    assert gf["id"] not in {m["id"] for m in memories()}
    assert c.delete(f"/api/profile/memories/{gf['id']}", headers=HB).status_code == 404  # already forgotten
    profile.reset("helsinki-bistro")  # what the per-buyer demo reset calls
    assert gf["id"] in {m["id"] for m in memories()}


def test_remember_this_adds_a_usual_product(shop1, monkeypatch):  # noqa: F811
    keys(monkeypatch)
    r = c.post("/api/profile/memories", json={"kind": "usual_product", "product_id": "476240", "scope": "this_order",
                                              "text": "Guests love it"}, headers=HB)
    assert r.status_code == 200, r.text
    m = r.json()["memory"]
    assert m["scope"] == "this_order" and m["product_id"] == "476240" and m["text"] == "Guests love it"
    assert m["source"] == "chosen_alternative" and m["id"] in {x["id"] for x in r.json()["profile"]["memories"]}
    assert "476240" in profile.usual("helsinki-bistro")  # the near-tie preference picks it up
    assert c.post("/api/profile/memories", json={"product_id": "999999", "scope": "always"},
                  headers=HB).status_code == 422  # not in the catalogue
    assert c.post("/api/profile/memories", json={"product_id": "476240"},
                  headers={"X-Agent-Key": "agent-hb"}).status_code == 401  # the agent can't decide what to remember


def post_menu(overrides=None, chef=True):
    body = {"menu_text": "Porridge with milk", "covers": 80, "requested_date": REQ.isoformat()}
    if overrides is not None:
        body["overrides"] = overrides
    r = c.post("/api/agent/menu", json=body, headers={"X-Agent-Key": "agent-lk"} | (LK if chef else {}))
    assert r.status_code == 200, r.text
    return r.json()


def test_menu_portions_set_by_the_chef_rescale_the_cart(shop1, monkeypatch):  # noqa: F811
    keys(monkeypatch)
    fake_gemini(monkeypatch, [PORRIDGE])
    plain = post_menu()
    assert plain["ingredients"][0]["amount"] == 16.0 and plain["assumptions"][0]["set_by"] == "gemini"
    fake_gemini(monkeypatch, [PORRIDGE])
    edited = post_menu([{"ingredient": "milk", "per_cover": 3, "unit": "dl"}])
    assert edited["ingredients"][0]["amount"] == 24.0  # 80 x 3 dl
    a = edited["assumptions"][0]
    assert a["set_by"] == "chef" and a["per_cover"] == 3 and a["check"] is None and a["flagged"] is False
    assert "set by the chef" in a["text"]
    assert edited["cart_total_cents"] == plain["cart_total_cents"] * 24 // 16
    assert edited["order_lines"] and edited["decision"]["outcome"] == "ASK_HUMAN" and "order" not in edited
    fake_gemini(monkeypatch, [PORRIDGE])
    missing = post_menu([{"ingredient": "saffron", "per_cover": 1, "unit": "g"}])
    assert any("No ingredient 'saffron'" in r["message"] for r in missing["decision"]["reasons"])
    assert missing["ingredients"][0]["amount"] == 16.0



def test_an_agent_can_not_claim_a_portion_is_the_chefs(shop1, monkeypatch):  # noqa: F811
    """Security review: with only the agent key, an override is 'changed by the agent' and still checked."""
    keys(monkeypatch)
    fake_gemini(monkeypatch, [PORRIDGE])
    body = post_menu([{"ingredient": "milk", "per_cover": 3, "unit": "dl"}], chef=False)
    a = body["assumptions"][0]
    assert a["set_by"] == "agent" and a["check"] is not None and "changed by the agent" in a["text"]
    assert body["ingredients"][0]["amount"] == 24.0
    fake_gemini(monkeypatch, [PORRIDGE])
    r = c.post("/api/agent/menu", json={"menu_text": "Porridge with milk", "covers": 80, "requested_date":
               REQ.isoformat(), "overrides": [{"ingredient": "milk", "per_cover": 3, "unit": "dl"}]},
               headers={"X-Agent-Key": "agent-lk", "X-Approver-Key": "appr-hb"})  # another buyer's approver
    assert r.status_code == 403  # refused (and audited), never quietly downgraded
    r = c.post("/api/agent/menu", json={"menu_text": "Porridge with milk", "covers": 80, "requested_date":
               REQ.isoformat(), "overrides": [{"ingredient": "milk", "per_cover": 3, "unit": "dl"}]},
               headers={"X-Agent-Key": "agent-lk", "X-Approver-Key": "wrong"})
    assert r.status_code == 401
