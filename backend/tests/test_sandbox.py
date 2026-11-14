"""QR test-kitchen sandboxes: minting, roles, limits, expiry, and isolated template reads."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from conftest import REQ
from fastapi.testclient import TestClient

from app import config, mandates, orders, sandbox
from app.main import app

c = TestClient(app, raise_server_exceptions=False)


def mint(monkeypatch, forwarded="203.0.113.10"):
    monkeypatch.setattr(config, "SANDBOX_ENABLED", True, raising=False)
    return c.post("/api/sandbox", headers={"X-Forwarded-For": forwarded})


def order_headers(session):
    return {"X-Agent-Key": session["agent_key"]}


def approver_headers(session):
    return {"X-Approver-Key": session["approver_key"]}


def test_mint_returns_fresh_keys_and_persists_only_hashes(shop, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "TRUST_X_FORWARDED_FOR", True)
    response = mint(monkeypatch)

    assert response.status_code == 200, response.text
    session = response.json()
    assert session["buyer_id"].startswith("try-") and len(session["buyer_id"]) == len("try-00000000")
    assert session["template"] == "helsinki-bistro"
    assert datetime.fromisoformat(session["expires_at"]) > datetime.now(timezone.utc)
    assert session["agent_key"] and session["approver_key"] and session["agent_key"] != session["approver_key"]

    registry = json.loads((tmp_path / "sandboxes.json").read_text())
    raw = (tmp_path / "sandboxes.json").read_text()
    record = registry[session["buyer_id"]]
    assert record["agent_key_hash"] == hashlib.sha256(session["agent_key"].encode()).hexdigest()
    assert record["approver_key_hash"] == hashlib.sha256(session["approver_key"].encode()).hexdigest()
    assert session["agent_key"] not in raw and session["approver_key"] not in raw


def test_agent_can_ask_and_order_in_a_sandbox(shop, monkeypatch):
    session = mint(monkeypatch).json()
    seen = {}

    async def fake_ask(text, requested, buyer_id, follow_up=None, have=None):
        seen.update(text=text, buyer_id=buyer_id)
        return {"intent": "order", "question": None, "buyer_id": buyer_id}

    monkeypatch.setattr("app.main.ask.ask", fake_ask)
    asked = c.post("/api/agent/ask", headers=order_headers(session),
                   json={"text": "milk", "requested_date": REQ.isoformat()})
    assert asked.status_code == 200 and seen["buyer_id"] == session["buyer_id"]

    placed = c.post("/api/orders", headers=order_headers(session),
                    json={"requested_date": REQ.isoformat(), "lines": [{"product_id": "463335", "quantity": 1}]})
    assert placed.status_code == 200 and placed.json()["status"] == "confirmed"


def test_only_sandbox_approver_can_approve(shop, monkeypatch):
    session = mint(monkeypatch).json()
    placed = c.post("/api/orders", headers=order_headers(session),
                    json={"requested_date": REQ.isoformat(), "lines": [{"product_id": "463335", "quantity": 600}]})
    assert placed.status_code == 200 and placed.json()["status"] == "pending_approval"
    order_id = placed.json()["order_id"]

    assert c.post(f"/api/orders/{order_id}/approve", headers=order_headers(session)).status_code == 401
    approved = c.post(f"/api/orders/{order_id}/approve", headers=approver_headers(session))
    assert approved.status_code == 200 and approved.json()["status"] == "confirmed"


def test_another_sandbox_cannot_read_this_sandbox_order(shop, monkeypatch):
    first, second = mint(monkeypatch).json(), mint(monkeypatch, "203.0.113.11").json()
    placed = c.post("/api/orders", headers=order_headers(first),
                    json={"requested_date": REQ.isoformat(), "lines": [{"product_id": "463335", "quantity": 1}]})
    assert placed.status_code == 200
    assert c.get(f"/api/orders/{placed.json()['order_id']}", headers=order_headers(second)).status_code == 404


def test_expired_sandbox_key_is_unauthorized(shop, monkeypatch, tmp_path):
    session = mint(monkeypatch).json()
    registry_path = tmp_path / "sandboxes.json"
    registry = json.loads(registry_path.read_text())
    registry[session["buyer_id"]]["expires_at"] = "2000-01-01T00:00:00+00:00"
    registry_path.write_text(json.dumps(registry))

    assert c.get("/api/profile", headers=order_headers(session)).status_code == 401


def test_sandbox_mints_are_limited_by_trusted_forwarded_ip(shop, monkeypatch):
    monkeypatch.setattr(config, "TRUST_X_FORWARDED_FOR", True)
    from app import ratelimit
    for _ in range(ratelimit.LIMITS["sandbox"][0]):  # venue Wi-Fi shares one IP: room for a judging table
        assert mint(monkeypatch, "198.51.100.40").status_code == 200
    limited = mint(monkeypatch, "198.51.100.40")
    assert limited.status_code == 429
    assert mint(monkeypatch, "198.51.100.41").status_code == 200


def test_sandbox_mint_is_not_available_when_disabled(shop, monkeypatch):
    monkeypatch.setattr(config, "SANDBOX_ENABLED", False, raising=False)
    assert c.post("/api/sandbox").status_code == 404


def test_expired_records_are_pruned_before_counting_live_sandboxes(shop, monkeypatch, tmp_path):
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    records = {f"try-{n:08x}": {"agent_key_hash": "a", "approver_key_hash": "b",
                                  "expires_at": future, "template": "helsinki-bistro"} for n in range(499)}
    records["try-deadbeef"] = {"agent_key_hash": "a", "approver_key_hash": "b",
                                "expires_at": "2000-01-01T00:00:00+00:00", "template": "helsinki-bistro"}
    (tmp_path / "sandboxes.json").write_text(json.dumps(records))

    created = mint(monkeypatch).json()
    saved = json.loads((tmp_path / "sandboxes.json").read_text())
    assert len(saved) == 500 and "try-deadbeef" not in saved and created["buyer_id"] in saved


def test_sandbox_cannot_exceed_max_live_records(shop, monkeypatch, tmp_path):
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    records = {f"try-{n:08x}": {"agent_key_hash": "a", "approver_key_hash": "b",
                                  "expires_at": future, "template": "helsinki-bistro"} for n in range(sandbox.MAX_LIVE)}
    (tmp_path / "sandboxes.json").write_text(json.dumps(records))

    blocked = mint(monkeypatch)
    assert blocked.status_code == 429


def test_one_address_cannot_fill_every_live_slot_within_the_ttl():
    from app import ratelimit
    per_ip, per_s = ratelimit.LIMITS["sandbox"]
    assert per_ip * (sandbox.TTL.total_seconds() / per_s) < sandbox.MAX_LIVE


def test_sandbox_reads_helsinki_template_without_copying_mutable_state(shop, monkeypatch, tmp_path):
    session = mint(monkeypatch).json()
    buyer_id = session["buyer_id"]

    profile = c.get("/api/profile", headers=order_headers(session))
    assert profile.status_code == 200
    assert profile.json()["dietary"] == [{"tag": "gluten_free", "label": "gluten-free",
                                           "because": "your profile says: Our kitchen is gluten-free"}]
    assert set(profile.json()["usual_product_ids"]) == {"464411", "475852", "471650"}

    kitchen = c.get("/api/kitchen/context", headers=order_headers(session))
    assert kitchen.status_code == 200 and kitchen.json()["simulated"] is True
    assert kitchen.json()["simulated_order_history"]["source"] == "demo seed (simulated order ledger)"
    assert mandates.get(buyer_id).per_line_cap_cents == mandates.get("helsinki-bistro").per_line_cap_cents
    assert not orders._store()
    assert not (tmp_path / "profiles" / f"{buyer_id}.jsonl").exists()
    assert not (tmp_path / "kitchen" / f"{buyer_id}.jsonl").exists()
