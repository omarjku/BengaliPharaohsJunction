"""Mandate versioning: ETag / If-Match on the rules, and the version every order and approval was judged under."""
import time
from concurrent.futures import ThreadPoolExecutor

from conftest import REQ
from fastapi.testclient import TestClient
from test_agent import decisions, shop1  # noqa: F401 - pytest fixtures
from test_rules import APPR, lk, mandate  # noqa: F401 - pytest fixture + helpers

from app import mandates, rules
from app.main import app
from app.signing import verify

c = TestClient(app, raise_server_exceptions=False)
SEEDED = "lapland-kitchen-2026-11"
AGENT = {"X-Agent-Key": "agent-lk"}


def save(m, etag=None, **extra):
    h = {**APPR, **({"If-Match": etag} if etag else {})}
    return c.put("/api/mandate", headers=h, json={"mandate": m, **extra})


def test_get_and_put_carry_the_version_as_etag(lk):
    r = c.get("/api/mandate", headers=APPR)
    assert r.headers["ETag"] == f'"{SEEDED}"'
    saved = save(mandate(weekly_budget_cents=500000), r.headers["ETag"])
    assert saved.status_code == 200
    v = saved.json()["version"]
    assert v != SEEDED and saved.headers["ETag"] == f'"{v}"' and saved.json()["mandate"]["id"] == v
    assert c.get("/api/mandate", headers=APPR).headers["ETag"] == f'"{v}"'
    assert save(mandate(weekly_budget_cents=400000), f'W/"{v}"').status_code == 200  # weak form accepted


def test_stale_if_match_is_412_and_saves_nothing(lk):
    first = save(mandate(weekly_budget_cents=500000), f'"{SEEDED}"').json()["version"]
    stale = save(mandate(weekly_budget_cents=100000), f'"{SEEDED}"')  # edited from an old screen
    assert stale.status_code == 412 and stale.json()["detail"]["current_version"] == first
    assert mandates.get("lapland-kitchen").weekly_budget_cents == 500000
    assert save(mandate(weekly_budget_cents=450000)).status_code == 200  # no If-Match: as before (UI compat)


def test_concurrent_saves_of_one_version_exactly_one_wins(lk, monkeypatch):
    real = rules.diff

    def slow_diff(*a, **k):  # both requests pass the early check, then race to the write
        time.sleep(0.1)
        return real(*a, **k)
    monkeypatch.setattr(rules, "diff", slow_diff)
    with ThreadPoolExecutor(2) as pool:
        rs = list(pool.map(lambda budget: save(mandate(weekly_budget_cents=budget), f'"{SEEDED}"'), (500000, 400000)))
    assert sorted(r.status_code for r in rs) == [200, 412]
    winner = next(r for r in rs if r.status_code == 200).json()
    assert mandates.get("lapland-kitchen").id == winner["version"]


def order(qty):
    return c.post("/api/orders", headers=AGENT,
                  json={"requested_date": REQ.isoformat(), "lines": [{"product_id": "463335", "quantity": qty}]})


def test_orders_and_approvals_record_the_version_they_were_judged_under(lk):
    held = order(1200).json()  # EUR 1,680 > the EUR 1,500 auto limit: held
    assert held["status"] == "pending_approval" and held["mandate_version"] == SEEDED
    assert held["signed_statement"]["mandate_version"] == SEEDED
    assert verify(held["signed_statement"], held["signature"])
    v2 = save(mandate(weekly_budget_cents=900000), f'"{SEEDED}"').json()["version"]  # rules change while it waits
    approved = c.post(f"/api/orders/{held['order_id']}/approve", headers=APPR).json()
    assert approved["mandate_version"] == v2 and approved["signed_statement"]["mandate_version"] == v2
    trail = [e.get("front_door", {}) for e in c.get("/api/audit", headers=APPR).json() if e.get("front_door")]
    assert [(f["action"], f["mandate_version"]) for f in trail if f["action"] in ("order", "approved",
                                                                                  "approval_blocked")] == [
        ("order", SEEDED), (approved and ("approved" if approved["status"] == "confirmed" else "approval_blocked"), v2)]
    assert c.get(f"/api/orders/{held['order_id']}", headers=APPR).json()["mandate_version"] == v2
