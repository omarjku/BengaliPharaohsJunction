"""Signed front-door statements: an Ed25519 signature over what the front door decided and the quote facts it
relied on, so a buyer's agent can check later, offline and without a manual check, that THIS front door said it.

What a valid signature proves: the holder of the published key issued exactly these bytes. It does NOT prove
Valio's warehouse holds the stock: the quote facts are what Valio's API told the front door at `fetched_at`.

Bytes signed: canonical(statement) = UTF-8 JSON, keys sorted, no whitespace (docs/STANDARDS.md has the details).
Public key: GET /.well-known/front-door-keys.json, a JWK Set (RFC 8037 OKP / Ed25519), selected by `kid`.
ponytail: one key, Python's JSON number formatting; key rotation (several kids) and RFC 8785 (JCS) canonical
numbers when a non-Python verifier needs them.
"""
import base64
import binascii
import hashlib
import json
import logging

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from . import config

ALG = "Ed25519"
ISSUER = "valio-front-door"
log = logging.getLogger(__name__)


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64url(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _load() -> Ed25519PrivateKey:
    """FRONT_DOOR_SIGNING_KEY = base64 of the 32-byte Ed25519 private key (seed). Unset → ephemeral dev key."""
    raw = config.FRONT_DOOR_SIGNING_KEY
    if not raw:
        log.warning("FRONT_DOOR_SIGNING_KEY is unset: signing with an EPHEMERAL key; signatures stop verifying "
                    "after a restart. Set it in production.")
        return Ed25519PrivateKey.generate()
    try:
        seed = base64.b64decode(raw, validate=True)
    except binascii.Error:
        raise RuntimeError("FRONT_DOOR_SIGNING_KEY is not valid base64") from None
    if len(seed) != 32:
        raise RuntimeError("FRONT_DOOR_SIGNING_KEY must be 32 bytes (base64 of an Ed25519 seed)")
    return Ed25519PrivateKey.from_private_bytes(seed)


_KEY = _load()
_PUB = _KEY.public_key()
_PUB_RAW = _PUB.public_bytes(Encoding.Raw, PublicFormat.Raw)
KID = "fd-" + hashlib.sha256(_PUB_RAW).hexdigest()[:16]


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sign(statement: dict) -> dict:
    return {"kid": KID, "alg": ALG, "value": b64url(_KEY.sign(canonical(statement)))}


def verify(statement: dict, signature: dict) -> bool:
    if signature.get("kid") != KID or signature.get("alg") != ALG:
        return False
    try:
        _PUB.verify(_unb64url(str(signature.get("value", ""))), canonical(statement))
    except (InvalidSignature, ValueError, binascii.Error):
        return False
    return True


def jwks() -> dict:
    return {"keys": [{"kty": "OKP", "crv": "Ed25519", "x": b64url(_PUB_RAW), "kid": KID, "alg": "EdDSA", "use": "sig"}]}
