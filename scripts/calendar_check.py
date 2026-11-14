#!/usr/bin/env python3
"""Black-box calendar acceptance check for a local Front Door backend.

Usage: python scripts/calendar_check.py [BASE_URL]
       DATA_DIR=... SANDBOX_ENABLED=1 python scripts/calendar_check.py --in-process
"""
from __future__ import annotations

import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta


BASE = (next((arg for arg in sys.argv[1:] if arg.startswith("http")), "http://127.0.0.1:8778")).rstrip("/")
IN_PROCESS = "--in-process" in sys.argv
ASGI_CLIENT = None
results: list[bool] = []


def call(method: str, path: str, body=None, headers=None, timeout: float = 120):
    if IN_PROCESS:
        try:
            response = ASGI_CLIENT.request(method, path, headers=headers, json=body, timeout=timeout)
            return response.status_code, response.json()
        except Exception as error:  # noqa: BLE001 - keep the check reporting the failing boundary
            return 0, {"detail": f"{type(error).__name__}: {error}"}
    request = urllib.request.Request(
        BASE + path,
        method=method,
        headers={"Content-Type": "application/json", "User-Agent": "calendar-check/1", **(headers or {})},
        data=json.dumps(body).encode() if body is not None else None,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        raw, status = error.read(), error.code
    except urllib.error.URLError as error:
        return 0, {"detail": str(error.reason)}
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, {"detail": raw.decode(errors="replace")[:300]}


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f" ({detail})" if detail else ""), flush=True)
    return bool(ok)


def next_weekday(start: date, weekday: int) -> date:
    days = (weekday - start.weekday()) % 7 or 7
    return start + timedelta(days=days)


def finish() -> int:
    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if results and all(results) else 1


def main() -> int:
    global ASGI_CLIENT
    if IN_PROCESS:
        from fastapi.testclient import TestClient
        from app import catalogue
        from app.main import app

        catalogue.load()
        ASGI_CLIENT = TestClient(app)
    print(f"Calendar check against {BASE}")
    status, credentials = call("POST", "/api/sandbox")
    if not check("mint a sandbox kitchen", status == 200 and isinstance(credentials, dict), f"HTTP {status}"):
        return finish()
    agent_key, approver_key = credentials.get("agent_key"), credentials.get("approver_key")
    agent = {"X-Agent-Key": agent_key}
    approver = {"X-Approver-Key": approver_key}

    health = {}
    for _ in range(30):
        status, health = call("GET", "/api/health")
        if status == 200 and isinstance(health, dict) and health.get("catalogue", {}).get("ready"):
            break
        time.sleep(2)
    check("backend and catalogue ready", status == 200 and health.get("catalogue", {}).get("ready"),
          f"HTTP {status}, {health.get('catalogue', {}).get('error')}")
    if not health.get("catalogue", {}).get("ready"):
        return finish()

    today = date.today()
    standing_date = next_weekday(today, 1)       # Tuesday
    skipped_date = standing_date + timedelta(days=7)
    confirmed_date = next_weekday(today, 0)       # Monday
    pending_date = confirmed_date + timedelta(days=2)  # Wednesday
    menu_date = next_weekday(today, 5)            # Saturday
    menu_day = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[menu_date.weekday()]
    standing_day = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[standing_date.weekday()]

    standing = {"lines": [{"text": "1 carton milk", "product_id": "463335", "quantity": 1, "unit": "ST"}]}
    status, body = call(f"PUT", f"/api/profile/standing-orders/{standing_day}", standing, approver)
    check("seed a standing order", status == 200 and any(
        item.get("weekday") == "tuesday" for item in body.get("standing_orders", [])
    ), f"HTTP {status}")

    weekly = {
        "weekday": menu_day,
        "name": "Calendar check Saturday menu",
        "dishes": [{"name": "Potato soup", "recipe": "Simmer potatoes and cream."}],
        "covers": 24,
        "active": True,
    }
    status, body = call("PUT", f"/api/menus/weekly/{menu_day}", weekly, approver)
    check("seed a weekly menu", status == 200 and body.get("name") == weekly["name"], f"HTTP {status}")

    status, quotes = call("POST", "/api/quotes", {"product_ids": ["463335"],
                                                   "requested_date": confirmed_date.isoformat()})
    quote = quotes[0] if status == 200 and isinstance(quotes, list) and quotes else {}
    usable = quote.get("orderable") and quote.get("unit_price_cents") and quote.get("quantity_known")
    check("find an orderable stocked product", bool(usable), f"HTTP {status}, flags={quote.get('flags')}")
    if not usable:
        return finish()

    product_id = quote["product_id"]
    unit_price = int(quote["unit_price_cents"])
    available = float(quote["available_amount"])
    pending_quantity = max(2, math.floor(150_000 / unit_price) + 1)
    if pending_quantity > available:
        check("pending quantity fits available stock", False,
              f"need {pending_quantity}, available {available:g}")
        return finish()

    status, confirmed = call("POST", "/api/orders", {
        "requested_date": confirmed_date.isoformat(), "lines": [{"product_id": product_id, "quantity": 1}]
    }, agent)
    check("place one confirmed delivery", status == 200 and confirmed.get("status") == "confirmed",
          f"HTTP {status}, status={confirmed.get('status')}")

    status, pending = call("POST", "/api/orders", {
        "requested_date": pending_date.isoformat(),
        "lines": [{"product_id": product_id, "quantity": pending_quantity}],
    }, agent)
    check("leave one delivery pending", status == 200 and pending.get("status") == "pending_approval",
          f"HTTP {status}, status={pending.get('status')}")

    status, planned = call("POST", f"/api/menus/weekly/{menu_day}/plan?date={menu_date.isoformat()}",
                           headers=agent, timeout=180)
    check("plan the weekly menu without placing it", status == 200 and isinstance(planned, dict)
          and planned.get("decision", {}).get("outcome") == "ASK_HUMAN"
          and not planned.get("order_id"), f"HTTP {status}, keys={sorted(planned) if isinstance(planned, dict) else []}")

    status, placed = call("POST", f"/api/calendar/recurring/{standing_day}/place?date={standing_date.isoformat()}",
                          headers=agent, timeout=180)
    check("place the recurring order", status == 200 and isinstance(placed, dict),
          f"HTTP {status}, keys={sorted(placed) if isinstance(placed, dict) else []}")

    status, skipped = call("POST", f"/api/calendar/recurring/{standing_day}/skip?date={skipped_date.isoformat()}",
                           headers=approver)
    check("skip the next recurring order", status == 200 and skipped == {
        "weekday": "tuesday", "date": skipped_date.isoformat(), "skipped": True
    }, f"HTTP {status}")

    start, end = today, today + timedelta(days=27)
    query = urllib.parse.urlencode({"from": start.isoformat(), "to": end.isoformat()})
    status, calendar = call("GET", f"/api/calendar?{query}", headers=agent)
    days = calendar.get("days", []) if isinstance(calendar, dict) else []
    entries = [entry for day in days for entry in day.get("entries", [])]
    kinds = {entry.get("kind") for entry in entries}
    expected_kinds = {"delivery_confirmed", "delivery_pending", "recurring_order", "weekly_menu", "guests_expected"}
    check("read a four-week calendar", status == 200 and len(days) == 28, f"HTTP {status}, days={len(days)}")
    check("calendar contains every entry kind", expected_kinds <= kinds and kinds <= expected_kinds,
          f"kinds={sorted(kinds)}")

    legend = calendar.get("legend", {}) if isinstance(calendar, dict) else {}
    expected_legend = {
        "delivery_confirmed": "Confirmed delivery",
        "delivery_pending": "Waiting for your OK",
        "recurring_order": "Recurring order",
        "weekly_menu": "Weekly menu",
        "guests_expected": "Expected guests",
    }
    check("calendar legend labels every entry kind", legend == expected_legend, f"legend={legend}")

    confirmed_entry = next((e for e in entries if e.get("kind") == "delivery_confirmed"), {})
    pending_entry = next((e for e in entries if e.get("kind") == "delivery_pending"), {})
    recurring_entries = [e for e in entries if e.get("kind") == "recurring_order"]
    menu_entry = next((e for e in entries if e.get("kind") == "weekly_menu"), {})
    guests = [e for e in entries if e.get("kind") == "guests_expected"]
    check("confirmed delivery is labelled and dated", confirmed_entry.get("title") == "Confirmed delivery"
          and confirmed_entry.get("status") == "confirmed" and confirmed_entry.get("order_id") == confirmed.get("order_id"),
          str(confirmed_entry))
    check("pending delivery is labelled with its reason", pending_entry.get("title") == "Delivery waiting for your OK"
          and pending_entry.get("reason") == "waiting for your OK"
          and pending_entry.get("status") == "pending_approval"
          and pending_entry.get("order_id") == pending.get("order_id"), str(pending_entry))
    check("recurring entry is exposed and skipped date is absent", any(
        e.get("weekday") == "tuesday" and isinstance(e.get("placed"), bool) for e in recurring_entries
    ) and not any(day.get("date") == skipped_date.isoformat() and any(
        e.get("kind") == "recurring_order" for e in day.get("entries", [])
    ) for day in days), f"recurring={recurring_entries}")
    check("weekly menu entry has its label and covers", menu_entry == {
        "kind": "weekly_menu", "name": weekly["name"], "dishes": [{"name": "Potato soup", "has_recipe": True}],
        "covers": 24
    }, str(menu_entry))
    check("guest entries carry the simulated label", bool(guests) and all(
        isinstance(e.get("value"), (int, float)) and e.get("simulated") is True for e in guests
    ), str(guests[:1]))

    by_date = {day["date"]: day for day in days}
    cutoff_dates = {confirmed_date.isoformat(), pending_date.isoformat(), standing_date.isoformat(),
                    menu_date.isoformat()}
    cutoffs = {day["date"]: day.get("cutoff") for day in days if day.get("cutoff")}
    check("calendar includes fresh cut-offs for each delivery date", cutoff_dates <= set(cutoffs)
          and all(isinstance(cutoff.get("closing_time"), str) and isinstance(cutoff.get("passed"), bool)
                  for cutoff in cutoffs.values()), f"cutoffs={cutoffs}")
    check("calendar cut-off is not an entry and dates remain stable",
          all("cutoff" not in entry for entry in entries)
          and menu_entry in by_date[menu_date.isoformat()]["entries"], "cut-off placement")
    return finish()


if __name__ == "__main__":
    sys.exit(main())
