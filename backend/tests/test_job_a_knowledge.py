"""Job A: the kitchen profile is available to onboarding, understand, kitchen and Talk."""
import asyncio
import json
from datetime import date

from fastapi.testclient import TestClient

from app import agent, ask, config, kitchen, live, orders, profile, understand
from app.main import app


c = TestClient(app, raise_server_exceptions=False)
APPROVER = {"X-Approver-Key": "appr-chef"}


def _standing_orders():
    return [{
        "weekday": "friday",
        "lines": [
            {"text": "20 L milk", "quantity": 20, "unit": "L"},
            {"text": "10 kg butter", "quantity": 10, "unit": "kg"},
            {"text": "5 L cream", "quantity": 5, "unit": "L"},
        ],
    }]


def _save_friday():
    profile.save_onboarding("chef", {"standing_orders": _standing_orders()})


def test_voice_onboarding_previews_and_confirms_standing_order_and_notes(shop, monkeypatch):
    async def fake(system, prompt, schema, *_args):
        assert "standing_orders" in system and "notes" in system
        assert len(prompt) > 4_000
        return {
            "business_type": "bistro",
            "delivery_days": ["friday"],
            "standing_orders": _standing_orders(),
            "usual_products": ["butter"],
            "covers": 80,
            "notes": ["The Friday order is for the weekend prep."],
            "unclear": ["We also keep a supplier habit I could not map."],
        }

    monkeypatch.setattr(agent, "_gemini", fake)
    about = "Our kitchen orders for Friday. " + ("We prep early. " * 300)
    preview_response = c.post("/api/profile/onboarding", headers=APPROVER, json={"about": about})
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    values = {entry["id"]: entry["value"] for entry in preview["proposed"]}
    assert values["standing_orders"][0]["weekday"] == "friday"
    assert values["usual_products"] == ["butter"] and values["covers"] == 80
    assert any("supplier habit" in note for note in values["notes"])

    saved_response = c.post("/api/profile/onboarding", headers=APPROVER,
                            json={"answers": values, "confirm": True})
    assert saved_response.status_code == 200, saved_response.text
    memory = next(m for m in profile._memories("chef") if m.key == "standing_order:friday")
    assert memory.kind.value == "preference_note"
    assert profile.standing_orders("chef")[0]["lines"][0]["quantity"] == 20
    assert any(m.key.startswith("note:") for m in profile._memories("chef"))
    assert "usual product: butter" in profile.compact_text("chef") and "covers: 80" in profile.compact_text("chef")


def test_long_about_text_is_accepted_to_six_thousand_characters(shop, monkeypatch):
    async def fake(*_args, **_kwargs):
        return {"unclear": ["A long sentence the chef said."]}

    monkeypatch.setattr(agent, "_gemini", fake)
    response = c.post("/api/profile/onboarding", headers=APPROVER,
                          json={"about": "spoken kitchen report " * 250})
    assert response.status_code == 200, response.text


def test_usual_friday_expands_with_an_extra_item_and_holds_the_saved_lines(shop, monkeypatch):
    _save_friday()

    async def down(*_args, **_kwargs):
        return None

    monkeypatch.setattr(agent, "_gemini", down)
    result = asyncio.run(understand.understand_fallback(
        "I want to do our usual Friday order. But I also want to add milk.",
        "chef", [], None, date(2026, 11, 14)))
    items = result["actions"][0]["slots"]["items"]
    assert len(items) == 4
    assert {(item["amount"], item["unit"], item["name"]) for item in items[:3]} == {
        (20.0, "L", "milk"), (10.0, "kg", "butter"), (5.0, "L", "cream")}
    assert any(item["name"] == "milk" and item["amount"] is None for item in items)
    assert all(item.get("_standing_order") for item in items[:3])


def test_phone_transcript_reaches_ask_as_four_unconfirmed_lines(shop, monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(ask.conversation, "STORE", tmp_path / "conversations.json")

    async def about_reader(system, prompt, schema, *_args):
        if "You fill an onboarding form" in system:
            return {"standing_orders": _standing_orders(), "unclear": []}
        return None

    monkeypatch.setattr(agent, "_gemini", about_reader)
    about = "Our usual Friday order is 20 L milk, 10 kg butter and 5 L cream."
    preview = c.post("/api/profile/onboarding", headers=APPROVER, json={"about": about})
    assert preview.status_code == 200, preview.text
    values = {entry["id"]: entry["value"] for entry in preview.json()["proposed"]}
    assert values["standing_orders"][0]["lines"][1]["text"] == "10 kg butter"
    saved = c.post("/api/profile/onboarding", headers=APPROVER, json={"answers": values, "confirm": True})
    assert saved.status_code == 200, saved.text

    async def down(*_args, **_kwargs):
        return None

    async def no_steering(*_args, **_kwargs):
        return 0.0

    async def fake_run(text, when, buyer_id, pre=None):
        captured.update(text=text, when=when, buyer_id=buyer_id, request=pre["parsed"][0])
        return {"request": pre["parsed"][0], "lines": [],
                "decision": {"outcome": "ASK_HUMAN", "reasons": []}, "order": None, "held_items": []}

    # The onboarding preview above is now accepted; the subsequent ask deliberately exercises the fallback path.
    monkeypatch.setattr(agent, "_gemini", down)
    monkeypatch.setattr(ask.agent, "steering", no_steering)
    monkeypatch.setattr(ask.agent, "date_intent", no_steering)
    monkeypatch.setattr(ask.agent, "run", fake_run)
    result = asyncio.run(ask.ask("I want to do our usual Friday order. But I also want to add milk.",
                                 date(2026, 11, 20), "chef"))
    items = captured["request"]["items"]
    assert [(item["query"], item["amount"], item["unit"]) for item in items] == [
        ("milk", 20.0, "L"), ("butter", 10.0, "kg"), ("cream", 5.0, "L"), ("milk", None, None)]
    assert all(item.get("amount_assumed") for item in items[:3])
    assert items[3].get("amount_assumed") is not True
    assert "20 L milk" in captured["text"] and "milk" in captured["text"]
    assert result["order"] is None and result["question"]


def test_missing_standing_order_never_uses_simulated_history_silently(shop):
    result = asyncio.run(understand.understand_fallback(
        "the same as every Friday order", "chef", [], None, date(2026, 11, 14)))
    action = result["actions"][0]
    assert "no saved friday standing order" in action["question"].lower()
    assert "tell me your usual friday order" in action["question"].lower()
    assert "simulated" not in action["question"].lower()


def test_understand_prompt_contains_profile_facts_and_sources(shop, monkeypatch):
    seen = {}
    monkeypatch.setattr(profile, "context", lambda _buyer: {
        "dietary": [{"tag": "gluten_free", "because": "you told me"}],
        "allergens": ["peanuts"],
        "delivery_days": ["friday"],
        "standing_orders": [{"weekday": "friday", "lines": [{"text": "20 L milk"}],
                              "source": "you told me"}],
        "notes": [{"text": "prep early", "source": "you told me"}],
        "memories": [{"text": "usually order butter", "source": "onboarding"}],
        "usual_product_ids": ["butter"],
    })

    async def fake(system, prompt, schema, *_args):
        seen["prompt"] = prompt
        return {"actions": [{"intent": "greeting", "slots": {
            "items": [], "dishes": [], "guests": None, "date": None,
            "diets": [], "exclusions": [], "language": "en"}}]}

    monkeypatch.setattr(agent, "_gemini", fake)
    asyncio.run(understand.understand("hello", "chef", [], None, date(2026, 11, 14)))
    assert "standing_orders" in seen["prompt"] and "20 L milk" in seen["prompt"]
    assert "peanuts" in seen["prompt"] and "delivery_days" in seen["prompt"]
    assert "you told me" in seen["prompt"]


def test_kitchen_marks_one_order_as_from_orders_not_usual_and_labels_facts(shop):
    orders._orders = {"one": {"buyer_id": "chef", "status": "confirmed", "created_at": "2026-11-13T10:00:00+00:00",
                               "total_cents": 100, "lines": [{"product_id": "463335", "quantity": 20, "unit": "L"}]}}
    products = kitchen._usual_products("chef", list(orders._store().values()))
    assert products and products[0]["source_label"] == "from your orders"
    assert products[0]["is_usual"] is False
    context = kitchen.kitchen_context("chef")
    assert context["spend"]["source_label"] == "from your orders"
    assert context["usual_products"][0]["source_label"] == "from your orders"


def test_live_setup_answers_in_any_language_and_exposes_profile_tool(shop, monkeypatch):
    monkeypatch.setattr(profile, "compact_text", lambda _buyer: "Standing order Friday: 20 L milk (you told me)")
    setup = live._setup("chef")["setup"]
    system = setup["systemInstruction"]["parts"][0]["text"]
    names = [f["name"] for group in setup["tools"] for f in group["functionDeclarations"]]
    assert "English or Finnish" not in system
    assert "whatever language" in system
    assert "Sorry, I didn't catch that, could you say it again?" in system
    assert "Standing order Friday" in system
    assert "profile_context" in names


def test_unquantified_parser_clause_becomes_a_questionable_clause():
    item = agent._item("milk", 20, "L", [])
    assert agent.unparsed_clauses("20 L milk and butter", [item]) == ["butter"]
