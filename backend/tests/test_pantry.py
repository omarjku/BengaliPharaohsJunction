"""Pantry: what the kitchen has stays out of a menu cart (visible, re-addable); the cart says what its total covers."""
from datetime import datetime, timezone

from conftest import REQ
from fastapi.testclient import TestClient
from test_agent import decisions, shop1  # noqa: F401 - pytest fixtures
from test_menu import PUDDING, fake_gemini

from app import agent, menu, profile
from app.main import app

c = TestClient(app, raise_server_exceptions=False)


def post(have=None, overrides=None):
    body = {"menu_text": "Milk pudding", "covers": 80, "requested_date": REQ.isoformat()}
    if have is not None:
        body["have"] = have
    if overrides:
        body["overrides"] = overrides
    r = c.post("/api/agent/menu", json=body, headers={"X-Agent-Key": "agent-lk"})
    assert r.status_code == 200, r.text
    return r.json()


def test_have_list_leaves_items_out_visibly_and_include_brings_them_back(shop1, monkeypatch):  # noqa: F811
    shop1.products["102"]["net_weight"] = {"unit": "KGM", "value": 0.5}
    fake_gemini(monkeypatch, [PUDDING])
    plain = post()  # no list: today's behaviour
    assert {ln["product_id"] for ln in plain["order_lines"]} == {"463335", "102"} and plain["cart_coverage"]["have"] == 0
    fake_gemini(monkeypatch, [PUDDING])
    body = post(have=["unsalted butter"])
    butter = next(i for i in body["ingredients"] if i["query"] == "butter")
    assert butter["have"] == {"source": "this_order", "matched": "unsalted butter"}
    assert [ln["product_id"] for ln in body["order_lines"]] == ["463335"]  # out of the order and the total
    assert body["cart_total_cents"] < plain["cart_total_cents"] and body["cart_coverage"]["have"] == 1
    assert any(r["message"].startswith("Left out because you have it: butter") for r in body["decision"]["reasons"])
    fake_gemini(monkeypatch, [PUDDING])
    back = post(have=["unsalted butter"], overrides=[{"ingredient": "butter", "include": True}])
    assert {ln["product_id"] for ln in back["order_lines"]} == {"463335", "102"}


def test_matching_never_guesses():
    have = [("flour", "kitchen"), ("salmon", "kitchen"), ("olive oil", "this_order")]
    item = lambda q, **k: {"query": q, "claims": [], "exclude_allergens": [], **k}
    assert menu.have_match(item("wheat flour"), have)["matched"] == "flour"
    assert menu.have_match(item("oil"), have)["matched"] == "olive oil"
    assert menu.have_match(item("salmon fillet"), have) is None  # not the same thing
    assert menu.have_match(item("flour", claims=["FREE_FROM_GLUTEN"]), have) is None  # a diet need isn't assumed met
    assert menu.have_match(item("flour", claims=["FREE_FROM_GLUTEN"]), [("gluten-free flour", "kitchen")])


def test_profile_staples_count_and_orders_ignore_the_pantry(shop1, monkeypatch):  # noqa: F811
    profile.store().add_memory("lapland-kitchen", kind=profile.MemoryKind.PREFERENCE_NOTE, key="staples",
                               text="Staples", value={"items": ["butter"]}, source=profile.MemorySource.ONBOARDING,
                               now=datetime.now(timezone.utc), scope=profile.PreferenceScope.ALWAYS)
    assert ("butter", "kitchen") in menu.pantry("lapland-kitchen", None)
    shop1.products["102"]["net_weight"] = {"unit": "KGM", "value": 0.5}
    fake_gemini(monkeypatch, [PUDDING])
    body = post()
    assert next(i for i in body["ingredients"] if i["query"] == "butter")["have"]["source"] == "kitchen"


def test_cart_coverage_says_what_the_total_covers(shop1, monkeypatch):  # noqa: F811
    shop1.products["102"]["net_weight"] = {"unit": "KGM", "value": 0.5}
    fake_gemini(monkeypatch, [PUDDING])
    real = agent.judge_line

    async def judge(text, p, expl):
        conf, why, weakest = await real(text, p, expl)
        return (0.3 if "butter" in text else conf), why, weakest
    monkeypatch.setattr(agent, "judge_line", judge)
    body = post()
    cov = body["cart_coverage"]
    assert (cov["ingredients"], cov["in_cart"], cov["to_check"]) == (2, 1, 1) and cov["check_total_cents"] > 0
    msg = next(r["message"] for r in body["decision"]["reasons"] if " covers " in r["message"])
    assert msg.startswith(f"EUR {body['cart_total_cents'] / 100:,.2f} covers 1 of 2 ingredients; 1 need your look")


def test_name_pack_size_converts_when_no_weight_is_recorded():
    """The 40-guest menu's blueberries ('PUNNET 125G', no weight recorded) were left out of the cart."""
    p = {"id": "b", "name_en": "BLUEBERRY PUNNET 125G NL/GE/PE", "sales_unit": "ST", "lot_size": 1, "base_unit": "ST",
         "units": {"ST": 1.0}, "volume": None, "net_weight": None}
    q = agent.resolve(p, 4, "kg")
    assert q["quantity"] == 32 and "0.125 kg per piece (from the product name)" in q["explanation"]



def test_a_doubted_line_the_kitchen_has_is_not_counted_as_to_check(shop1, monkeypatch):  # noqa: F811
    shop1.products["102"]["net_weight"] = {"unit": "KGM", "value": 0.5}
    fake_gemini(monkeypatch, [PUDDING])
    real = agent.judge_line

    async def judge(text, p, expl):
        conf, why, weakest = await real(text, p, expl)
        return (0.3 if "butter" in text else conf), why, weakest
    monkeypatch.setattr(agent, "judge_line", judge)
    body = post(have=["butter"])
    assert body["cart_coverage"]["to_check"] == 0 and body["check_lines"] == []
    assert not any(" need your look" in r["message"] or "until you check them" in r["message"]
                   for r in body["decision"]["reasons"])
