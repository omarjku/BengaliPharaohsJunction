#!/usr/bin/env python3
"""Live smoke test of a deployed front door: python3 scripts/smoke.py [BASE_URL] [--env PATH]

Reads AGENT_KEYS / APPROVER_KEYS (first entry of each) from the repo-root .env; never prints a key.
Checks: health + catalogue ready, protected routes refuse no key (401), the milk run gives a held or confirmed
order with a Gemini confidence, approve with the approver key (if held), the buyer's audit trail has the run,
and the order's signature verifies (and fails once tampered). Exits 1 on any failure. Stdlib only.
"""
import copy
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE = next((a for a in sys.argv[1:] if a.startswith("http")), "https://valio-front-door-api.onrender.com").rstrip("/")
ENV = Path(sys.argv[sys.argv.index("--env") + 1]) if "--env" in sys.argv else Path(__file__).resolve().parents[1] / ".env"
MILK = "1000 L lactose-free milk for Monday"
results: list[bool] = []


def env_key(name: str) -> str:
    for line in ENV.read_text().splitlines() if ENV.exists() else []:
        if line.startswith(name + "="):
            first = line.split("=", 1)[1].strip().strip('"').split(",")[0]
            return first.split("=", 1)[0]  # key=buyer[:name] → key
    return ""


def call(method: str, path: str, body=None, headers=None, timeout=90) -> tuple[int, dict | list | str]:
    req = urllib.request.Request(BASE + path, method=method, headers={"Content-Type": "application/json",
                                 "User-Agent": "front-door-smoke/1", **(headers or {})},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw.decode(errors="replace")[:200]


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    return bool(ok)


def next_monday() -> date:
    d = date.today() + timedelta(days=1)
    return d + timedelta(days=(7 - d.weekday()) % 7)


def main() -> int:
    print(f"Front-door smoke test against {BASE}")
    agent_key, approver_key = env_key("AGENT_KEYS"), env_key("APPROVER_KEYS")
    check("keys found in .env (values not shown)", bool(agent_key and approver_key), str(ENV))

    for _ in range(12):  # a cold Render instance builds the catalogue first
        status, h = call("GET", "/api/health")
        if status == 200 and isinstance(h, dict) and h.get("catalogue", {}).get("ready"):
            break
        time.sleep(10)
    check("health ok", status == 200 and isinstance(h, dict) and h.get("status") == "ok", f"HTTP {status}")
    cat = h.get("catalogue", {}) if isinstance(h, dict) else {}
    check("catalogue ready", bool(cat.get("ready")), f"{cat.get('products')} products")

    day = next_monday().isoformat()
    line = {"product_id": "463335", "quantity": 1}
    for method, path, body in [("POST", "/api/orders", {"requested_date": day, "lines": [line]}),
                               ("POST", "/api/agent/run", {"text": MILK, "requested_date": day}),
                               ("GET", "/api/audit", None),
                               ("POST", "/api/orders/00000000-0000-4000-8000-000000000000/approve", None)]:
        status, _ = call(method, path, body)
        check(f"no key → 401: {method} {path.replace('00000000-0000-4000-8000-000000000000', '{id}')}",
              status == 401, f"HTTP {status}")

    status, run = call("POST", "/api/agent/run", {"text": MILK, "requested_date": day}, {"X-Agent-Key": agent_key},
                       timeout=180)
    order = run.get("order") if isinstance(run, dict) else None
    conf = (run.get("decision") or {}).get("confidence") if isinstance(run, dict) else None
    check("milk run answered", status == 200, f"HTTP {status}")
    check("milk run placed a held or confirmed order", bool(order) and order.get("status") in ("confirmed", "pending_approval"),
          f"order status {order and order.get('status')}, decision {isinstance(run, dict) and (run.get('decision') or {}).get('outcome')}")
    check("decision carries a confidence value", isinstance(conf, (int, float)), f"confidence {conf}")
    if not order:
        return finish()

    if order["status"] == "pending_approval":
        status, ap = call("POST", f"/api/orders/{order['order_id']}/approve",
                          {"decided_at": order["decision"]["decided_at"]}, {"X-Approver-Key": approver_key}, timeout=120)
        check("approve with the approver key", status == 200 and isinstance(ap, dict)
              and ap.get("status") in ("confirmed", "pending_approval", "refused"),
              f"HTTP {status}, status {isinstance(ap, dict) and ap.get('status')}")
        status, _ = call("POST", f"/api/orders/{order['order_id']}/approve", None, {"X-Approver-Key": agent_key})
        check("agent key cannot approve", status in (401, 403), f"HTTP {status}")
    else:
        print("SKIP  approve (the order was confirmed automatically within the mandate)")

    status, trail = call("GET", "/api/audit", headers={"X-Approver-Key": approver_key})
    ids = {e.get("id") for e in trail} if isinstance(trail, list) else set()
    check("audit trail has the run", status == 200 and order.get("audit_id") in ids, f"HTTP {status}, {len(ids)} entries")

    status, keys = call("GET", "/.well-known/front-door-keys.json")
    kids = [k.get("kid") for k in keys.get("keys", [])] if isinstance(keys, dict) else []
    sig = order.get("signature") or {}
    check("public key published", status == 200 and sig.get("kid") in kids, f"kid {sig.get('kid')}")
    status, v = call("POST", "/api/verify", {"signed_statement": order.get("signed_statement"), "signature": sig})
    check("order signature verifies", status == 200 and isinstance(v, dict) and v.get("valid") is True, f"HTTP {status}")
    tampered = copy.deepcopy(order.get("signed_statement") or {})
    tampered["total_cents"] = (tampered.get("total_cents") or 0) + 1
    status, v = call("POST", "/api/verify", {"signed_statement": tampered, "signature": sig})
    check("tampered statement fails", status == 200 and isinstance(v, dict) and v.get("valid") is False, f"HTTP {status}")
    return finish()


def finish() -> int:
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
