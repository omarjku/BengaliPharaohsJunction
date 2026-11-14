#!/usr/bin/env python3
"""Get a deployed front door ready for a live demo: python3 scripts/demo_prep.py [BASE_URL] [--env PATH]
[--no-reset] [--restore-mandate]

1. Reset (unless --no-reset): POST /api/admin/demo/reset, so earlier smoke / QA runs don't eat the demo buyer's
   weekly budget. Nothing is deleted: the server archives the old files under DATA_DIR/archive/.
2. Warm up: health until the catalogue is ready, one product search and one live quote (Valio and caches hot).
3. Checklist: keys present, signing key id published, demo buyer's confidence threshold and budget left.
Keys come from the repo-root .env (as in smoke.py) and are never printed. Exits 1 if something critical fails.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smoke  # noqa: E402  (shares BASE / --env parsing, key lookup, HTTP calls and check output)

DEMO_BUYER = "lapland-kitchen"


def main() -> int:
    print(f"Demo prep for {smoke.BASE}\n")
    agent_key = smoke.env_key("AGENT_KEYS", DEMO_BUYER)
    approver_key = smoke.env_key("APPROVER_KEYS", DEMO_BUYER)
    admin_key = smoke.env_key("VALIO_ADMIN_KEYS")
    smoke.check(f"agent + approver keys for {DEMO_BUYER} in .env (values not shown)", bool(agent_key and approver_key))
    smoke.check("Valio admin key in .env", bool(admin_key))
    if smoke.smoke_buyer():
        print(f"INFO  smoke tests run as {smoke.SMOKE_BUYER}, so they won't spend {DEMO_BUYER}'s budget")
    else:
        print(f"WARN  no {smoke.SMOKE_BUYER} keys: smoke.py would spend {DEMO_BUYER}'s budget")

    if "--no-reset" not in sys.argv:
        status, r = smoke.call("POST", "/api/admin/demo/reset", {"restore_mandate": "--restore-mandate" in sys.argv},
                               {"X-Valio-Admin-Key": admin_key}, timeout=60)
        smoke.check("demo reset (old orders / audit archived, not deleted)", status == 200,
                    f"archived to {r.get('archived_to')}" if status == 200 else f"HTTP {status}: "
                    f"{r.get('detail') if isinstance(r, dict) else r} (set DEMO_RESET_ENABLED=1?)")

    for _ in range(18):
        status, h = smoke.call("GET", "/api/health")
        if status == 200 and isinstance(h, dict) and h.get("catalogue", {}).get("ready"):
            break
        time.sleep(10)
    smoke.check("backend up, catalogue ready", status == 200 and isinstance(h, dict)
                and h.get("catalogue", {}).get("ready"), f"{isinstance(h, dict) and h.get('catalogue')}")
    smoke.check("Valio and Gemini keys configured on the server", isinstance(h, dict)
                and h.get("valio_key_configured") and h.get("gemini_key_configured"))
    status, hits = smoke.call("GET", "/api/products/search?q=milk&claims=FREE_FROM_LACTOSE&limit=3")
    smoke.check("warm: product search", status == 200 and isinstance(hits, list) and hits, f"{len(hits or [])} hits")
    pid = hits[0]["id"] if status == 200 and hits else "463335"
    t = time.monotonic()
    status, q = smoke.call("POST", "/api/quotes", {"product_ids": [pid], "requested_date": smoke.next_monday().isoformat()})
    smoke.check("warm: live Valio quote", status == 200 and isinstance(q, list) and q,
                f"{pid}: {q[0].get('unit_price_cents') if status == 200 and q else status} cents, "
                f"{time.monotonic() - t:.1f}s")

    status, st = smoke.call("GET", "/api/admin/demo/status", headers={"X-Valio-Admin-Key": admin_key})
    _, keys = smoke.call("GET", "/.well-known/front-door-keys.json")
    kids = [k.get("kid") for k in keys.get("keys", [])] if isinstance(keys, dict) else []
    kid = st.get("signing_kid") if isinstance(st, dict) else None
    smoke.check("signing key published", status == 200 and kid in kids, f"kid {kid}")
    b = (st.get("buyers") or {}).get(DEMO_BUYER, {}) if isinstance(st, dict) else {}
    left, cap = b.get("remaining_cents"), b.get("weekly_budget_cents")
    smoke.check(f"{DEMO_BUYER} weekly budget left", bool(cap) and left == cap,
                f"EUR {(left or 0) / 100:,.2f} of {(cap or 0) / 100:,.2f}; confidence threshold "
                f"{b.get('confidence_threshold')}")
    return smoke.finish()


if __name__ == "__main__":
    sys.exit(main())
