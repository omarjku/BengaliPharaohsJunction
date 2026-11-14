import asyncio

from conftest import REQ, product, quote, store_mandate
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


def _risk(ingredient, *, safe=False, reason="", single=False, certain=False):
    return {"ingredient": ingredient, "safe_by_nature": safe, "reason": reason,
            "single_ingredient_unprocessed": single, "certain": certain}


def _menu_gemini(monkeypatch, dishes, risk, matcher=None):
    async def fake(system, prompt, schema, *_):
        if schema is menu._MENU_SCHEMA:
            return {"dishes": dishes}
        if schema is diet._RISK_SCHEMA:
            return risk
        return {"queries": []}

    async def all_hits(item, hits):
        return [p["id"] for p in hits] if matcher is None else matcher(item, hits)

    monkeypatch.setattr(agent, "_gemini", fake)
    monkeypatch.setattr(agent, "match", all_hits)
    diet._RISK_CACHE.clear()


def test_diet_levels_use_allergen_evidence_and_claims():
    wheat = {"claims": [], "allergens": {"contains": ["AW"], "may_contain": [], "free_from": []}}
    plain_carrot = {"claims": [], "allergens": {"contains": [], "may_contain": [], "free_from": ["AW"]}}
    labelled = {"claims": ["FREE_FROM_GLUTEN"], "allergens": {}}

    assert diet.contradicts(wheat, "gluten_free")
    assert diet.check(wheat, "gluten_free", True)["level"] == "contradicts"
    assert diet.check(plain_carrot, "gluten_free", True) == {
        "level": "verified", "basis": "allergen data shows no gluten"}
    assert diet.check(labelled, "gluten_free", True) == {
        "level": "verified", "basis": "labelled gluten-free"}
    assert diet.check(plain_carrot, "gluten_free", False)["level"] == "verified"
    assert diet.check({"claims": [], "allergens": {}}, "gluten_free", True)["level"] == "unverifiable"


def test_safe_by_nature_needs_explicit_certainty_and_no_conflicting_trace_data():
    product_with_trace_conflict = {"name_en": "Potato starch", "claims": [],
                                   "allergens": {"contains": [], "may_contain": ["AW"], "free_from": ["AW"]}}
    model = {"safe_by_nature": True, "reason": "potato starch contains no gluten",
             "single_ingredient_unprocessed": True}

    assert diet.check(product_with_trace_conflict, "gluten_free", True, model)["level"] == "unverifiable"
    assert diet.check({"name_en": "Potato starch", "claims": [], "allergens": {}}, "gluten_free", True,
                      model)["level"] == "unverifiable"
    assert diet.check({"name_en": "Potato starch", "claims": [], "allergens": {}}, "gluten_free", True,
                      model | {"certain": True})["level"] == "safe_by_nature"


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


def test_label_and_free_from_are_verified_and_shown_on_cart_lines(shop, monkeypatch, decisions):
    _catalogue_product(shop, "labelled-flour", "Labelled flour", claims=("FREE_FROM_GLUTEN",), contains=())
    _catalogue_product(shop, "free-flour", "Free flour", claims=(), contains=(), free=("AW",))
    dishes = [{"name": "Gluten-free flour", "ingredients": [
        {"name": "labelled flour", "per_cover": 0.1, "unit": "kg", "assumption": "100 g", "dietary": []},
        {"name": "free flour", "per_cover": 0.1, "unit": "kg", "assumption": "100 g", "dietary": []}]}]
    def by_ingredient(item, hits):
        wanted = "labelled-flour" if item["query"] == "labelled flour" else "free-flour"
        return [p["id"] for p in hits if p["id"] == wanted]

    _menu_gemini(monkeypatch, dishes, {"gluten_free": [
        _risk("labelled flour"), _risk("free flour")]}, by_ingredient)

    result = asyncio.run(menu.propose("Gluten-free flour for 10 people", 10, REQ, "chef"))
    chosen = {line["product"]["id"]: line for line in result["lines"] if line["chosen"]}

    assert chosen["labelled-flour"]["diet_checks"] == [{
        "diet": "gluten_free", "level": "verified", "basis": "labelled gluten-free"}]
    assert chosen["free-flour"]["diet_checks"] == [{
        "diet": "gluten_free", "level": "verified", "basis": "allergen data shows no gluten"}]
    assert {line["product_id"] for line in result["order_lines"]} >= {"labelled-flour", "free-flour"}


def test_safe_by_nature_requires_gemini_certainty_and_is_shown_on_cart_lines(shop, monkeypatch, decisions):
    for pid, name in (("potato-starch", "Potato starch"), ("plain-carrots", "Plain carrots"),
                      ("fresh-salmon", "Fresh salmon"), ("olive-oil", "Olive oil")):
        _catalogue_product(shop, pid, name, claims=(), contains=())
    dishes = [{"name": "Gluten-free vegan produce", "ingredients": [
        {"name": "potato starch", "per_cover": 0.1, "unit": "kg", "assumption": "100 g", "dietary": []},
        {"name": "plain carrots", "per_cover": 0.1, "unit": "kg", "assumption": "100 g", "dietary": []},
        {"name": "fresh salmon", "per_cover": 0.1, "unit": "kg", "assumption": "100 g", "dietary": []},
        {"name": "olive oil", "per_cover": 0.01, "unit": "L", "assumption": "10 ml", "dietary": []}]}]
    _menu_gemini(monkeypatch, dishes, {
        "gluten_free": [_risk("potato starch", safe=True, reason="potato starch contains no gluten", single=True, certain=True),
                        _risk("plain carrots", safe=True, reason="plain carrots contain no gluten", single=True, certain=True),
                        _risk("fresh salmon", safe=True, reason="fresh salmon contains no gluten", single=True, certain=True)],
        "vegan": [_risk("olive oil", safe=True, reason="olive oil is made from olives", single=True, certain=True)]})

    result = asyncio.run(menu.propose("Gluten-free vegan produce for 10 people", 10, REQ, "chef"))
    chosen = {line["product"]["id"]: line for line in result["lines"] if line["chosen"]}

    assert chosen["potato-starch"]["diet_checks"] == [{
        "diet": "gluten_free", "level": "safe_by_nature", "basis": "potato starch contains no gluten"}]
    assert chosen["plain-carrots"]["diet_checks"][0]["level"] == "safe_by_nature"
    assert chosen["fresh-salmon"]["diet_checks"][0]["basis"] == "fresh salmon contains no gluten"
    assert chosen["olive-oil"]["diet_checks"] == [{
        "diet": "vegan", "level": "safe_by_nature", "basis": "olive oil is made from olives"}]
    assert all(pid in {line["product_id"] for line in result["order_lines"]}
               for pid in chosen)


def test_processed_products_never_qualify_as_safe_by_nature(shop, monkeypatch, decisions):
    for pid, name in (("vegetable-stock", "Vegetable stock"), ("tomato-sauce", "Tomato sauce"),
                      ("pork-sausage", "Pork sausage")):
        _catalogue_product(shop, pid, name, claims=(), contains=())
    dishes = [{"name": "Vegan prepared food", "ingredients": [
        {"name": "vegetable stock", "per_cover": 0.1, "unit": "L", "assumption": "100 ml", "dietary": []},
        {"name": "tomato sauce", "per_cover": 0.1, "unit": "L", "assumption": "100 ml", "dietary": []},
        {"name": "pork sausage", "per_cover": 1, "unit": "pcs", "assumption": "1 piece", "dietary": []}]}]
    _menu_gemini(monkeypatch, dishes, {"vegan": [
        _risk("vegetable stock", safe=True, reason="stock is natural", single=True, certain=True),
        _risk("tomato sauce", safe=True, reason="sauce is natural", single=True, certain=True),
        _risk("pork sausage", safe=True, reason="sausage is natural", single=True, certain=True)]})

    result = asyncio.run(menu.propose("Vegan prepared food for 10 people", 10, REQ, "chef"))
    chosen = [line for line in result["lines"] if line["chosen"]]

    assert all(line["diet_checks"][0]["level"] == "unverifiable" for line in chosen)
    assert all("safe_by_nature" not in line["diet_checks"][0]["basis"] for line in chosen)
    assert result["order_lines"] == []
    assert sum("Can't verify this" in r["message"] for r in result["decision"]["reasons"]) == 3


def test_unverifiable_asks_once_and_offers_labelled_alternative(shop, monkeypatch, decisions):
    _catalogue_product(shop, "stock", "Vegetable stock", claims=(), contains=())
    _catalogue_product(shop, "labelled-stock", "Gluten-free vegetable stock", claims=("FREE_FROM_GLUTEN",), contains=())
    dishes = [{"name": "Gluten-free soup", "ingredients": [
        {"name": "vegetable stock", "per_cover": 0.1, "unit": "L", "assumption": "100 ml", "dietary": []}]}]

    def only_unlabelled(item, hits):
        return [p["id"] for p in hits if p["id"] == "stock"]

    _menu_gemini(monkeypatch, dishes, {"gluten_free": [_risk("vegetable stock")]}, only_unlabelled)
    result = asyncio.run(menu.propose("Gluten-free soup for 10 people", 10, REQ, "chef"))
    line = next(line for line in result["lines"] if line["chosen"])
    questions = [r["message"] for r in result["decision"]["reasons"] if "Can't verify this" in r["message"]]

    assert line["diet_checks"] == [{"diet": "gluten_free", "level": "unverifiable",
                                     "basis": "no gluten-free label or proving allergen data"}]
    assert len(questions) == 1
    assert "Gluten-free vegetable stock" in questions[0] and "labelled" in questions[0]
    assert result["order_lines"] == [] and result["check_lines"] == [{
        "product_id": "stock", "quantity": 1, "name": "Vegetable stock"}]


def test_contradiction_and_mandate_exclusion_beat_safe_by_nature(shop, monkeypatch, decisions):
    contradictory = {"claims": [], "allergens": {"contains": ["AP"], "may_contain": [], "free_from": []}}
    assert diet.check(contradictory, "peanut_free", True,
                      _risk("peanut oil", safe=True, reason="peanut oil is natural", single=True, certain=True))["level"] == "contradicts"

    _catalogue_product(shop, "peanut-oil", "Natural peanut oil", claims=(), contains=())
    store_mandate({"id": "peanut-mandate", "buyer_id": "chef", "per_line_cap_cents": 10**9,
                   "hard_rules": [{"kind": "excluded_allergen", "value": "AP"}]})
    dishes = [{"name": "Peanut-free oil", "ingredients": [
        {"name": "peanut oil", "per_cover": 0.01, "unit": "L", "assumption": "10 ml", "dietary": []}]}]
    _menu_gemini(monkeypatch, dishes, {"peanut_free": [
        _risk("peanut oil", safe=True, reason="peanut oil is natural", single=True, certain=True)]})
    result = asyncio.run(menu.propose("Peanut-free oil for 10 people", 10, REQ, "chef"))

    assert result["order_lines"] == []
    assert any(r["code"] == "ALLERGEN_CONTAINS" for r in result["decision"]["reasons"])


def test_gemini_down_has_no_safe_by_nature_and_holds_the_line(shop, monkeypatch, decisions):
    _catalogue_product(shop, "plain-carrots-down", "Plain carrots", claims=(), contains=())
    dishes = [{"name": "Vegan carrots", "ingredients": [
        {"name": "plain carrots", "per_cover": 0.1, "unit": "kg", "assumption": "100 g", "dietary": []}]}]

    async def down(*args, **kwargs):
        return None

    monkeypatch.setattr(agent, "_gemini", down)
    async def all_hits(item, hits):
        return [p["id"] for p in hits]
    monkeypatch.setattr(agent, "match", all_hits)
    diet._RISK_CACHE.clear()
    result = asyncio.run(menu.propose("Vegan carrots for 10 people", 10, REQ, "chef",
                                      dishes_task=asyncio.sleep(0, result=dishes)))
    line = next(line for line in result["lines"] if line["chosen"])

    assert line["diet_checks"] == [{"diet": "vegan", "level": "unverifiable",
                                     "basis": "no vegan label or proving allergen data"}]
    assert result["order_lines"] == []
    assert sum("Can't verify this" in r["message"] for r in result["decision"]["reasons"]) == 1


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


def test_overconservative_vegan_risk_keeps_plain_flour_and_olive_oil(shop, monkeypatch, decisions):
    _catalogue_product(shop, "natural-flour", "Plain wheat flour")
    _catalogue_product(shop, "natural-oil", "Olive oil")
    dishes = [{"name": "Vegan pizza", "ingredients": [
        {"name": "flour", "per_cover": 0.2, "unit": "kg", "assumption": "200 g flour", "dietary": []},
        {"name": "olive oil", "per_cover": 0.01, "unit": "L", "assumption": "10 ml oil", "dietary": []},
    ]}]

    async def fake(system, prompt, schema, *_):
        if schema is menu._MENU_SCHEMA:
            return {"dishes": dishes}
        if schema is diet._RISK_SCHEMA:
            return {"vegan": [_risk("flour"), _risk("olive oil")]}
        return {"queries": []}

    async def all_hits(item, hits):
        return [p["id"] for p in hits]

    monkeypatch.setattr(agent, "_gemini", fake)
    monkeypatch.setattr(agent, "match", all_hits)
    diet._RISK_CACHE.clear()
    result = asyncio.run(menu.propose("Vegan pizza for 20 people", 20, REQ, "chef"))

    chosen = {line["product"]["id"]: line for line in result["lines"] if line["chosen"]}
    assert chosen["natural-flour"]["diet_checks"][0]["level"] == "safe_by_nature"
    assert chosen["natural-oil"]["diet_checks"][0]["level"] == "safe_by_nature"
    assert {line["product_id"] for line in result["order_lines"]} >= {"natural-flour", "natural-oil"}


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

