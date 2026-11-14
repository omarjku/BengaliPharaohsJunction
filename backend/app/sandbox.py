"""Short-lived QR test kitchens backed by an atomic, hash-only registry."""
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from . import config

TEMPLATE = "helsinki-bistro"
TTL = timedelta(hours=24)
MAX_LIVE = 1200  # > per-IP mint limit × TTL (40/h × 24 h = 960): one address can't fill every slot
_BUYER = re.compile(r"^try-[0-9a-f]{8}$")
_lock = threading.Lock()


@dataclass(frozen=True)
class Credential:
    buyer_id: str
    role: str
    name: str
    expires_at: datetime


def is_sandbox_buyer(buyer_id: str) -> bool:
    return bool(_BUYER.fullmatch(buyer_id))


def _path():
    return config.DATA_DIR / "sandboxes.json"


def _read() -> dict[str, dict]:
    path = _path()
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError):
        raise HTTPException(503, detail="The test-kitchen registry cannot be read right now.") from None
    if not isinstance(data, dict):
        raise HTTPException(503, detail="The test-kitchen registry cannot be read right now.")
    return data


def _expires(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _write(data: dict[str, dict]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    os.replace(tmp, path)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _record_credential(buyer_id: str, record: dict, key: str, role: str, now: datetime) -> Credential | None:
    if not isinstance(record, dict):
        return None
    expires_at = _expires(record.get("expires_at"))
    if expires_at is None or expires_at <= now:
        return None
    field = f"{role}_key_hash"
    stored = record.get(field)
    if not isinstance(stored, str) or not hmac.compare_digest(stored, _hash(key)):
        return None
    return Credential(buyer_id, role, buyer_id, expires_at)


def lookup(key: str | None, role: str) -> Credential | None:
    """Return a live credential for exactly one sandbox role, never the secret itself."""
    if not config.SANDBOX_ENABLED or not key or role not in ("agent", "approver"):
        return None
    now = datetime.now(timezone.utc)
    with _lock:
        for buyer_id, record in _read().items():
            if credential := _record_credential(buyer_id, record, key, role, now):
                return credential
    return None


def lookup_any(key: str | None) -> Credential | None:
    if not config.SANDBOX_ENABLED or not key:
        return None
    for role in ("agent", "approver"):
        if credential := lookup(key, role):
            return credential
    return None


def recognizes(key: str | None) -> bool:
    """Whether a key hash is registered, including an expired or wrong-role sandbox key."""
    if not key:
        return False
    digest = _hash(key)
    with _lock:
        for record in _read().values():
            if isinstance(record, dict) and digest in (record.get("agent_key_hash"), record.get("approver_key_hash")):
                return True
    return False


def mint() -> dict:
    """Mint and persist one fresh sandbox, returning its plaintext keys exactly once."""
    now = datetime.now(timezone.utc)
    expires_at = now + TTL
    with _lock:
        records = {
            buyer_id: record for buyer_id, record in _read().items()
            if isinstance(record, dict) and (_expires(record.get("expires_at")) or datetime.min.replace(tzinfo=timezone.utc)) > now
        }
        if len(records) >= MAX_LIVE:
            raise HTTPException(429, detail="Too many live test kitchens; try again later.")
        while True:
            buyer_id = f"try-{secrets.token_hex(4)}"
            if buyer_id not in records:
                break
        agent_key, approver_key = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        records[buyer_id] = {
            "agent_key_hash": _hash(agent_key),
            "approver_key_hash": _hash(approver_key),
            "expires_at": expires_at.isoformat(),
            "template": TEMPLATE,
        }
        _write(records)
    return {"buyer_id": buyer_id, "agent_key": agent_key, "approver_key": approver_key,
            "expires_at": expires_at.isoformat(), "template": TEMPLATE}
