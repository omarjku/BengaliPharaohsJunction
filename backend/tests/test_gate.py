"""Front-door gate: one test per hard check, on the offline shop fixture (conftest.py)."""
import asyncio
from datetime import timedelta
from types import SimpleNamespace as L

from conftest import NOW, REQ, quote
from trade_contracts import Mandate

from app import gate


def mandate(**kw):
    rules = kw.pop("rules", [])
    return Mandate(id="m1", buyer_id="chef", hard_rules=[{"kind": k, "value": v} for k, v in rules], **kw)


def run(lines, m=None, **kw):
    lines = [L(product_id=p, quantity=q) for p, q in lines]
    return asyncio.run(gate.check(lines, REQ, m or mandate(per_line_cap_cents=10**9), "req-1", now=NOW, **kw))


def codes(res, pid=None):
    return [r.code.value for r in res.decision.reasons if pid is None or r.product_id == pid]


def test_happy_path_is_auto_and_confirmed(shop):
    res = run([("463335", 10)])
    assert res.status == "confirmed" and res.decision.outcome == "AUTO" and res.decision.reasons == []
    assert res.total_cents == 1400 and res.lines[0]["unit_price_cents"] == 140 and res.lines[0]["unit"] == "ST"
    assert res.quotes[0].product_name == "Eila milk 1 l" and res.rejected_options == []


def test_spend_over_limit_needs_approval_not_refusal(shop):
    m = mandate(rules=[("auto_approve_limit_cents", 100000)], per_line_cap_cents=10**9)
    res = run([("463335", 1000)], m)
    assert res.status == "pending_approval" and res.decision.outcome == "ASK_HUMAN"
    assert codes(res) == ["SPEND_OVER_LIMIT"] and res.total_cents == 140000
    assert res.decision.reasons[0].facts == {"total_cents": 140000, "limit_cents": 100000}


def test_line_cap_and_weekly_budget(shop):
    res = run([("463335", 1000)], mandate(weekly_budget_cents=150000), spent_7d_cents=20000)
    assert res.status == "pending_approval" and set(codes(res)) == {"LINE_OVER_CAP", "WEEKLY_BUDGET_EXCEEDED"}


def test_terminal_cutoff_passed_and_unknown_qty_is_refused_with_alternatives(shop):
    res = run([("463038", 1)])
    assert res.status == "refused" and res.decision.outcome == "ASK_HUMAN"  # contract: only HARD_CODES may DECLINE
    assert set(codes(res)) == {"CUTOFF_PASSED", "QTY_UNKNOWN"}
    assert res.rejected_options[0].product_id == "463038"
    alts = [a.product_id for a in res.decision.alternatives]
    assert alts[0] == "476240" and "463038" not in alts and all("instead of 463038" in a.summary for a in res.decision.alternatives)
    rejected_alts = {ro.product_id for ro in res.rejected_options[1:]}
    assert {"104", "105"} <= rejected_alts  # candidates that failed their own checks are logged, not offered


def test_cutoff_rechecked_against_clock_even_if_quote_was_cached(shop):
    shop.quotes["463335"] = quote("463335", cutoff=(NOW - timedelta(seconds=1)).isoformat())
    shop.quotes["463335"]["flags"] = []  # as if cached before the cut-off passed
    assert codes(run([("463335", 1)])) == ["CUTOFF_PASSED"]


def test_partial_stock_suggests_the_available_amount(shop):
    res = run([("462775", 100)])
    assert res.status == "refused" and codes(res) == ["STOCK_PARTIAL"]
    r = res.decision.reasons[0]
    assert r.facts == {"available": 51.0, "requested": 100} and "51 ST of Arla milk 1 l + 49 ST" in r.suggested_fix


def test_unknown_product_is_declined(shop):
    res = run([("999999999", 1)])
    assert res.status == "refused" and res.decision.outcome == "DECLINE" and codes(res) == ["UNKNOWN_PRODUCT"]


def test_out_of_stock_undeliverable_sales_block(shop):
    shop.quotes["106"]["flags"].append("sales_block")
    res = run([("104", 1), ("105", 1), ("106", 1)])
    assert res.status == "refused"
    assert codes(res, "104") == ["STOCK_NONE"] and codes(res, "105") == ["UNDELIVERABLE"]
    assert codes(res, "106") == ["UNDELIVERABLE"] and res.decision.reasons[-1].facts == {"sales_block": True}


def test_lot_size_multiple(shop):
    assert codes(run([("102", 4)])) == []
    res = run([("102", 3)])
    assert res.decision.outcome == "DECLINE" and codes(res) == ["QTY_INVALID"]


def test_blocklist(shop):
    res = run([("463335", 1)], mandate(blocklist=["463335"]))
    assert res.decision.outcome == "DECLINE" and codes(res) == ["BLOCKLISTED"]


def test_excluded_allergen_by_name_or_code(shop):
    for value in ("peanut", "AP", "peanuts"):
        res = run([("100", 1), ("101", 1)], mandate(rules=[("excluded_allergen", value)]))
        assert codes(res, "100") == ["ALLERGEN_CONTAINS"] and codes(res, "101") == ["ALLERGEN_MAY_CONTAIN"]
        assert res.decision.outcome == "DECLINE" and res.status == "refused"


def test_allergen_rule_without_data_or_unmappable_value_asks(shop):
    res = run([("103", 1)], mandate(rules=[("excluded_allergen", "AP"), ("excluded_allergen", "kryptonite")]))
    assert set(codes(res)) == {"ALLERGEN_DATA_MISSING", "MANDATE_INVALID"} and res.status == "pending_approval"


def test_unrelated_free_from_does_not_verify_an_excluded_allergen(shop):
    shop.products["103"]["allergens"]["free_from"] = ["AM"]
    res = run([("103", 1)], mandate(rules=[("excluded_allergen", "AP")]))
    assert res.status == "pending_approval" and codes(res) == ["ALLERGEN_DATA_MISSING"]
    assert res.decision.reasons[0].message == "Mystery item has no allergen data for peanuts, so your rule can't be verified."


def test_nonempty_contains_list_is_a_complete_declaration_for_other_excluded_allergen(shop):
    shop.products["103"]["allergens"]["contains"] = ["AM"]
    res = run([("103", 1)], mandate(rules=[("excluded_allergen", "AP")]))
    assert res.status == "confirmed" and codes(res) == []


def test_free_from_excluded_allergen_passes(shop):
    shop.products["103"]["allergens"]["free_from"] = ["AP"]
    res = run([("103", 1)], mandate(rules=[("excluded_allergen", "AP")]))
    assert res.status == "confirmed" and codes(res) == []


def test_dansukker_caster_sugar_free_from_peanuts_is_not_missing_data(shop):
    shop.products["460325"] = dict(shop.products["103"], id="460325", name_en="Dansukker Caster Sugar 1kg",
                                     allergens={"contains": [], "may_contain": [], "free_from": ["AP"], "undeclared": []})
    shop.quotes["460325"] = quote("460325")
    res = run([("460325", 1)], mandate(rules=[("excluded_allergen", "AP")]))
    assert res.status == "confirmed" and "ALLERGEN_DATA_MISSING" not in codes(res)


def test_breyers_undeclared_peanuts_never_passes_a_peanut_ban(shop):
    shop.products["468099"] = dict(shop.products["103"], id="468099", name_en="Breyers Cookies & Cream",
                                     allergens={"contains": ["AM", "AE", "AW"], "may_contain": [], "free_from": [],
                                                "undeclared": ["AP", "AN"]})
    shop.quotes["468099"] = quote("468099")
    res = run([("468099", 1)], mandate(rules=[("excluded_allergen", "AP")]))
    assert res.status == "pending_approval" and codes(res) == ["ALLERGEN_DATA_MISSING"]


def test_product_name_still_overrides_inconsistent_free_from_declaration(shop):
    shop.products["460325"] = dict(shop.products["103"], id="460325", name_en="Peanut butter 1kg",
                                     allergens={"contains": [], "may_contain": [], "free_from": ["AP"], "undeclared": []})
    shop.quotes["460325"] = quote("460325")
    res = run([("460325", 1)], mandate(rules=[("excluded_allergen", "AP")]))
    assert res.status == "refused" and codes(res) == ["ALLERGEN_CONTAINS"]


def test_alternative_with_undeclared_banned_allergen_is_not_offered(shop):
    shop.products["source"] = dict(shop.products["103"], id="source", name_en="Peanut snack",
                                    allergens={"contains": ["AM"], "may_contain": [], "free_from": [], "undeclared": []},
                                    substitutes=["candidate"])
    shop.products["candidate"] = dict(shop.products["103"], id="candidate", name_en="Peanut snack alternative",
                                       allergens={"contains": ["AM"], "may_contain": [], "free_from": [], "undeclared": ["AP"]})
    shop.quotes["source"] = quote("source")
    shop.quotes["candidate"] = quote("candidate")
    res = run([("source", 1)], mandate(rules=[("excluded_allergen", "AP")]))
    assert all(a.product_id != "candidate" for a in res.decision.alternatives)


def test_uncertainty_policy_decline_and_approve(shop):
    shop.quotes["463038"] = quote("463038", "Terminal", 999999.0, price=31.31, unit="KI")  # cut-off still open
    assert run([("463038", 1)]).status == "pending_approval"
    res = run([("463038", 1)], mandate(uncertainty_policy="decline"))
    assert codes(res) == ["POLICY_DECLINE_UNKNOWN"] and res.decision.reasons[0].facts["unknown"] == "QTY_UNKNOWN"
    res = run([("463038", 1)], mandate(uncertainty_policy="approve"))
    assert res.status == "confirmed" and res.decision.reasons[0].severity == "INFO"


def test_reliability_rule(shop):
    m = mandate(rules=[("min_delivery_reliability", 0.9)])
    assert codes(run([("106", 1)], m)) == ["LOW_RELIABILITY"]


def test_price_missing_and_price_changed(shop):
    shop.quotes["102"] = quote("102", price=None)
    assert run([("102", 2)]).status == "refused"
    res = run([("463335", 1)], approved_prices={"463335": 130})
    assert codes(res) == ["PRICE_CHANGED"] and res.status == "pending_approval"


def test_deposit_note_is_carried_on_order_line(shop):
    shop.products["463335"]["deposits"] = [{"material": "4", "unit": "ST", "quantity": 1}]
    res = run([("463335", 1)])
    assert res.lines[0]["deposit"] == "returnable packaging deposit charged by Valio; not priced by the mock API"


def test_mandate_expired(shop):
    res = run([("463335", 1)], mandate(expires_at=NOW - timedelta(hours=1)))
    assert codes(res) == ["MANDATE_EXPIRED"] and res.status == "pending_approval"


def test_reasons_sorted_and_decision_round_trips(shop):
    res = run([("463335", 1000), ("100", 1)], mandate(rules=[("excluded_allergen", "AP"),
                                                           ("auto_approve_limit_cents", 100)]))
    sev = [r.severity.value for r in res.decision.reasons]
    assert sev[0] == "DECLINE" and sev == sorted(sev, key=["DECLINE", "ASK_HUMAN", "INFO"].index)
    assert type(res.decision).model_validate_json(res.decision.model_dump_json()) == res.decision
