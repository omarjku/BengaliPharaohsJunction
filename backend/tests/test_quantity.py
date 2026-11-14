"""Quantity resolver (T05): small fixture dicts in the catalogue's slim shape, no real data needed."""
import pytest
from fastapi.testclient import TestClient

from app import catalogue
from app.quantity import resolve


def product(**kw) -> dict:
    p = {"id": "1", "sales_unit": "ST", "base_unit": "ST", "lot_size": 0.01, "units": {"ST": 1.0, "KI": 5.0},
         "volume": {"unit": "LTR", "value": 1.0}, "net_weight": {"unit": "GRM", "value": 1025.0}}
    return p | kw


MILK_1L = product()                                                        # like 463335 Valio Eila 1 L, sold per ST
MILK_CASE = product(sales_unit="KI", units={"ST": 1.0, "KI": 12.0})        # 12 x 1 L, sold per case
CHICKEN = product(sales_unit="KG", base_unit="KG", lot_size=3.0, units={"KG": 1.0, "KI": 3.0},
                  volume={"unit": "KGM", "value": 3.0}, net_weight={"unit": "KGM", "value": 3.0})  # like 469013 ca 3 kg


def test_litres_to_single_units():
    r = resolve(MILK_1L, 1000, "L")
    assert (r["quantity"], r["sales_unit"], r["delivered"], r["over_delivery"]) == (1000, "ST", 1000, 0)
    assert r["confidence"] == "high" and not r["needs_confirmation"] and not r["rounded_up"]


def test_litres_to_case_converts_but_asks_to_confirm_case_assumption():
    r = resolve(MILK_CASE, 1000, "L")
    assert (r["quantity"], r["per_sales_unit"], r["delivered"], r["over_delivery"]) == (84, 12, 1008, 8)
    assert r["confidence"] == "medium" and r["needs_confirmation"] and "whole KI" in r["explanation"]


def test_kilograms_by_net_weight_and_by_kg_base_unit():
    r = resolve(MILK_1L, 41, "kg")                     # 1,025 g per carton → exactly 40
    assert (r["quantity"], r["confidence"], r["rounded_up"]) == (40, "high", False)
    r = resolve(product(sales_unit="KG", base_unit="KG", units={"KG": 1.0}, net_weight=None, volume=None), 7.25, "kg")
    assert (r["quantity"], r["sales_unit"], r["rounded_up"]) == (7.25, "KG", False)  # KG stays continuous at lot 0.01


def test_count_in_pieces_and_in_product_unit_codes():
    assert resolve(MILK_CASE, 24, "pcs")["quantity"] == 2
    assert resolve(MILK_1L, 3, "KI")["quantity"] == 15     # 3 cases of 5 = 15 cartons
    r = resolve(product(base_unit="PAK", sales_unit="PAK", units={"PAK": 1.0}), 10, "pcs")
    assert r["quantity"] == 10 and r["needs_confirmation"] and "one piece = one PAK" in r["explanation"]


def test_rounds_up_and_reports_over_delivery():
    r = resolve(MILK_CASE, 100, "L")                   # 100 / 12 = 8.33 → 9 cases
    assert (r["quantity"], r["delivered"], r["over_delivery"], r["rounded_up"]) == (9, 108, 8, True)
    assert "8 L more than asked" in r["explanation"]


def test_lot_size_multiples():
    r = resolve(CHICKEN, 40, "kg")                     # lot 3 kg → 42
    assert (r["quantity"], r["over_delivery"], r["confidence"]) == (42, 2, "high") and "lot size 3" in r["explanation"]
    assert resolve(product(lot_size=1.5), 4, "L")["quantity"] == 6   # whole units AND multiple of 1.5 → steps of 3


def test_no_float_drift():
    r = resolve(product(volume={"unit": "MLT", "value": 150.0}), 2.1, "L")   # 2.1 / (150 * 0.001) = 14.000000000000002 in floats → 15
    assert (r["quantity"], r["rounded_up"], r["over_delivery"]) == (14, False, 0)


def test_missing_volume_refuses():
    r = resolve(product(sales_unit="KI", volume=None), 1000, "L")   # like 463038 10 L novobox: no volume recorded
    assert r["quantity"] is None and r["needs_confirmation"] and r["confidence"] == "none"
    assert "no volume is recorded" in r["explanation"]


@pytest.mark.parametrize("p, amount, unit, why", [
    (product(volume={"unit": "GRM", "value": 900.0}), 10, "L", "recorded in GRM"),   # volume given as a weight
    (CHICKEN, 10, "pcs", "sold by weight"),                                          # pieces of a per-kg product
    (MILK_1L, 2, "PAL", "not a unit of this product"),                               # unit code the product lacks
    (product(units={"ST": 0.0}), 2, "L", "size of one ST"),                          # broken units table
])
def test_contradictory_or_unusable_data_refuses(p, amount, unit, why):
    r = resolve(p, amount, unit)
    assert r["quantity"] is None and r["needs_confirmation"] and why in r["explanation"]


def test_route(monkeypatch):
    from app.main import app
    monkeypatch.setattr(catalogue, "_products", {"463335": dict(MILK_1L, id="463335")})
    monkeypatch.setattr(catalogue, "_ready", type("E", (), {"is_set": lambda self: True})())
    c = TestClient(app)
    ok = c.post("/api/quantity/resolve", json={"product_id": "463335", "amount": 1000, "unit": "l"})
    assert ok.status_code == 200 and ok.json()["quantity"] == 1000
    assert c.post("/api/quantity/resolve", json={"product_id": "999", "amount": 1, "unit": "L"}).status_code == 404
    for bad in ({"product_id": "46a", "amount": 1, "unit": "L"}, {"product_id": "463335", "amount": 0, "unit": "L"},
                {"product_id": "463335", "amount": 1e9, "unit": "L"}, {"product_id": "463335", "amount": 1, "unit": "boxes"},
                {"product_id": "463335", "amount": 1, "unit": "ki"}):
        assert c.post("/api/quantity/resolve", json=bad).status_code == 422, bad
    monkeypatch.setattr(catalogue, "_ready", type("E", (), {"is_set": lambda self: False})())
    assert c.post("/api/quantity/resolve", json={"product_id": "463335", "amount": 1, "unit": "L"}).status_code == 503
