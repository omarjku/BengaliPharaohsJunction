"""What the independent QA couldn't test: races, upstream failures, restarts, buyer isolation, and quotes changing
between hold and approval. Offline (conftest.py); races run concurrently through the real ASGI app."""
import asyncio
import json

import httpx
import pytest
from conftest import REQ, quote, store_mandate, outcome
from fastapi.testclient import TestClient

from app import agent, mandates, orders, valio
from app.main import app

REAL_GET_QUOTES = valio.get_quotes  # captured before the shop fixture swaps in the fake
c = TestClient(app, raise_server_exceptions=False)
AG, AP, ADM = {"X-Agent-Key": "agent-chef"}, {"X-Approver-Key": "appr-chef"}, {"X-Valio-Admin-Key": "valio-ops"}
MANDATE = {"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9,
           "hard_rules": [{"kind": "auto_approve_limit_cents", "value": 100000}]}


def body(qty, pid="463335"):
    return {"requested_date": REQ.isoformat(), "lines": [{"product_id": pid, "quantity": qty}]}


def post(qty, headers=AG, mandate=None):
    store_mandate(mandate or MANDATE)
    return c.post("/api/orders", headers=headers, json=body(qty))


def slow_valio(shop, monkeypatch, delay=0.05):
    """Make every Valio call take a while so concurrent requests really interleave."""
    fast = shop.get_quotes

    async def slow(*a, **k):
        await asyncio.sleep(delay)
        return await fast(*a, **k)
    monkeypatch.setattr(valio, "get_quotes", slow)


async def concurrently(*requests):
    # The app's locks belong to one event loop (uvicorn has exactly one); this race runs in its own loop, so it gets
    # fresh ones. Production code is unchanged.
    orders._order_lock, orders._idem_save = asyncio.Lock(), asyncio.Lock()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://door") as cl:
        return await asyncio.gather(*(cl.request(m, url, **kw) for m, url, kw in requests))


# --- 1. Races
def test_two_concurrent_approvals_confirm_exactly_once(shop, monkeypatch):
    oid = post(1000).json()["order_id"]
    slow_valio(shop, monkeypatch)
    a, b = asyncio.run(concurrently(("POST", f"/api/orders/{oid}/approve", {"headers": AP}),
                                    ("POST", f"/api/orders/{oid}/approve", {"headers": AP})))
    assert sorted([a.status_code, b.status_code]) == [200, 409]
    assert orders._store()[oid]["status"] == "confirmed"
    approvals = [e for e in orders.audit_log("chef", 100) if (e.get("front_door") or {}).get("action") == "approved"]
    assert len(approvals) == 1


def test_two_orders_racing_one_weekly_budget_never_both_auto_confirm(shop, monkeypatch):
    store_mandate(dict(MANDATE, hard_rules=[], weekly_budget_cents=2000))  # each order 1400: only one fits
    slow_valio(shop, monkeypatch)
    a, b = asyncio.run(concurrently(("POST", "/api/orders", {"headers": AG, "json": body(10)}),
                                    ("POST", "/api/orders", {"headers": AG, "json": body(10)})))
    statuses = sorted([a.json()["status"], b.json()["status"]])
    assert statuses == ["confirmed", "pending_approval"]
    held = a.json() if a.json()["status"] == "pending_approval" else b.json()
    assert held["decision"]["primary_reason"]["code"] == "WEEKLY_BUDGET_EXCEEDED"
    confirmed = sum(o["total_cents"] for o in orders._store().values() if o["status"] == "confirmed")
    assert confirmed <= 2000


def test_same_idempotency_key_sent_concurrently_places_one_order(shop, monkeypatch):
    store_mandate(MANDATE)
    slow_valio(shop, monkeypatch)
    h = {**AG, "Idempotency-Key": "race-1"}
    rs = asyncio.run(concurrently(*[("POST", "/api/orders", {"headers": h, "json": body(10)})] * 3))
    assert len(orders._store()) == 1 and len(shop.calls) == 1
    assert sorted(r.status_code for r in rs) == [200, 409, 409]  # the duplicates are told it's still running
    assert c.post("/api/orders", headers=h, json=body(10)).headers.get("Idempotent-Replayed") == "true"


# --- 2. Failure modes: Valio down / slow / broken, Gemini down
def broken_valio(monkeypatch, mode):
    def handler(request):
        if mode == "down":
            raise httpx.ConnectError("connection refused to secret-host")
        if mode == "timeout":
            raise httpx.ReadTimeout("read timed out")
        if mode == "500":
            return httpx.Response(500, text="Traceback (most recent call last): internal secret")
        return httpx.Response(200, text="{not json")  # malformed
    monkeypatch.setattr(valio, "get_quotes", REAL_GET_QUOTES)
    monkeypatch.setattr(valio, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                                                    base_url="http://valio"))
    valio._cache.clear()


MODES = ["down", "timeout", "500", "malformed"]


def no_leak(r):
    assert "Traceback" not in r.text and "secret" not in r.text and "ConnectError" not in r.text


@pytest.mark.parametrize("mode", MODES)
def test_valio_failure_on_order_is_a_clean_503_audited_nothing_ordered(shop, monkeypatch, mode):
    store_mandate(MANDATE)
    broken_valio(monkeypatch, mode)
    r = c.post("/api/orders", headers=AG, json=body(10))
    assert r.status_code == 503 and orders._store() == {}
    no_leak(r)
    [entry] = orders.audit_log("chef", 10)
    assert entry["decision"]["primary_reason"]["code"] == "ENGINE_ERROR"
    assert entry["front_door"]["status"] == "failed"


@pytest.mark.parametrize("mode", MODES)
def test_valio_failure_on_approve_leaves_the_order_pending_and_audited(shop, monkeypatch, mode):
    oid = post(1000).json()["order_id"]
    broken_valio(monkeypatch, mode)
    r = c.post(f"/api/orders/{oid}/approve", headers=AP)
    assert r.status_code == 503 and orders._store()[oid]["status"] == "pending_approval"
    no_leak(r)
    last = orders.audit_log("chef", 10)[-1]
    assert last["front_door"]["action"] == "approval_failed" and last["front_door"]["status"] == "pending_approval"
    monkeypatch.setattr(valio, "get_quotes", shop.get_quotes)  # Valio back: the approval goes through
    assert outcome(c.post(f"/api/orders/{oid}/approve", headers=AP))["status"] == "confirmed"


@pytest.fixture
def lapland(shop, monkeypatch):
    for p in shop.products.values():
        p.update(base_unit="ST", units={"ST": 1.0, "KI": 10.0}, volume={"unit": "LTR", "value": 1.0}, net_weight=None)
    from app import config
    monkeypatch.setattr(config, "AGENT_KEYS", config.AGENT_KEYS + ",agent-lk=lapland-kitchen")
    return shop


def agent_run(text="20 L lactose-free milk for Monday"):
    return c.post("/api/agent/run", headers={"X-Agent-Key": "agent-lk"},
                  json={"text": text, "requested_date": REQ.isoformat()})


@pytest.mark.parametrize("mode", MODES)
def test_valio_failure_during_agent_run_asks_and_orders_nothing(lapland, monkeypatch, mode):
    async def gemini(system, prompt, schema):
        if schema is agent._PARSE_SCHEMA:
            return {"summary": "milk", "items": [{"query": "milk", "amount": 20, "unit": "L",
                                                  "dietary": ["lactose_free"]}]}
        return {"ids": ["463335"]}

    async def decide(text, questions):
        return {k: {"type": "noul", "noul": 0.95} for k in questions}
    monkeypatch.setattr(agent, "_gemini", gemini)
    monkeypatch.setattr(agent, "_decisions", decide)
    broken_valio(monkeypatch, mode)
    r = agent_run()
    assert r.status_code == 200
    no_leak(r)
    out = r.json()
    assert out["order"] is None or out["order"]["status"] != "confirmed"
    assert out["decision"]["outcome"] != "AUTO" and orders._store() == {}
    assert orders.audit_log("lapland-kitchen", 10)  # the run is on the record


def test_gemini_down_during_agent_run_falls_back_and_never_auto_orders(lapland, monkeypatch):
    async def down(*a, **k):
        return None
    monkeypatch.setattr(agent, "_gemini", down)
    monkeypatch.setattr(agent, "_decisions", down)
    r = agent_run()
    assert r.status_code == 200
    out = r.json()
    assert "fallback" in out["request"]["summary"]
    assert not (out["order"] and out["order"]["status"] == "confirmed")
    assert out["decision"]["outcome"] != "AUTO" and not any(o["status"] == "confirmed" for o in orders._store().values())


# --- 3. Restart persistence (DATA_DIR = tmp dir via conftest)
def restart(monkeypatch):
    """Drop every in-memory copy, as a process restart would; the files under DATA_DIR stay."""
    monkeypatch.setattr(orders, "_orders", None)
    monkeypatch.setattr(orders, "_idem", None)


def test_place_restart_approve_keeps_a_continuous_audit(shop, monkeypatch):
    oid = post(1000).json()["order_id"]
    restart(monkeypatch)
    r = c.post(f"/api/orders/{oid}/approve", headers=AP)
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    restart(monkeypatch)
    assert c.get(f"/api/orders/{oid}", headers=AP).json()["signed_off_by"] == "Chef Aino"
    actions = [e["front_door"]["action"] for e in c.get("/api/audit", headers=AP).json()]
    assert actions == ["order", "approved"]


def test_idempotency_replay_and_saved_mandates_survive_a_restart(shop, monkeypatch):
    store_mandate(MANDATE)
    h = {**AG, "Idempotency-Key": "restart-1"}
    first = c.post("/api/orders", headers=h, json=body(10)).json()
    restart(monkeypatch)
    again = c.post("/api/orders", headers=h, json=body(10))
    assert again.json() == first and again.headers.get("Idempotent-Replayed") == "true"
    assert len(orders._store()) == 1


# --- 4. A second buyer can't reach the first one's orders through any route
def test_buyer_b_cannot_read_approve_reject_or_audit_buyer_a(shop):
    oid = post(1000).json()["order_id"]
    store_mandate(dict(MANDATE, buyer_id="other"))
    b_agent, b_appr = {"X-Agent-Key": "agent-other"}, {"X-Approver-Key": "appr-other"}
    assert c.get(f"/api/orders/{oid}", headers=b_appr).status_code == 404
    assert c.get(f"/api/orders/{oid}", headers=b_agent).status_code == 404  # MCP-style agent read
    assert c.post(f"/api/orders/{oid}/approve", headers=b_appr).status_code == 404
    assert c.post(f"/api/orders/{oid}/reject", headers=b_appr).status_code == 404
    assert c.post(f"/api/orders/{oid}/approve", headers=b_agent).status_code == 401
    assert c.get("/api/audit", headers=b_appr).json() == []
    assert c.get("/api/audit", params={"buyer_id": "chef"}, headers=b_appr).status_code == 403
    assert c.get("/api/admin/audit", headers={"X-Valio-Admin-Key": "appr-other"}).status_code == 401
    assert c.get("/api/admin/audit", headers=b_appr).status_code == 401
    r = c.post("/api/orders", headers=b_agent, json={**body(1), "buyer_id": "chef"})  # order as A
    assert r.status_code == 403
    assert orders._store()[oid]["status"] == "pending_approval" and len(orders._store()) == 1
    assert c.get("/api/admin/audit", params={"buyer_id": "chef"}, headers=ADM).status_code == 200  # Valio sees all


# --- 5. Quote changes between hold and approval
def test_higher_price_at_approval_goes_back_to_pending_with_the_new_total(shop):
    held = post(1000).json()
    assert held["status"] == "pending_approval" and held["total_cents"] == 140000
    shop.quotes["463335"] = quote("463335", price=1.6)
    r = outcome(c.post(f"/api/orders/{held['order_id']}/approve", headers=AP))
    assert r["status"] == "pending_approval" and r["total_cents"] == 160000
    changed = next(x for x in r["decision"]["reasons"] if x["code"] == "PRICE_CHANGED")
    assert changed["facts"] == {"old_unit_price_cents": 140, "unit_price_cents": 160}
    assert orders._store()[held["order_id"]]["status"] == "pending_approval"


def test_stock_dropping_below_the_quantity_refuses_with_a_split(shop):
    held = post(1000).json()
    shop.quotes["463335"] = quote("463335", amount=400.0)  # sold out to 400 while the chef decided
    r = outcome(c.post(f"/api/orders/{held['order_id']}/approve", headers=AP))
    assert r["status"] == "refused" and "STOCK_PARTIAL" in [x["code"] for x in r["decision"]["reasons"]]
    split = r["alternative_order"]
    assert split["order_lines"][0] == {"product_id": "463335", "quantity": 400.0}
    assert sum(x["quantity"] for x in split["order_lines"]) >= 1000
    assert orders._store()[held["order_id"]]["status"] == "refused"
