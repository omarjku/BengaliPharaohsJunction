"""Product choice: the right product FAMILY is retrieved for unseen wordings (typos, Finnish inflections, English and
Finnish, abbreviations, perturbed catalogue names), the chef's own hard attributes (unsalted, organic, fat %) must be
evidenced by the chosen product or the line is not auto-approved, and substitutes are same-family and allergen-safe.

Retrieval cases run against the real slim catalogue when data/catalogue_slim.json exists (it is not in git) and skip
otherwise; the gating and substitution cases run on the offline shop (conftest.py)."""
import asyncio
import json
import random
import re
from pathlib import Path
from types import SimpleNamespace as L

import pytest
from conftest import NOW, REQ, product, quote
from trade_contracts import Mandate

from app import catalogue, facets, gate

SLIM = Path(__file__).resolve().parents[2] / "data" / "catalogue_slim.json"

# (chef's wording, regex the top-3 names must hit: the product FAMILY, not one product). Typos, Finnish slang and
# inflections, abbreviations, English and Finnish; none of these strings appear in the catalogue.
PHRASINGS = [
    ("french friees", r"fries|ranskalaiset"),
    ("bologense sauce", r"bolognese|bolognes"),
    ("mozzarela cheese", r"mozzarella"),
    ("cremme fraiche", r"cr[eè]me fra[iî]che|ranskankerma"),
    ("whiping cream", r"whipping|kuohukerma|cream"),
    ("greek yoghurt", r"yog|jogurt"),
    ("turkkilaist jugurttii", r"yog|jogurt"),
    ("kananmunii", r"egg|kananmun"),
    ("suolaamaton voita", r"butter|voi\b"),
    ("kuohukermaa", r"cream|kerma"),
    ("maitoa", r"milk|maito"),
    ("perunoita", r"potato|peruna"),
    ("tomatos", r"tomato|tomaat"),
    ("cucmber", r"cucumber|kurkku"),
    ("salmon filet", r"salmon|lohi"),
    ("sourcream", r"sour cream|smetana|kermaviili|cream"),
    ("rapseed oil", r"rapeseed|rypsi|oil"),
    ("wheet flour", r"wheat|vehn|flour"),
    ("kanafile", r"chicken|kana"),
    ("juustoo", r"cheese|juusto"),
]


@pytest.fixture(scope="module")
def real_catalogue():
    if not SLIM.exists():
        pytest.skip("data/catalogue_slim.json is not in git")
    products = {p["id"]: p for p in json.loads(SLIM.read_text(encoding="utf-8"))["products"]}
    old = catalogue._products
    catalogue._products = products
    yield products
    catalogue._products = old


def names(p):
    return " ".join(filter(None, [p["name_en"], p["name_fi"]])).lower()


@pytest.mark.parametrize("wording,family", PHRASINGS)
def test_unseen_wordings_reach_the_right_family_in_the_top_three(real_catalogue, wording, family):
    top = catalogue.search(wording, limit=3)
    assert top, f"nothing found for {wording!r}"
    assert any(re.search(family, names(p)) for p in top), [p["name_en"] for p in top]


def perturb(name: str, rng: random.Random) -> str:
    """A chef's rougher version of a catalogue name: no pack sizes/brand-ish digits, one transposition typo in the
    longest word, lower case."""
    words = [w for w in re.findall(r"[a-zäöå]{4,}", name.lower())]
    if not words:
        return ""
    longest = max(words, key=len)
    i = rng.randrange(1, len(longest) - 2)
    typo = longest[:i] + longest[i + 1] + longest[i] + longest[i + 2:]
    return " ".join(typo if w == longest else w for w in words[:3])


def test_perturbed_catalogue_names_find_their_own_family(real_catalogue):
    rng = random.Random(2026)
    pool = [p for p in sorted(real_catalogue.values(), key=lambda p: p["id"]) if p["name_en"] and p["category"]]
    sample = rng.sample(pool, 60)
    hit = total = 0
    for p in sample:
        query = perturb(p["name_en"], rng)
        if not query:
            continue
        total += 1
        mine = gate._kind_words(p)
        top = catalogue.search(query, limit=3)
        hit += any(mine & gate._kind_words(x) for x in top)
    assert total >= 40 and hit / total >= 0.85, (hit, total)


# --- hard attributes in the chef's words


def test_facets_read_english_and_finnish_attributes():
    assert facets.request_facets("2 kg unsalted butter")["concepts"] == ["unsalted"]
    assert facets.request_facets("pari kiloo suolatont voita")["concepts"] == ["unsalted"]
    assert facets.request_facets("luomu porkkanaa")["concepts"] == ["organic"]
    assert facets.request_facets("1,5 % milk")["percent"] == {1.5}
    assert facets.request_facets("salted butter")["concepts"] == ["salted"]
    assert facets.request_facets("a lot of milk") == {"concepts": [], "percent": set()}


def test_facet_check_needs_evidence_and_catches_the_opposite():
    unsalted = {"name_en": "Valio butter 500 g unsalted", "name_fi": "Valio voi 500 g suolaamaton", "brand": "Valio"}
    plain = {"name_en": "Valio butter 500 g", "name_fi": None, "brand": "Valio"}
    salted = {"name_en": "Arla butter salted 500 g", "name_fi": None, "brand": "Arla"}
    want = facets.request_facets("unsalted butter")
    assert facets.check(want, unsalted) == []
    assert [k for k, *_ in facets.check(want, plain)] == ["missing"]
    assert [k for k, *_ in facets.check(want, salted)] == ["conflict"]
    assert [k for k, *_ in facets.check(facets.request_facets("salted butter"), unsalted)] == ["conflict"]
    fat = {"name_en": "Valio milk 1,5 % 1 l"}
    assert facets.check(facets.request_facets("1.5 % milk"), fat) == []
    assert [k for k, *_ in facets.check(facets.request_facets("3 % milk"), fat)] == ["conflict"]
    assert facets.penalty(want, unsalted) < facets.penalty(want, plain) < facets.penalty(want, salted)


# --- end to end on the offline shop: a product that can't be shown to match the chef's words is not auto-approved
from test_agent import decisions, gemini, run, shop1  # noqa: E402,F401  (shared fixtures and fakes)

BUTTER = [{"query": "butter", "amount": 10, "unit": "L", "dietary": []}]


def _butter(shop, pid, name, price):
    shop.products[pid] = dict(product(pid, name, claims=(), contains=("AM",), category="10500"), name_fi=None,
                              base_unit="ST", units={"ST": 1.0, "KI": 10.0}, volume={"unit": "LTR", "value": 1.0},
                              net_weight=None)
    shop.quotes[pid] = quote(pid, price=price)


def test_unsalted_asked_for_the_evidenced_product_wins_even_when_dearer(shop1, monkeypatch):
    _butter(shop1, "b1", "Valio butter 500 g", 2.0)
    _butter(shop1, "b2", "Valio butter 500 g unsalted", 3.0)
    gemini(monkeypatch, BUTTER, ranked=["b1", "b2"])
    body = run("10 L unsalted butter")
    assert [ln["product"]["id"] for ln in body["lines"] if ln["chosen"]] == ["b2"]
    assert body["decision"]["outcome"] == "AUTO"


def test_unsalted_asked_but_no_product_says_so_is_not_auto_approved(shop1, monkeypatch):
    _butter(shop1, "b1", "Valio butter 500 g", 2.0)
    gemini(monkeypatch, BUTTER, ranked=["b1"])
    body = run("10 L unsalted butter")
    assert body["order"] is None and body["decision"]["outcome"] == "ASK_HUMAN"
    assert any("unsalted" in r["message"] and "can't confirm" in r["message"] for r in body["decision"]["reasons"])


def test_a_product_that_says_the_opposite_is_not_auto_approved(shop1, monkeypatch):
    _butter(shop1, "b1", "Arla butter salted 500 g", 2.0)
    gemini(monkeypatch, BUTTER, ranked=["b1"])
    body = run("10 L unsalted butter")
    assert body["order"] is None and body["decision"]["outcome"] == "ASK_HUMAN"


def test_fat_percent_mismatch_is_not_auto_approved(shop1, monkeypatch):
    _butter(shop1, "m1", "Valio milk 1,5 % 1 l", 1.0)
    gemini(monkeypatch, [{"query": "milk", "amount": 10, "unit": "L", "dietary": []}], ranked=["m1"])
    assert run("10 L milk 3 %")["order"] is None
    assert run("10 L milk 1,5 %")["decision"]["outcome"] == "AUTO"


def test_no_attribute_written_changes_nothing(shop1, monkeypatch):
    _butter(shop1, "b1", "Valio butter 500 g", 2.0)
    gemini(monkeypatch, BUTTER, ranked=["b1"])
    assert run("10 L butter")["decision"]["outcome"] == "AUTO"


# --- substitutes: same family, allergen-safe, orderable


def _check(lines, rules=()):
    m = Mandate(id="m1", buyer_id="chef", per_line_cap_cents=10**9, hard_rules=[{"kind": k, "value": v} for k, v in rules])
    return asyncio.run(gate.check([L(product_id=p, quantity=q) for p, q in lines], REQ, m, "r", now=NOW))


def _add(shop, pid, name, category="777", contains=(), amount=500.0, price=2.0, rel=1.0, subs=()):
    shop.products[pid] = product(pid, name, category=category, claims=(), contains=contains, subs=subs, rel=rel)
    shop.products[pid]["allergens"]["free_from"] = ["AP"]
    shop.quotes[pid] = quote(pid, amount=amount, price=price)


@pytest.mark.parametrize("old,same,other", [
    ("Valio butter 500 g", "Arla butter 500 g", "Felix horseradish 200 g"),
    ("Apetit Onion Cubes frozen 200g", "Iglu Onion cube 2,5 kg frozen", "Felix horseradish 200g"),
    ("Valio whipping cream 1 l", "Arla whipping cream 1 l", "Valio sour cream 1 l"),
    ("Kieku Egg M90 5200g", "Danaeg Egg L 5000g", "Egg noodles 500g"),
    ("Fazer rye bread 500 g", "Vaasan rye bread 600 g", "Rice cakes 100 g"),
    ("Valio plain yoghurt 1 kg", "Arla plain yoghurt 1 kg", "Plain flour 1 kg"),
])
def test_substitutes_are_same_family_orderable_and_say_why(shop, old, same, other):
    _add(shop, "o", old, amount=0.0)  # sold out: needs a substitute
    for n in range(20):  # a crowded category: the old "first 8 of the category" pool never reached the right kind
        _add(shop, f"f{n:02d}", f"AAA Filler{n} unrelated item {n}")
    _add(shop, "s", same, price=3.0)
    _add(shop, "x", other, price=1.0)
    res = _check([("o", 10)])
    subs = {s["product_id"]: s for s in res.substitutes}
    assert "s" in subs and subs["s"]["why_safe"] and subs["s"]["replaces"] == "o"
    assert all(gate.same_kind(shop.products["o"], shop.products[i]) for i in subs)
    assert shop.products["s"]["category"] == shop.products["o"]["category"]
    assert subs["s"]["tier"] in ("best", "better", "good")


def test_substitutes_never_add_an_excluded_allergen_or_an_unreliable_slot(shop):
    _add(shop, "o", "Valio butter 500 g", amount=0.0)
    _add(shop, "peanut", "Peanut butter 500 g", contains=("AP",))
    _add(shop, "ok", "Arla butter 500 g", price=3.0)
    res = _check([("o", 10)], rules=[("excluded_allergen", "AP")])
    subs = {s["product_id"] for s in res.substitutes}
    assert "ok" in subs and "peanut" not in subs



def test_a_model_pinned_product_must_still_be_what_the_chef_asked_for(shop1, monkeypatch, decisions):
    """Codex finding: propose_order {product_id: coffee milk} for "lactose-free milk" used to pin it unchecked."""
    from app import agent
    pinned = {"query": "milk", "amount": 10, "unit": "L", "dietary": []}
    shop1.products["coffee"] = dict(shop1.products["463335"], id="coffee", name_en="Valio coffee milk 1 l")
    shop1.quotes["coffee"] = dict(shop1.quotes["463335"], product_id="coffee")
    decisions["scores"] = {"meets": 0.40}  # Decisions: the pinned coffee milk is not the milk the chef asked for
    item = agent._item("milk", 10, "L", [])
    item["product_id"] = "coffee"
    ids, _ = asyncio.run(agent.candidates("10 L milk", item, set(), {}, [], [], "10 L milk"))
    assert ids == []  # not honoured as an override: the normal search ran and Decisions rejected every hit
    decisions["scores"] = {"meets": 0.95}
    item = agent._item("milk", 10, "L", [])
    item["product_id"] = "coffee"
    assert asyncio.run(agent.candidates("10 L milk", item, set(), {}, [], [], "10 L milk"))[0] == ["coffee"]
