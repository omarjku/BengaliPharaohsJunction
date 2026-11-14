"""The text fallback for the short kitchen setup interview."""
from fastapi.testclient import TestClient

from app import profile
from app.main import app

c = TestClient(app)
AGENT = {"X-Agent-Key": "agent-chef"}


def test_interview_asks_topics_in_order_then_returns_the_onboarding_preview(shop, monkeypatch):
    seen = []

    async def fake_from_about(about):
        seen.append(about)
        return {"business_type": "bistro"}, []

    monkeypatch.setattr(profile, "from_about", fake_from_about)
    answers = []
    topics = ["kitchen", "delivery_days", "standing_orders", "dietary_allergens", "usual_products", "budget",
              "anything_else"]

    for topic in topics:
        response = c.post("/api/profile/interview/next", headers=AGENT, json={"answers": answers})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["topic"] == topic and body["done"] is False and body["question"]
        answers.append({"topic": topic, "text": f"Details for {topic}."})

    response = c.post("/api/profile/interview/next", headers=AGENT, json={"answers": answers})
    assert response.status_code == 200, response.text
    assert response.json() == {
        "done": True,
        "preview": {
            "stored": False,
            "proposed": [{"id": "business_type", "question": "What kind of business do you run?", "value": "bistro"}],
            "unclear": [],
            "hints": [],
        },
    }
    assert len(seen) == 1 and len(seen[0]) <= 6000
    assert "Details for kitchen." in seen[0] and "Details for anything_else." in seen[0]


def test_interview_skips_topics_already_in_the_profile(shop, monkeypatch):
    original = profile.onboarding

    def seeded(buyer_id):
        result = original(buyer_id)
        for question in result["questions"]:
            if question["id"] in {"delivery_days", "budget"}:
                question["answer"] = ["monday"] if question["id"] == "delivery_days" else 1000
        return result

    monkeypatch.setattr(profile, "onboarding", seeded)
    first = c.post("/api/profile/interview/next", headers=AGENT, json={"answers": []}).json()
    assert first["topic"] == "kitchen"
    answers = [{"topic": "kitchen", "text": "A 40-seat Nordic bistro."}]
    second = c.post("/api/profile/interview/next", headers=AGENT, json={"answers": answers}).json()
    assert second["topic"] == "standing_orders"


def test_interview_skips_facts_learned_outside_the_onboarding_question_list(shop, monkeypatch):
    monkeypatch.setattr(profile, "context", lambda _buyer: {
        "onboarding_facts": [{"key": "cuisine", "value": "Nordic"}],
        "delivery_days": ["monday"],
        "standing_orders": [{"weekday": "monday", "lines": [{"text": "milk"}]}],
        "dietary": [{"tag": "gluten_free"}],
        "allergens": ["peanuts"],
        "usual_products": [{"text": "butter"}],
        "notes": [{"text": "prep early"}],
    })
    response = c.post("/api/profile/interview/next", headers=AGENT, json={"answers": []})
    assert response.status_code == 200 and response.json()["topic"] == "budget"


def test_vague_interview_answer_gets_one_follow_up(shop):
    response = c.post("/api/profile/interview/next", headers=AGENT, json={"answers": [
        {"topic": "kitchen", "text": "A restaurant."},
    ]})
    assert response.status_code == 200
    body = response.json()
    assert body["done"] is False and body["topic"] == "kitchen"
    assert "more" in body["question"].lower()


def test_interview_fallback_requires_the_agent_key(shop):
    assert c.post("/api/profile/interview/next", json={"answers": []}).status_code == 401
