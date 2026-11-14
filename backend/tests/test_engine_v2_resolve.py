"""Safety regressions for the Engine-v2 resolve integration."""
import asyncio
import json

from conftest import product

from app import agent, diet, voice


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
