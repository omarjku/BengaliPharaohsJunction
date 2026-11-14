"""Blackbox test 2026-11-14 #6 / #9: a substitute that changes what the product IS is never "good", and a refused
(undeliverable) pick gets a deliverable same-kind alternative. Real catalogue names; offline (conftest.py)."""
import asyncio
from types import SimpleNamespace as L

from conftest import NOW, REQ, product, quote
from trade_contracts import Mandate

from app import gate


def run(lines, rules=()):
    m = Mandate(id="m1", buyer_id="chef", per_line_cap_cents=10**9, hard_rules=[{"kind": k, "value": v} for k, v in rules])
    return asyncio.run(gate.check([L(product_id=p, quantity=q) for p, q in lines], REQ, m, "r", now=NOW))


def add(shop, pid, name, category, name_fi=None, subs=(), contains=(), amount=500.0, price=2.0, brand=None):
    shop.products[pid] = product(pid, name, category=category, claims=(), contains=contains, subs=subs)
    shop.products[pid].update(name_fi=name_fi, brand=brand)
    shop.products[pid]["allergens"]["free_from"] = ["AP"]  # allergen data present, so only the kind decides
    shop.quotes[pid] = quote(pid, amount=amount, price=price)


def test_same_kind_by_name_words_valio_list_and_never_by_guess():
    onion = {"id": "461339", "name_en": "Apetit Kotimainen Onion Cubes frozen 200g", "brand": "Apetit", "substitutes": []}
    assert gate.same_kind(onion, {"id": "465097", "name_en": "Suomen Iglu Oy Onion cube 6*6 mm 2,5 kg frozen"})
    assert not gate.same_kind(onion, {"id": "461229", "name_en": "Felix horseradish 200g", "brand": "Felix"})
    pb = {"id": "464315", "name_en": "PCD 500G PEANUT BUTTER", "substitutes": []}
    assert not gate.same_kind(pb, {"id": "463679", "name_en": "Nutella Hazelnut spread with cacao 350g"})
    rolls = {"id": "468902", "name_en": "Fazer Gluten-Free Oat and Carrot Bread Roll 16 x 70g, single-packed frozen "
             "fully baked", "brand": "Fazer", "substitutes": []}
    assert not gate.same_kind(rolls, {"id": "462456", "name_en": "Fazer Vuoksen Small Rice Pasty 100 x 50g, raw frozen",
                                      "brand": "Fazer"})
    assert gate.same_kind(rolls, {"id": "468979", "name_en": "8 x Fazer Gluten-Free Cheese Bread Roll 3pcs 215g",
                                  "brand": "Fazer"})
    assert gate.same_kind({**pb, "substitutes": ["463679"]}, {"id": "463679", "name_en": "Nutella"})  # Valio says so
    assert gate.same_kind({"id": "1", "name_en": "Sipulikuutiot", "name_fi": "sipuli kuutio"},
                          {"id": "2", "name_en": "Diced", "name_fi": "Sipuli 6 mm"})  # Finnish names count too


def test_horseradish_for_onion_is_only_an_alternative_and_says_so(shop):
    add(shop, "461339", "Apetit Kotimainen Onion Cubes frozen 200g", "41731", subs=("465097",), amount=0.0,
        brand="Apetit")
    add(shop, "461229", "Felix horseradish 200g", "41731", price=1.0, brand="Felix")  # cheapest, wrong kind
    add(shop, "465097", "Suomen Iglu Oy Onion cube 6*6 mm 2,5 kg frozen", "41731", price=9.0)
    res = run([("461339", 10)])
    subs = {s["product_id"]: s for s in res.substitutes}
    assert subs["465097"]["tier"] == "best"  # dearer, but an onion
    assert "461229" not in subs
    rejected = next(ro for ro in res.rejected_options if ro.product_id == "461229")
    assert any("not a similar kind of product" in reason.message for reason in rejected.reasons)
    assert [a.product_id for a in res.decision.alternatives] == ["465097"]


def test_a_different_kind_never_fills_a_split(shop):
    add(shop, "500", "Basmati rice 5 kg", "777", amount=10.0)  # short: 10 of 30 (the noodles come from search)
    add(shop, "501", "Jasmine noodles 5 kg", "777", amount=5000.0)            # same category, not rice
    res = run([("500", 30)])
    assert res.alternative_order is None
    assert res.substitutes == []
    rejected = next(ro for ro in res.rejected_options if ro.product_id == "501")
    assert any("not a similar kind of product" in reason.message for reason in rejected.reasons)


def test_undeliverable_pick_gets_a_deliverable_same_kind_alternative_and_why(shop):
    # Blackbox #6: an undeliverable basmati was chosen although orderable ones existed. The agent ranks deliverable
    # candidates first; at the door, the refused line now always points to the deliverable rice, not something else.
    add(shop, "600", "Tilda Basmati rice 5 kg", "778", subs=("601",))
    shop.quotes["600"] = quote("600", model=None)                   # no delivery schedule
    add(shop, "601", "Risella Basmati rice 5 kg", "778", price=12.0)  # deliverable rice
    add(shop, "602", "Crushed tomatoes 400 g", "778", price=1.0)      # cheaper, but not rice at all
    res = run([("600", 4)])
    assert res.status == "refused" and "UNDELIVERABLE" in [r.code.value for r in res.decision.reasons]
    best = res.decision.alternatives[0]
    assert best.product_id == "601" and best.summary.startswith("BEST") and f"Orderable for {REQ}" in best.summary
