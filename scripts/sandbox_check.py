#!/usr/bin/env python3
"""Exercise the QR sandbox contract against a running backend.

Usage: python scripts/sandbox_check.py http://127.0.0.1:8779 --registry /tmp/front-door/sandboxes.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx


def check(condition: bool, label: str, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{label}{': ' + detail if detail else ''}")
    print(f"PASS  {label}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", nargs="?", default="http://127.0.0.1:8779")
    parser.add_argument("--registry", type=Path, required=True,
                        help="backend DATA_DIR/sandboxes.json, used to force an expiry check")
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=240) as client:
        def mint() -> dict:
            response = client.post("/api/sandbox")
            check(response.status_code == 200, "sandbox mint succeeds", response.text[:200])
            body = response.json()
            check(body.get("buyer_id", "").startswith("try-"), "mint returns sandbox buyer")
            check(body.get("agent_key") and body.get("approver_key"), "mint returns both credentials")
            check(body["agent_key"] != body["approver_key"], "agent and approver credentials differ")
            check(body.get("template") == "helsinki-bistro", "mint uses the Helsinki template")
            return body

        first = mint()
        second = mint()

        profile = client.get("/api/profile", headers={"X-Agent-Key": first["agent_key"]})
        check(profile.status_code == 200, "sandbox agent reads its profile", profile.text[:200])
        profile_body = profile.json()
        check(profile_body.get("buyer_id") == first["buyer_id"], "profile is bound to the minted buyer")
        check({"464411", "475852", "471650"}.issubset(set(profile_body.get("usual_product_ids", []))),
              "sandbox sees the template's usual products")
        check(profile_body.get("dietary") == [{
            "tag": "gluten_free",
            "label": "gluten-free",
            "because": "your profile says: Our kitchen is gluten-free",
        }], "sandbox sees the template's dietary profile")

        kitchen = client.get("/api/kitchen/context", headers={"X-Agent-Key": first["agent_key"]})
        check(kitchen.status_code == 200, "sandbox agent reads kitchen context", kitchen.text[:200])
        kitchen_body = kitchen.json()
        check(kitchen_body.get("simulated") is True, "sandbox kitchen context is marked simulated")
        check((kitchen_body.get("simulated_order_history") or {}).get("source") ==
              "demo seed (simulated order ledger)", "sandbox sees the template's example history")

        order = client.post("/api/orders", headers={"X-Agent-Key": first["agent_key"]}, json={
            "requested_date": (date.today() + timedelta(days=2)).isoformat(),
            "lines": [{"product_id": "463335", "quantity": 1000}],
        })
        check(order.status_code == 200, "sandbox agent can place an order", order.text[:300])
        order_body = order.json()
        order_id = order_body.get("order_id")
        check(order_body.get("status") == "pending_approval" and order_id, "test order requires approval",
              json.dumps(order_body)[:300])

        wrong_role = client.post(f"/api/orders/{order_id}/approve",
                                 headers={"X-Approver-Key": first["agent_key"]})
        check(wrong_role.status_code == 401, "agent credential cannot approve", wrong_role.text[:200])

        approved = client.post(f"/api/orders/{order_id}/approve",
                               headers={"X-Approver-Key": first["approver_key"]})
        check(approved.status_code == 200 and approved.json().get("status") == "confirmed",
              "sandbox approver can approve", approved.text[:300])

        cross_read = client.get(f"/api/orders/{order_id}", headers={"X-Agent-Key": second["agent_key"]})
        check(cross_read.status_code == 404, "a second sandbox cannot read the first sandbox's order",
              cross_read.text[:200])

        registry = json.loads(args.registry.read_text())
        registry[second["buyer_id"]]["expires_at"] = "2000-01-01T00:00:00+00:00"
        args.registry.write_text(json.dumps(registry))
        expired = client.get("/api/profile", headers={"X-Agent-Key": second["agent_key"]})
        check(expired.status_code == 401, "expired sandbox credential is rejected", expired.text[:200])

        extra = [mint() for _ in range(3)]
        check(len(extra) == 3, "five sandbox mints are allowed in the rate-limit window")
        limited = client.post("/api/sandbox")
        check(limited.status_code == 429, "the sixth sandbox mint is rate-limited", limited.text[:200])

    print("sandbox check: all contract checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, httpx.HTTPError, OSError, ValueError, KeyError) as error:
        print(f"FAIL  sandbox check: {error}", file=sys.stderr)
        raise SystemExit(1)
