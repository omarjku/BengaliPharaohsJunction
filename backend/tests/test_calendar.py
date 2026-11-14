"""Calendar and weekly-menu contract routes."""
import time
from datetime import date, timedelta

from fastapi.testclient import TestClient
from conftest import REQ, store_mandate

from app import config, menu, orders, profile, valio
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_agent_can_read_the_seeded_lapland_example_menu(shop, monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-lapland=lapland-kitchen")

    response = client.get("/api/menus/weekly", headers={"X-Agent-Key": "agent-lapland"})

    assert response.status_code == 200
    [menu] = response.json()
    assert menu["weekday"] == "fri"
    assert menu["name"] == "Example: Lapland special: salmon soup and blueberry pie"
    assert menu["active"] is True
    assert menu["dishes"][0]["recipe"]


def test_try_sandbox_gets_the_labelled_example_seed(shop, monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-try=try-qa")

    response = client.get("/api/menus/weekly", headers={"X-Agent-Key": "agent-try"})

    assert response.status_code == 200
    assert response.json()[0]["name"].startswith("Example:")


def test_weekly_menu_edit_is_approver_only_and_persists_atomically(shop, monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-chef=chef")
    monkeypatch.setattr(config, "APPROVER_KEYS", "appr-chef=chef:Chef Aino")
    body = {"weekday": "mon", "name": "Monday test menu", "dishes": [{"name": "Soup", "recipe": "Simmer."}],
            "covers": 20, "active": True}

    assert client.put("/api/menus/weekly/mon", headers={"X-Agent-Key": "agent-chef"}, json=body).status_code == 401
    response = client.put("/api/menus/weekly/mon", headers={"X-Approver-Key": "appr-chef"}, json=body)

    assert response.status_code == 200
    assert response.json() == {**body}
    saved = config.DATA_DIR / "menus" / "chef.json"
    assert saved.exists() and not list(saved.parent.glob("*.tmp"))
    assert client.get("/api/menus/weekly", headers={"X-Agent-Key": "agent-chef"}).json() == [response.json()]
    assert client.delete("/api/menus/weekly/mon", headers={"X-Approver-Key": "appr-chef"}).json() == {
        "weekday": "mon", "deleted": True}
    assert client.get("/api/menus/weekly", headers={"X-Agent-Key": "agent-chef"}).json() == []


def test_weekly_menu_rejects_a_recipe_over_4000_characters(shop, monkeypatch):
    monkeypatch.setattr(config, "APPROVER_KEYS", "appr-chef=chef")
    body = {"name": "Too long", "dishes": [{"name": "Soup", "recipe": "x" * 4001}]}

    response = client.put("/api/menus/weekly/mon", headers={"X-Approver-Key": "appr-chef"}, json=body)

    assert response.status_code == 422


def test_weekly_menu_plan_calls_the_existing_menu_planner_without_ordering(shop, monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-lapland=lapland-kitchen")
    target = _upcoming(4)
    seen = {}

    async def fake_propose(text, covers, requested, buyer_id, *args, **kwargs):
        seen.update(text=text, covers=covers, requested=requested, buyer_id=buyer_id)
        return {"normal": "menu-cart", "order_id": None}

    monkeypatch.setattr(menu, "propose", fake_propose)
    response = client.post(f"/api/menus/weekly/fri/plan?date={target.isoformat()}",
                           headers={"X-Agent-Key": "agent-lapland"})

    assert response.status_code == 200 and response.json() == {"normal": "menu-cart", "order_id": None}
    assert seen["covers"] == 40 and seen["requested"] == target and seen["buyer_id"] == "lapland-kitchen"
    assert "Salmon soup" in seen["text"] and "Blueberry pie" in seen["text"]


def test_calendar_returns_weekly_menu_and_simulated_guest_entries(shop, monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-lapland=lapland-kitchen")
    target = _upcoming(4)

    response = client.get(f"/api/calendar?from={target.isoformat()}&to={target.isoformat()}",
                          headers={"X-Agent-Key": "agent-lapland"})

    assert response.status_code == 200
    day = response.json()["days"][0]
    assert day["date"] == target.isoformat() and day["today"] is (target == date.today())
    entries = {entry["kind"]: entry for entry in day["entries"]}
    assert entries["weekly_menu"] == {
        "kind": "weekly_menu", "name": "Example: Lapland special: salmon soup and blueberry pie",
        "dishes": [{"name": "Salmon soup", "has_recipe": True}, {"name": "Blueberry pie", "has_recipe": True}],
        "covers": 40}
    assert entries["guests_expected"]["simulated"] is True
    assert "weekly_menu" in response.json()["legend"]


def test_calendar_keys_buyers_and_range_limit_are_enforced(shop, monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-chef=chef,agent-other=other")
    start = date.today()

    assert client.get(f"/api/calendar?from={start.isoformat()}&to={start.isoformat()}").status_code == 401
    other = client.get(f"/api/calendar?from={start.isoformat()}&to={start.isoformat()}",
                       headers={"X-Agent-Key": "agent-other"})
    assert other.status_code == 200 and other.json()["days"][0]["entries"] == []
    too_long = client.get(f"/api/calendar?from={start.isoformat()}&to={(start + timedelta(days=62)).isoformat()}",
                          headers={"X-Agent-Key": "agent-chef"})
    reversed_range = client.get(f"/api/calendar?from={(start + timedelta(days=1)).isoformat()}&to={start.isoformat()}",
                                headers={"X-Agent-Key": "agent-chef"})
    assert too_long.status_code == 422 and reversed_range.status_code == 422


def test_calendar_marks_confirmed_and_pending_deliveries_and_recurring_placement(shop, monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-chef=chef")
    target = _upcoming(0)
    standing = [{"weekday": "monday", "lines": [{"text": "10 L milk", "quantity": 10, "unit": "L"}],
                 "source": "you told me"}]
    monkeypatch.setattr(profile, "standing_orders", lambda buyer: standing if buyer == "chef" else [])
    confirmed = {"id": "confirmed-id", "status": "confirmed", "requested_date": target.isoformat(),
                 "lines": [{"name": "Milk", "quantity": 10, "unit": "L"}], "total_cents": 1400}
    pending = {"id": "pending-id", "status": "pending_approval", "requested_date": target.isoformat(),
               "lines": [{"name": "Bread", "quantity": 2, "unit": "ST"}], "total_cents": 2000}
    monkeypatch.setattr(orders, "audit_log", lambda buyer, limit: [
        {"front_door": {"status": "confirmed"}, "input": {"request": {"id": confirmed["id"]}}},
        {"front_door": {"status": "pending_approval"}, "input": {"request": {"id": pending["id"]}}},
    ])
    monkeypatch.setattr(orders, "get", lambda order_id, buyer: {confirmed["id"]: confirmed, pending["id"]: pending}[order_id])

    response = client.get(f"/api/calendar?from={target.isoformat()}&to={target.isoformat()}",
                          headers={"X-Agent-Key": "agent-chef"})

    assert response.status_code == 200
    entries = {entry["kind"]: entry for entry in response.json()["days"][0]["entries"]}
    assert entries["delivery_confirmed"]["status"] == "confirmed"
    assert entries["delivery_pending"]["reason"] == "waiting for your OK"
    assert entries["recurring_order"]["placed"] is True
    assert entries["recurring_order"]["lines"] == standing[0]["lines"]


def test_calendar_reads_a_real_front_door_order_through_public_order_functions(shop, monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-chef=chef")
    store_mandate({"id": "m1", "buyer_id": "chef", "hard_rules": [], "per_line_cap_cents": 10**9})
    placed = client.post("/api/orders", headers={"X-Agent-Key": "agent-chef"},
                         json={"requested_date": REQ.isoformat(), "lines": [{"product_id": "463335", "quantity": 10}]})
    assert placed.status_code == 200 and placed.json()["status"] == "confirmed"

    response = client.get(f"/api/calendar?from={REQ.isoformat()}&to={REQ.isoformat()}",
                          headers={"X-Agent-Key": "agent-chef"})

    assert response.status_code == 200
    [delivery] = [entry for entry in response.json()["days"][0]["entries"] if entry["kind"] == "delivery_confirmed"]
    assert delivery["order_id"] == placed.json()["order_id"]
    assert delivery["lines"] == [{"name": "Eila milk 1 l", "quantity": 10, "unit": "ST"}]
    assert delivery["total_cents"] == 1400 and delivery["status"] == "confirmed"


def test_recurring_skip_is_approver_only_and_removes_the_day_entry(shop, monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-chef=chef")
    monkeypatch.setattr(config, "APPROVER_KEYS", "appr-chef=chef:Chef Aino")
    target = _upcoming(2)
    standing = [{"weekday": "wednesday", "lines": [{"text": "5 kg potatoes", "quantity": 5, "unit": "kg"}],
                 "source": "you told me"}]
    monkeypatch.setattr(profile, "standing_orders", lambda buyer: standing if buyer == "chef" else [])

    assert client.post(f"/api/calendar/recurring/wed/skip?date={target.isoformat()}",
                       headers={"X-Agent-Key": "agent-chef"}).status_code == 401
    response = client.post(f"/api/calendar/recurring/wed/skip?date={target.isoformat()}",
                           headers={"X-Approver-Key": "appr-chef"})
    calendar_response = client.get(f"/api/calendar?from={target.isoformat()}&to={target.isoformat()}",
                                   headers={"X-Agent-Key": "agent-chef"})

    assert response.json() == {"weekday": "wednesday", "date": target.isoformat(), "skipped": True}
    assert all(entry["kind"] != "recurring_order" for entry in calendar_response.json()["days"][0]["entries"])


def test_recurring_place_uses_the_normal_ask_path(shop, monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-chef=chef")
    target = _upcoming(1)
    standing = [{"weekday": "tuesday", "lines": [{"text": "3 L cream", "quantity": 3, "unit": "L"}],
                 "source": "you told me"}]
    monkeypatch.setattr(profile, "standing_orders", lambda buyer: standing if buyer == "chef" else [])
    seen = {}

    async def fake_ask(text, requested, buyer_id, *args, **kwargs):
        seen.update(text=text, requested=requested, buyer_id=buyer_id)
        return {"normal": "front-door-response"}

    monkeypatch.setattr("app.calendar.ask.ask", fake_ask)
    response = client.post(f"/api/calendar/recurring/tue/place?date={target.isoformat()}",
                           headers={"X-Agent-Key": "agent-chef"})

    assert response.status_code == 200 and response.json() == {"normal": "front-door-response"}
    assert seen == {"text": "usual tuesday order", "requested": target, "buyer_id": "chef"}


def test_calendar_cutoff_uses_only_a_fresh_cached_quote(shop, monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-chef=chef")
    target = _upcoming(0)
    closing = (datetime_now_utc() + timedelta(hours=2)).isoformat()
    monkeypatch.setattr(valio, "_cache", {("463335", target.isoformat()):
                                            (time.monotonic(), {"order_cutoff": closing})})

    async def no_poll(*args, **kwargs):
        raise AssertionError("calendar must not poll Valio")

    monkeypatch.setattr(valio, "get_quotes", no_poll)
    response = client.get(f"/api/calendar?from={target.isoformat()}&to={target.isoformat()}",
                          headers={"X-Agent-Key": "agent-chef"})

    assert response.status_code == 200
    assert response.json()["days"][0]["cutoff"] == {"closing_time": closing, "passed": False}


def _upcoming(weekday: int) -> date:
    today = date.today()
    days = (weekday - today.weekday()) % 7 or 7
    return today + timedelta(days=days)


def datetime_now_utc():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
