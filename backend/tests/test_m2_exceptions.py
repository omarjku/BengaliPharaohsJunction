"""M2 (J4): partial-stock split and allergen-safe, ranked substitution. Offline (conftest.py)."""
import asyncio
from types import SimpleNamespace as L

from conftest import NOW, REQ, product, quote, store_mandate
from fastapi.testclient import TestClient
from trade_contracts import Mandate

from app import gate
from app.main import app

c = TestClient(app, raise_server_exceptions=False)


def run(lines, rules=(), **kw):
    m = Mandate(id="m1", buyer_id="chef", per_line_cap_cents=10**9,
                hard_rules=[{"kind": k, "value": v} for k, v in rules], **kw)
    return asyncio.run(gate.check([L(product_id=p, quantity=q) for p, q in lines], REQ, m, "r", now=NOW))


# --- partial stock split
def test_short_line_gets_a_split_proposal_never_auto(shop):
    res = run([("462775", 100)])  # only 51 in stock
    assert res.status == "refused" and res.decision.outcome == "ASK_HUMAN"
    alt = res.alternative_order
    assert [(x["product_id"], x["quantity"]) for x in alt["lines"]] == [("462775", 51.0), ("476240", 49.0)]
    assert alt["lines"][1]["replaces"] == "462775" and alt["total_cents"] == 51 * 257 + 49 * 120
    assert res.decision.reasons[0].code == "STOCK_PARTIAL" and res.decision.reasons[0].suggested_fix == alt["summary"]


def test_split_parts_each_pass_the_gate(shop):
    shop.quotes["476240"] = quote("476240", amount=30.0, price=1.2)  # best substitute can't cover the 49 either
    shop.products["102"]["category"] = "999"  # leave 463335 as the next same-category option
    alt = run([("462775", 100)]).alternative_order  # 463335 has 5000
    assert alt["lines"][1]["product_id"] == "463335" and alt["lines"][1]["quantity"] == 49.0


def test_split_respects_lot_sizes(shop):
    shop.products["462775"]["lot_size"] = 10.0  # 51 in stock → only 50 orderable
    shop.products["476240"]["lot_size"] = 4.0   # rest 50 → rounded up to 52
    alt = run([("462775", 100)]).alternative_order
    assert [x["quantity"] for x in alt["lines"]] == [50.0, 52.0]


def test_no_split_across_units_or_when_another_line_is_refused_for_something_else(shop):
    shop.quotes["476240"] = quote("476240", price=1.2, unit="KI")
    shop.quotes["463335"] = quote("463335", price=1.4, unit="KI")
    for pid in ("463038", "102", "105", "104", "106"):
        shop.products[pid]["category"] = "999"  # leave no same-unit substitute
    assert run([("462775", 100)]).alternative_order is None
    shop.quotes["476240"] = quote("476240", price=1.2)
    assert run([("462775", 100)]).alternative_order is not None
    assert run([("462775", 100), ("104", 1)]).alternative_order is None  # 104 is out of stock, not just short


def test_split_is_exposed_by_the_front_door_and_reorderable(shop):
    store_mandate({"id": "m1", "buyer_id": "chef", "per_line_cap_cents": 10**9})
    h = {"X-Agent-Key": "agent-chef"}
    body = c.post("/api/orders", headers=h, json={"requested_date": REQ.isoformat(),
                                                  "lines": [{"product_id": "462775", "quantity": 100}]}).json()
    assert body["status"] == "refused" and body["alternative_order"]["lines"][0]["quantity"] == 51.0
    assert body["substitutes"][0]["tier"] == "best"
    again = c.post("/api/orders", headers=h, json={"requested_date": REQ.isoformat(),
                                                   "lines": body["alternative_order"]["order_lines"]})  # verbatim
    assert again.json()["status"] == "confirmed"  # the human chose the split; the door re-checks it


# --- allergen-safe substitution
def peanut_shop(shop):
    shop.products["110"] = product("110", "Sold-out cookies", category="200", claims=(), contains=("AE",),
                                   subs=("101", "111", "112", "113"))
    shop.products["111"] = product("111", "Oat cookies", category="200", claims=(), contains=("AE",), rel=0.95)
    shop.products["112"] = product("112", "Finnish oat cookies", category="200", claims=(), contains=("AE",), rel=0.95)
    shop.products["112"]["origin"] = "fi"
    shop.products["113"] = product("113", "Cheap less reliable cookies", category="200", claims=(), contains=("AE",), rel=0.8)  # exactly the 80% default floor: still allowed
    shop.quotes.update({"110": quote("110", amount=0.0), "111": quote("111", price=2.0),
                        "112": quote("112", price=2.1), "113": quote("113", price=1.9)})


def test_peanut_free_mandate_skips_the_may_contain_substitute(shop):
    peanut_shop(shop)  # 101 "Choc bar" is the listed first substitute but MAY_CONTAIN peanuts
    res = run([("110", 5)], [("excluded_allergen", "peanut")])
    subs = {s["product_id"]: s for s in res.substitutes}
    assert "101" not in subs and "100" not in subs  # contains / may contain peanuts: never offered
    skipped = {ro.product_id: [r.code.value for r in ro.reasons] for ro in res.rejected_options}
    assert skipped["101"] == ["ALLERGEN_MAY_CONTAIN", "DATA_MISSING"]
    assert all("neither containing nor 'may contain' peanuts" in s["why_safe"] for s in res.substitutes)


def test_substitutes_ranked_best_better_good_by_price_reliability_origin(shop):
    peanut_shop(shop)
    res = run([("110", 5)], [("excluded_allergen", "AP")])
    ranked = [(s["tier"], s["product_id"]) for s in res.substitutes]
    # 112 is 5% dearer than 111 but Finnish; 113 is cheapest but least reliable (80%)
    assert ranked == [("best", "112"), ("better", "111"), ("good", "113")]
    assert [a.product_id for a in res.decision.alternatives] == ["112", "111", "113"]
    assert res.decision.alternatives[0].summary.startswith("BEST instead of 110")


def test_substitutes_keep_required_and_dietary_claims_and_category(shop):
    shop.products["463335"]["substitutes"] = ["100", "476240"]  # 100: other category, no lactose-free claim
    shop.quotes["463335"] = quote("463335", amount=0.0)
    res = run([("463335", 1)])
    assert "100" not in {s["product_id"] for s in res.substitutes}
    assert "keeps FREE_FROM_LACTOSE" in res.substitutes[0]["why_safe"]


# --- Codex review #4 follow-ups
def test_substitute_needs_an_allergen_declaration_covering_the_excluded_ones(shop):
    peanut_shop(shop)
    for pid in ("111", "112"):  # only a free-from list, and not for peanuts: unknown, not safe
        shop.products[pid]["allergens"] = {"contains": [], "may_contain": [], "free_from": ["AM"]}
    shop.products["113"]["allergens"] = {"contains": [], "may_contain": [], "free_from": ["AP"]}  # explicitly free
    for policy in ("ask", "approve"):  # "approve unknowns" governs the order, never what we offer instead
        res = run([("110", 5)], [("excluded_allergen", "AP")], uncertainty_policy=policy)
        assert [s["product_id"] for s in res.substitutes] == ["113"]


def test_unknown_category_is_not_the_same_category(shop):
    shop.products["104"]["category"] = None  # out of stock, unknown category
    shop.products["104"]["substitutes"] = ["476240"]
    shop.products["476240"]["category"] = None
    assert run([("104", 1)]).substitutes == []


def test_split_units_compared_after_resolving_the_catalogue_unit(shop):
    shop.quotes["462775"]["sales_unit"] = None   # Valio silent; catalogue says ST
    for pid in ("476240", "463335", "102", "106"):
        shop.quotes[pid]["sales_unit"] = None
        shop.products[pid]["sales_unit"] = "KI"  # substitutes are sold per case
    assert run([("462775", 100)]).alternative_order is None


def test_zero_price_substitute_is_not_offered(shop):
    shop.quotes["104"] = quote("104", amount=0.0)
    shop.products["104"]["substitutes"] = ["476240"]
    shop.quotes["476240"] = quote("476240", price=0.0)
    for pid in ("463335", "463038", "462775", "102", "105", "106"):
        shop.products[pid]["category"] = "999"  # 476240 is the only candidate left
    res = run([("104", 1)])
    assert res.substitutes == [] and "476240" in {ro.product_id for ro in res.rejected_options}


def test_alternatives_reject_cross_food_types_and_profile_avoided_allergens(shop):
    shop.products["102"].update(name_en="Butter block", category="butter", substitutes=["peanut-butter", "ham"])
    shop.products["peanut-butter"] = product("peanut-butter", "Peanut butter", category="butter", claims=(), contains=("AP",))
    shop.products["ham"] = product("ham", "Ham", category="butter", claims=(), contains=("AM",))
    shop.quotes["peanut-butter"] = quote("peanut-butter")
    shop.quotes["ham"] = quote("ham")
    mandate = Mandate(id="m1", buyer_id="chef", per_line_cap_cents=10**9)
    alternatives = asyncio.run(gate._alternatives(["102"], set(), REQ, mandate, {"AM"}, NOW))
    assert alternatives[2] == []


def test_split_that_breaks_route_limits_is_not_proposed(shop):
    shop.products["462775"]["lot_size"] = 0.01
    shop.products["476240"]["lot_size"] = 3.0
    shop.quotes["462775"] = quote("462775", amount=0.01, price=2.57)
    for pid in ("463335", "102"):
        shop.products[pid]["category"] = "999"
    shop.quotes["476240"] = quote("476240", amount=200000.0, price=1.2)
    assert run([("462775", 100000)]).alternative_order is None  # 0.01 + 100002 > 100000 per line
