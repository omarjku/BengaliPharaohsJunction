"""Trust features: Valio's admin audit view and signed decisions. Offline (conftest.py)."""
import json
from conftest import REQ, store_mandate
from fastapi.testclient import TestClient

from app import config, orders
from app.main import app

c = TestClient(app, raise_server_exceptions=False)
AG, AP, ADM = {"X-Agent-Key": "agent-chef"}, {"X-Approver-Key": "appr-chef"}, {"X-Valio-Admin-Key": "valio-ops"}
MANDATE = {"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9,
           "hard_rules": [{"kind": "auto_approve_limit_cents", "value": 100000}]}


def order(lines, buyer="chef"):
    store_mandate(dict(MANDATE, buyer_id=buyer))
    return c.post("/api/orders", headers={"X-Agent-Key": f"agent-{buyer}"},
                  json={"requested_date": REQ.isoformat(), "lines": [{"product_id": p, "quantity": q} for p, q in lines]})


# --- 1. Valio-side audit view
def test_admin_sees_every_buyer_and_can_filter(shop):
    order([("463335", 1)])                       # chef, AUTO
    order([("463335", 1000)])                    # chef, ASK_HUMAN (over the limit)
    order([("463335", 1)], buyer="other")        # other, AUTO
    rows = c.get("/api/admin/audit", headers=ADM).json()
    assert [r["input"]["request"]["buyer_id"] for r in rows] == ["chef", "chef", "other"]
    assert len(c.get("/api/admin/audit", params={"buyer_id": "other"}, headers=ADM).json()) == 1
    asks = c.get("/api/admin/audit", params={"outcome": "ASK_HUMAN"}, headers=ADM).json()
    assert len(asks) == 1 and asks[0]["decision"]["outcome"] == "ASK_HUMAN"
    assert len(c.get("/api/admin/audit", params={"limit": 2}, headers=ADM).json()) == 2
    assert c.get("/api/admin/audit", params={"outcome": "MAYBE"}, headers=ADM).status_code == 422


def test_admin_audit_needs_an_admin_key(shop, monkeypatch):
    assert c.get("/api/admin/audit").status_code == 401
    assert c.get("/api/admin/audit", headers={"X-Valio-Admin-Key": "nope"}).status_code == 401
    assert c.get("/api/admin/audit", headers={"X-Valio-Admin-Key": "appr-chef"}).status_code == 401  # approver ≠ admin
    assert c.get("/api/admin/audit", headers=AP).status_code == 401  # wrong header entirely
    monkeypatch.setattr(config, "VALIO_ADMIN_KEYS", "")
    assert c.get("/api/admin/audit", headers=ADM).status_code == 503  # never open by default


def test_admin_keys_are_read_only(shop, monkeypatch):
    oid = order([("463335", 1000)]).json()["order_id"]
    assert c.post(f"/api/orders/{oid}/approve", headers={"X-Approver-Key": "valio-ops"}).status_code == 401
    assert c.post("/api/orders", headers={"X-Agent-Key": "valio-ops"},
                  json={"requested_date": REQ.isoformat(), "lines": [{"product_id": "463335", "quantity": 1}]}
                  ).status_code == 401
    # misconfigured: the same secret listed as admin AND approver/agent → still read-only, and no admin view
    monkeypatch.setattr(config, "APPROVER_KEYS", config.APPROVER_KEYS + ",valio-ops=chef:Ops")
    monkeypatch.setattr(config, "AGENT_KEYS", config.AGENT_KEYS + ",valio-ops=chef")
    assert c.post(f"/api/orders/{oid}/approve", headers={"X-Approver-Key": "valio-ops"}).status_code == 403
    assert c.post("/api/orders", headers={"X-Agent-Key": "valio-ops"},
                  json={"requested_date": REQ.isoformat(), "lines": [{"product_id": "463335", "quantity": 1}]}
                  ).status_code == 403
    assert c.get("/api/admin/audit", headers=ADM).status_code == 403
    assert orders._store()[oid]["status"] == "pending_approval"


def test_buyer_audit_stays_scoped(shop):
    order([("463335", 1)])
    order([("463335", 1)], buyer="other")
    assert len(c.get("/api/audit", headers=AP).json()) == 1


# --- 2. Signed decisions and quote facts
import base64  # noqa: E402
import copy  # noqa: E402

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # noqa: E402

from app import signing  # noqa: E402


def verify(body):
    return c.post("/api/verify", json={"signed_statement": body["signed_statement"], "signature": body["signature"]})


def test_order_response_is_signed_and_verifies(shop):
    body = order([("463335", 10)]).json()
    st, sig = body["signed_statement"], body["signature"]
    assert sig["alg"] == "Ed25519" and sig["kid"] == signing.KID
    assert st["order_id"] == body["order_id"] and st["decision"] == body["decision"] and st["total_cents"] == 1400
    [q] = st["quotes"]
    assert q["product_id"] == "463335" and q["unit_price_cents"] == 140 and q["availability"] == "available"
    assert q["cut_off"] and q["fetched_at"] and q["cut_off_passed"] is False
    r = verify(body).json()
    assert r["valid"] is True and r["kid"] == signing.KID


def test_tampering_with_any_field_breaks_the_signature(shop):
    body = order([("463335", 10)]).json()
    for path, value in [(("total_cents",), 1), (("quotes", 0, "unit_price_cents"), 1),
                        (("quotes", 0, "availability"), "unknown"), (("decision", "outcome"), "ASK_HUMAN"),
                        (("status",), "pending_approval")]:
        bad = copy.deepcopy(body)
        node = bad["signed_statement"]
        for k in path[:-1]:
            node = node[k]
        node[path[-1]] = value
        assert verify(bad).json()["valid"] is False, path
    forged = copy.deepcopy(body)
    forged["signature"]["kid"] = "fd-someone-else"
    assert verify(forged).json()["valid"] is False
    forged["signature"] = {"kid": signing.KID, "alg": "Ed25519", "value": "not base64 !!"}
    assert verify(forged).json()["valid"] is False


def test_published_jwk_verifies_independently_of_the_server(shop):
    """A buyer's agent needs only the JWK and the canonical-bytes rule from docs/STANDARDS.md."""
    body = order([("463335", 10)]).json()
    [jwk] = c.get("/.well-known/front-door-keys.json").json()["keys"]
    assert (jwk["kty"], jwk["crv"], jwk["kid"]) == ("OKP", "Ed25519", body["signature"]["kid"])
    pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
    pub = Ed25519PublicKey.from_public_bytes(base64.urlsafe_b64decode(pad(jwk["x"])))
    msg = signing.canonical(body["signed_statement"])
    pub.verify(base64.urlsafe_b64decode(pad(body["signature"]["value"])), msg)  # raises if invalid
    assert msg.startswith(b'{"audit_id":') and b" " not in msg.split(b'"decision"')[0]


def test_refusals_approvals_and_rejections_are_signed_too(shop):
    assert verify(order([("463038", 1)]).json()).json()["valid"]  # refused
    oid = order([("463335", 1000)]).json()["order_id"]
    assert verify(c.post(f"/api/orders/{oid}/approve", headers=AP).json()).json()["valid"]
    oid = order([("463335", 1000)]).json()["order_id"]
    assert verify(c.post(f"/api/orders/{oid}/reject", headers=AP).json()).json()["valid"]


def test_signing_key_from_env(monkeypatch):
    seed = bytes(range(32))
    monkeypatch.setattr(config, "FRONT_DOOR_SIGNING_KEY", base64.b64encode(seed).decode())
    k = signing._load()
    assert k.private_bytes_raw() == seed
    monkeypatch.setattr(config, "FRONT_DOOR_SIGNING_KEY", base64.b64encode(b"short").decode())
    import pytest
    with pytest.raises(RuntimeError):
        signing._load()


# --- the audit line carries the response's signed statement (Room 4's "Signed by the front door ✓")
def test_audit_lines_carry_a_verifiable_signed_statement(shop):
    placed = order([("463335", 1000)]).json()   # held
    approved = c.post(f"/api/orders/{placed['order_id']}/approve", headers=AP).json()
    held2 = order([("463335", 1000)]).json()
    rejected = c.post(f"/api/orders/{held2['order_id']}/reject", headers=AP).json()
    refused = order([("463038", 1)]).json()     # cut-off passed: refused, still audited and signed
    rows = [r for r in c.get("/api/admin/audit", headers=ADM).json() if r.get("front_door", {}).get("signature")]
    assert len(rows) == 5
    for row, resp in zip(rows, [placed, approved, held2, rejected, refused]):
        fd = row["front_door"]
        assert fd["signed_statement"] == resp["signed_statement"] and fd["signature"] == resp["signature"]
        assert fd["signed_statement"]["audit_id"] == row["id"]  # the statement names this very audit line
        assert c.post("/api/verify", json={"signed_statement": fd["signed_statement"],
                                           "signature": fd["signature"]}).json()["valid"] is True
    tampered = json.loads(json.dumps(rows[1]["front_door"]))
    tampered["signed_statement"]["status"] = "rejected"
    assert c.post("/api/verify", json={"signed_statement": tampered["signed_statement"],
                                       "signature": tampered["signature"]}).json()["valid"] is False
    assert c.get("/api/audit", headers=AP).json()[0]["front_door"]["signature"]  # the buyer's view has it too
