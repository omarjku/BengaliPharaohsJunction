"""Production gaps: Idempotency-Key, rate limits, DATA_DIR. Offline (conftest.py)."""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from conftest import REQ, store_mandate
from fastapi.testclient import TestClient

from app import config, mandates, orders, ratelimit
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


def kid(key: str) -> str:
    """The credential label conftest gives each key (its name, else its buyer): never derived from the secret."""
    return {"agent-chef": "chef", "agent-other": "other"}[key]


def test_in_flight_duplicate_is_409(shop):
    import hashlib
    from app import signing
    body = {"requested_date": REQ.isoformat(), "lines": [{"product_id": "463335", "quantity": 1.0}]}
    orders._idem_store()[f"agent:chef:orders:{kid('agent-chef')}:busy"] = {
        "caller": "chef", "fingerprint": hashlib.sha256(signing.canonical(body)).hexdigest(), "response": None,
        "at": datetime.now(timezone.utc).isoformat()}
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
    spoof = {"X-Approver-Key": "guess", "X-Forwarded-For": "1.2.3.4, 9.9.9.9"}
    assert c.get("/api/audit", headers=spoof).status_code == 429  # no trusted proxy: the header picks nothing
    monkeypatch.setattr(config, "TRUST_X_FORWARDED_FOR", True)  # behind Render's proxy
    assert c.get("/api/audit", headers=spoof).status_code == 401  # last hop = the address the proxy saw


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
    out = subprocess.run([sys.executable, "-c", "from app import mandates, orders; print(orders.ORDERS_FILE, "
                          "orders.AUDIT_FILE, orders.IDEM_FILE, mandates.STORE)"], env={**os.environ, "DATA_DIR": str(tmp_path)}, capture_output=True,
                         text=True, cwd=Path(__file__).resolve().parents[1], check=True).stdout.split()
    assert [Path(p).parent for p in out] == [tmp_path] * 4
    default = subprocess.run([sys.executable, "-c", "from app import orders; print(orders.ORDERS_FILE)"],
                             env={k: v for k, v in os.environ.items() if k != "DATA_DIR"}, capture_output=True,
                             text=True, cwd=Path(__file__).resolve().parents[1], check=True).stdout.strip()
    assert Path(default).parent.name == "data"


# --- agents can follow their own orders (Room 1's MCP server)
def test_agent_reads_its_own_buyers_order_only(shop):
    oid = post(1000).json()["order_id"]  # pending approval
    assert c.get(f"/api/orders/{oid}", headers={"X-Agent-Key": "agent-chef"}).json()["status"] == "pending_approval"
    assert c.get(f"/api/orders/{oid}", headers={"X-Agent-Key": "agent-other"}).status_code == 404  # other buyer
    assert c.get(f"/api/orders/{oid}", headers={"X-Agent-Key": "guess"}).status_code == 401
    assert c.get(f"/api/orders/{oid}").status_code == 401
    assert c.get(f"/api/orders/{oid}", headers=AP).status_code == 200  # approvers as before
    for action in ("approve", "reject"):  # still approver-only
        assert c.post(f"/api/orders/{oid}/{action}", headers={"X-Agent-Key": "agent-chef"}).status_code == 401
    assert orders._store()[oid]["status"] == "pending_approval"


# --- automated security review follow-ups
def test_bucket_overflow_never_resets_drained_or_key_buckets(monkeypatch):
    ratelimit._buckets.clear()
    monkeypatch.setattr(ratelimit, "MAX_BUCKETS", 50)
    cap = ratelimit.LIMITS["agent"][0]
    for _ in range(cap):
        ratelimit.wait_s("agent", "key-holder", now=0.0)
    for _ in range(ratelimit.LIMITS["ip"][0]):
        ratelimit.wait_s("ip", "attacker", now=0.0)
    for i in range(500):  # flood of fresh addresses
        ratelimit.wait_s("ip", f"10.0.{i // 250}.{i % 250}", now=0.0)
    assert ratelimit.wait_s("agent", "key-holder", now=0.0) > 0  # still limited
    assert ratelimit.wait_s("ip", "attacker", now=0.0) > 0       # still limited
    assert len(ratelimit._buckets) <= 60


def test_ipv6_callers_share_a_slash_64():
    assert ratelimit._ip("2001:db8::1") == ratelimit._ip("2001:db8::ffff") == "2001:db8::/64"
    assert ratelimit._ip("203.0.113.9") == "203.0.113.9" and ratelimit._ip("testclient") == "testclient"


def test_idempotency_quota_is_per_caller_and_never_evicts_another_buyers_keys(shop, monkeypatch):
    monkeypatch.setattr(orders, "IDEM_PER_CALLER", 3)
    post(1, key="theirs", agent="agent-other", buyer="other")
    for i in range(5):
        post(1, key=f"k{i}")  # chef floods its own quota
    keys = list(orders._idem_store())
    assert f"agent:other:orders:{kid('agent-other')}:theirs" in keys  # the other buyer's retry protection survives
    assert [k for k in keys if k.startswith("agent:chef")] == [f"agent:chef:orders:{kid('agent-chef')}:k{i}"
                                                               for i in (2, 3, 4)]
    assert json.loads(orders.IDEM_FILE.read_text()).keys() == orders._idem_store().keys()


# --- Codex review of room2-prod
def test_two_credentials_of_one_buyer_never_share_a_replay(shop, monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", config.AGENT_KEYS + ",agent-chef-2=chef:second agent")
    a, b = post(10, key="same"), post(10, key="same", agent="agent-chef-2")
    assert a.json()["order_id"] != b.json()["order_id"] and "Idempotent-Replayed" not in b.headers


def test_equivalent_requests_share_a_fingerprint(shop):
    oid = post(1000).json()["order_id"]
    h = {**AP, "Idempotency-Key": "ap"}
    first = c.post(f"/api/orders/{oid}/approve", headers=h)  # no body
    again = c.post(f"/api/orders/{oid}/approve", headers=h, json={})  # empty body: same action
    assert again.status_code == 200 and again.headers.get("Idempotent-Replayed") == "true" and again.json() == first.json()
    r1, r2 = post(5, key="buyer"), None
    store_mandate(MANDATE)
    r2 = c.post("/api/orders", headers={"X-Agent-Key": "agent-chef", "Idempotency-Key": "buyer"},
                json={"buyer_id": "chef", "requested_date": REQ.isoformat(),
                      "lines": [{"product_id": "463335", "quantity": 5}]})
    assert r2.headers.get("Idempotent-Replayed") == "true" and r2.json() == r1.json()


def test_stored_replay_is_served_while_the_catalogue_loads(shop, monkeypatch):
    from app import catalogue
    first = post(10, key="boot").json()
    monkeypatch.setattr(catalogue, "_ready", type("E", (), {"is_set": lambda self: False})())
    assert post(10, key="boot").json() == first   # replay: no catalogue needed
    assert post(11, key="new").status_code == 503  # a new action still waits for it


def test_idempotency_store_holds_no_trace_of_the_secret(shop):
    post(10, key="k1")
    import hashlib
    text = orders.IDEM_FILE.read_text()
    assert "agent-chef" not in text and hashlib.sha256(b"agent-chef").hexdigest()[:16] not in text


def test_health_reports_the_deployed_commit(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "54ad847abc")
    assert c.get("/api/health").json()["commit"] == "54ad847abc"
    monkeypatch.delenv("RENDER_GIT_COMMIT")
    assert c.get("/api/health").json()["commit"] is None
