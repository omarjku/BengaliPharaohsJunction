"""The chef's rules in plain language: compile (T09 compiler, Gemini faked) → confirm → stored → used at once."""
import pytest
from conftest import REQ
from fastapi.testclient import TestClient
from test_agent import ITEM, decisions, gemini, shop1  # noqa: F401 - pytest fixtures + helpers

from app import config, mandates, orders, rules
from app.main import app

c = TestClient(app, raise_server_exceptions=False)
APPR = {"X-Approver-Key": "appr-lk"}
TEXT = "Never anything with peanuts. Auto-approve up to €1,500 per order, €6,000 a week. Prefer Finnish."
GOOD = {"excluded_allergens": [{"name": "peanut", "scope_cue": "always"}],
        "auto_approve_limit": {"amount_eur": "1,500", "scope_cue": "none"}, "per_line_cap": None,
        "weekly_budget": {"amount_eur": "6,000", "scope_cue": "none"}, "blocklist_product_ids": [],
        "uncertainty_policy": None, "guidance": [], "open_questions": [], "expires_on": None}


@pytest.fixture
def lk(shop1, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "APPROVER_KEYS", config.APPROVER_KEYS + ",appr-lk=lapland-kitchen:Chef Aino")
    return shop1


def compiler_says(monkeypatch, out):
    monkeypatch.setattr(rules.RestLLM, "generate_structured", lambda self, prompt, schema, model: out)


def mandate(**kw):
    m = mandates.get("lapland-kitchen").model_dump(mode="json")
    return {**m, **kw}


def test_agent_key_can_never_change_rules(lk):
    for headers in ({"X-Agent-Key": "agent-lk"}, {}):
        assert c.post("/api/mandate/compile", json={"text": TEXT}, headers=headers).status_code == 401
        assert c.put("/api/mandate", json={"mandate": mandate()}, headers=headers).status_code == 401
    assert c.put("/api/mandate", json={"mandate": mandate(buyer_id="chef")}, headers=APPR).status_code == 403


def test_compile_proposes_and_saves_nothing(lk, monkeypatch):
    compiler_says(monkeypatch, GOOD)
    body = c.post("/api/mandate/compile", json={"text": TEXT}, headers=APPR).json()
    rules_ = {(r["kind"], r["value"]) for r in body["proposed_mandate"]["hard_rules"]}
    assert ("auto_approve_limit_cents", 150000) in rules_ and ("excluded_allergen", "peanut") in rules_
    assert body["proposed_mandate"]["weekly_budget_cents"] == 600000
    diff = {d["field"]: d for d in body["diff_from_current"]}
    # the seeded mandate had a 90% on-time floor; the compiled one doesn't → shown as a looser change to confirm
    assert diff["min_delivery_reliability"]["change"] == "looser" and diff["min_delivery_reliability"]["needs_confirmation"]
    assert diff["per_line_cap_cents"]["change"] == "tighter"  # not mentioned → back to the safe default
    assert any("net of VAT" in a for a in body["assumptions"])
    assert not mandates.STORE.exists()  # nothing saved


def test_ambiguous_rules_become_questions_not_guesses(lk, monkeypatch):
    # The model "guesses" EUR 9,000 that the chef never wrote: the compiler drops it and asks instead.
    compiler_says(monkeypatch, {**GOOD, "auto_approve_limit": {"amount_eur": "9000", "scope_cue": "none"},
                                "weekly_budget": None, "excluded_allergens": [],
                                "open_questions": [{"question": "What counts as 'cheap'?", "why": "No number given."}]})
    body = c.post("/api/mandate/compile", json={"text": "Keep it cheap, auto-approve a reasonable amount"},
                  headers=APPR).json()
    limits = [r["value"] for r in body["proposed_mandate"]["hard_rules"] if r["kind"] == "auto_approve_limit_cents"]
    assert limits == [50000]  # the guessed EUR 9,000 is gone; only the safe default stands
    qs = [q["question"] for q in body["open_questions"]]
    assert "What counts as 'cheap'?" in qs and any("auto-approve limit amount" in q for q in qs)
    r = c.put("/api/mandate", json={"mandate": body["proposed_mandate"]}, headers=APPR)
    assert r.status_code == 422  # can't save while questions are open


def test_big_loosening_needs_explicit_confirmation(lk):
    loose = mandate(hard_rules=[{"kind": "excluded_allergen", "value": "AP"},
                                {"kind": "auto_approve_limit_cents", "value": 2_000_000},  # 13x the EUR 1,500
                                {"kind": "min_delivery_reliability", "value": 0.9}])
    r = c.put("/api/mandate", json={"mandate": loose}, headers=APPR)
    assert r.status_code == 409 and r.json()["detail"]["changes"][0]["field"] == "auto_approve_limit_cents"
    no_peanut_rule = mandate(hard_rules=[{"kind": "auto_approve_limit_cents", "value": 150000},
                                         {"kind": "min_delivery_reliability", "value": 0.9}])
    assert c.put("/api/mandate", json={"mandate": no_peanut_rule}, headers=APPR).status_code == 409
    r = c.put("/api/mandate", json={"mandate": loose, "confirm_large_change": True}, headers=APPR)
    assert r.status_code == 200 and mandates.get("lapland-kitchen").id == r.json()["mandate"]["id"]


def test_saved_rules_are_audited_and_used_at_once(lk, monkeypatch):
    tight = mandate(hard_rules=[{"kind": "excluded_allergen", "value": "AP"},
                                {"kind": "auto_approve_limit_cents", "value": 1000},  # EUR 10
                                {"kind": "min_delivery_reliability", "value": 0.9}])
    r = c.put("/api/mandate", json={"mandate": tight}, headers=APPR)
    assert r.status_code == 200
    [entry] = orders.audit_log("lapland-kitchen", 10)
    assert entry["id"] == r.json()["audit_id"] and entry["actor"] == "human:Chef Aino:mandate"
    assert "EUR 1,500.00 → EUR 10.00" in entry["input"]["request"]["text"]
    assert entry["decision"]["reasons"][0]["facts"]["change"] == "tighter"
    assert c.get("/api/mandate", headers=APPR).json()["id"] == r.json()["mandate"]["id"]
    # the agent and the front door both apply it immediately: 10 L milk (EUR 14) is now over the limit
    gemini(monkeypatch, [dict(ITEM[0], amount=10)], ranked=["463335"])
    run = c.post("/api/agent/run", json={"text": "10 L lactose-free milk", "requested_date": REQ.isoformat()},
                 headers={"X-Agent-Key": "agent-lk"}).json()
    assert run["order"]["status"] == "pending_approval" and "SPEND_OVER_LIMIT" in [
        x["code"] for x in run["decision"]["reasons"]]
    door = c.post("/api/orders", json={"requested_date": REQ.isoformat(),
                                       "lines": [{"product_id": "463335", "quantity": 10}]},
                  headers={"X-Agent-Key": "agent-lk"}).json()
    assert door["status"] == "pending_approval"


def test_diff_directions():
    cur = mandates._MANDATES["lapland-kitchen"]
    new = cur.model_copy(update={"weekly_budget_cents": None, "per_line_cap_cents": 100000})
    d = {x["field"]: x for x in rules.diff(cur, new)}
    assert d["weekly_budget_cents"]["change"] == "looser" and d["weekly_budget_cents"]["needs_confirmation"]
    assert d["per_line_cap_cents"]["change"] == "tighter" and not d["per_line_cap_cents"]["needs_confirmation"]
    assert rules.diff(cur, cur) == []


def test_no_stated_limit_means_the_default_not_unlimited(lk, monkeypatch):
    compiler_says(monkeypatch, {**GOOD, "auto_approve_limit": None})
    body = c.post("/api/mandate/compile", json={"text": "Never anything with peanuts."}, headers=APPR).json()
    assert ("auto_approve_limit_cents", 50000) in {(r["kind"], r["value"]) for r in body["proposed_mandate"]["hard_rules"]}
    d = {x["field"]: x for x in body["diff_from_current"]}
    assert d["auto_approve_limit_cents"]["change"] == "tighter"  # EUR 1,500 → EUR 500, not "→ none"
    assert any("default EUR 500.00" in a for a in body["assumptions"])
    stripped = mandate(hard_rules=[{"kind": "excluded_allergen", "value": "AP"},
                                   {"kind": "min_delivery_reliability", "value": 0.9}])
    r = c.put("/api/mandate", json={"mandate": stripped}, headers=APPR)  # PUT without a limit: default added
    assert r.status_code == 200 and rules.gate._nums(mandates.get("lapland-kitchen"), rules.RuleKind.AUTO_APPROVE_LIMIT_CENTS) == [50000]
