"""Room3-understand: a product without an amount asks "how much", stated dietary needs never guess a label, and the
buyer profile (Zoha's trade_profile) adds visible, overridable assumptions. Gemini, Valio and Decisions are faked."""
from conftest import REQ, product, quote
from fastapi.testclient import TestClient
from test_agent import decisions, shop1  # noqa: F401 - pytest fixtures
from test_menu import fake_gemini

from app import agent, ask, config, menu, profile
from app.main import app

c = TestClient(app, raise_server_exceptions=False)
KEYS = {"lapland-kitchen": "agent-lk", "helsinki-bistro": "agent-hb"}


def pizza_shop(shop):
    for p in [product("201", "Gluten-free pizza base", claims=("FREE_FROM_GLUTEN",)),
              product("202", "Pizza base", claims=()), product("203", "Mozzarella block", claims=()),
              product("204", "Mozzarella grated", claims=())]:
        p.update(base_unit="ST", units={"ST": 1.0}, volume={"unit": "LTR", "value": 1.0}, net_weight=None)
        shop.products[p["id"]] = p
        shop.quotes[p["id"]] = quote(p["id"], price=3.0)


def fake(monkeypatch, items, intent="order", covers=None):
    async def gemini(system, prompt, schema, *_):
        if schema is ask._INTENT_SCHEMA:
            return {"intent": intent, "covers": covers}
        if schema is agent._PARSE_SCHEMA:
            return {"summary": "x", "items": items}
        return None
    monkeypatch.setattr(agent, "_gemini", gemini)

    async def match(item, hits):  # every hit matches, in search order
        return [p["id"] for p in hits]
    monkeypatch.setattr(agent, "match", match)


def post(text, buyer="lapland-kitchen", path="/api/agent/ask", **extra):
    r = c.post(path, json={"text": text, **extra}, headers={"X-Agent-Key": KEYS[buyer]})
    assert r.status_code == 200, r.text
    return r.json()


def reasons(body):
    return body["decision"]["reasons"]


def test_a_product_without_an_amount_asks_how_much_with_options(shop1, monkeypatch):  # noqa: F811
    """'gluten-free pizza' used to be refused as off-topic; it is an order that asks the amount (and remembers it)."""
    pizza_shop(shop1)
    fake(monkeypatch, [{"query": "pizza", "amount": None, "unit": None, "dietary": ["gluten_free"]}])
    body = post("gluten-free pizza for Monday")
    assert body["intent"] == "order" and body["question"].startswith("How much pizza?")
    assert body["conversation_id"] and body["order"] is None
    assert [ln["product"]["id"] for ln in body["lines"]] == ["201"]  # only the labelled base is an option
    assert "gluten-free pizza" in ask.INTENT_PROMPT and "WITH OR WITHOUT an amount" in ask.INTENT_PROMPT


def test_a_stated_need_never_guesses_a_label_and_says_so_plainly(shop1, monkeypatch):  # noqa: F811
    """No mozzarella is labelled gluten-free: the closest one is offered with 'check its label', and the order asks."""
    pizza_shop(shop1)
    fake(monkeypatch, [{"query": "mozzarella", "amount": 2, "unit": "L", "dietary": ["gluten_free"]}])
    body = post("2 L gluten-free mozzarella", path="/api/agent/run", requested_date=REQ.isoformat())
    msg = [r for r in reasons(body) if r["code"] == "DATA_MISSING"]
    assert msg and msg[0]["severity"] == "ASK_HUMAN" and "check its label" in msg[0]["message"].lower()
    assert "Valio labels no mozzarella gluten-free" in msg[0]["message"]
    assert body["order"] is None or body["order"]["status"] != "confirmed"
    assert not any("FREE_FROM" in r["message"] for r in reasons(body))  # plain words, never codes


def test_menu_says_the_dietary_rule_once_for_the_cart(shop1, monkeypatch):  # noqa: F811
    pizza_shop(shop1)
    fake_gemini(monkeypatch, [{"name": "Gluten-free pizza", "ingredients": [
        {"name": "pizza base", "per_cover": 1, "unit": "L", "assumption": "1 base", "dietary": ["gluten_free"]},
        {"name": "mozzarella", "per_cover": 0.1, "unit": "L", "assumption": "100 g", "dietary": ["gluten_free"]}]}])

    async def match(item, hits):
        return [p["id"] for p in hits]
    monkeypatch.setattr(agent, "match", match)
    r = c.post("/api/agent/menu", json={"menu_text": "Gluten-free pizza", "covers": 20,
                                        "requested_date": REQ.isoformat()}, headers={"X-Agent-Key": "agent-lk"})
    body = r.json()
    cart = [x for x in reasons(body) if x["code"] == "MENU_ASSUMPTIONS" and x["severity"] == "INFO"
            and x["message"].startswith("Gluten-free")]
    assert len(cart) == 1 and cart[0]["message"].startswith("Gluten-free: I only pick products Valio labels gluten-free")
    assert any(x["code"] == "DATA_MISSING" and "mozzarella" in x["message"] for x in reasons(body))


def test_profile_gluten_free_kitchen_is_a_visible_default_and_words_beat_it(shop1, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "AGENT_KEYS", config.AGENT_KEYS + ",agent-hb=helsinki-bistro")
    pizza_shop(shop1)
    fake(monkeypatch, [{"query": "pizza base", "amount": 10, "unit": "L", "dietary": []}])
    body = post("10 L pizza base", "helsinki-bistro", "/api/agent/run", requested_date=REQ.isoformat())
    chosen = [ln["product"]["id"] for ln in body["lines"] if ln["chosen"]]
    assert chosen == ["201"]  # the labelled base, because of the profile
    why = [r for r in reasons(body) if r["code"] == "PROFILE_DEFAULT"][0]
    assert why["severity"] == "INFO" and why["message"].startswith("Gluten-free, because your profile says")
    assert why["facts"]["profile"].startswith("your profile says")
    plain = post("10 L regular pizza base", "helsinki-bistro", "/api/agent/run", requested_date=REQ.isoformat())
    assert not any(r["code"] == "PROFILE_DEFAULT" for r in reasons(plain))  # the buyer's own word wins
    empty = post("10 L pizza base again", "lapland-kitchen", "/api/agent/run", requested_date=REQ.isoformat())
    assert not any(r["code"] == "PROFILE_DEFAULT" for r in reasons(empty))  # lapland's profile stays empty


def test_usual_product_breaks_near_ties_only(shop1, monkeypatch, decisions):  # noqa: F811
    monkeypatch.setattr(config, "AGENT_KEYS", config.AGENT_KEYS + ",agent-hb=helsinki-bistro")
    pizza_shop(shop1)
    monkeypatch.setattr(profile, "usual", lambda buyer: {"204"} if buyer == "helsinki-bistro" else set())
    fake(monkeypatch, [{"query": "mozzarella", "amount": 2, "unit": "L", "dietary": []}])
    body = post("2 L regular mozzarella", "helsinki-bistro", "/api/agent/run", requested_date=REQ.isoformat())
    best = [ln for ln in body["lines"] if ln["chosen"]][0]
    assert best["product"]["id"] == "204" and best["usual"] and "You usually order this." in best["why"]
    real = agent.judge_line

    async def judge(text, p, expl):  # the usual one is far less sure: confidence still leads
        conf, why, weakest = await real(text, p, expl)
        return (0.5 if p["id"] == "204" else conf), why, weakest
    monkeypatch.setattr(agent, "judge_line", judge)
    body = post("2 L regular mozzarella please", "helsinki-bistro", "/api/agent/run", requested_date=REQ.isoformat())
    assert [ln for ln in body["lines"] if ln["chosen"]][0]["product"]["id"] == "203"


def test_get_profile_is_read_only_per_buyer(shop1, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "AGENT_KEYS", config.AGENT_KEYS + ",agent-hb=helsinki-bistro")
    hb = c.get("/api/profile", headers={"X-Agent-Key": "agent-hb"}).json()
    assert hb["dietary"] == [{"tag": "gluten_free", "label": "gluten-free",
                              "because": "your profile says: Our kitchen is gluten-free"}]
    assert set(hb["usual_product_ids"]) == {"464411", "475852", "471650"} and hb["memories"]
    lk = c.get("/api/profile", headers={"X-Agent-Key": "agent-lk"}).json()
    assert lk["dietary"] == [] and lk["usual_product_ids"] == [] and lk["memories"] == []
    assert c.get("/api/profile").status_code == 401


def test_labelled_but_wrong_products_fall_back_to_the_real_one(shop1, monkeypatch):  # noqa: F811
    """'wheat flour' + gluten-free found only buckwheat: when no labelled product IS the item, the unlabelled ones are
    judged too, and the line says 'check the label' instead of 'not stocked'."""
    pizza_shop(shop1)
    fake(monkeypatch, [{"query": "pizza base", "amount": 2, "unit": "L", "dietary": ["gluten_free"]}])

    async def match(item, hits):  # the labelled base "isn't" a pizza base here; the plain one is
        return [p["id"] for p in hits if p["id"] != "201"]
    monkeypatch.setattr(agent, "match", match)
    body = post("2 L gluten-free pizza base", path="/api/agent/run", requested_date=REQ.isoformat())
    assert [ln["product"]["id"] for ln in body["lines"] if ln["chosen"]] == ["202"]
    assert any(r["code"] == "DATA_MISSING" and "check its label" in r["message"].lower() for r in reasons(body))
    assert not any(r["code"] == "UNKNOWN_PRODUCT" for r in reasons(body))


def test_menu_reading_knows_the_kitchen_is_gluten_free(monkeypatch, tmp_path):
    """helsinki-bistro's pizza came back with wheat flour: the menu reading now gets the profile's standing needs
    (from our data, never the buyer's text); lapland-kitchen and a menu that states its own diet don't."""
    import asyncio
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    seen = []

    async def gemini(system, prompt, schema, *_):
        seen.append(system)
        return {"dishes": []}
    monkeypatch.setattr(agent, "_gemini", gemini)
    asyncio.run(menu.parse_menu("pizza for 20 people", "helsinki-bistro"))
    asyncio.run(menu.parse_menu("pizza for 20 people", "lapland-kitchen"))
    asyncio.run(menu.parse_menu("regular pizza for 20 people", "helsinki-bistro"))
    assert "standing dietary needs (from its profile): gluten-free" in seen[0]
    assert seen[1] == seen[2] == menu.MENU_PROMPT


def test_eggs_convert_through_the_count_in_the_name():
    """Black-box A5: '180 eggs' became 180 cases of 90-egg trays (about 16,200 eggs)."""
    def egg(name, unit="KI"):
        return {"id": "e", "name_en": name, "sales_unit": unit, "lot_size": 1, "base_unit": unit, "units": {unit: 1.0},
                "volume": None, "net_weight": None}
    assert agent.resolve(egg("Kieku Organic egg M90 5200g"), 180, "pcs")["quantity"] == 2
    assert agent.resolve(egg("Kieku Barn egg M10 580g", "RAS"), 180, "pcs")["quantity"] == 18
    assert agent.resolve(egg("20 x Kieku Barn egg L6 408g"), 180, "pcs")["quantity"] == 2  # 120 per case, rounded up


def test_counted_eggs_sold_by_weight_use_a_shown_assumption():
    """Black-box E1: '80 eggs' in a menu became 80 x 1 kg of whole egg."""
    p = {"id": "w", "name_en": "Munax whole egg barn 1000 g", "sales_unit": "ST", "lot_size": 1, "base_unit": "ST",
         "units": {"ST": 1.0}, "volume": None, "net_weight": {"unit": "KGM", "value": 1.0}}
    q = agent.resolve(p, 80, "pcs")
    assert q["quantity"] == 4 and q["needs_confirmation"] and "about 50 g each (assumption)" in q["explanation"]


def test_a_doubted_menu_line_is_not_in_order_lines(shop1, monkeypatch):  # noqa: F811
    """Black-box #7: a flagged line went into order_lines; it is listed under check_lines instead."""
    pizza_shop(shop1)
    fake_gemini(monkeypatch, [{"name": "Pizza", "ingredients": [
        {"name": "pizza base", "per_cover": 1, "unit": "L", "assumption": "1 base", "dietary": []},
        {"name": "mozzarella", "per_cover": 0.1, "unit": "L", "assumption": "100 g", "dietary": []}]}])

    async def match(item, hits):
        return [p["id"] for p in hits]
    monkeypatch.setattr(agent, "match", match)
    real = agent.judge_line

    async def judge(text, p, expl):
        conf, why, weakest = await real(text, p, expl)
        return (0.3 if "mozzarella" in text else conf), why, weakest
    monkeypatch.setattr(agent, "judge_line", judge)
    body = c.post("/api/agent/menu", json={"menu_text": "Pizza", "covers": 20, "requested_date": REQ.isoformat()},
                  headers={"X-Agent-Key": "agent-lk"}).json()
    in_order = {ln["product_id"] for ln in body["order_lines"]}
    assert body["check_lines"] and all(x["product_id"] not in in_order for x in body["check_lines"])
    assert "mozzarella" in body["check_lines"][0]["name"].lower()
    assert any(r["message"].startswith("Left out of the order lines") for r in reasons(body))


def test_gemini_down_a_product_word_still_asks_the_amount(shop1, monkeypatch, tmp_path):  # noqa: F811
    """Black-box B3: with Gemini timing out, 'lactose-free milk for Monday' was called off-topic."""
    from app import conversation
    monkeypatch.setattr(conversation, "STORE", tmp_path / "conv.json")

    async def down(*a, **k):
        return None
    monkeypatch.setattr(agent, "_gemini", down)
    body = post("lactose-free milk for Monday")
    assert body["intent"] == "order" and body["question"].startswith("How much milk?") and body["conversation_id"]


def test_an_unsure_order_asks_which_one_and_the_answer_continues(shop1, monkeypatch, tmp_path):  # noqa: F811
    """Black-box #8: 'cream' at 0.50 ended with no question, no conversation and no order."""
    from app import conversation
    monkeypatch.setattr(conversation, "STORE", tmp_path / "conv.json")
    pizza_shop(shop1)
    fake(monkeypatch, [{"query": "mozzarella", "amount": 2, "unit": "L", "dietary": []}])
    real = agent.judge_line
    seen = []

    async def judge(text, p, expl):
        seen.append(text)
        conf, why, weakest = await real(text, p, expl)
        return 0.5, why, weakest
    monkeypatch.setattr(agent, "judge_line", judge)
    body = post("2 L mozzarella for Monday")
    assert body["order"] is None and body["question"].startswith("Which one did you mean: 1) Mozzarella")
    assert body["conversation_id"]
    r = c.post("/api/agent/ask", json={"follow_up": {"to": body["conversation_id"], "answer": "the second"}},
               headers={"X-Agent-Key": "agent-lk"})
    assert r.status_code == 200, r.text
    assert r.json()["intent"] == "order"  # the request re-ran with the chosen product added


def test_each_held_line_of_a_list_gets_its_own_next_step(shop1, monkeypatch, tmp_path):  # noqa: F811
    """Room 2 (multi-line photo list): a held 'cream' line had no question. Every held line now has one, with its own
    conversation_id, and answering it re-runs only that line (the milk already ordered is not sent again)."""
    from app import conversation
    monkeypatch.setattr(conversation, "STORE", tmp_path / "conv.json")
    pizza_shop(shop1)
    fake(monkeypatch, [{"query": "milk", "amount": 10, "unit": "L", "dietary": []},
                       {"query": "mozzarella", "amount": 2, "unit": "L", "dietary": []}])
    real = agent.judge_line

    async def judge(text, p, expl):
        conf, why, weakest = await real(text, p, expl)
        return (0.5 if "mozzarella" in text else conf), why, weakest
    monkeypatch.setattr(agent, "judge_line", judge)
    body = post("10 L milk, 2 L mozzarella for Monday")
    assert body["order"]["status"] == "confirmed"  # the milk went through
    step = body["next_steps"][0]
    assert body["held_items"] == [1] and step["item"] == 1 and step["kind"] == "which"
    assert step["question"].startswith("Which mozzarella did you mean: 1) Mozzarella") and step["conversation_id"]
    assert body["question"] == step["question"] and body["conversation_id"] == step["conversation_id"]
    fake(monkeypatch, [])  # the follow-up must not need a new parse
    monkeypatch.setattr(agent, "judge_line", real)
    r = c.post("/api/agent/ask", json={"follow_up": {"to": step["conversation_id"], "answer": "the first"}},
               headers={"X-Agent-Key": "agent-lk"}).json()
    assert [it["query"] for it in r["request"]["items"]] == ["Mozzarella block"]  # only the held line ran again
    assert r["order"] and r["order"]["status"] == "confirmed" and r["held_items"] == [], (r.get("question"), [(x["code"], x["message"][:120]) for x in r["decision"]["reasons"]])


def test_a_held_line_follow_up_can_not_skip_request_level_guards(shop1, monkeypatch, tmp_path):  # noqa: F811
    """Security review: a request held for request-level reasons (here an item that isn't in the chef's words) gets
    no per-line next step, and a stored line is re-grounded against the ORIGINAL text before it runs again."""
    from app import ask as ask_mod, conversation
    monkeypatch.setattr(conversation, "STORE", tmp_path / "conv.json")
    pizza_shop(shop1)
    fake(monkeypatch, [{"query": "milk", "amount": 10, "unit": "L", "dietary": []},
                       {"query": "mozzarella", "amount": 2, "unit": "L", "dietary": []}])
    body = post("10 L milk for Monday")  # 'mozzarella' was never said: request-level grounding holds everything
    assert body["held_items"] == [] and body["next_steps"] == []
    entry = {"text": "10 L milk for Monday", "requested": REQ.isoformat(), "item": 1, "line_only": True,
             "request": {"summary": "x", "items": [{"query": "milk", "amount": 10, "unit": "L"},
                                                   {"query": "mozzarella", "amount": 2, "unit": "L"}]}}
    assert not ask_mod._line_grounded(entry)
    assert ask_mod._line_grounded(dict(entry, item=0))
