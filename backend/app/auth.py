"""Minimal API-key auth for the front door (FastAPI dependencies).

X-Agent-Key: a buyer's purchasing agent; may place orders for its buyer only.
X-Approver-Key: a human at the buyer; may read, approve and reject that buyer's orders and audit trail.
X-Valio-Admin-Key: Valio staff; may read every buyer's audit trail, nothing else (never order or approve).
Keys live in env (config.AGENT_KEYS / APPROVER_KEYS, `key=buyer_id[:name]`), so the buyer and the approver's
name come from the key, never from the request body. No keys configured → 503: the door is never open by default.
ponytail: static shared secrets; per-buyer OAuth / signed mandates before production.
"""
import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Header, HTTPException, Request

from . import config


@dataclass(frozen=True)
class Principal:
    buyer_id: str
    name: str
    key_id: str = field(default="", compare=False)  # non-secret fingerprint of the credential (scopes idempotency)


def _parse(spec: str) -> list[tuple[bytes, Principal]]:
    out = []
    for item in spec.split(","):
        key, _, who = item.strip().partition("=")
        buyer, _, name = who.partition(":")
        if key and buyer:  # malformed entries grant nothing
            out.append((key.encode(), Principal(buyer, name or buyer, hashlib.sha256(key.encode()).hexdigest()[:16])))
    return out


def _match(spec: str, key: str | None, what: str) -> Principal:
    keys = _parse(spec)
    if not keys:
        raise HTTPException(503, detail=f"{what} keys are not configured on this server")
    hit = None
    for k, p in keys:  # compare against every key, constant time each
        if hmac.compare_digest(k, (key or "").encode()):
            hit = p
    if hit is None:
        raise HTTPException(401, detail=f"Missing or invalid {what} key")
    return hit


def _listed(spec: str, key: str) -> bool:
    return any(hmac.compare_digest(k, key.encode()) for k, _ in _parse(spec))


def _agent(key: str | None) -> Principal:
    p = _match(config.AGENT_KEYS, key, "X-Agent-Key")
    if _listed(config.VALIO_ADMIN_KEYS, key):  # same secret listed twice: the read-only role wins
        raise HTTPException(403, detail="A Valio admin key is read-only")
    return p


def _approver(key: str | None) -> Principal:
    p = _match(config.APPROVER_KEYS, key, "X-Approver-Key")
    if _listed(config.AGENT_KEYS, key):
        raise HTTPException(403, detail="An agent key can never sign off")  # same secret listed in both: refuse
    if _listed(config.VALIO_ADMIN_KEYS, key):
        raise HTTPException(403, detail="A Valio admin key is read-only")
    return p


def _admin(key: str | None) -> Principal:
    p = _match(config.VALIO_ADMIN_KEYS, key, "X-Valio-Admin-Key")
    if _listed(config.AGENT_KEYS, key) or _listed(config.APPROVER_KEYS, key):
        raise HTTPException(403, detail="Admin keys must be separate from agent and approver keys")
    return p


def _owner(key: str) -> tuple[str, str] | None:
    """(role, buyer) of a configured key, whichever list it is in."""
    for role, spec in (("agent", config.AGENT_KEYS), ("approver", config.APPROVER_KEYS),
                       ("valio_admin", config.VALIO_ADMIN_KEYS)):
        for k, p in _parse(spec):
            if hmac.compare_digest(k, key.encode()):
                return role, p.buyer_id
    return None


def _guarded(request: Request, header: str, key: str | None, check) -> Principal:
    """Run a key check; a presented key that is refused (wrong, or used outside its role) is audited as a security
    event. No key at all is not audited (the rate limiter handles probing) so the trail stays readable."""
    try:
        return check(key)
    except HTTPException as e:
        if key and e.status_code in (401, 403):
            from . import orders, ratelimit  # late: both import this module
            owner = _owner(key)
            orders.security_event("key_used_outside_its_role" if owner else "invalid_key",
                                  f"{request.method} {request.url.path}", ratelimit.client_ip(request),
                                  buyer_id=owner[1] if owner else None, header=header,
                                  key_role=owner[0] if owner else None, http_status=e.status_code)
        raise


def agent(request: Request, x_agent_key: Annotated[str | None, Header()] = None) -> Principal:
    return _guarded(request, "X-Agent-Key", x_agent_key, _agent)


def approver(request: Request, x_approver_key: Annotated[str | None, Header()] = None) -> Principal:
    return _guarded(request, "X-Approver-Key", x_approver_key, _approver)


def order_reader(request: Request, x_agent_key: Annotated[str | None, Header()] = None,
                 x_approver_key: Annotated[str | None, Header()] = None) -> Principal:
    """Read-only access to one buyer's orders: the buyer's approver, or its agent checking an order it placed."""
    if x_approver_key is not None or x_agent_key is None:
        return approver(request, x_approver_key)
    return agent(request, x_agent_key)


def valio_admin(request: Request, x_valio_admin_key: Annotated[str | None, Header()] = None) -> Principal:
    """Valio's own view across buyers. Principal.buyer_id is the label from the key (e.g. "valio"), not a buyer."""
    return _guarded(request, "X-Valio-Admin-Key", x_valio_admin_key, _admin)
