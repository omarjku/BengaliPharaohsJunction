"""Section B: editable kitchen history and the example-data policy."""
from fastapi.testclient import TestClient

from app import config, kitchen, profile
from app.main import app


c = TestClient(app, raise_server_exceptions=False)


def _demo_keys(monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", config.AGENT_KEYS + ",agent-hb=helsinki-bistro")
    monkeypatch.setattr(config, "APPROVER_KEYS", config.APPROVER_KEYS + ",appr-hb=helsinki-bistro")
    return {"X-Agent-Key": "agent-hb"}, {"X-Approver-Key": "appr-hb"}


def test_history_is_example_by_default_and_has_the_contract_shape(shop, monkeypatch):
    agent_headers, _ = _demo_keys(monkeypatch)

    response = c.get("/api/kitchen/history", headers=agent_headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"basis", "covers_by_weekday", "covers_source", "standing_orders", "usual_products", "labels"}
    assert body["basis"] == "example"
    assert body["labels"] == {"example": "Example history (simulated)"}
    assert set(body["covers_by_weekday"]) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
    assert set(body["covers_source"].values()) == {"example"}
    assert all(set(order) == {"weekday", "lines", "source"} for order in body["standing_orders"])
    assert all(set(product) == {"product_id", "name", "source"} for product in body["usual_products"])


def test_history_keys_and_buyer_scope(shop, monkeypatch):
    agent_headers, approver_headers = _demo_keys(monkeypatch)

    assert c.get("/api/kitchen/history").status_code == 401
    assert c.get("/api/kitchen/history", headers=approver_headers).status_code == 401
    other = c.get("/api/kitchen/history", headers={"X-Agent-Key": "agent-other"})
    assert other.status_code == 200 and other.json()["basis"] == "own"
    assert other.json()["usual_products"] == []
    assert c.put("/api/kitchen/history/covers", headers={"X-Agent-Key": "agent-hb"}, json={"mon": 42}).status_code == 401
    assert c.put("/api/kitchen/history/covers", headers={"X-Approver-Key": "appr-other"}, json={"mon": 42}).status_code == 200
    assert c.get("/api/kitchen/history", headers=agent_headers).json()["covers_source"]["mon"] == "example"


def test_own_covers_override_example_and_clear_hides_seeded_history(shop, monkeypatch):
    agent_headers, approver_headers = _demo_keys(monkeypatch)

    saved = c.put("/api/kitchen/history/covers", headers=approver_headers, json={"mon": 42})
    assert saved.status_code == 200
    history = c.get("/api/kitchen/history", headers=agent_headers).json()
    assert history["basis"] == "mixed"
    assert history["covers_by_weekday"]["mon"] == 42
    assert history["covers_source"]["mon"] == "own"
    assert history["covers_source"]["fri"] == "example"
    context = kitchen.kitchen_context("helsinki-bistro")
    assert context["covers"]["avg_per_weekday"]["mon"] == 42
    assert context["covers"]["source_by_weekday"]["mon"] == "you told me"
    assert "Example history (simulated)" in kitchen.summary("helsinki-bistro")

    cleared = c.post("/api/kitchen/history/clear-example", headers=approver_headers)
    assert cleared.status_code == 200
    history = c.get("/api/kitchen/history", headers=agent_headers).json()
    assert history["basis"] == "own"
    assert set(history["covers_source"].values()) == {"own"}
    assert history["covers_by_weekday"]["mon"] == 42
    context = kitchen.kitchen_context("helsinki-bistro")
    assert context["simulated"] is False
    assert "simulated_order_history" not in context
    assert "Example history (simulated)" not in kitchen.summary("helsinki-bistro")

    other = c.get("/api/kitchen/history", headers={"X-Agent-Key": "agent-other"}).json()
    assert other["basis"] == "own"


def test_demo_reset_restores_example_history(shop, monkeypatch):
    agent_headers, approver_headers = _demo_keys(monkeypatch)

    assert c.post("/api/kitchen/history/clear-example", headers=approver_headers).status_code == 200
    kitchen.reset("helsinki-bistro")

    history = c.get("/api/kitchen/history", headers=agent_headers).json()
    assert history["basis"] == "example"
    assert set(history["covers_source"].values()) == {"example"}


def test_standing_order_can_be_replaced_and_deleted_with_approver_key(shop):
    payload = {"lines": [{"text": "20 L milk", "quantity": 20, "unit": "L"}]}
    put = c.put("/api/profile/standing-orders/friday", headers={"X-Approver-Key": "appr-chef"}, json=payload)
    assert put.status_code == 200
    assert [x for x in put.json()["standing_orders"] if x["weekday"] == "friday"][0]["lines"] == [payload["lines"][0]]

    updated = {"lines": [{"text": "30 kg flour", "quantity": 30, "unit": "kg"}]}
    assert c.put("/api/profile/standing-orders/friday", headers={"X-Approver-Key": "appr-chef"}, json=updated).status_code == 200
    standing = [x for x in profile.standing_orders("chef") if x["weekday"] == "friday"]
    assert standing[0]["lines"] == updated["lines"]

    deleted = c.delete("/api/profile/standing-orders/friday", headers={"X-Approver-Key": "appr-chef"})
    assert deleted.status_code == 200
    assert not [x for x in profile.standing_orders("chef") if x["weekday"] == "friday"]
    assert c.delete("/api/profile/standing-orders/friday", headers={"X-Agent-Key": "agent-chef"}).status_code == 401
