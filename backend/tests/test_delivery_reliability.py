"""Delivery reliability: below the buyer's on-time floor (their rule, else the 80% default) an order is ASK_HUMAN,
never AUTO, with a plain reason and, when one exists, a more reliable same-kind alternative.

The products are picked from Valio's real catalogue + delivery-reliability data (data/catalogue_slim.json, not in git:
the module skips without it), by rank and spacing, never by name. Valio itself is faked: every product quotes as in
stock at a normal price, so the ONLY thing that can hold an order is what the gate thinks of the supplier."""
import asyncio
import json
from types import SimpleNamespace as L

import pytest
from conftest import NOW, REQ, quote
from trade_contracts import Mandate

from app import catalogue, gate, valio

pytestmark = pytest.mark.skipif(not catalogue.SLIM.exists(), reason="needs data/catalogue_slim.json (Valio data, not in git)")


@pytest.fixture
def real(monkeypatch):
    slim = json.loads(catalogue.SLIM.read_text(encoding="utf-8"))
    products = {p["id"]: p for p in (slim["products"] if isinstance(slim, dict) else slim)}

    async def get_quotes(ids, requested_date, customer="123", fresh=False):
        return [quote(i, unit=(products.get(i) or {}).get("sales_unit") or "ST") for i in ids]

    monkeypatch.setattr(catalogue, "_products", products)
    monkeypatch.setattr(valio, "get_quotes", get_quotes)
    return products


def mandate(floor=None):
    rules = [{"kind": "min_delivery_reliability", "value": floor}] if floor is not None else []
    return Mandate(id="m1", buyer_id="chef", hard_rules=rules, per_line_cap_cents=10**9)


def order(pid, m):
    """The gate's verdict for one unit-lot of `pid` (the lot size, so the quantity itself is never the problem)."""
    lot = catalogue.get(pid).get("lot_size")
    return asyncio.run(gate.check([L(product_id=pid, quantity=lot if lot and lot >= 1 else 1)], REQ, m, "r1", now=NOW))


def spread(ids, n):
    """n products evenly spaced over a sorted id list (deterministic, name-blind)."""
    ids = sorted(ids)
    return [ids[i * len(ids) // n] for i in range(n)]


def with_rel(real, lo, hi, pred=lambda p: True):
    return [p["id"] for p in real.values() if (r := p.get("delivery_reliability")) is not None and lo <= r < hi and pred(p)]


def test_unreliable_products_are_never_auto_with_or_without_a_rule_of_their_own(real):
    bad = spread(with_rel(real, 0.0, 0.8), 8)
    assert len(set(bad)) == 8
    for pid in bad:
        for m, source in ((mandate(), "default"), (mandate(0.9), "mandate")):
            res = order(pid, m)
            rel = real[pid]["delivery_reliability"]
            assert res.decision.outcome == "ASK_HUMAN" and res.status == "pending_approval", (pid, rel)
            low = next(r for r in res.decision.reasons if r.code.value == "LOW_RELIABILITY")
            assert low.severity.value == "ASK_HUMAN" and low.product_id == pid
            assert low.facts["reliability"] == rel and low.facts["floor_source"] == source
            assert f"{rel:.0%}" in low.message and "on time only" in low.message and "rule" in low.message


def test_reliable_products_still_go_through_automatically(real):
    good = spread(with_rel(real, 0.95, 1.01), 8)
    for pid in good:
        for m in (mandate(), mandate(0.9)):
            res = order(pid, m)
            assert res.decision.outcome == "AUTO" and res.status == "confirmed", (pid, [r.code for r in res.decision.reasons])
            assert not [r for r in res.decision.reasons if r.code.value == "LOW_RELIABILITY"]


def test_the_buyers_own_floor_beats_the_default_in_both_directions(real):
    middling = spread(with_rel(real, 0.8, 0.9), 6)  # fine under the 80% default, held under a 90% rule
    for pid in middling:
        assert order(pid, mandate()).decision.outcome == "AUTO"
        assert order(pid, mandate(0.9)).decision.outcome == "ASK_HUMAN"
    poor = spread(with_rel(real, 0.3, 0.8), 6)  # a chef who wrote a lower floor (even 0) is believed
    for pid in poor:
        assert order(pid, mandate(0.2)).decision.outcome == "AUTO"
        assert order(pid, mandate(0)).decision.outcome == "AUTO"


def test_no_reliability_record_is_not_a_default_floor_breach(real):
    unknown = spread([p["id"] for p in real.values() if p.get("delivery_reliability") is None], 6)
    for pid in unknown:  # most products have no record; only a rule that asks for one makes that a question
        res = order(pid, mandate())
        assert "LOW_RELIABILITY" not in [r.code.value for r in res.decision.reasons] and "DATA_MISSING" not in [
            r.code.value for r in res.decision.reasons]
        assert "DATA_MISSING" in [r.code.value for r in order(pid, mandate(0.9)).decision.reasons]


def _replaceable(real, floor=gate.DEFAULT_MIN_RELIABILITY):
    """(unreliable product, reliable same-category same-kind products): found by the data, not named."""
    out = []
    for pid in sorted(with_rel(real, 0.0, floor)):
        p = real[pid]
        better = [c["id"] for c in real.values() if c["category"] == p["category"] and c["id"] != pid
                  and (c.get("delivery_reliability") or 0) >= floor and (c["delivery_reliability"] > p["delivery_reliability"])
                  and gate._same_kind_for_alternative(p, c)]
        if better:
            out.append((pid, better))
    return out


def test_a_more_reliable_same_kind_alternative_is_offered(real):
    pairs = _replaceable(real)
    assert len(pairs) >= 6, "the data should hold at least six unreliable products with a reliable same-kind twin"
    for pid, better in (pairs[i * len(pairs) // 6] for i in range(6)):
        res = order(pid, mandate())
        assert res.decision.outcome == "ASK_HUMAN"  # still held for the chef, never silently swapped
        offered = [a.product_id for a in res.decision.alternatives]
        assert offered, pid
        for c in offered:
            assert c in better and real[c]["category"] == real[pid]["category"]
            assert real[c]["delivery_reliability"] >= gate.DEFAULT_MIN_RELIABILITY > real[pid]["delivery_reliability"]
        assert all(s["replaces"] == pid and s["reliability"] >= gate.DEFAULT_MIN_RELIABILITY for s in res.substitutes)


def test_alternatives_never_include_unreliable_or_unrecorded_products(real):
    for pid, _ in _replaceable(real)[:10]:
        res = order(pid, mandate(0.9))
        for s in res.substitutes:
            assert s["reliability"] is not None and s["reliability"] >= 0.9
