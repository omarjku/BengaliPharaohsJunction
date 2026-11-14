"""Trust features: Valio's admin audit view and signed decisions. Offline (conftest.py)."""
from conftest import REQ, store_mandate
from fastapi.testclient import TestClient

from app import config, orders
from app.main import app

c = TestClient(app, raise_server_exceptions=False)
AG, AP, ADM = {"X-Agent-Key": "agent-chef"}, {"X-Approver-Key": "appr-chef"}, {"X-Valio-Admin-Key": "valio-ops"}
MANDATE = {"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9,
           "hard_rules": [{"kind": "auto_approve_limit_cents", "value": 100000}]}


def order(lines, buyer="chef"):
    store_mandate(dict(MANDATE, buyer_id=buyer))
    return c.post("/api/orders", headers={"X-Agent-Key": f"agent-{buyer}"},
                  json={"requested_date": REQ.isoformat(), "lines": [{"product_id": p, "quantity": q} for p, q in lines]})


# --- 1. Valio-side audit view
def test_admin_sees_every_buyer_and_can_filter(shop):
    order([("463335", 1)])                       # chef, AUTO
    order([("463335", 1000)])                    # chef, ASK_HUMAN (over the limit)
    order([("463335", 1)], buyer="other")        # other, AUTO
    rows = c.get("/api/admin/audit", headers=ADM).json()
    assert [r["input"]["request"]["buyer_id"] for r in rows] == ["chef", "chef", "other"]
    assert len(c.get("/api/admin/audit", params={"buyer_id": "other"}, headers=ADM).json()) == 1
    asks = c.get("/api/admin/audit", params={"outcome": "ASK_HUMAN"}, headers=ADM).json()
    assert len(asks) == 1 and asks[0]["decision"]["outcome"] == "ASK_HUMAN"
    assert len(c.get("/api/admin/audit", params={"limit": 2}, headers=ADM).json()) == 2
    assert c.get("/api/admin/audit", params={"outcome": "MAYBE"}, headers=ADM).status_code == 422


def test_admin_audit_needs_an_admin_key(shop, monkeypatch):
    assert c.get("/api/admin/audit").status_code == 401
    assert c.get("/api/admin/audit", headers={"X-Valio-Admin-Key": "nope"}).status_code == 401
    assert c.get("/api/admin/audit", headers={"X-Valio-Admin-Key": "appr-chef"}).status_code == 401  # approver ≠ admin
    assert c.get("/api/admin/audit", headers=AP).status_code == 401  # wrong header entirely
    monkeypatch.setattr(config, "VALIO_ADMIN_KEYS", "")
    assert c.get("/api/admin/audit", headers=ADM).status_code == 503  # never open by default


def test_admin_keys_are_read_only(shop, monkeypatch):
    oid = order([("463335", 1000)]).json()["order_id"]
    assert c.post(f"/api/orders/{oid}/approve", headers={"X-Approver-Key": "valio-ops"}).status_code == 401
    assert c.post("/api/orders", headers={"X-Agent-Key": "valio-ops"},
                  json={"requested_date": REQ.isoformat(), "lines": [{"product_id": "463335", "quantity": 1}]}
                  ).status_code == 401
    # misconfigured: the same secret listed as admin AND approver/agent → still read-only, and no admin view
    monkeypatch.setattr(config, "APPROVER_KEYS", config.APPROVER_KEYS + ",valio-ops=chef:Ops")
    monkeypatch.setattr(config, "AGENT_KEYS", config.AGENT_KEYS + ",valio-ops=chef")
    assert c.post(f"/api/orders/{oid}/approve", headers={"X-Approver-Key": "valio-ops"}).status_code == 403
    assert c.post("/api/orders", headers={"X-Agent-Key": "valio-ops"},
                  json={"requested_date": REQ.isoformat(), "lines": [{"product_id": "463335", "quantity": 1}]}
                  ).status_code == 403
    assert c.get("/api/admin/audit", headers=ADM).status_code == 403
    assert orders._store()[oid]["status"] == "pending_approval"


def test_buyer_audit_stays_scoped(shop):
    order([("463335", 1)])
    order([("463335", 1)], buyer="other")
    assert len(c.get("/api/audit", headers=AP).json()) == 1
