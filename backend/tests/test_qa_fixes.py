"""Fixes for the independent black-box QA run (docs/testing/independent-qa-2026-11-14.md). Offline (conftest.py)."""
import asyncio
from types import SimpleNamespace as L

from conftest import NOW, REQ, product, quote, store_mandate
from fastapi.testclient import TestClient
from trade_contracts import Mandate

from app import gate, orders, valio
from app.main import app

c = TestClient(app, raise_server_exceptions=False)
AG, AP, ADM = {"X-Agent-Key": "agent-chef"}, {"X-Approver-Key": "appr-chef"}, {"X-Valio-Admin-Key": "valio-ops"}
MANDATE = {"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9,
           "hard_rules": [{"kind": "auto_approve_limit_cents", "value": 100000}]}


def run(lines, rules=(), **kw):
    m = Mandate(id="m1", buyer_id="chef", per_line_cap_cents=10**9,
                hard_rules=[{"kind": k, "value": v} for k, v in rules], **kw)
    return asyncio.run(gate.check([L(product_id=p, quantity=q) for p, q in lines], REQ, m, "r", now=NOW))


def codes(res):
    return [r.code.value for r in res.decision.reasons]


def post(lines, mandate=None, headers=AG):
    store_mandate(mandate or MANDATE)
    return c.post("/api/orders", headers=headers,
                  json={"requested_date": REQ.isoformat(), "lines": [{"product_id": p, "quantity": q} for p, q in lines]})


def no_allergen_data(shop, pid, name_en, name_fi=None, category="300"):
    shop.products[pid] = product(pid, name_en, category=category, claims=(), contains=())
    shop.products[pid]["name_fi"] = name_fi
    shop.quotes[pid] = quote(pid)


# --- DI-02: a peanut product with empty allergen data is refused by its name
def test_name_says_peanut_is_refused_not_just_held(shop):
    no_allergen_data(shop, "464315", "PCD 500G PEANUT BUTTER")
    res = run([("464315", 1)], [("excluded_allergen", "AP")])
    assert res.status == "refused" and res.decision.outcome == "DECLINE"
    r = res.decision.reasons[0]
    assert r.code == "ALLERGEN_CONTAINS" and r.facts["source"] == "product_name" and r.facts["word"] == "peanut"
    assert r.message.startswith("Name says peanut; your rules exclude peanuts")


def test_name_check_covers_finnish_and_groundnut(shop):
    no_allergen_data(shop, "900", "Salted snack", "Suolatut maapähkinät 1 kg")
    no_allergen_data(shop, "901", "HS 1L GROUND NUT OIL")
    for pid in ("900", "901"):
        assert run([(pid, 1)], [("excluded_allergen", "peanut")]).status == "refused", pid
    no_allergen_data(shop, "902", "Wheat flour 1 kg", "Vehnäjauho")
    assert run([("902", 1)], [("excluded_allergen", "AW")]).status == "refused"


def test_negated_names_and_declared_free_from_are_not_refused_by_name(shop):
    no_allergen_data(shop, "903", "Peanut-free cookies")
    no_allergen_data(shop, "904", "Keksi", "Pähkinätön keksi")
    no_allergen_data(shop, "905", "Gluten free bread")
    no_allergen_data(shop, "907", "Gluten and milk free wafer cones")
    no_allergen_data(shop, "908", "Leipä", "Gluteenittomat sämpylät")
    no_allergen_data(shop, "909", "Coconut milk 2900ml")
    for pid, code in (("903", "AP"), ("904", "AN"), ("905", "AW"), ("907", "AW"), ("907", "AM"), ("908", "AW"),
                      ("909", "AM")):
        res = run([(pid, 1)], [("excluded_allergen", code)])
        assert res.status == "pending_approval" and codes(res) == ["ALLERGEN_DATA_MISSING"], pid  # held, not refused
    shop.products["906"] = product("906", "Peanut-style crunch", category="300", claims=(), contains=())
    shop.products["906"]["allergens"]["free_from"] = ["AP"]  # the label explicitly rules it out
    shop.quotes["906"] = quote("906")
    assert run([("906", 1)], [("excluded_allergen", "AP")]).status == "confirmed"


def test_name_refusal_survives_the_route_and_cannot_be_approved(shop):
    no_allergen_data(shop, "464534", "Katjang Peanuts 1 kg")
    body = post([("464534", 1)], dict(MANDATE, hard_rules=[{"kind": "excluded_allergen", "value": "AP"}])).json()
    assert body["status"] == "refused" and body["order_id"] is None  # nothing stored, nothing to approve


# --- FD-05: piece units are whole numbers
def test_half_a_carton_is_refused_with_a_rounding_fix(shop):
    res = run([("463335", 2.5)])
    assert res.status == "refused" and codes(res) == ["QTY_INVALID"]
    assert res.decision.reasons[0].suggested_fix == "Round to 3."
    assert post([("463335", 2.5)]).json()["status"] == "refused"
    assert run([("463335", 3)]).status == "confirmed"


def test_weight_units_may_be_fractional(shop):
    shop.products["463335"]["sales_unit"] = "KG"
    shop.quotes["463335"] = quote("463335", unit="KG")
    assert run([("463335", 2.5)]).status == "confirmed"


# --- QU-06: Stock sentinel and the per-line cap on every path
def test_stock_sentinel_is_not_real_stock():
    q = valio._merge({"productId": "x", "logisticModel": "Stock", "closingTime": None, "scheduleLines": [
        {"availableAmount": 9999999999.0, "salesUnit": "ST", "availableDate": REQ.isoformat()}]},
        {"productId": "x", "catalogPrice": {"value": 1.4}}, NOW)
    assert q["available_amount"] is None and not q["quantity_known"] and "quantity_unreported" in q["flags"]
    assert valio.to_contract_quote(q).availability == "available"  # Stock: orderable, amount just not reported


def test_unreported_stock_neither_asks_nor_counts_as_stock(shop):
    shop.quotes["463335"] = quote("463335", amount=9999999999.0)
    assert run([("463335", 10)]).status == "confirmed"
    shop.products["104"]["substitutes"] = ["463335"]
    res = run([("104", 1)])
    s = next(x for x in res.substitutes if x["product_id"] == "463335")
    assert s["available"] is None and "9,999,999,999" not in res.decision.alternatives[0].summary


def test_per_line_cap_holds_inside_the_gate(shop):
    res = run([("463335", 1_000_000)])  # what the agent path produced (QU-06)
    assert res.status == "refused" and codes(res)[0] == "QTY_INVALID"
    assert res.decision.reasons[0].facts["max_quantity"] == 100_000


# --- SU-02: substitutes keep what the product is, not only allergen safety
def test_substitute_that_drops_a_nutrition_claim_is_demoted_and_says_why(shop):
    shop.products["462775"]["claims"] = ["FREE_FROM_LACTOSE", "FREE_FROM_FAT"]   # fat-free lactose-free (51 left)
    shop.products["463335"]["claims"] = ["FREE_FROM_LACTOSE", "FREE_FROM_FAT"]   # same spec, dearer
    # 476240 (cheapest, "coffee milk") is lactose-free but not fat-free
    res = run([("462775", 100)])
    subs = {s["product_id"]: s for s in res.substitutes}
    assert subs["476240"]["tier"] == "good" and subs["476240"]["differs"] == ["not FREE_FROM_FAT"]
    assert "Differs: not FREE_FROM_FAT" in subs["476240"]["why_safe"]
    assert subs["463335"]["tier"] == "best" and subs["463335"]["differs"] == []
    fill = res.alternative_order["lines"][1]
    assert fill["product_id"] == "463335"  # the split is filled with the matching product, not the cheaper one


def test_no_split_when_only_differing_substitutes_exist(shop):
    shop.products["462775"]["claims"] = ["FREE_FROM_LACTOSE", "FREE_FROM_FAT"]
    assert run([("462775", 100)]).alternative_order is None
    shop.products["462775"]["labels"] = ["EU_ORGANIC_FARMING"]
    shop.products["462775"]["claims"] = ["FREE_FROM_LACTOSE"]
    assert all("not organic" in s["differs"] for s in run([("462775", 100)]).substitutes)


# --- AT-01 / AT-02: audit says what happened, and refused access leaves a trace
def test_audit_lines_carry_action_and_status(shop):
    oid = post([("463335", 1000)]).json()["order_id"]
    c.post(f"/api/orders/{oid}/approve", headers=AP)
    oid2 = post([("463335", 1000)]).json()["order_id"]
    c.post(f"/api/orders/{oid2}/reject", headers=AP)
    fd = [e["front_door"] for e in c.get("/api/audit", headers=AP).json()]
    assert fd[0] == {"action": "order", "status": "pending_approval", "signed_off_by": None, "mandate_version": "m1"}
    assert fd[1] == {"action": "approved", "status": "confirmed", "signed_off_by": "Chef Aino", "mandate_version": "m1"}
    assert fd[3] == {"action": "rejected", "status": "rejected", "signed_off_by": "Chef Aino", "mandate_version": "m1"}


def test_agent_entries_are_marked_as_the_agents_own_view(shop):
    oid = post([("463335", 1)]).json()["order_id"]
    entry = orders.AUDIT_FILE.read_text().splitlines()[0]
    import json
    raw = json.loads(entry)
    raw.pop("front_door")
    from trade_contracts import AuditEntry
    agent_entry = AuditEntry.model_validate(raw).model_copy(update={"actor": "buyer_agent"})  # contract-valid sans annotation
    orders._append_audit(agent_entry)
    assert c.get("/api/audit", headers=AP).json()[-1]["front_door"]["action"] == "agent_proposal"
    assert oid


def test_refused_access_is_audited_without_secrets(shop):
    oid = post([("463335", 1000)]).json()["order_id"]
    c.post(f"/api/orders/{oid}/approve", headers={"X-Approver-Key": "agent-chef"})  # agent key used to approve
    c.get("/api/audit", headers={"X-Approver-Key": "wrong-guess"})                   # unknown key
    c.post("/api/orders", headers=AG, json={"requested_date": REQ.isoformat(), "mandate": MANDATE,
                                            "lines": [{"product_id": "463335", "quantity": 1}]})
    c.get("/api/audit")  # no key at all: rate-limited, not audited
    events = [e for e in c.get("/api/admin/audit", headers=ADM).json() if e.get("kind") == "security_event"]
    assert [(e["event"], e["buyer_id"]) for e in events] == [
        ("key_used_outside_its_role", "chef"), ("invalid_key", None), ("client_sent_mandate", "chef")]
    assert events[0]["key_role"] == "agent" and events[0]["route"].endswith("/approve")
    text = orders.AUDIT_FILE.read_text()
    assert "agent-chef" not in text and "wrong-guess" not in text  # never the key itself
    mine = [e for e in c.get("/api/audit", headers=AP).json() if e.get("kind") == "security_event"]
    assert len(mine) == 2  # the buyer sees events about its own keys, not anonymous probes


def test_admin_can_filter_every_refusal_by_status(shop):
    post([("463038", 1)])  # cut-off passed: refused, but outcome ASK_HUMAN
    post([("100", 1)], dict(MANDATE, hard_rules=[{"kind": "excluded_allergen", "value": "AP"}]))  # DECLINE
    post([("463335", 1)])  # confirmed
    refused = c.get("/api/admin/audit", params={"status": "refused"}, headers=ADM).json()
    assert sorted(e["decision"]["outcome"] for e in refused) == ["ASK_HUMAN", "DECLINE"]
    assert len(c.get("/api/admin/audit", params={"outcome": "DECLINE"}, headers=ADM).json()) == 1


# --- HP-04: quotes carry integer cents
def test_quotes_carry_integer_cents(shop):
    q = quote("463335", price=1.4)
    assert q["unit_price_cents"] == 140 and q["price"] == 1.4
    assert quote("x", price=None)["unit_price_cents"] is None


def test_security_events_are_capped_per_minute(shop, monkeypatch):  # Codex whole-backend audit
    import json as _json
    monkeypatch.setattr(orders, "SECURITY_EVENTS_PER_MIN", 3)
    monkeypatch.setattr(orders, "_sec", {"window": 0.0, "count": 0, "suppressed": 0})
    for i in range(10):
        c.get("/api/audit", headers={"X-Approver-Key": f"junk-{i}"})
    lines = [_json.loads(x) for x in orders.AUDIT_FILE.read_text().splitlines()]
    assert len(lines) == 3  # the rest were counted, not written
    orders._sec["window"] = -1  # a new minute
    c.get("/api/audit", headers={"X-Approver-Key": "junk-x"})
    last = _json.loads(orders.AUDIT_FILE.read_text().splitlines()[-1])
    assert last["suppressed_before"] == 7
