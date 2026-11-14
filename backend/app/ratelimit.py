"""Per-caller rate limits: in-process token buckets, 429 + Retry-After when one runs dry.

A caller is its key when the key is a configured one (agent → "agent" bucket, approver/admin → "human"), else its IP:
made-up keys can't buy fresh buckets, and unauthenticated probing is limited per address.
ponytail: per-process memory, so the limits only hold with ONE uvicorn worker (as the order lock and store already
require); move the buckets to Redis if the API ever scales out.
"""
import hashlib
import math
import time

from fastapi import Request
from fastapi.responses import JSONResponse

from . import config
from .auth import _listed

LIMITS = {"agent": (30, 60.0), "human": (120, 60.0), "ip": (120, 60.0)}  # kind → (requests, per seconds)
MAX_BUCKETS = 10_000  # memory bound; on overflow everyone starts fresh (a brief gift, never a lockout)
_buckets: dict[tuple[str, str], list[float]] = {}  # (kind, who) → [tokens, last refill]


def wait_s(kind: str, who: str, now: float | None = None) -> float:
    """Take one token: 0 if allowed, else seconds until the next one."""
    cap, per = LIMITS[kind]
    now, rate = time.monotonic() if now is None else now, cap / per
    if (b := _buckets.get((kind, who))) is None:
        if len(_buckets) >= MAX_BUCKETS:
            _buckets.clear()
        b = _buckets[(kind, who)] = [float(cap), now]
    b[0], b[1] = min(cap, b[0] + (now - b[1]) * rate), now
    if b[0] >= 1:
        b[0] -= 1
        return 0.0
    return (1 - b[0]) / rate


def caller(request: Request) -> tuple[str, str]:
    h = request.headers
    for header, spec, kind in (("x-agent-key", config.AGENT_KEYS, "agent"),
                               ("x-approver-key", config.APPROVER_KEYS, "human"),
                               ("x-valio-admin-key", config.VALIO_ADMIN_KEYS, "human")):
        if (k := h.get(header)) and _listed(spec, k):
            return kind, hashlib.sha256(k.encode()).hexdigest()  # never keep the key itself
    # Render's proxy appends the connecting address last; earlier X-Forwarded-For entries are client-supplied.
    xff = h.get("x-forwarded-for")
    return "ip", xff.split(",")[-1].strip() if xff else (request.client.host if request.client else "unknown")


async def middleware(request: Request, call_next):
    if request.method != "OPTIONS" and request.url.path.startswith("/api/"):
        kind, who = caller(request)
        if (wait := wait_s(kind, who)) > 0:
            return JSONResponse({"detail": f"Too many requests; limit is {LIMITS[kind][0]} per minute"},
                                status_code=429, headers={"Retry-After": str(math.ceil(wait))})
    return await call_next(request)
