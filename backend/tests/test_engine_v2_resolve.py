"""Safety regressions for the Engine-v2 resolve integration."""
import asyncio
import json

import pytest
from conftest import REQ, product, quote, store_mandate
from fastapi.testclient import TestClient
from test_agent import decisions  # noqa: F401 - pytest fixture

from app import agent, diet, expand, menu, voice
from app.main import app

c = TestClient(app, raise_server_exceptions=False)


def test_vegan_backstop_marks_honey_gelatine_and_meat_risky_when_model_omits_them(monkeypatch):
    async def under_reports(*_args, **_kwargs):
        return {"vegan": []}

    monkeypatch.setattr(agent, "_gemini", under_reports)
    diet._RISK_CACHE.clear()

    risks = asyncio.run(diet.at_risk(["honey", "gelatine", "beef mince", "olive oil"], ["vegan"]))

    assert risks["vegan"] >= {"honey", "gelatine", "beef mince"}
    assert "olive oil" not in risks["vegan"]


def test_processed_or_unknown_vegan_product_never_passes_by_nature():
    model = {"safe_by_nature": True, "single_ingredient_unprocessed": True,
             "certain": True, "reason": "the model says so"}

    assert diet.check({"name_en": "Vegetable stock", "claims": [], "allergens": {}}, "vegan", True, model)["level"] == "unverifiable"
    assert diet.check({"name_en": "Unspecified ingredient", "claims": [], "allergens": {}}, "vegan", True, None)["level"] == "unverifiable"


def test_partial_or_trace_allergen_evidence_cannot_verify_a_diet_claim():
    cases = [
        ({"claims": ["FREE_FROM_GLUTEN"], "allergens": {"may_contain": ["AW"]}}, "gluten_free"),
        ({"claims": ["VEGAN"], "allergens": {"may_contain": ["AM"]}}, "vegan"),
        ({"claims": [], "allergens": {"free_from": ["AM"]}}, "vegan"),
    ]

    for product_data, tag in cases:
        result = diet.check(product_data, tag, True)
        assert result["level"] == "unverifiable"


def test_vegan_backstops_cover_mayonnaise_and_animal_derived_ingredients(monkeypatch):
    async def under_reports(*_args, **_kwargs):
        return {"vegan": []}

    monkeypatch.setattr(agent, "_gemini", under_reports)
    diet._RISK_CACHE.clear()

    risks = asyncio.run(diet.at_risk(["mayonnaise", "ghee", "whey powder", "lard", "olive oil"], ["vegan"]))

    assert risks["vegan"] >= {"mayonnaise", "ghee", "whey powder", "lard"}
    assert "olive oil" not in risks["vegan"]


def test_honey_cannot_be_safe_by_nature_for_a_vegan_diet():
    model = {"safe_by_nature": True, "single_ingredient_unprocessed": True,
             "certain": True, "reason": "honey is natural"}

    assert diet.check({"name_en": "Honey", "claims": [], "allergens": {}}, "vegan", True, model)["level"] == "unverifiable"


@pytest.mark.parametrize("name,tag,claims,may,free,risk", [
    ("trace flour", "gluten_free", ("FREE_FROM_GLUTEN",), ("AW",), (), []),
    ("gluten trace ingredient", "gluten_free", ("FREE_FROM_GLUTEN",), ("AW",), (), []),
    ("trace spread", "vegan", ("VEGAN",), ("AM",), (), []),
    ("vegan trace ingredient", "vegan", ("VEGAN",), ("AM",), (), []),
    ("partial free powder", "vegan", (), (), ("AM",), ["partial free powder"]),
    ("mayonnaise", "vegan", (), (), (), []),
    ("honey", "vegan", ("VEGAN",), (), (), [{"ingredient": "honey", "safe_by_nature": True,
                                                   "single_ingredient_unprocessed": True, "certain": True,
                                                   "reason": "honey is natural"}]),
])
def test_direct_and_menu_hold_diet_evidence_that_cannot_prove_suitability(
        shop, monkeypatch, decisions, name, tag, claims, may, free, risk):
    """Unsafe evidence must stay out of both a direct order and menu ``order_lines``."""
    pid = "diet-" + name.replace(" ", "-")
    candidate = product(pid, name, claims=claims, contains=(), may=may)
    candidate["allergens"]["free_from"] = list(free)
    candidate.update(base_unit="ST", units={"ST": 1.0}, volume={"unit": "LTR", "value": 1.0},
                     net_weight={"unit": "KGM", "value": 1.0})
    shop.products[pid], shop.quotes[pid] = candidate, quote(pid, price=2.0)
    store_mandate({"id": "chef-diet", "buyer_id": "chef", "per_line_cap_cents": 10**9})

    async def fake(system, _prompt, schema, *_args):
        if schema is agent._PARSE_SCHEMA:
            return {"summary": name, "items": [{"query": name, "amount": 1, "unit": "kg", "dietary": [tag]}]}
        if schema is menu._MENU_SCHEMA:
            return {"dishes": [{"name": f"{tag.replace('_', '-')} {name}", "ingredients": [
                {"name": name, "per_cover": 0.1, "unit": "kg", "assumption": "100 g", "dietary": []}]}]}
        if schema is diet._RISK_SCHEMA:
            return {tag: risk}
        if schema is expand._SCHEMA:
            return {"queries": []}
        return None

    async def all_hits(_item, hits):
        return [hit["id"] for hit in hits]

    monkeypatch.setattr(agent, "_gemini", fake)
    monkeypatch.setattr(agent, "match", all_hits)
    diet._RISK_CACHE.clear()

    direct = c.post("/api/agent/run", json={"text": f"1 kg {tag.replace('_', '-')} {name}",
                                              "requested_date": REQ.isoformat()},
                    headers={"X-Agent-Key": "agent-chef"}).json()
    diet._RISK_CACHE.clear()
    proposed = c.post("/api/agent/menu", json={"menu_text": f"{tag.replace('_', '-')} {name}", "covers": 10,
                                                 "requested_date": REQ.isoformat()},
                      headers={"X-Agent-Key": "agent-chef"}).json()

    assert direct["order"] is None
    assert proposed["order_lines"] == []
    assert any(reason["code"] in {"DATA_MISSING", "ALLERGEN_DATA_MISSING"}
               for reason in direct["decision"]["reasons"]), direct["decision"]["reasons"]
    assert any(reason["code"] in {"DATA_MISSING", "ALLERGEN_DATA_MISSING"}
               for reason in proposed["decision"]["reasons"])


def test_candidates_merge_finnish_expansion(shop, monkeypatch):
    lentils = product("red-lentils", "Sevan Red lentils 5kg", claims=(), contains=())
    lentils["name_fi"] = "punainen linssi"
    shop.products[lentils["id"]] = lentils

    async def expanded(*_args, **_kwargs):
        return {"queries": ["punainen linssi"]}

    async def all_hits(_item, hits):
        return [hit["id"] for hit in hits]

    monkeypatch.setattr(agent, "_gemini", expanded)
    monkeypatch.setattr(agent, "match", all_hits)

    lentil_ids, used_gemini = asyncio.run(agent.candidates("", agent._item("red lentils", 1, "kg", []), set()))

    assert used_gemini and "red-lentils" in lentil_ids


class _LiveSetup:
    def __init__(self):
        self.sent = []
        self.replies = [{"setupComplete": {}}, {"serverContent": {"inputTranscription": {"text": "maito"},
                                                               "generationComplete": True}}]

    def __call__(self, *_args, **_kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def recv(self):
        return json.dumps(self.replies.pop(0))


def test_live_transcription_setup_limits_recognition_to_english_and_finnish(monkeypatch):
    fake = _LiveSetup()
    monkeypatch.setattr(voice, "connect", fake)

    assert asyncio.run(voice.live_transcribe(b"\0\0" * voice.CHUNK)) == "maito"

    instruction = fake.sent[0]["setup"]["systemInstruction"]["parts"][0]["text"].lower()
    assert "english" in instruction and "finnish" in instruction
    assert "never in any other language" in instruction
