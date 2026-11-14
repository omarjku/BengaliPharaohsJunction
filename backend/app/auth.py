"""Minimal API-key auth for the front door (FastAPI dependencies).

X-Agent-Key: a buyer's purchasing agent; may place orders for its buyer only.
X-Approver-Key: a human at the buyer; may read, approve and reject that buyer's orders and audit trail.
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


def agent(x_agent_key: Annotated[str | None, Header()] = None) -> Principal:
    return _match(config.AGENT_KEYS, x_agent_key, "X-Agent-Key")


def approver(x_approver_key: Annotated[str | None, Header()] = None) -> Principal:
    p = _match(config.APPROVER_KEYS, x_approver_key, "X-Approver-Key")
    if any(hmac.compare_digest(k, x_approver_key.encode()) for k, _ in _parse(config.AGENT_KEYS)):
        raise HTTPException(403, detail="An agent key can never sign off")  # same secret listed in both: refuse
    return p
