"""Front-door routes: place / approve / reject / get / audit, plus input validation. Offline (conftest.py)."""
import json
from datetime import timedelta

import pytest
from conftest import NOW, PAST, REQ, quote, store_mandate, outcome
from fastapi.testclient import TestClient

from app import orders, valio
from app.main import app

c = TestClient(app, raise_server_exceptions=False, headers={"X-Agent-Key": "agent-chef", "X-Approver-Key": "appr-chef"})
AGENT = {"chef": "agent-chef", "other": "agent-other"}
APPROVER = {"chef": "appr-chef", "other": "appr-other"}
MANDATE = {"id": "m1", "buyer_id": "chef", "hard_rules": [{"kind": "auto_approve_limit_cents", "value": 100000}],
           "per_line_cap_cents": 10**9}


def order(lines, buyer="chef", mandate=None, **extra):
    store_mandate(mandate or dict(MANDATE, buyer_id=buyer))
    body = {"buyer_id": buyer, "requested_date": REQ.isoformat(),
            "lines": [{"product_id": p, "quantity": q} for p, q in lines], **extra}
    return c.post("/api/orders", json=body, headers={"X-Agent-Key": AGENT.get(buyer, "agent-chef")})


def audit(buyer="chef"):
    r = c.get("/api/audit", headers={"X-Approver-Key": APPROVER.get(buyer, "appr-chef")})
    assert r.status_code == 200
    return r.json()


def test_auto_order_is_confirmed_stored_and_audited(shop):
    r = order([("463335", 10)])
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "confirmed" and body["decision"]["outcome"] == "AUTO" and body["total_cents"] == 1400
    got = c.get(f"/api/orders/{body['order_id']}").json()
    assert got["status"] == "confirmed" and got["lines"][0]["line_total_cents"] == 1400
    [entry] = audit()
    assert entry["id"] == body["audit_id"] and entry["actor"] == "valio_front_door"
    assert entry["input"]["request"]["id"] == body["order_id"] and entry["input"]["quotes"][0]["unit_price_cents"] == 140
    assert entry["input"]["mandate"]["id"] == "m1" and entry["decision"]["outcome"] == "AUTO"


@pytest.mark.parametrize("evidence, expected_status", [
    ({"status": "ok", "blocking_vulnerability_count": 2}, "pending_approval"),
    ({"status": "ok", "blocking_vulnerability_count": 0}, "confirmed"),
    ({"status": "unavailable", "blocking_vulnerability_count": 2}, "confirmed"),
])
def test_cached_craci_build_trust_gate_only_holds_blocking_builds(shop, monkeypatch, evidence, expected_status):
    monkeypatch.setattr(orders.craci_evidence, "cached_live_evidence", lambda *_: evidence)
    monkeypatch.setattr(orders.signing, "signed_build_provenance", lambda: evidence)

    body = order([("463335", 10)]).json()

    assert body["status"] == expected_status
    if expected_status == "pending_approval":
        reason = body["decision"]["primary_reason"]
        assert reason["code"] == "BUILD_NOT_TRUSTED"
        assert "2 known high-risk vulnerabilities" in reason["message"]
    else:
        assert body["decision"]["outcome"] == "AUTO"


def test_human_can_approve_a_build_trust_hold(shop, monkeypatch):
    monkeypatch.setattr(orders.craci_evidence, "cached_live_evidence",
                        lambda *_: {"status": "ok", "blocking_vulnerability_count": 1})
    monkeypatch.setattr(orders.signing, "signed_build_provenance",
                        lambda: {"status": "ok", "blocking_vulnerability_count": 1})

    held = order([("463335", 10)]).json()
    approved = c.post(f"/api/orders/{held['order_id']}/approve").json()

    assert held["status"] == "pending_approval"
    assert approved["status"] == "confirmed"


def test_refused_order_is_audited_but_not_stored(shop):
    body = order([("463038", 1)]).json()
    assert body["status"] == "refused" and body["order_id"] is None
    assert {r["code"] for r in body["decision"]["reasons"]} == {"CUTOFF_PASSED", "QTY_UNKNOWN"}
    assert body["decision"]["alternatives"] and orders._store() == {}
    [entry] = audit()
    assert entry["rejected_options"][0]["product_id"] == "463038"


def test_over_limit_waits_then_human_approves(shop):
    body = order([("463335", 1000)]).json()
    assert body["status"] == "pending_approval" and body["decision"]["primary_reason"]["code"] == "SPEND_OVER_LIMIT"
    oid = body["order_id"]
    calls = len(shop.calls)
    r = c.post(f"/api/orders/{oid}/approve", json={"approver": "Chef Aino"})
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    assert len(shop.calls) == calls + 1  # re-quoted at approval time
    assert c.get(f"/api/orders/{oid}").json()["signed_off_by"] == "Chef Aino"
    assert [e["actor"] for e in audit()] == ["valio_front_door", "human:Chef Aino:approve"]
    assert c.post(f"/api/orders/{oid}/approve", json={"approver": "Chef Aino"}).status_code == 409


def test_approve_rechecks_cutoff_that_passed_while_waiting(shop):
    oid = order([("463335", 1000)]).json()["order_id"]
    shop.quotes["463335"] = quote("463335", cutoff=PAST)  # the cut-off passed while the chef was deciding
    body = outcome(c.post(f"/api/orders/{oid}/approve", json={"approver": "Chef Aino"}))
    assert body["status"] == "refused" and "CUTOFF_PASSED" in {r["code"] for r in body["decision"]["reasons"]}
    assert c.get(f"/api/orders/{oid}").json()["status"] == "refused"


def test_approve_with_new_price_goes_back_to_the_human(shop):
    oid = order([("463335", 1000)]).json()["order_id"]
    shop.quotes["463335"] = quote("463335", price=1.5)
    body = outcome(c.post(f"/api/orders/{oid}/approve", json={"approver": "Chef Aino"}))
    assert body["status"] == "pending_approval" and "PRICE_CHANGED" in {r["code"] for r in body["decision"]["reasons"]}
    body = outcome(c.post(f"/api/orders/{oid}/approve", json={"approver": "Chef Aino"}))  # approves the new price
    assert body["status"] == "confirmed" and body["total_cents"] == 150000


def test_approved_later_delivery_is_stored_returned_and_audited(shop):
    later_date = REQ + timedelta(days=2)
    later = later_date.isoformat()
    shop.quotes["463335"] = quote("463335", avail_date=later_date)
    pending = order([("463335", 1000)]).json()
    assert pending["status"] == "pending_approval"

    approved = outcome(c.post(f"/api/orders/{pending['order_id']}/approve", json={"approver": "Chef Aino"}))
    assert approved["delivery_date"] == later
    stored = c.get(f"/api/orders/{pending['order_id']}").json()
    assert stored["delivery_date"] == later
    assert later in audit()[-1]["input"]["request"]["text"]


def test_reject(shop):
    oid = order([("463335", 1000)]).json()["order_id"]
    body = c.post(f"/api/orders/{oid}/reject", json={"approver": "Chef Aino"}).json()
    assert body["status"] == "rejected" and c.get(f"/api/orders/{oid}").json()["status"] == "rejected"
    assert audit()[-1]["actor"] == "human:Chef Aino:reject"
    assert c.post(f"/api/orders/{oid}/approve", json={"approver": "x"}).status_code == 409


def test_weekly_budget_counts_confirmed_orders(shop):
    m = dict(MANDATE, hard_rules=[], weekly_budget_cents=2000)
    assert order([("463335", 10)], mandate=m).json()["status"] == "confirmed"
    assert order([("463335", 10)], mandate=m).json()["decision"]["primary_reason"]["code"] == "WEEKLY_BUDGET_EXCEEDED"


def test_audit_is_per_buyer_and_append_only(shop):
    order([("463335", 1)])
    order([("463335", 1)], buyer="other", mandate=dict(MANDATE, buyer_id="other"))
    assert len(audit("chef")) == 1 and len(audit("other")) == 1
    lines = orders.AUDIT_FILE.read_text().splitlines()
    assert len(lines) == 2 and all(json.loads(x)["contract_version"] == "0.2" for x in lines)


def test_orders_survive_a_restart(shop, monkeypatch):
    oid = order([("463335", 1)]).json()["order_id"]
    monkeypatch.setattr(orders, "_orders", None)  # drop the in-memory copy
    assert c.get(f"/api/orders/{oid}").json()["status"] == "confirmed"


@pytest.mark.parametrize("body", [
    {"lines": [{"product_id": "DROP TABLE", "quantity": 1}]},
    {"lines": [{"product_id": "463335", "quantity": 0}]},
    {"lines": [{"product_id": "463335", "quantity": 100_001}]},
    {"lines": [{"product_id": "463335", "quantity": 1}] * 2},  # duplicate product
    {"lines": [{"product_id": str(i), "quantity": 1} for i in range(51)]},
    {"lines": []},
    {"requested_date": "2030-01-01"},
    {"requested_date": "monday"},
    {"buyer_id": "a b"},
    {"unit_price_cents": 1},  # the client can't set prices
    {"mandate": MANDATE},  # nor its own rules: the stored mandate decides
    {"lines": [{"product_id": "463335", "quantity": 1, "unit_price_cents": 1}]},
])
def test_order_validation_422(shop, body):
    store_mandate(MANDATE)
    base = {"buyer_id": "chef", "requested_date": REQ.isoformat(), "lines": [{"product_id": "463335", "quantity": 1}]}
    assert c.post("/api/orders", json={**base, **body}).status_code == 422
    assert shop.calls == []  # rejected before Valio is called


def test_unknown_ids_404_and_bad_ids_422(shop):
    missing = "00000000-0000-4000-8000-000000000000"
    assert c.get(f"/api/orders/{missing}").status_code == 404
    assert c.post(f"/api/orders/{missing}/approve", json={"approver": "A"}).status_code == 404
    assert c.post(f"/api/orders/{missing}/reject", json={"approver": "A"}).status_code == 404
    assert c.get("/api/orders/../../etc").status_code in (404, 422)
    assert c.get("/api/orders/not-a-uuid").status_code == 422
    assert c.get("/api/audit", params={"limit": 0}).status_code == 422


def test_valio_failure_is_503_without_leaking_details(shop, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("secret upstream https://internal/?key=abc")
    monkeypatch.setattr("app.valio.get_quotes", boom)
    r = order([("463335", 1)])
    assert r.status_code == 503 and "secret" not in r.text and "key" not in r.text
    [entry] = audit()  # the failure is on the record (ENGINE_ERROR), without the upstream details
    assert entry["decision"]["primary_reason"]["code"] == "ENGINE_ERROR" and orders._store() == {}
    assert "secret" not in orders.AUDIT_FILE.read_text()


def test_valio_429_is_a_calm_503_and_never_stores_order(shop, monkeypatch):
    async def busy(*a, **k):
        raise valio.ValioBusyError(valio.VALIO_BUSY_MESSAGE)

    monkeypatch.setattr(valio, "get_quotes", busy)
    r = order([("463335", 1)])
    assert r.status_code == 503 and r.json()["detail"] == valio.VALIO_BUSY_MESSAGE
    assert orders._store() == {}
