"""QA round 2 (docs/testing/independent-qa-round2-2026-11-14.md): N3, N4, N13, N14, N11. Offline (conftest.py)."""
import asyncio
from types import SimpleNamespace as L

import pytest
from conftest import NOW, REQ, product, quote, store_mandate
from fastapi.testclient import TestClient
from test_agent import ITEM, codes, decisions, gemini, run, shop1  # noqa: F401 - fixtures + helpers
from trade_contracts import Mandate

from app import gate, orders
from app.main import app
from app.signing import verify

c = TestClient(app, raise_server_exceptions=False)
AG, AP = {"X-Agent-Key": "agent-chef"}, {"X-Approver-Key": "appr-chef"}
MANDATE = {"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9,
           "hard_rules": [{"kind": "auto_approve_limit_cents", "value": 100000}]}


def held_order():
    store_mandate(MANDATE)
    return c.post("/api/orders", headers=AG, json={"requested_date": REQ.isoformat(),
                                                   "lines": [{"product_id": "463335", "quantity": 1000}]}).json()


# --- N3 / N13: an approve that doesn't approve is a 409; the approver is named, and signed
def test_approve_after_a_rules_change_is_409_with_the_new_decision(shop):
    held = held_order()
    store_mandate(dict(MANDATE, id="m2", hard_rules=[{"kind": "auto_approve_limit_cents", "value": 50000}]))  # tighter
    r = c.post(f"/api/orders/{held['order_id']}/approve", headers=AP, json={"decided_at": held["decision"]["decided_at"]})
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["status"] == "pending_approval" and d["mandate_version"] == "m2" and "Not approved" in d["error"]
    assert d["decision"]["decided_at"] != held["decision"]["decided_at"] and d["signed_off_by"] is None
    assert orders._store()[held["order_id"]]["status"] == "pending_approval"
    ok = c.post(f"/api/orders/{held['order_id']}/approve", headers=AP, json={"decided_at": d["decision"]["decided_at"]})
    assert ok.status_code == 200 and ok.json()["status"] == "confirmed" and ok.json()["signed_off_by"] == "Chef Aino"


def test_approved_and_rejected_statements_name_the_human(shop):
    held = held_order()
    ok = c.post(f"/api/orders/{held['order_id']}/approve", headers=AP).json()
    assert ok["signed_statement"]["signed_off_by"] == "Chef Aino" and verify(ok["signed_statement"], ok["signature"])
    assert held["signed_statement"]["signed_off_by"] is None  # the door's own decision has no human on it
    held2 = held_order()
    rej = c.post(f"/api/orders/{held2['order_id']}/reject", headers=AP).json()
    assert rej["signed_statement"]["signed_off_by"] == "Chef Aino"


def test_approve_that_the_recheck_refuses_is_409_too(shop):
    held = held_order()
    shop.quotes["463335"] = quote("463335", amount=0.0)  # sold out meanwhile
    r = c.post(f"/api/orders/{held['order_id']}/approve", headers=AP)
    assert r.status_code == 409 and r.json()["detail"]["status"] == "refused"


# --- N4: substitutes that add allergens say so and are never "best"
def test_substitute_adding_allergens_is_excluded_and_says_which(shop):
    shop.products["464315"] = product("464315", "PCD 500G PEANUT BUTTER", category="21453", claims=(), contains=(),
                                      subs=("468793", "470000"))
    shop.products["468793"] = product("468793", "Nugatti hazelnut-cocoa spread 500g", category="21453", claims=(),
                                      contains=("AM", "AN", "AY", "ML", "SH"))
    shop.products["470000"] = product("470000", "Sunflower seed butter", category="21453", claims=(), contains=())
    shop.products["470000"]["allergens"]["free_from"] = ["AP"]
    shop.quotes.update({"464315": quote("464315"), "468793": quote("468793", price=3.0),
                        "470000": quote("470000", price=4.0)})
    m = Mandate(id="m1", buyer_id="chef", per_line_cap_cents=10**9, hard_rules=[{"kind": "excluded_allergen", "value": "AP"}])
    res = asyncio.run(gate.check([L(product_id="464315", quantity=1)], REQ, m, "r", now=NOW))
    assert res.status == "refused"  # the name says peanut
    subs = {s["product_id"]: s for s in res.substitutes}
    assert "468793" not in subs
    rejected = next(ro for ro in res.rejected_options if ro.product_id == "468793")
    assert any("adds allergens" in reason.message and "milk" in reason.message and "tree nuts" in reason.message
               for reason in rejected.reasons)
    assert subs["470000"]["tier"] == "best"  # dearer, but adds nothing


# --- N4: the agent respects Gemini's acceptability: below the threshold = at most "good", and says so
def test_doubted_substitute_is_at_most_good(shop1, monkeypatch, decisions):  # noqa: F811
    gemini(monkeypatch, ITEM, ranked=["463038"])  # Terminal, cut-off passed → substitutes from the door's finder
    decisions["scores"] = {"sub": 0.04}
    alts = run()["decision"]["alternatives"]
    assert alts and all(not a["summary"].startswith(("BEST", "BETTER")) for a in alts)
    assert all("Gemini doubts this substitute" in a["summary"] for a in alts)


def test_a_not_approved_409_is_replayed_for_the_same_idempotency_key(shop):
    """Automated security review: the 409 must not be dropped, or a retry with the same key re-runs approve
    against the NEW decision and confirms terms nobody looked at."""
    held = held_order()
    store_mandate(dict(MANDATE, id="m2", hard_rules=[{"kind": "auto_approve_limit_cents", "value": 50000}]))
    h = {**AP, "Idempotency-Key": "approve-once"}
    first = c.post(f"/api/orders/{held['order_id']}/approve", headers=h)
    again = c.post(f"/api/orders/{held['order_id']}/approve", headers=h)
    assert first.status_code == again.status_code == 409 and again.headers.get("Idempotent-Replayed") == "true"
    assert again.json() == first.json() and orders._store()[held["order_id"]]["status"] == "pending_approval"
    orders._idem = None  # survives a restart too
    assert c.post(f"/api/orders/{held['order_id']}/approve", headers=h).status_code == 409
    assert orders._store()[held["order_id"]]["status"] == "pending_approval"


def test_rules_saved_without_if_match_get_a_warning(shop1, monkeypatch):  # noqa: F811
    from app import config, mandates
    monkeypatch.setattr(config, "APPROVER_KEYS", config.APPROVER_KEYS + ",appr-lk=lapland-kitchen:Chef Aino")
    h = {"X-Approver-Key": "appr-lk"}
    m = mandates.get("lapland-kitchen").model_dump(mode="json")
    r = c.put("/api/mandate", headers=h, json={"mandate": {**m, "weekly_budget_cents": 500000}})
    assert r.status_code == 200 and r.headers["Warning"].startswith("299 -") and "If-Match" in r.json()["warning"]
    etag = r.headers["ETag"]
    ok = c.put("/api/mandate", headers={**h, "If-Match": etag}, json={"mandate": {**m, "weekly_budget_cents": 400000}})
    assert ok.status_code == 200 and "Warning" not in ok.headers and "warning" not in ok.json()


def test_cross_buyer_attempts_are_audited_for_valio_only(shop):
    held = held_order()
    store_mandate(dict(MANDATE, buyer_id="other"))
    b_appr, b_agent = {"X-Approver-Key": "appr-other"}, {"X-Agent-Key": "agent-other"}
    assert c.get(f"/api/orders/{held['order_id']}", headers=b_appr).status_code == 404
    assert c.post(f"/api/orders/{held['order_id']}/approve", headers=b_appr).status_code == 404
    assert c.post(f"/api/orders/{held['order_id']}/reject", headers=b_appr).status_code == 404
    unknown = "00000000-0000-4000-8000-000000000000"
    assert c.get(f"/api/orders/{unknown}", headers=b_appr).status_code == 404  # same answer, nothing logged
    assert c.get("/api/audit", params={"buyer_id": "chef"}, headers=b_appr).status_code == 403
    assert c.post("/api/orders", headers=b_agent, json={"buyer_id": "chef", "requested_date": REQ.isoformat(),
                                                        "lines": [{"product_id": "463335", "quantity": 1}]}).status_code == 403
    ev = [e for e in c.get("/api/admin/audit", headers={"X-Valio-Admin-Key": "valio-ops"}).json()
          if e.get("event") == "cross_buyer_attempt"]
    assert [(e["route"], e["caller_buyer_id"], e["target_buyer_id"]) for e in ev] == [
        ("read order", "other", "chef"), ("approve order", "other", "chef"), ("reject order", "other", "chef"),
        ("GET /api/audit", "other", "chef"), ("POST /api/orders", "other", "chef")]
    assert c.get("/api/audit", headers=b_appr).json() == []  # the caller's own trail reveals nothing
    assert orders._store()[held["order_id"]]["status"] == "pending_approval"
