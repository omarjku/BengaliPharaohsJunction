import asyncio

from conftest import REQ, product, quote
from test_agent import decisions  # noqa: F401 - pytest fixture

from app import agent, diet, menu


def _catalogue_product(shop, pid, name, *, claims=(), contains=(), may=(), free=(), price=2.0):
    p = product(pid, name, unit="ST", lot=0.01, claims=claims, contains=contains, may=may)
    p["allergens"]["free_from"] = list(free)
    p.update(base_unit="ST", units={"ST": 1.0}, volume={"unit": "LTR", "value": 1.0},
             net_weight={"unit": "KGM", "value": 1.0})
    shop.products[pid] = p
    shop.quotes[pid] = quote(pid, price=price)
    return p


def test_diet_verdict_uses_allergen_evidence_and_claims():
    wheat = {"claims": [], "allergens": {"contains": ["AW"], "may_contain": [], "free_from": []}}
    plain_carrot = {"claims": [], "allergens": {"contains": [], "may_contain": [], "free_from": ["AW"]}}
    labelled = {"claims": ["FREE_FROM_GLUTEN"], "allergens": {}}

    assert diet.contradicts(wheat, "gluten_free")
    assert diet.verdict(wheat, "gluten_free", True) == "contradicts"
    assert diet.verdict(plain_carrot, "gluten_free", False) == "ok"
    assert diet.verdict(labelled, "gluten_free", True) == "ok"
    assert diet.verdict(plain_carrot, "gluten_free", True) == "need_label"
    assert diet.verdict({"claims": [], "allergens": {}}, "gluten_free", True) == "unknown"


def test_at_risk_is_one_batched_data_call_and_down_is_strict(monkeypatch):
    calls = []

    async def fake(system, prompt, schema, *_):
        calls.append((system, prompt, schema))
        return {"gluten_free": ["wheat flour"], "vegan": ["cheese"]}

    monkeypatch.setattr(agent, "_gemini", fake)
    diet._RISK_CACHE.clear()
    got = asyncio.run(diet.at_risk(["wheat flour", "carrot", "cheese"], ["gluten_free", "vegan"]))

    assert got == {"gluten_free": {"wheat flour"}, "vegan": {"cheese"}}
    assert len(calls) == 1
    assert "<untrusted>" in calls[0][1] and "DATA" in calls[0][0]

    async def down(*args, **kwargs):
        return None

    monkeypatch.setattr(agent, "_gemini", down)
    diet._RISK_CACHE.clear()
    strict = asyncio.run(diet.at_risk(["flour", "oil"], ["vegan"]))
    assert strict == {"vegan": {"flour", "oil"}}


def test_vegan_menu_prices_natural_ingredients_and_drops_animal_cheese(shop, monkeypatch, decisions):
    _catalogue_product(shop, "v-flour", "Plain flour")
    _catalogue_product(shop, "v-oil", "Olive oil")
    _catalogue_product(shop, "v-tomato", "Crushed tomato")
    _catalogue_product(shop, "v-cheese", "Vegan cheese", claims=("VEGAN",))
    _catalogue_product(shop, "bad-cheese", "Mozzarella cheese", contains=("AM",))

    dishes = [{"name": "Vegan pizza", "ingredients": [
        {"name": "flour", "per_cover": 0.2, "unit": "kg", "assumption": "200 g flour", "dietary": []},
        {"name": "olive oil", "per_cover": 0.01, "unit": "L", "assumption": "10 ml oil", "dietary": []},
        {"name": "tomato", "per_cover": 0.1, "unit": "kg", "assumption": "100 g tomato", "dietary": []},
        {"name": "cheese", "per_cover": 0.05, "unit": "kg", "assumption": "50 g cheese", "dietary": []},
    ]}]

    async def fake(system, prompt, schema, *_):
        if schema is menu._MENU_SCHEMA:
            return {"dishes": dishes}
        if schema is diet._RISK_SCHEMA:
            return {"vegan": ["cheese"]}
        return {"queries": [prompt.split("ingredient: ", 1)[-1].split("\n", 1)[0]]}

    async def all_hits(item, hits):
        return [p["id"] for p in hits]

    monkeypatch.setattr(agent, "_gemini", fake)
    monkeypatch.setattr(agent, "match", all_hits)
    result = asyncio.run(menu.propose("Vegan pizza for 20 people", 20, REQ, "chef"))

    chosen = [line for line in result["lines"] if line["chosen"]]
    assert {line["product"]["id"] for line in chosen} >= {"v-flour", "v-oil", "v-tomato", "v-cheese"}
    assert result["cart_total_cents"] > 0
    assert all("AM" not in (line["product"].get("allergens") or {}).get("contains", []) for line in chosen)


def test_gluten_free_menu_keeps_natural_foods_and_explains_flour_swap(shop, monkeypatch, decisions):
    for pid, name, contains in (("salmon", "Salmon fillet", ("AF",)), ("carrot", "Carrot", ()),
                                ("leek", "Leek", ()), ("dill", "Dill", ())):
        _catalogue_product(shop, pid, name, contains=contains)
    _catalogue_product(shop, "gf-flour", "Gluten-free wheat flour", claims=("FREE_FROM_GLUTEN",))
    _catalogue_product(shop, "aw-pasta", "Wheat pasta", contains=("AW",))

    dishes = [{"name": "Gluten-free salmon soup", "ingredients": [
        {"name": "salmon", "per_cover": 0.15, "unit": "kg", "assumption": "150 g salmon", "dietary": []},
        {"name": "carrot", "per_cover": 0.05, "unit": "kg", "assumption": "50 g carrot", "dietary": []},
        {"name": "leek", "per_cover": 0.03, "unit": "kg", "assumption": "30 g leek", "dietary": []},
        {"name": "dill", "per_cover": 0.005, "unit": "kg", "assumption": "5 g dill", "dietary": []},
        {"name": "wheat flour", "per_cover": 0.02, "unit": "kg", "assumption": "20 g flour", "dietary": []},
        {"name": "pasta", "per_cover": 0.02, "unit": "kg", "assumption": "20 g pasta", "dietary": []},
    ]}]

    async def fake(system, prompt, schema, *_):
        if schema is menu._MENU_SCHEMA:
            return {"dishes": dishes}
        if schema is diet._RISK_SCHEMA:
            return {"gluten_free": ["wheat flour"]}
        return {"queries": [prompt.split("ingredient: ", 1)[-1].split("\n", 1)[0]]}

    async def all_hits(item, hits):
        return [p["id"] for p in hits]

    monkeypatch.setattr(agent, "_gemini", fake)
    monkeypatch.setattr(agent, "match", all_hits)
    result = asyncio.run(menu.propose("Gluten-free salmon soup for 20 people", 20, REQ, "chef"))

    chosen = [line for line in result["lines"] if line["chosen"]]
    assert {line["product"]["id"] for line in chosen} >= {"salmon", "carrot", "leek", "dill", "gf-flour"}
    assert all(line["product"]["id"] != "aw-pasta" for line in chosen)
    flour = next(line for line in chosen if line["product"]["id"] == "gf-flour")
    assert "because" in flour["why"].lower() and "gluten-free" in flour["why"].lower()
    assert not any("check this" in line["why"].lower() for line in chosen if line["product"]["id"] in {"salmon", "carrot", "leek", "dill"})


def test_at_risk_missing_allergen_data_is_asked_not_guessed(shop, monkeypatch, decisions):
    _catalogue_product(shop, "mystery-stock", "Vegetable stock", claims=())
    shop.products["mystery-stock"]["allergens"] = {}
    dishes = [{"name": "Vegan soup", "ingredients": [
        {"name": "stock", "per_cover": 0.2, "unit": "L", "assumption": "200 ml stock", "dietary": []}]}]

    async def fake(system, prompt, schema, *_):
        if schema is menu._MENU_SCHEMA:
            return {"dishes": dishes}
        if schema is diet._RISK_SCHEMA:
            return {"vegan": ["stock"]}
        return {"queries": ["stock"]}

    async def all_hits(item, hits):
        return [p["id"] for p in hits]

    monkeypatch.setattr(agent, "_gemini", fake)
    monkeypatch.setattr(agent, "match", all_hits)
    result = asyncio.run(menu.propose("Vegan soup for 10 people", 10, REQ, "chef"))

    assert any(r["code"] == "ALLERGEN_DATA_MISSING" and r["severity"] == "ASK_HUMAN"
               for r in result["decision"]["reasons"])
    assert result["order_lines"] == []


def test_gemini_down_uses_strict_diet_fallback_without_unsafe_lines(shop, monkeypatch, decisions):
    _catalogue_product(shop, "plain-flour", "Plain flour")
    _catalogue_product(shop, "animal-cheese", "Cheese", contains=("AM",))
    dishes = [{"name": "Vegan pizza", "ingredients": [
        {"name": "flour", "per_cover": 0.2, "unit": "kg", "assumption": "200 g flour", "dietary": []},
        {"name": "cheese", "per_cover": 0.05, "unit": "kg", "assumption": "50 g cheese", "dietary": []}]}]

    async def down(*args, **kwargs):
        return None

    async def all_hits(item, hits):
        return [p["id"] for p in hits]

    monkeypatch.setattr(agent, "_gemini", down)
    monkeypatch.setattr(agent, "match", all_hits)
    result = asyncio.run(menu.propose("Vegan pizza for 10 people", 10, REQ, "chef", dishes_task=asyncio.sleep(0, result=dishes)))

    assert result["order_lines"] == []
    assert all(line["product"]["id"] != "animal-cheese" for line in result["lines"] if line["chosen"])

