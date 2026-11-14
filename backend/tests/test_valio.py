"""Offline checks for the quote merge: one case per trap seen on the live API (docs/valio-api-notes.md)."""
from datetime import datetime

from app.valio import _merge

NOW = datetime.fromisoformat("2026-11-13T22:58:00+02:00")
PRICE = {"productId": "x", "catalogPrice": {"value": 1.4}, "priceWithTax": {"value": 1.59}, "listPrice": {"value": 1.57},
         "netPriceFound": True, "comparisonPrice": {"value": 1.4}, "comparisonUnit": "L", "tax": {"taxRate": 13.5}, "error": False}


def avail(model="Stock", amount=500.0, cutoff="2026-11-15T17:00:00+02:00", lines=True):
    a = {"productId": "x", "salesBlock": False,
         "scheduleLines": [{"salesBlock": False, "availableAmount": amount, "availableDate": "2026-11-16T00:00:00+02:00", "salesUnit": "ST"}] if lines else []}
    if model:
        a["logisticModel"] = model
        a["closingTime"] = cutoff
    return a


def test_happy_stock_product_is_orderable():
    q = _merge(avail(), PRICE, NOW)
    assert q["orderable"] and q["flags"] == [] and q["available_amount"] == 500.0 and q["price"] == 1.4


def test_terminal_999999_means_unknown_quantity_and_past_cutoff_blocks():
    q = _merge(avail("Terminal", 999999.0, "2026-11-12T15:00:00+02:00"), PRICE, NOW)
    assert q["available_amount"] is None and not q["quantity_known"]
    assert {"quantity_unknown", "cutoff_passed"} <= set(q["flags"]) and not q["orderable"]


def test_undeliverable_has_no_model_or_lines():
    q = _merge(avail(model=None, lines=False), PRICE, NOW)
    assert "undeliverable" in q["flags"] and not q["orderable"]


def test_unknown_product_only_caught_by_price_error():
    q = _merge(avail(model=None, lines=False), {"productId": "x", "error": True, "netPriceFound": False}, NOW)
    assert q["flags"][0] == "unknown_product" and "undeliverable" not in q["flags"]


def test_zero_stock_is_out_of_stock():
    q = _merge(avail(amount=0.0), PRICE, NOW)
    assert "out_of_stock" in q["flags"] and not q["orderable"]
