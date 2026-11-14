"""Optional RFC 9421 request signatures for agents. Uses the client example's own signer (scripts/sign_request.py)."""
import base64
import json
import sys
import time
from pathlib import Path

from conftest import REQ, store_mandate
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient

from app import config, httpsig, orders
from app.main import app

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from sign_request import sign_headers  # noqa: E402

c = TestClient(app, raise_server_exceptions=False)
URL = "http://testserver/api/orders"
KEY = Ed25519PrivateKey.generate()
PUB = base64.b64encode(KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
MANDATE = {"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9}


def register(monkeypatch):
    monkeypatch.setattr(config, "AGENT_SIGNING_KEYS", f"chef:kitchen-1:{PUB},malformed-entry")
    httpsig._seen.clear()
    store_mandate(MANDATE)


def body(qty=10) -> bytes:
    return json.dumps({"requested_date": REQ.isoformat(),
                       "lines": [{"product_id": "463335", "quantity": qty}]}).encode()


def send(raw: bytes, signed: dict | None = None, agent="agent-chef", path="/api/orders"):
    h = {"X-Agent-Key": agent, "Content-Type": "application/json", **(signed or {})}
    return c.post(path, content=raw, headers=h)


def test_valid_signature_is_accepted(shop, monkeypatch):
    register(monkeypatch)
    raw = body()
    r = send(raw, sign_headers("POST", URL, raw, KEY, "kitchen-1"))
    assert r.status_code == 200 and r.json()["status"] == "confirmed"


def test_buyer_with_a_key_must_sign_others_work_as_before(shop, monkeypatch):
    register(monkeypatch)
    assert send(body()).status_code == 401
    store_mandate(dict(MANDATE, buyer_id="other"))
    assert send(body(), agent="agent-other").status_code == 200  # no key registered for "other"
    assert orders._store() and all(o["buyer_id"] == "other" for o in orders._store().values())


def test_tampered_body_is_rejected(shop, monkeypatch):
    register(monkeypatch)
    signed = sign_headers("POST", URL, body(10), KEY, "kitchen-1")
    assert send(body(1000), signed).status_code == 401  # body changed, digest no longer matches
    forged = {**signed, "Content-Digest": httpsig.content_digest(body(1000))}  # digest fixed up, signature not
    r = send(body(1000), forged)
    assert r.status_code == 401 and "does not verify" in r.json()["detail"]
    assert orders._store() == {}


def test_replay_outside_the_window_and_exact_replay_are_rejected(shop, monkeypatch):
    register(monkeypatch)
    raw = body()
    old = sign_headers("POST", URL, raw, KEY, "kitchen-1", created=int(time.time()) - httpsig.WINDOW_S - 60)
    r = send(raw, old)
    assert r.status_code == 401 and "window" in r.json()["detail"]
    fresh = sign_headers("POST", URL, raw, KEY, "kitchen-1")
    assert send(raw, fresh).status_code == 200
    assert send(raw, fresh).status_code == 401  # the same signature again: replay


def test_missing_content_digest_is_rejected(shop, monkeypatch):
    register(monkeypatch)
    raw = body()
    signed = sign_headers("POST", URL, raw, KEY, "kitchen-1")
    del signed["Content-Digest"]
    r = send(raw, signed)
    assert r.status_code == 401 and "Content-Digest" in r.json()["detail"]


def test_wrong_key_path_or_components_are_rejected(shop, monkeypatch):
    register(monkeypatch)
    raw = body()
    other_key = sign_headers("POST", URL, raw, Ed25519PrivateKey.generate(), "kitchen-1")
    assert send(raw, other_key).status_code == 401
    unknown_kid = sign_headers("POST", URL, raw, KEY, "someone-else")
    assert send(raw, unknown_kid).status_code == 401
    for_other_path = sign_headers("POST", "http://testserver/api/agent/run", raw, KEY, "kitchen-1")
    assert send(raw, for_other_path).status_code == 401  # signed for another route
    fewer = sign_headers("POST", URL, raw, KEY, "kitchen-1")
    fewer["Signature-Input"] = fewer["Signature-Input"].replace(' "content-digest"', "")
    assert send(raw, fewer).status_code == 401  # must cover method, path and content-digest


def test_agent_routes_need_the_signature_too_and_failures_are_audited(shop, monkeypatch):
    register(monkeypatch)
    r = c.post("/api/agent/ask", headers={"X-Agent-Key": "agent-chef"}, json={"text": "milk for Monday"})
    assert r.status_code == 401
    events = [json.loads(x) for x in orders.AUDIT_FILE.read_text().splitlines()]
    assert events[-1]["event"] == "bad_request_signature" and events[-1]["buyer_id"] == "chef"
    assert "agent-chef" not in orders.AUDIT_FILE.read_text()
