"""Orders at Valio's front door + the append-only audit log.

Every gate run appends one contract `AuditEntry` (JSON line) to data/audit.jsonl, refusals included.
confirmed (AUTO) → order record; pending_approval (ASK_HUMAN) → pending order a human approves / rejects;
refused → nothing stored, still audited. Approve re-runs the gate with fresh quotes (cut-offs pass).
Who may call what is decided in auth.py: the buyer comes from the caller's key, never from the body.
"""
import asyncio
import json
import logging
import os
import threading
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from trade_contracts import AuditEntry, AuditInput, Decision, Mandate, PurchaseRequest, RequestItem

from . import catalogue, config, gate, mandates, signing
from .auth import Principal

# ponytail: JSON files on local disk (D8). Render's disk is ephemeral, so orders + audit vanish on redeploy and
# the public routes can grow the files without bound; move to Postgres (Aiven) with retention before production.
AUDIT_FILE = config.DATA_DIR / "audit.jsonl"
ORDERS_FILE = config.DATA_DIR / "orders.json"
IDEM_FILE = config.DATA_DIR / "idempotency.json"
IDEM_PER_CALLER = 5_000  # keys kept per caller (agent key's buyer / approver); a caller only ever evicts its own
IDEM_TTL = timedelta(hours=24)  # how long a retry with the same Idempotency-Key gets the original answer (as Stripe)
FRONT_DOOR = "valio_front_door"

log = logging.getLogger(__name__)
_file_lock = threading.Lock()
# Decide WITHOUT the lock (Valio calls take seconds), then commit under it only if nothing the decision rested on
# changed meanwhile (the buyer's 7-day spend, the order's state); otherwise decide again. So two orders can't both
# pass the weekly budget and one order can't be approved twice, and nobody waits on someone else's Valio call.
# ponytail: in-process lock + in-memory store → run exactly ONE uvicorn worker (README); a DB transaction to scale out.
_order_lock = asyncio.Lock()
MAX_RETRIES = 3
_orders: dict[str, dict] | None = None
_idem: dict[str, dict] | None = None
_idem_save = asyncio.Lock()  # snapshot + write in order: a newer snapshot is never overwritten by an older one


def _store() -> dict[str, dict]:
    global _orders
    if _orders is None:
        _orders = json.loads(ORDERS_FILE.read_text()) if ORDERS_FILE.exists() else {}
    return _orders


def _write(path, obj) -> None:
    with _file_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False))
        os.replace(tmp, path)  # atomic: a crash never leaves half a file


def _save() -> None:
    _write(ORDERS_FILE, _store())


def _idem_store() -> dict[str, dict]:
    global _idem
    if _idem is None:
        _idem = json.loads(IDEM_FILE.read_text()) if IDEM_FILE.exists() else {}
    return _idem


def _idem_snapshot() -> dict:
    """Copy on the event loop: the file write runs in a thread while new keys keep arriving."""
    return {k: r for k, r in _idem_store().items() if r["response"] is not None}


async def idempotent(caller: str, scope: str, fingerprint: str, run) -> tuple[dict, bool]:
    """Stripe-style Idempotency-Key. `scope` = caller + route + key; `fingerprint` = hash of the request.
    First call runs and stores its response; a retry with the same request gets that response back (→ True) without
    placing anything again; the same key with a different request → 422; while the first is still running → 409.
    Errors are not stored, so a failed call can be retried with the same key. Check-and-set has no await in between,
    so the single event loop makes it atomic (ponytail: one worker, see main.py)."""
    store, now = _idem_store(), datetime.now(timezone.utc)
    for k in [k for k, r in store.items() if datetime.fromisoformat(r["at"]) < now - IDEM_TTL]:
        del store[k]
    if scope not in store:  # over quota: drop this caller's own oldest finished keys, never another buyer's
        mine = [k for k, r in store.items() if r.get("caller") == caller and r["response"] is not None]
        for k in mine[: max(0, len(mine) - IDEM_PER_CALLER + 1)]:  # insertion order = oldest first
            del store[k]
    if rec := store.get(scope):
        if rec["fingerprint"] != fingerprint:
            raise HTTPException(422, detail="This Idempotency-Key was already used with a different request")
        if rec["response"] is None:
            raise HTTPException(409, detail="A request with this Idempotency-Key is still running; retry shortly")
        return rec["response"], True
    store[scope] = {"caller": caller, "fingerprint": fingerprint, "response": None, "at": now.isoformat()}
    try:
        resp = await run()
    except BaseException:
        store.pop(scope, None)
        raise
    store[scope]["response"] = resp
    async with _idem_save:
        await asyncio.to_thread(_write, IDEM_FILE, _idem_snapshot())
    return resp, False


def _annotation(actor: str) -> dict:
    """Default front_door annotation for writers that don't pass one (agent.py, menu.py, rules.py)."""
    return {"action": "agent_proposal" if actor == "buyer_agent" else actor.split(":")[-1], "status": None}


def _write_line(row: dict) -> None:
    with _file_lock:
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _append_audit(entry: AuditEntry, front_door: dict | None = None) -> None:
    """One audit line = the contract AuditEntry + a `front_door` annotation (the contract has no field for it):
    action = order | approved | approval_blocked | rejected | agent_proposal (the agent's own view, before the door
    decides) | …, status = the order's status after this event. Drop `front_door` to get the bare contract entry."""
    _write_line({**json.loads(entry.model_dump_json()), "front_door": front_door or _annotation(entry.actor)})


def security_event(event: str, route: str, ip: str | None, buyer_id: str | None = None, **detail) -> None:
    """A refused attempt (wrong / missing key, a key used outside its role, a client-sent mandate), audited as its
    own kind of line. Never holds a key or secret; buyer_id is the buyer a recognised key belongs to, if any."""
    _write_line({"kind": "security_event", "id": str(uuid4()), "timestamp": datetime.now(timezone.utc).isoformat(),
                 "actor": "front_door_security", "event": event, "route": route, "ip": ip, "buyer_id": buyer_id,
                 **detail})


async def _audit(actor: str, order_id: str, buyer_id: str, requested_date: str, lines: list[dict], mandate: Mandate | None,
           res: gate.GateResult | None, decision=None, now: datetime | None = None, action: str = "order",
           status: str | None = None) -> str:
    """The contracts have no Order shape, so the order is recorded as the PurchaseRequest it fulfils."""
    now = now or datetime.now(timezone.utc)
    text = "Order via Valio front door: " + "; ".join(
        f"{gate._qty(li['quantity'])} {li['unit'] or 'units'} x {li['product_id']} ({li['name']})" for li in lines
    ) + f", for {requested_date}"
    request = PurchaseRequest(
        id=order_id, buyer_id=buyer_id, text=text, created_at=now, needed_by=requested_date,
        items=[RequestItem(name=li["name"], quantity=li["quantity"], unit=li["unit"]) for li in lines])
    entry = AuditEntry(
        id=str(uuid4()), timestamp=now, actor=actor,
        input=AuditInput(request=request, mandate=mandate, quotes=res.quotes if res else []),
        decision=res.decision if res else decision, rejected_options=res.rejected_options if res else [])
    signer = actor.split(":")[1] if actor.startswith("human:") else None
    await asyncio.to_thread(_append_audit, entry, {"action": action, "status": status, "signed_off_by": signer})
    return entry.id


def _spent_7d(buyer_id: str, now: datetime, skip: str | None = None) -> int:
    since = (now - timedelta(days=7)).isoformat()
    return sum(o["total_cents"] for o in _store().values() if o["buyer_id"] == buyer_id and o["id"] != skip
               and o["status"] == "confirmed" and o["updated_at"] >= since)


async def _gate(audit: dict, lines, requested_date, mandate, oid, **kwargs) -> gate.GateResult:
    """gate.check; if Valio can't be asked, the failure is audited (ENGINE_ERROR, `audit` = actor / buyer_id /
    action / status for the line) and the caller gets a clean 503. Raw errors stay in the server log."""
    try:
        return await gate.check(lines, requested_date, mandate, oid, **kwargs)
    except Exception:
        log.exception("front-door gate failed")
        now = kwargs.get("now") or datetime.now(timezone.utc)
        res = gate.engine_error(lines, oid, now)
        await _audit(audit["actor"], oid, audit["buyer_id"], requested_date.isoformat(), res.lines, mandate, res,
                     now=now, action=audit["action"], status=audit["status"])
        raise HTTPException(503, detail="Valio availability check failed; nothing was ordered. Retry shortly.")


def _response(order_id: str | None, status: str, body: dict, audit_id: str) -> dict:
    """Every order response carries a signed statement of what the front door decided and the quote facts it used."""
    statement = {"v": 1, "iss": signing.ISSUER, "order_id": order_id, "status": status, "audit_id": audit_id,
                 "total_cents": body["total_cents"], "decision": body["decision"],
                 "quotes": body.get("quote_facts", []),
                 "lines": [{k: li.get(k) for k in ("product_id", "quantity", "unit", "unit_price_cents", "line_total_cents")}
                           for li in body.get("lines", [])]}
    return {"order_id": order_id, "status": status, "audit_id": audit_id, **body,
            "signed_statement": statement, "signature": signing.sign(statement)}


def _quote_facts(res: gate.GateResult) -> list[dict]:
    """What Valio's API told the front door, per product (origin is Valio's catalogue data)."""
    return [{"product_id": q.product_id, "unit_price_cents": q.unit_price_cents, "unit": q.unit,
             "availability": q.availability.value, "available_quantity": q.quantity.value,
             "cut_off": q.cut_off.closing_time.isoformat() if q.cut_off and q.cut_off.closing_time else None,
             "cut_off_passed": bool(q.cut_off and q.cut_off.passed), "fetched_at": q.fetched_at.isoformat(),
             "origin": (catalogue.get(q.product_id) or {}).get("origin")} for q in res.quotes]


def _view(res: gate.GateResult) -> dict:
    return {"total_cents": res.total_cents, "lines": res.lines, "decision": res.decision.model_dump(mode="json"),
            "rejected_options": [r.model_dump(mode="json") for r in res.rejected_options],
            "substitutes": res.substitutes, "alternative_order": res.alternative_order, "quote_facts": _quote_facts(res)}


def _busy() -> HTTPException:
    return HTTPException(409, detail="The buyer's orders changed while this one was being checked; retry.")


async def place(buyer_id: str, requested_date, lines: list, mandate: Mandate | None) -> dict:
    """`mandate` is the buyer's stored one (mandates.get), never the client's; None → refused (MANDATE_MISSING)."""
    oid = str(uuid4())
    for _ in range(MAX_RETRIES):
        now = datetime.now(timezone.utc)
        spent = _spent_7d(buyer_id, now)
        res = await _gate({"actor": FRONT_DOOR, "buyer_id": buyer_id, "action": "order", "status": "failed"},
                          lines, requested_date, mandate, oid, spent_7d_cents=spent, now=now)  # Valio calls, no lock
        async with _order_lock:
            if _spent_7d(buyer_id, now) != spent:
                continue  # another order of this buyer was confirmed meanwhile: decide again on the new budget
            if res.status != "refused":
                _store()[oid] = {
                    "id": oid, "buyer_id": buyer_id, "status": res.status, "requested_date": requested_date.isoformat(),
                    "lines": res.lines, "total_cents": res.total_cents, "mandate": mandate.model_dump(mode="json"),
                    "decision": res.decision.model_dump(mode="json"), "signed_off_by": None,
                    "created_at": now.isoformat(), "updated_at": now.isoformat()}
                await asyncio.to_thread(_save)
            audit_id = await _audit(FRONT_DOOR, oid, buyer_id, requested_date.isoformat(), res.lines, mandate, res,
                                    now=now, status=res.status)
        return _response(oid if res.status != "refused" else None, res.status, _view(res), audit_id)
    raise _busy()


def get(order_id: str, buyer_id: str) -> dict:
    """Another buyer's order is reported as unknown, not forbidden: ids don't leak."""
    if not (o := _store().get(order_id)) or o["buyer_id"] != buyer_id:
        raise HTTPException(404, detail="Unknown order id")
    return o


def _pending(order_id: str, buyer_id: str) -> dict:
    o = get(order_id, buyer_id)
    if o["status"] != "pending_approval":
        raise HTTPException(409, detail=f"Order is {o['status']}, not pending approval")
    return o


def _key(r: dict) -> tuple:
    return r["code"], r["product_id"], json.dumps(r["facts"], sort_keys=True)


def _approval_status(o: dict, res: gate.GateResult) -> str:
    """The human signed off on exactly what they were shown. Any concern that is new or whose facts changed
    (a bigger overrun, a new price) or a different total sends it back to them instead of confirming."""
    if res.status == "refused":
        return "refused"
    shown = {_key(r) for r in o["decision"]["reasons"]}
    got = {_key(r.model_dump(mode="json")) for r in res.decision.reasons if r.severity is not gate.INFO}
    return "pending_approval" if got - shown or res.total_cents != o["total_cents"] else "confirmed"


def _stale(o: dict, seen_decided_at: datetime | None) -> HTTPException | None:
    if seen_decided_at and datetime.fromisoformat(o["decision"]["decided_at"]) != seen_decided_at:
        return HTTPException(409, detail="The order changed since you looked at it; review the new decision and approve again.")
    return None


async def approve(order_id: str, who: Principal, seen_decided_at: datetime | None = None) -> dict:
    """Human sign-off. The gate runs again with fresh quotes: a passed cut-off or vanished stock refuses the order;
    anything the human wasn't shown (e.g. PRICE_CHANGED) sends it back to them instead of confirming.
    seen_decided_at (the decision.decided_at the human was shown) binds the click to that decision: if the order was
    re-decided since (another approver, a re-check), 409. Without it, a change DURING this call is still a 409, never
    a silent retry that would sign off on terms nobody saw."""
    o = _pending(order_id, who.buyer_id)
    if err := _stale(o, seen_decided_at):
        raise err
    seen, now = o["updated_at"], datetime.now(timezone.utc)
    mandate = mandates.get(o["buyer_id"])  # the buyer's CURRENT rules, not the snapshot taken at order time
    lines = [SimpleNamespace(product_id=li["product_id"], quantity=li["quantity"]) for li in o["lines"]]
    spent = _spent_7d(o["buyer_id"], now, skip=order_id)
    res = await _gate({"actor": f"human:{who.name}:approve", "buyer_id": o["buyer_id"], "action": "approval_failed",
                       "status": "pending_approval"},
                      lines, date.fromisoformat(o["requested_date"]), mandate, order_id, spent_7d_cents=spent,
                      approved_prices={li["product_id"]: li["unit_price_cents"] for li in o["lines"]}, now=now)
    async with _order_lock:
        o = _pending(order_id, who.buyer_id)  # 409 if someone else approved / rejected it meanwhile
        if o["updated_at"] != seen or _spent_7d(o["buyer_id"], now, skip=order_id) != spent:
            raise HTTPException(409, detail="The order or the buyer's spend changed while it was being re-checked; "
                                            "review it and approve again.")
        status = _approval_status(o, res)
        o.update(status=status, lines=res.lines, total_cents=res.total_cents, updated_at=now.isoformat(),
                 decision=res.decision.model_dump(mode="json"),
                 signed_off_by=who.name if status == "confirmed" else None)
        await asyncio.to_thread(_save)
        audit_id = await _audit(f"human:{who.name}:approve", order_id, o["buyer_id"], o["requested_date"],
                                res.lines, mandate, res, now=now, status=status,
                                action="approved" if status == "confirmed" else "approval_blocked")
    return _response(order_id, status, _view(res), audit_id)


async def reject(order_id: str, who: Principal) -> dict:
    """Human says no. Audited with the decision they were shown (AuditEntry has no action field, so the
    action is in the actor: human:<name>:reject)."""
    async with _order_lock:
        o = _pending(order_id, who.buyer_id)
        now = datetime.now(timezone.utc)
        o.update(status="rejected", signed_off_by=who.name, updated_at=now.isoformat())
        await asyncio.to_thread(_save)
        decision = Decision.model_validate(o["decision"])
        audit_id = await _audit(f"human:{who.name}:reject", order_id, o["buyer_id"], o["requested_date"], o["lines"],
                                Mandate.model_validate(o["mandate"]), None, decision=decision, now=now,
                                action="rejected", status="rejected")
    return _response(order_id, "rejected", {"total_cents": o["total_cents"], "lines": o["lines"],
                                            "decision": o["decision"], "rejected_options": []}, audit_id)


def _buyer(r: dict) -> str | None:
    return r.get("buyer_id") if r.get("kind") else r["input"]["request"]["buyer_id"]  # kind: security / admin event


def budgets(now: datetime | None = None) -> dict[str, dict]:
    """Weekly budget use for every buyer with a mandate (seeded or saved): what the demo checklist shows."""
    now = now or datetime.now(timezone.utc)
    out = {}
    for b in sorted(set(mandates._MANDATES) | set(mandates._stored())):
        m, spent = mandates.get(b), _spent_7d(b, now)
        cap = m.weekly_budget_cents if m else None
        out[b] = {"weekly_budget_cents": cap, "spent_7d_cents": spent,
                  "remaining_cents": None if cap is None else max(0, cap - spent),
                  "confidence_threshold": mandates.confidence_threshold(b)}
    return out


async def demo_reset(admin: str, restore_mandate: bool) -> dict:
    """Start the demo from a clean slate WITHOUT deleting anything: orders, audit trail and idempotency keys move
    to DATA_DIR/archive/<UTC timestamp>/; saved mandates stay unless restore_mandate (then they move too and every
    buyer is back on its seeded mandate). The fresh audit trail starts with who reset it."""
    global _orders, _idem
    async with _order_lock:
        now = datetime.now(timezone.utc)
        folder = config.DATA_DIR / "archive" / now.strftime("%Y%m%dT%H%M%S%fZ")
        moved = [p for p in (ORDERS_FILE, AUDIT_FILE, IDEM_FILE) + ((mandates.STORE,) if restore_mandate else ())
                 if p.exists()]

        def archive():
            folder.mkdir(parents=True, exist_ok=False)
            with _file_lock:
                for p in moved:
                    os.replace(p, folder / p.name)
        await asyncio.to_thread(archive)
        _orders, _idem = {}, {}
        rel = str(folder.relative_to(config.DATA_DIR))
        await asyncio.to_thread(_write_line, {
            "kind": "admin_event", "id": str(uuid4()), "timestamp": now.isoformat(), "actor": f"valio_admin:{admin}",
            "event": "demo_reset", "message": f"demo reset by {admin}", "archived_to": rel,
            "archived_files": [p.name for p in moved], "restore_mandate": restore_mandate, "buyer_id": None})
    return {"archived_to": rel, "archived_files": [p.name for p in moved], "restore_mandate": restore_mandate}


def audit_log(buyer_id: str | None, limit: int, outcome: str | None = None, status: str | None = None) -> list[dict]:
    """Newest last. buyer_id=None = every buyer (Valio's admin view only); outcome filters on decision.outcome,
    status on the order's status after the event (front_door.status: e.g. every refusal, whatever its outcome).
    Security events show to Valio, and to the buyer whose key was involved; outcome/status filters leave them out.
    Blocking file read: call it off the event loop (the route is a sync def → threadpool).
    ponytail: reads the whole file per call; index by buyer in a DB when it grows."""
    with _file_lock:
        if not AUDIT_FILE.exists():
            return []
        text = AUDIT_FILE.read_text(encoding="utf-8")
    rows = []
    for line in text.splitlines():
        try:
            r = json.loads(line)
            if (buyer_id is None or _buyer(r) == buyer_id) and \
                    (outcome is None or (r.get("decision") or {}).get("outcome") == outcome) and \
                    (status is None or (r.get("front_door") or {}).get("status") == status):
                rows.append(r)
        except (ValueError, KeyError, TypeError, AttributeError):  # a torn line (crash mid-write) or junk: skip, keep the rest
            if line.strip():
                log.warning("skipping unreadable audit line")
    return rows[-limit:]
