"""Live-demo safety: admin demo reset (archive, never delete), demo status, the smoke-test buyer. Offline."""
import json

from conftest import REQ, store_mandate
from fastapi.testclient import TestClient
from trade_contracts import Mandate

from app import config, mandates, orders
from app.main import app

c = TestClient(app, raise_server_exceptions=False)
AG, AP, ADM = {"X-Agent-Key": "agent-chef"}, {"X-Approver-Key": "appr-chef"}, {"X-Valio-Admin-Key": "valio-ops"}
MANDATE = {"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9, "weekly_budget_cents": 500000,
           "hard_rules": [{"kind": "auto_approve_limit_cents", "value": 100000}]}


def setup_store(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(mandates, "STORE", tmp_path / "mandates.json")


def place(qty=10, key=None):
    h = {**AG, **({"Idempotency-Key": key} if key else {})}
    return c.post("/api/orders", headers=h, json={"requested_date": REQ.isoformat(),
                                                  "lines": [{"product_id": "463335", "quantity": qty}]})


def test_reset_is_off_unless_enabled_and_admin_only(shop, monkeypatch):
    assert c.post("/api/admin/demo/reset", headers=ADM).status_code == 404  # DEMO_RESET_ENABLED unset
    monkeypatch.setattr(config, "DEMO_RESET_ENABLED", True)
    assert c.post("/api/admin/demo/reset").status_code == 401
    assert c.post("/api/admin/demo/reset", headers={"X-Valio-Admin-Key": "appr-chef"}).status_code == 401
    assert c.post("/api/admin/demo/reset", headers=AP).status_code == 401


def test_reset_archives_everything_and_starts_fresh(shop, monkeypatch, tmp_path):
    setup_store(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "DEMO_RESET_ENABLED", True)
    store_mandate(MANDATE)
    first = place(10, key="k1").json()
    oid = place(1000).json()["order_id"]  # held
    before = {p.name: p.read_text() for p in (orders.ORDERS_FILE, orders.AUDIT_FILE, orders.IDEM_FILE)}
    r = c.post("/api/admin/demo/reset", headers=ADM)
    assert r.status_code == 200
    out = r.json()
    archive = tmp_path / out["archived_to"]
    assert sorted(out["archived_files"]) == ["audit.jsonl", "idempotency.json", "orders.json"]
    assert {p.name: p.read_text() for p in archive.iterdir()} == before  # moved intact, nothing deleted
    assert orders._store() == {} and c.get(f"/api/orders/{oid}", headers=AP).status_code == 404
    [line] = c.get("/api/admin/audit", headers=ADM).json()
    assert line["kind"] == "admin_event" and line["message"] == "demo reset by Valio ops"
    assert c.get("/api/audit", headers=AP).json() == []  # the buyer's trail starts empty
    again = place(10, key="k1").json()  # the old idempotency key is archived too
    assert again["order_id"] != first["order_id"]
    assert out["buyers"]["chef"]["spent_7d_cents"] == 0 and out["buyers"]["chef"]["remaining_cents"] == 500000


def test_reset_keeps_saved_mandates_unless_restore(shop, monkeypatch, tmp_path):
    setup_store(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "DEMO_RESET_ENABLED", True)
    seeded = mandates.get("lapland-kitchen")
    mandates.put(seeded.model_copy(update={"id": "edited-in-the-ui", "weekly_budget_cents": 1000}))
    c.post("/api/admin/demo/reset", headers=ADM)
    assert mandates.get("lapland-kitchen").id == "edited-in-the-ui"  # left alone
    out = c.post("/api/admin/demo/reset", headers=ADM, json={"restore_mandate": True}).json()
    assert "mandates.json" in out["archived_files"] and mandates.get("lapland-kitchen") == seeded
    archived = json.loads((tmp_path / out["archived_to"] / "mandates.json").read_text())
    assert archived["lapland-kitchen"]["id"] == "edited-in-the-ui"  # the edit is archived, not lost


def test_demo_status_shows_budget_and_kid(shop, monkeypatch, tmp_path):
    setup_store(monkeypatch, tmp_path)
    store_mandate(MANDATE)
    place(10)
    st = c.get("/api/admin/demo/status", headers=ADM).json()
    assert st["buyers"]["chef"] == {"weekly_budget_cents": 500000, "spent_7d_cents": 1400, "remaining_cents": 498600,
                                    "confidence_threshold": 0.8}
    assert st["buyers"]["lapland-kitchen"]["weekly_budget_cents"] == 600000 and st["signing_kid"].startswith("fd-")
    assert st["demo_reset_enabled"] is False
    assert c.get("/api/admin/demo/status", headers=AP).status_code == 401


def test_smoke_buyer_has_the_demo_rules_but_its_own_budget():
    smoke, demo = mandates.get("smoke-kitchen"), mandates.get("lapland-kitchen")
    assert isinstance(smoke, Mandate) and smoke.buyer_id == "smoke-kitchen" and smoke.id != demo.id
    assert smoke.hard_rules == demo.hard_rules and smoke.weekly_budget_cents == demo.weekly_budget_cents
    assert mandates.confidence_threshold("smoke-kitchen") == mandates.confidence_threshold("lapland-kitchen")
    assert mandates.kitchen("smoke-kitchen") == mandates.kitchen("lapland-kitchen")  # the size guard judges it the same
    assert "bistro" in mandates.kitchen("helsinki-bistro") and mandates.kitchen("unknown") == mandates.DEFAULT_KITCHEN
