"""Optional RFC 9421 HTTP Message Signatures for buyer agents (Ed25519, RFC 9530 Content-Digest).

A buyer may register its agent's public key(s): AGENT_SIGNING_KEYS = comma list of `buyer:kid:base64pub` (32-byte raw
Ed25519 public key). From then on every POST /api/orders and /api/agent/* for that buyer must be signed, on top of
X-Agent-Key; unsigned or badly signed requests get 401 (audited). Buyers without a registered key work as before.

Accepted (and nothing looser), e.g.:
  Content-Digest: sha-256=:<base64 sha256(body)>:
  Signature-Input: sig1=("@method" "@path" "content-digest");created=1763100000;keyid="kitchen-1";alg="ed25519"
  Signature: sig1=:<base64 64-byte Ed25519 signature>:
Signature base (RFC 9421 §2.5), lines joined by "\\n", no trailing newline:
  "@method": POST
  "@path": /api/orders
  "content-digest": sha-256=:…:
  "@signature-params": ("@method" "@path" "content-digest");created=…;keyid="kitchen-1";alg="ed25519"
`created` must be within WINDOW_S of the server clock, and an exact signature is accepted once (replay cache).
ponytail: one signature per request, three covered components, in-memory replay cache (one worker, like the rest).
"""
import base64
import binascii
import hashlib
import re
import time
from typing import Annotated

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import Depends, HTTPException, Request

from . import auth, config

ALG = "ed25519"
REQUIRED = ("@method", "@path", "content-digest")
WINDOW_S = 300
_INPUT = re.compile(r'^\s*([A-Za-z0-9_.*-]+)=(\((?:"[^"]+"\s*)*\)(?:;[a-z]+=(?:"[^"]*"|-?\d+))*)\s*$')
_seen: dict[bytes, float] = {}  # signature → expiry (replay cache)


def keys_for(buyer_id: str) -> dict[str, Ed25519PublicKey]:
    out = {}
    for item in config.AGENT_SIGNING_KEYS.split(","):
        parts = item.strip().split(":")
        if len(parts) == 3 and parts[0] == buyer_id:
            try:
                out[parts[1]] = Ed25519PublicKey.from_public_bytes(base64.b64decode(parts[2], validate=True))
            except (ValueError, binascii.Error):
                continue  # a malformed entry registers nothing (and so can't lock a buyer out by accident)
    return out


def content_digest(body: bytes) -> str:
    return "sha-256=:" + base64.b64encode(hashlib.sha256(body).digest()).decode() + ":"


def signature_base(components: list[str], values: dict[str, str], params: str) -> bytes:
    lines = [f'"{c}": {values[c]}' for c in components] + [f'"@signature-params": {params}']
    return "\n".join(lines).encode()


def _fail(request: Request, buyer_id: str, why: str) -> HTTPException:
    from . import orders, ratelimit  # late import: orders imports auth, which this module imports
    orders.security_event("bad_request_signature", f"{request.method} {request.url.path}", ratelimit.client_ip(request),
                          buyer_id=buyer_id, detail=why)
    return HTTPException(401, detail=f"Request signature required for this buyer (RFC 9421): {why}")


async def verify(request: Request, buyer_id: str, now: float | None = None) -> None:
    """Raise 401 unless the request carries a valid signature from one of the buyer's registered keys."""
    keys = keys_for(buyer_id)
    if not keys:
        return
    now = time.time() if now is None else now
    sig_input, sig = request.headers.get("signature-input"), request.headers.get("signature")
    if not sig_input or not sig:
        raise _fail(request, buyer_id, "missing Signature-Input / Signature")
    m = _INPUT.match(sig_input)
    if not m:
        raise _fail(request, buyer_id, "Signature-Input must hold exactly one signature in RFC 9421 form")
    label, params = m.group(1), m.group(2)
    components = re.findall(r'"([^"]+)"', params.split(")")[0])
    p = dict(re.findall(r';([a-z]+)=("[^"]*"|-?\d+)', params.split(")", 1)[1]))
    if sorted(components) != sorted(REQUIRED):
        raise _fail(request, buyer_id, f"must cover exactly {', '.join(REQUIRED)}")
    if p.get("alg", f'"{ALG}"') != f'"{ALG}"' or "keyid" not in p or "created" not in p:
        raise _fail(request, buyer_id, 'needs keyid, created and alg="ed25519"')
    kid, created = p["keyid"].strip('"'), int(p["created"])
    if abs(now - created) > WINDOW_S or ("expires" in p and int(p["expires"]) < now):
        raise _fail(request, buyer_id, f"created is outside the {WINDOW_S}s window (clock skew or replay)")
    if kid not in keys:
        raise _fail(request, buyer_id, "keyid is not registered for this buyer")
    body = await request.body()
    digest = request.headers.get("content-digest", "")
    if digest != content_digest(body):
        raise _fail(request, buyer_id, "Content-Digest is missing or doesn't match the body (sha-256)")
    sm = re.fullmatch(rf'\s*{re.escape(label)}=:([A-Za-z0-9+/=]+):\s*', sig)
    if not sm:
        raise _fail(request, buyer_id, "Signature must be <label>=:<base64>: for the same label")
    raw_path = request.scope.get("raw_path", b"").decode("latin-1").split("?")[0] or request.url.path
    values = {"@method": request.method.upper(), "@path": raw_path or "/", "content-digest": digest}
    signature = base64.b64decode(sm.group(1))
    try:
        keys[kid].verify(signature, signature_base(components, values, params))
    except InvalidSignature:
        raise _fail(request, buyer_id, "signature does not verify") from None
    for s in [s for s, exp in _seen.items() if exp < now]:
        del _seen[s]
    if signature in _seen:
        raise _fail(request, buyer_id, "this exact signature was already used (replay)")
    _seen[signature] = created + WINDOW_S


async def signed_agent(request: Request, who: Annotated[auth.Principal, Depends(auth.agent)]) -> auth.Principal:
    """X-Agent-Key, plus an RFC 9421 signature when the key's buyer has registered a signing key."""
    await verify(request, who.buyer_id)
    return who
