"""Regression tests for the T07 front-door security review, one block per finding. Offline (conftest.py)."""
import asyncio
import json
from datetime import date, timedelta
from types import SimpleNamespace as L

import httpx
import pytest
from conftest import NOW, REQ, product, quote, store_mandate
from fastapi.testclient import TestClient
from trade_contracts import Mandate

from app import config, gate, orders, valio
from app.main import app

c = TestClient(app, raise_server_exceptions=False)
AG = {"X-Agent-Key": "agent-chef"}
AP = {"X-Approver-Key": "appr-chef"}
MANDATE = {"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9}


def order(lines, mandate=None, headers=AG, **extra):
    store_mandate(mandate or MANDATE)
    body = {"requested_date": REQ.isoformat(), "lines": [{"product_id": p, "quantity": q} for p, q in lines], **extra}
    return c.post("/api/orders", json=body, headers=headers)


def run(lines, rules=(), **kw):
    m = Mandate(id="m1", buyer_id="chef", per_line_cap_cents=10**9,
                hard_rules=[{"kind": k, "value": v} for k, v in rules], **kw)
    return asyncio.run(gate.check([L(product_id=p, quantity=q) for p, q in lines], REQ, m, "r", now=NOW))


def codes(res):
    return [r.code.value for r in res.decision.reasons]


# 1. CRITICAL: REQUIRED_CLAIM and MAX_UNIT_PRICE_CENTS are enforced, alternatives included.
def test_required_claim_refuses_a_product_without_it_and_alternatives_must_have_it(shop):
    shop.products["107"] = product("107", "Oat drink 1 l", claims=("VEGAN", "FREE_FROM_LACTOSE"), contains=())
    shop.quotes["107"] = quote("107", price=1.9)
    shop.products["463335"]["substitutes"] = ["476240", "107"]  # 476240 is milk: not vegan
    res = run([("463335", 10)], [("required_claim", "VEGAN")])
    assert res.status == "refused"
    [r] = res.decision.reasons
    assert r.code == gate.CLAIM_MISSING and r.facts["required_claim"] == "VEGAN" and r.facts["hard_rule"]
    assert [a.product_id for a in res.decision.alternatives] == ["107"]
    assert "476240" in {ro.product_id for ro in res.rejected_options}
    assert run([("107", 1)], [("required_claim", "vegan")]).status == "confirmed"


def test_max_unit_price_refuses_a_dearer_item(shop):
    res = run([("463335", 1)], [("max_unit_price_cents", 10)])
    assert res.status == "refused" and codes(res) == [gate.UNIT_PRICE_OVER_MAX.value]
    assert res.decision.reasons[0].facts["unit_price_cents"] == 140
    assert run([("463335", 1)], [("max_unit_price_cents", 140)]).status == "confirmed"


def test_required_claim_is_refused_through_the_route(shop):
    assert order([("463335", 1)], dict(MANDATE, hard_rules=[{"kind": "required_claim", "value": "VEGAN"}])
                 ).json()["status"] == "refused"


# 2. CRITICAL: auth.
def test_no_keys_configured_means_503_never_open(shop, monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", "")
    monkeypatch.setattr(config, "APPROVER_KEYS", "")
    oid = "00000000-0000-4000-8000-000000000000"
    assert order([("463335", 1)]).status_code == 503
    assert c.get(f"/api/orders/{oid}", headers=AP).status_code == 503
    assert c.post(f"/api/orders/{oid}/approve", headers=AP).status_code == 503
    assert c.post(f"/api/orders/{oid}/reject", headers=AP).status_code == 503
    assert c.get("/api/audit", headers=AP).status_code == 503
    assert shop.calls == []


def test_missing_or_wrong_keys_are_401(shop):
    assert order([("463335", 1)], headers={}).status_code == 401
    assert order([("463335", 1)], headers={"X-Agent-Key": "nope"}).status_code == 401
    assert order([("463335", 1)], headers=AP).status_code == 401  # an approver key doesn't place orders
    assert c.get("/api/audit").status_code == 401
    assert shop.calls == []


def test_agent_keys_never_approve(shop, monkeypatch):
    oid = order([("463335", 1000)], dict(MANDATE, hard_rules=[{"kind": "auto_approve_limit_cents", "value": 100}])
                ).json()["order_id"]
    assert c.post(f"/api/orders/{oid}/approve", headers={"X-Approver-Key": "agent-chef"}).status_code == 401
    assert c.post(f"/api/orders/{oid}/approve", headers=AG).status_code == 401
    monkeypatch.setattr(config, "APPROVER_KEYS", config.APPROVER_KEYS + ",agent-chef=chef:Bot")  # misconfigured
    assert c.post(f"/api/orders/{oid}/approve", headers={"X-Approver-Key": "agent-chef"}).status_code == 403
    assert orders._store()[oid]["status"] == "pending_approval"


def test_buyer_comes_from_the_agent_key(shop):
    assert order([("463335", 1)], buyer_id="other").status_code == 403
    body = order([("463335", 1)], buyer_id="chef").json()
    assert orders._store()[body["order_id"]]["buyer_id"] == "chef" and len(shop.calls) == 1


def test_orders_are_judged_by_the_stored_mandate_never_the_clients(shop):
    store_mandate(dict(MANDATE, hard_rules=[{"kind": "max_unit_price_cents", "value": 10}]))
    r = c.post("/api/orders", headers=AG, json={"requested_date": REQ.isoformat(), "mandate": MANDATE,
                                                "lines": [{"product_id": "463335", "quantity": 1}]})
    assert r.status_code == 422 and shop.calls == []  # a body mandate is refused outright
    body = c.post("/api/orders", headers=AG, json={"requested_date": REQ.isoformat(),
                                                   "lines": [{"product_id": "463335", "quantity": 1}]}).json()
    assert body["status"] == "refused" and body["decision"]["reasons"][0]["facts"]["max_cents"] == 10


def test_no_stored_mandate_is_refused_without_calling_valio(shop):
    r = c.post("/api/orders", headers={"X-Agent-Key": "agent-other"},  # "other" has no mandate on file
               json={"requested_date": REQ.isoformat(), "lines": [{"product_id": "463335", "quantity": 1}]})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "refused" and body["order_id"] is None
    assert [x["code"] for x in body["decision"]["reasons"]] == ["MANDATE_MISSING"] and shop.calls == []
    [entry] = c.get("/api/audit", headers={"X-Approver-Key": "appr-other"}).json()
    assert entry["input"]["mandate"] is None and entry["decision"]["primary_reason"]["code"] == "MANDATE_MISSING"


def test_approve_uses_the_current_stored_mandate(shop, monkeypatch):
    m = dict(MANDATE, hard_rules=[{"kind": "auto_approve_limit_cents", "value": 100}])
    oid = order([("463335", 1000)], m).json()["order_id"]
    store_mandate(dict(m, hard_rules=m["hard_rules"] + [{"kind": "required_claim", "value": "VEGAN"}]))  # tightened
    assert c.post(f"/api/orders/{oid}/approve", headers=AP).json()["status"] == "refused"
    oid = order([("463335", 1000)], m).json()["order_id"]
    from app import mandates
    del mandates._MANDATES["chef"]  # mandate withdrawn while the order waited
    body = c.post(f"/api/orders/{oid}/approve", headers=AP).json()
    assert body["status"] == "refused" and body["decision"]["reasons"][0]["code"] == "MANDATE_MISSING"


def test_approver_must_belong_to_the_orders_buyer_and_name_comes_from_the_key(shop):
    oid = order([("463335", 1000)], dict(MANDATE, hard_rules=[{"kind": "auto_approve_limit_cents", "value": 100}])
                ).json()["order_id"]
    other = {"X-Approver-Key": "appr-other"}
    assert c.get(f"/api/orders/{oid}", headers=other).status_code == 404
    assert c.post(f"/api/orders/{oid}/approve", headers=other).status_code == 404
    assert c.post(f"/api/orders/{oid}/reject", headers=other).status_code == 404
    assert c.get("/api/audit", headers=other).json() == []
    assert c.get("/api/audit", params={"buyer_id": "chef"}, headers=other).status_code == 403
    r = c.post(f"/api/orders/{oid}/approve", json={"approver": "Mallory"}, headers=AP)
    assert r.json()["status"] == "confirmed" and orders._store()[oid]["signed_off_by"] == "Chef Aino"
    assert c.get("/api/audit", headers=AP).json()[-1]["actor"] == "human:Chef Aino:approve"


# 3. HIGH: approve compares facts and the total, not just (code, product).
def test_a_bigger_overrun_than_was_shown_goes_back_to_the_human(shop):
    m = dict(MANDATE, weekly_budget_cents=2000)
    assert order([("463335", 10)], m).json()["status"] == "confirmed"  # 1400 spent
    b = order([("463335", 10)], m).json()  # 2800 > 2000: shown spent 1400
    cc = order([("463335", 5)], m).json()  # 2100 > 2000
    assert b["status"] == cc["status"] == "pending_approval"
    assert c.post(f"/api/orders/{cc['order_id']}/approve", headers=AP).json()["status"] == "confirmed"
    r = c.post(f"/api/orders/{b['order_id']}/approve", headers=AP).json()  # same code + product, bigger overrun
    assert r["status"] == "pending_approval"
    assert r["decision"]["reasons"][0]["facts"]["spent_7d_cents"] == 2100
    assert c.post(f"/api/orders/{b['order_id']}/approve", headers=AP).json()["status"] == "confirmed"  # now seen


def test_approval_status_compares_total():
    shown = {"total_cents": 100, "decision": {"reasons": []}}
    res = L(status="pending_approval", total_cents=101, decision=L(reasons=[]))
    assert orders._approval_status(shown, res) == "pending_approval"
    assert orders._approval_status(shown, L(status="confirmed", total_cents=100, decision=L(reasons=[]))) == "confirmed"


# 4. MEDIUM: the gate decides on fresh quotes; get_quotes(fresh=True) skips the cache read.
def test_gate_asks_for_fresh_quotes(shop):
    run([("463335", 1)])
    assert shop.fresh[0] is True


def test_get_quotes_fresh_skips_cache_but_refreshes_it(monkeypatch):
    hits = []

    def handler(req):
        hits.append(req.url.path)
        body = json.loads(req.content)
        if req.url.path.endswith("availability"):
            return httpx.Response(200, json={"timeNow": NOW.isoformat(), "products": [
                {"productId": p, "logisticModel": "Stock", "closingTime": None, "scheduleLines": [
                    {"availableAmount": 5.0, "salesUnit": "ST", "availableDate": REQ.isoformat()}]}
                for p in body["products"]]})
        return httpx.Response(200, json={"currency": "EUR", "products": [
            {"productId": p, "catalogPrice": {"value": 1.4 + len(hits)}} for p in body["products"]]})

    monkeypatch.setattr(valio, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                                                    base_url="http://valio"))
    valio._cache.clear()
    asyncio.run(valio.get_quotes(["1"], "d"))
    asyncio.run(valio.get_quotes(["1"], "d"))
    assert len(hits) == 2  # second call served from cache
    q = asyncio.run(valio.get_quotes(["1"], "d", fresh=True))
    assert len(hits) == 4 and q[0]["price"] == 1.4 + 4
    assert asyncio.run(valio.get_quotes(["1"], "d"))[0]["price"] == 1.4 + 4  # cache refreshed


# 5. MEDIUM: no lock across Valio calls; decide again if the budget moved before commit.
def test_lock_is_not_held_during_valio_calls(shop, monkeypatch):
    held = []
    real = shop.get_quotes

    async def spy(*a, **k):
        held.append(orders._order_lock.locked())
        return await real(*a, **k)
    monkeypatch.setattr(valio, "get_quotes", spy)
    oid = order([("463335", 1000)], dict(MANDATE, hard_rules=[{"kind": "auto_approve_limit_cents", "value": 100}])
                ).json()["order_id"]
    c.post(f"/api/orders/{oid}/approve", headers=AP)
    assert held == [False, False]


def test_budget_change_between_decide_and_commit_is_redecided(shop, monkeypatch):
    m = dict(MANDATE, weekly_budget_cents=2000)
    real, sneaked = shop.get_quotes, []

    async def racing(*a, **k):  # another order of the buyer is confirmed while this one is being checked
        if not sneaked:
            sneaked.append(1)
            orders._store()["x"] = {"id": "x", "buyer_id": "chef", "status": "confirmed", "total_cents": 1500,
                                    "updated_at": NOW.isoformat()}
        return await real(*a, **k)
    monkeypatch.setattr(valio, "get_quotes", racing)
    body = order([("463335", 10)], m).json()  # 1400 alone fits; with the sneaked 1500 it doesn't
    assert body["status"] == "pending_approval"
    assert body["decision"]["reasons"][0]["code"] == "WEEKLY_BUDGET_EXCEEDED" and len(shop.calls) == 2


# 6. MEDIUM: size cap (mandates are server-side now, so no list caps), file I/O off the loop, torn audit lines.
def test_request_size_is_capped(shop):
    assert order([("463335", 1)], padding="x" * 70_000).status_code == 413
    chunks = iter([b'{"requested_date": "', REQ.isoformat().encode(), b'"}'])
    assert c.post("/api/orders", content=chunks, headers={**AG, "Content-Type": "application/json"}).status_code == 411
    assert shop.calls == []


def test_file_io_runs_off_the_event_loop(shop, monkeypatch):
    ran = []
    real = asyncio.to_thread

    async def spy(fn, *a, **k):
        ran.append(fn.__name__)
        return await real(fn, *a, **k)
    monkeypatch.setattr(orders.asyncio, "to_thread", spy)
    order([("463335", 1)])
    assert ran == ["_save", "_append_audit"]


def test_torn_audit_lines_are_skipped(shop):
    order([("463335", 1)])
    with open(orders.AUDIT_FILE, "a") as f:
        f.write('{"id": "torn", "inp\n[1, 2]\n')
    order([("463335", 1)])
    r = c.get("/api/audit", headers=AP)
    assert r.status_code == 200 and len(r.json()) == 2


# 7. MEDIUM: unknown allergen codes and bad numbers in rules → MANDATE_INVALID, not ignored, not 503.
def test_unknown_allergen_code_is_mandate_invalid(shop):
    res = run([("463335", 1)], [("excluded_allergen", "ZZ")])
    assert codes(res) == ["MANDATE_INVALID"] and res.status == "pending_approval"


@pytest.mark.parametrize("kind", ["max_unit_price_cents", "min_delivery_reliability", "auto_approve_limit_cents"])
@pytest.mark.parametrize("value", ["abc", "nan", "inf", float("nan")])
def test_bad_numeric_rule_is_mandate_invalid(shop, kind, value):
    res = run([("463335", 1)], [(kind, value)])
    assert codes(res) == ["MANDATE_INVALID"] and res.status == "pending_approval"


def test_bad_numeric_rule_via_route_is_not_503(shop):
    r = order([("463335", 1)], dict(MANDATE, hard_rules=[{"kind": "auto_approve_limit_cents", "value": "lots"}]))
    assert r.status_code == 200 and r.json()["decision"]["reasons"][0]["code"] == "MANDATE_INVALID"


# 8. LOW.
def test_alternatives_lookup_failure_means_no_alternatives(shop, monkeypatch):
    real = shop.get_quotes

    async def flaky(ids, d, customer="123", fresh=False):
        if not fresh:
            raise httpx.ConnectError("valio down")
        return await real(ids, d, customer, fresh)
    monkeypatch.setattr(valio, "get_quotes", flaky)
    res = run([("104", 1)])
    assert res.status == "refused" and res.decision.alternatives == []


def test_requested_date_in_the_past_is_422(shop):
    r = c.post("/api/orders", headers=AG, json={"requested_date": (date.today() - timedelta(days=1)).isoformat(),
                                                "mandate": MANDATE, "lines": [{"product_id": "463335", "quantity": 1}]})
    assert r.status_code == 422 and shop.calls == []


def test_line_total_must_be_at_least_a_cent(shop):
    shop.products["463335"]["lot_size"] = 0
    res = run([("463335", 0.003)])  # 0.42 cents rounds to 0
    assert res.status == "refused" and codes(res) == ["QTY_INVALID"]
    assert res.decision.reasons[0].facts["line_total_cents"] == 0


def test_nan_quantity_is_422_not_500(shop):
    raw = ('{"requested_date": "%s", "mandate": {"id": "m1", "buyer_id": "chef"}, '
           '"lines": [{"product_id": "463335", "quantity": NaN}]}' % REQ.isoformat())
    r = c.post("/api/orders", content=raw, headers={**AG, "Content-Type": "application/json"})
    assert r.status_code == 422 and shop.calls == []


# Codex review #3 follow-ups.
def test_approve_is_bound_to_the_decision_the_human_saw(shop):
    m = dict(MANDATE, hard_rules=[{"kind": "auto_approve_limit_cents", "value": 100}])
    body = order([("463335", 1000)], m).json()
    oid, seen = body["order_id"], body["decision"]["decided_at"]
    shop.quotes["463335"] = quote("463335", price=1.5)
    first = c.post(f"/api/orders/{oid}/approve", headers=AP, json={"decided_at": seen}).json()  # approver A
    assert first["status"] == "pending_approval"  # new price: back to the humans
    stale = c.post(f"/api/orders/{oid}/approve", headers=AP, json={"decided_at": seen})  # approver B, old screen
    assert stale.status_code == 409 and orders._store()[oid]["status"] == "pending_approval"
    ok = c.post(f"/api/orders/{oid}/approve", headers=AP, json={"decided_at": first["decision"]["decided_at"]})
    assert ok.json()["status"] == "confirmed"


def test_change_during_approve_is_409_not_a_silent_retry(shop, monkeypatch):
    m = dict(MANDATE, hard_rules=[{"kind": "auto_approve_limit_cents", "value": 100}])
    oid = order([("463335", 1000)], m).json()["order_id"]
    real = shop.get_quotes

    async def racing(*a, **k):  # another approver re-decides the order while this approval re-checks it
        orders._store()[oid]["updated_at"] = "changed"
        return await real(*a, **k)
    monkeypatch.setattr(valio, "get_quotes", racing)
    assert c.post(f"/api/orders/{oid}/approve", headers=AP).status_code == 409
    assert orders._store()[oid]["status"] == "pending_approval"


def test_gate_refuses_past_dates_whoever_calls_it(shop):
    from datetime import date as d
    m = Mandate(id="m1", buyer_id="chef", per_line_cap_cents=10**9)
    res = asyncio.run(gate.check([L(product_id="463335", quantity=1)], d.today() - timedelta(days=1), m, "r", now=NOW))
    assert res.status == "refused" and "DATE_NOT_HONOURED" in codes(res)
