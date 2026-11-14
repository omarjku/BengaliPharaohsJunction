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


def test_cache_is_bounded_and_drops_expired(monkeypatch):
    from app import valio
    monkeypatch.setattr(valio, "CACHE_MAX", 3)
    valio._cache.clear()
    valio._cache[("old", "d")] = (0.0, {})                      # expired
    for i in range(5):
        valio._cache[(str(i), "d")] = (1000.0, {})              # fresh
    valio._prune(1000.0 + 1)
    assert ("old", "d") not in valio._cache and len(valio._cache) == 3
    assert list(valio._cache) == [("2", "d"), ("3", "d"), ("4", "d")]  # oldest dropped first


def test_quotes_route_rejects_bad_input_before_calling_valio():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    assert c.post("/api/quotes", json={"product_ids": ["DROP TABLE"], "requested_date": "2026-11-16"}).status_code == 422
    assert c.post("/api/quotes", json={"product_ids": ["463335"], "requested_date": "2030-01-01"}).status_code == 422
    assert c.post("/api/quotes", json={"product_ids": ["463335"], "requested_date": "monday"}).status_code == 422
