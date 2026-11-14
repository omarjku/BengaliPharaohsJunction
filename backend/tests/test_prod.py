"""Production gaps: Idempotency-Key, rate limits, DATA_DIR. Offline (conftest.py)."""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from conftest import REQ, store_mandate
from fastapi.testclient import TestClient

from app import orders, ratelimit
from app.main import app

c = TestClient(app, raise_server_exceptions=False)
AP = {"X-Approver-Key": "appr-chef"}
MANDATE = {"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9,
           "hard_rules": [{"kind": "auto_approve_limit_cents", "value": 100000}]}


def post(qty=1, key=None, agent="agent-chef", buyer="chef"):
    store_mandate(dict(MANDATE, buyer_id=buyer))
    h = {"X-Agent-Key": agent, **({"Idempotency-Key": key} if key else {})}
    return c.post("/api/orders", headers=h,
                  json={"requested_date": REQ.isoformat(), "lines": [{"product_id": "463335", "quantity": qty}]})


# --- 1. Idempotency-Key
def test_retry_with_the_same_key_places_one_order(shop):
    a, b = post(10, key="retry-1"), post(10, key="retry-1")
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json() and b.headers.get("Idempotent-Replayed") == "true"
    assert "Idempotent-Replayed" not in a.headers
    assert len(orders._store()) == 1 and len(shop.calls) == 1  # Valio asked once, one order, one audit entry
    assert len(c.get("/api/audit", headers=AP).json()) == 1


def test_same_key_different_body_is_422(shop):
    post(10, key="k")
    r = post(11, key="k")
    assert r.status_code == 422 and len(orders._store()) == 1


def test_without_a_key_each_post_is_a_new_order(shop):
    post(10), post(10)
    assert len(orders._store()) == 2


def test_keys_are_scoped_per_buyer(shop):
    post(10, key="shared"), post(10, key="shared", agent="agent-other", buyer="other")
    assert len(orders._store()) == 2


def test_approve_and_reject_retries_are_replayed_not_409(shop):
    oid = post(1000).json()["order_id"]
    h = {**AP, "Idempotency-Key": "approve-1"}
    first = c.post(f"/api/orders/{oid}/approve", headers=h)
    again = c.post(f"/api/orders/{oid}/approve", headers=h)
    assert first.json()["status"] == "confirmed" and again.status_code == 200 and again.json() == first.json()
    assert c.post(f"/api/orders/{oid}/approve", headers=AP).status_code == 409  # without the key: really twice
    oid = post(1000).json()["order_id"]
    h = {**AP, "Idempotency-Key": "reject-1"}
    assert c.post(f"/api/orders/{oid}/reject", headers=h).json() == c.post(f"/api/orders/{oid}/reject", headers=h).json()


def test_failures_are_not_stored_so_the_retry_runs(shop, monkeypatch):
    async def down(*a, **k):
        raise RuntimeError("valio down")
    real = shop.get_quotes
    monkeypatch.setattr("app.valio.get_quotes", down)
    assert post(10, key="flaky").status_code == 503
    monkeypatch.setattr("app.valio.get_quotes", real)
    r = post(10, key="flaky")
    assert r.status_code == 200 and "Idempotent-Replayed" not in r.headers and len(orders._store()) == 1


def test_keys_survive_a_restart_and_expire_after_24h(shop, monkeypatch):
    first = post(10, key="persist").json()
    monkeypatch.setattr(orders, "_idem", None)  # drop the in-memory copy
    assert post(10, key="persist").json() == first
    stored = json.loads(orders.IDEM_FILE.read_text())
    for rec in stored.values():
        rec["at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    orders.IDEM_FILE.write_text(json.dumps(stored))
    monkeypatch.setattr(orders, "_idem", None)
    assert post(10, key="persist").json()["order_id"] != first["order_id"]  # expired: a new order


def test_in_flight_duplicate_is_409(shop):
    orders._idem_store()["agent:chef:orders:busy"] = {"fingerprint": "x", "response": None,
                                                      "at": datetime.now(timezone.utc).isoformat()}
    import hashlib
    from app import signing
    body = {"buyer_id": None, "requested_date": REQ.isoformat(), "lines": [{"product_id": "463335", "quantity": 1.0}]}
    orders._idem_store()["agent:chef:orders:busy"]["fingerprint"] = hashlib.sha256(signing.canonical(body)).hexdigest()
    assert post(1, key="busy").status_code == 409


def test_bad_idempotency_key_is_422(shop):
    assert post(1, key="has space").status_code == 422
    assert post(1, key="x" * 256).status_code == 422
    assert shop.calls == []


# --- 2. Rate limits
def test_agent_burst_gets_429_with_retry_after(shop, monkeypatch):
    monkeypatch.setitem(ratelimit.LIMITS, "agent", (3, 60.0))
    codes = [post(1).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    r = post(1)
    assert r.status_code == 429 and 1 <= int(r.headers["Retry-After"]) <= 20
    assert post(1, agent="agent-other", buyer="other").status_code == 200  # per key, not global


def test_human_reads_limited_per_key(shop, monkeypatch):
    monkeypatch.setitem(ratelimit.LIMITS, "human", (2, 60.0))
    assert [c.get("/api/audit", headers=AP).status_code for _ in range(3)] == [200, 200, 429]
    assert c.get("/api/audit", headers={"X-Approver-Key": "appr-other"}).status_code == 200


def test_made_up_keys_share_the_ip_bucket(shop, monkeypatch):
    monkeypatch.setitem(ratelimit.LIMITS, "ip", (3, 60.0))
    codes = [c.get("/api/audit", headers={"X-Approver-Key": f"guess-{i}"}).status_code for i in range(4)]
    assert codes == [401, 401, 401, 429]  # rotating fake keys doesn't buy fresh buckets
    other_ip = {"X-Approver-Key": "guess", "X-Forwarded-For": "1.2.3.4, 9.9.9.9"}
    assert c.get("/api/audit", headers=other_ip).status_code == 401  # last XFF hop = the proxy-seen address


def test_buckets_refill_over_time():
    ratelimit._buckets.clear()
    cap, per = ratelimit.LIMITS["agent"]
    for _ in range(cap):
        assert ratelimit.wait_s("agent", "k", now=100.0) == 0
    assert ratelimit.wait_s("agent", "k", now=100.0) > 0
    assert ratelimit.wait_s("agent", "k", now=100.0 + per / cap) == 0  # one token back after per/cap seconds


def test_cors_preflight_and_non_api_paths_are_not_limited(shop, monkeypatch):
    monkeypatch.setitem(ratelimit.LIMITS, "ip", (1, 60.0))
    c.get("/api/health")
    assert c.get("/api/health").status_code == 429
    assert c.get("/.well-known/front-door-keys.json").status_code == 200
    assert c.options("/api/orders", headers={"Origin": "http://localhost:5173",
                                             "Access-Control-Request-Method": "POST"}).status_code == 200


# --- 3. DATA_DIR
def test_data_dir_moves_all_state(tmp_path):
    out = subprocess.run([sys.executable, "-c", "from app import orders; print(orders.ORDERS_FILE, orders.AUDIT_FILE, "
                          "orders.IDEM_FILE)"], env={**os.environ, "DATA_DIR": str(tmp_path)}, capture_output=True,
                         text=True, cwd=Path(__file__).resolve().parents[1], check=True).stdout.split()
    assert [Path(p).parent for p in out] == [tmp_path] * 3
    default = subprocess.run([sys.executable, "-c", "from app import orders; print(orders.ORDERS_FILE)"],
                             env={k: v for k, v in os.environ.items() if k != "DATA_DIR"}, capture_output=True,
                             text=True, cwd=Path(__file__).resolve().parents[1], check=True).stdout.strip()
    assert Path(default).parent.name == "data"
