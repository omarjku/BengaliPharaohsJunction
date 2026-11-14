"""Minimal API-key auth for the front door (FastAPI dependencies).

X-Agent-Key: a buyer's purchasing agent; may place orders for its buyer only.
X-Approver-Key: a human at the buyer; may read, approve and reject that buyer's orders and audit trail.
X-Valio-Admin-Key: Valio staff; may read every buyer's audit trail, nothing else (never order or approve).
Keys live in env (config.AGENT_KEYS / APPROVER_KEYS, `key=buyer_id[:name]`), so the buyer and the approver's
name come from the key, never from the request body. No keys configured → 503: the door is never open by default.
ponytail: static shared secrets; per-buyer OAuth / signed mandates before production.
"""
import hmac
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException

from . import config


@dataclass(frozen=True)
class Principal:
    buyer_id: str
    name: str


def _parse(spec: str) -> list[tuple[bytes, Principal]]:
    out = []
    for item in spec.split(","):
        key, _, who = item.strip().partition("=")
        buyer, _, name = who.partition(":")
        if key and buyer:  # malformed entries grant nothing
            out.append((key.encode(), Principal(buyer, name or buyer)))
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


def agent(x_agent_key: Annotated[str | None, Header()] = None) -> Principal:
    p = _match(config.AGENT_KEYS, x_agent_key, "X-Agent-Key")
    if _listed(config.VALIO_ADMIN_KEYS, x_agent_key):  # same secret listed twice: the read-only role wins
        raise HTTPException(403, detail="A Valio admin key is read-only")
    return p


def approver(x_approver_key: Annotated[str | None, Header()] = None) -> Principal:
    p = _match(config.APPROVER_KEYS, x_approver_key, "X-Approver-Key")
    if _listed(config.AGENT_KEYS, x_approver_key):
        raise HTTPException(403, detail="An agent key can never sign off")  # same secret listed in both: refuse
    if _listed(config.VALIO_ADMIN_KEYS, x_approver_key):
        raise HTTPException(403, detail="A Valio admin key is read-only")
    return p


def order_reader(x_agent_key: Annotated[str | None, Header()] = None,
                 x_approver_key: Annotated[str | None, Header()] = None) -> Principal:
    """Read-only access to one buyer's orders: the buyer's approver, or its agent checking an order it placed."""
    if x_approver_key is not None or x_agent_key is None:
        return approver(x_approver_key)
    return agent(x_agent_key)


def valio_admin(x_valio_admin_key: Annotated[str | None, Header()] = None) -> Principal:
    """Valio's own view across buyers. Principal.buyer_id is the label from the key (e.g. "valio"), not a buyer."""
    p = _match(config.VALIO_ADMIN_KEYS, x_valio_admin_key, "X-Valio-Admin-Key")
    if _listed(config.AGENT_KEYS, x_valio_admin_key) or _listed(config.APPROVER_KEYS, x_valio_admin_key):
        raise HTTPException(403, detail="Admin keys must be separate from agent and approver keys")
    return p
