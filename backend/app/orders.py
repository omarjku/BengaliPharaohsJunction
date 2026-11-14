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

from . import catalogue, gate, mandates
from .auth import Principal

# ponytail: JSON files on local disk (D8). Render's disk is ephemeral, so orders + audit vanish on redeploy and
# the public routes can grow the files without bound; move to Postgres (Aiven) with retention before production.
AUDIT_FILE = catalogue.DATA / "audit.jsonl"
ORDERS_FILE = catalogue.DATA / "orders.json"
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


def _store() -> dict[str, dict]:
    global _orders
    if _orders is None:
        _orders = json.loads(ORDERS_FILE.read_text()) if ORDERS_FILE.exists() else {}
    return _orders


def _save() -> None:
    with _file_lock:
        ORDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = ORDERS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_store(), ensure_ascii=False))
        os.replace(tmp, ORDERS_FILE)  # atomic: a crash never leaves half a file


def _append_audit(entry: AuditEntry) -> None:
    with _file_lock:
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")


async def _audit(actor: str, order_id: str, buyer_id: str, requested_date: str, lines: list[dict], mandate: Mandate | None,
           res: gate.GateResult | None, decision=None, now: datetime | None = None) -> str:
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
    await asyncio.to_thread(_append_audit, entry)
    return entry.id


def _spent_7d(buyer_id: str, now: datetime, skip: str | None = None) -> int:
    since = (now - timedelta(days=7)).isoformat()
    return sum(o["total_cents"] for o in _store().values() if o["buyer_id"] == buyer_id and o["id"] != skip
               and o["status"] == "confirmed" and o["updated_at"] >= since)


async def _gate(*args, **kwargs) -> gate.GateResult:
    try:
        return await gate.check(*args, **kwargs)
    except Exception:
        # Raw errors (URLs, upstream bodies) stay in the server log; nothing was ordered.
        log.exception("front-door gate failed")
        raise HTTPException(503, detail="Valio availability check failed; nothing was ordered. Retry shortly.")


def _response(order_id: str | None, status: str, body: dict, audit_id: str) -> dict:
    return {"order_id": order_id, "status": status, "audit_id": audit_id, **body}


def _view(res: gate.GateResult) -> dict:
    return {"total_cents": res.total_cents, "lines": res.lines, "decision": res.decision.model_dump(mode="json"),
            "rejected_options": [r.model_dump(mode="json") for r in res.rejected_options]}


def _busy() -> HTTPException:
    return HTTPException(409, detail="The buyer's orders changed while this one was being checked; retry.")


async def place(buyer_id: str, requested_date, lines: list, mandate: Mandate | None) -> dict:
    """`mandate` is the buyer's stored one (mandates.get), never the client's; None → refused (MANDATE_MISSING)."""
    oid = str(uuid4())
    for _ in range(MAX_RETRIES):
        now = datetime.now(timezone.utc)
        spent = _spent_7d(buyer_id, now)
        res = await _gate(lines, requested_date, mandate, oid, spent_7d_cents=spent, now=now)  # Valio calls, no lock
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
                                    now=now)
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


async def approve(order_id: str, who: Principal) -> dict:
    """Human sign-off. The gate runs again with fresh quotes: a passed cut-off or vanished stock refuses the order;
    anything the human wasn't shown (e.g. PRICE_CHANGED) sends it back to them instead of confirming."""
    for _ in range(MAX_RETRIES):
        o = _pending(order_id, who.buyer_id)
        seen, now = o["updated_at"], datetime.now(timezone.utc)
        mandate = mandates.get(o["buyer_id"])  # the buyer's CURRENT rules, not the snapshot taken at order time
        lines = [SimpleNamespace(product_id=li["product_id"], quantity=li["quantity"]) for li in o["lines"]]
        spent = _spent_7d(o["buyer_id"], now, skip=order_id)
        res = await _gate(lines, date.fromisoformat(o["requested_date"]), mandate, order_id, spent_7d_cents=spent,
                          approved_prices={li["product_id"]: li["unit_price_cents"] for li in o["lines"]}, now=now)
        async with _order_lock:
            o = _pending(order_id, who.buyer_id)  # 409 if someone else approved / rejected it meanwhile
            if o["updated_at"] != seen or _spent_7d(o["buyer_id"], now, skip=order_id) != spent:
                continue
            status = _approval_status(o, res)
            o.update(status=status, lines=res.lines, total_cents=res.total_cents, updated_at=now.isoformat(),
                     decision=res.decision.model_dump(mode="json"),
                     signed_off_by=who.name if status == "confirmed" else None)
            await asyncio.to_thread(_save)
            audit_id = await _audit(f"human:{who.name}:approve", order_id, o["buyer_id"], o["requested_date"],
                                    res.lines, mandate, res, now=now)
        return _response(order_id, status, _view(res), audit_id)
    raise _busy()


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
                                Mandate.model_validate(o["mandate"]), None, decision=decision, now=now)
    return _response(order_id, "rejected", {"total_cents": o["total_cents"], "lines": o["lines"],
                                            "decision": o["decision"], "rejected_options": []}, audit_id)


def audit_log(buyer_id: str, limit: int) -> list[dict]:
    """Newest last. Blocking file read: call it off the event loop (the route is a sync def → threadpool).
    ponytail: reads the whole file per call; index by buyer in a DB when it grows."""
    with _file_lock:
        if not AUDIT_FILE.exists():
            return []
        text = AUDIT_FILE.read_text(encoding="utf-8")
    rows = []
    for line in text.splitlines():
        try:
            r = json.loads(line)
            if r["input"]["request"]["buyer_id"] == buyer_id:
                rows.append(r)
        except (ValueError, KeyError, TypeError):  # a torn line (crash mid-write) or junk: skip, keep the rest
            if line.strip():
                log.warning("skipping unreadable audit line")
    return rows[-limit:]
