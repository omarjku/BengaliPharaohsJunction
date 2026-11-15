"""Offline checks for the quote merge: one case per trap seen on the live API (docs/valio-api-notes.md)."""
import asyncio
from datetime import datetime

import httpx
import pytest

from app import valio
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


def test_stock_at_or_above_999999_is_unknown_but_orderable():
    q = _merge(avail("Stock", 1000000.0, None), PRICE, NOW)
    assert q["available_amount"] is None and not q["quantity_known"]
    assert q["flags"] == ["quantity_unknown"] and q["orderable"]


def test_429_raises_busy_error_without_retrying(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(429, headers={"Retry-After": "30"})

    monkeypatch.setattr(valio, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                                                      base_url="http://valio"))
    valio._cache.clear()
    with pytest.raises(valio.ValioBusyError, match="try again in about 30 seconds"):
        asyncio.run(valio.get_quotes(["1"], "d"))
    assert calls == ["/api/availability"]


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


def test_contract_quote_matches_t02_shapes_for_each_trap():
    from app.valio import to_contract_quote
    ok = to_contract_quote(_merge(avail(), PRICE, NOW))
    assert ok.availability == "available" and ok.quantity.known and ok.quantity.value == 500 and not ok.cut_off.passed
    terminal = to_contract_quote(_merge(avail("Terminal", 999999.0, "2026-11-12T15:00:00+02:00"), PRICE, NOW))
    assert terminal.availability == "unavailable" and not terminal.quantity.known and terminal.quantity.value is None
    assert terminal.cut_off.passed and terminal.valid_until is None
    assert to_contract_quote(_merge(avail(model=None, lines=False), {"productId": "x", "error": True}, NOW)) is None
    assert to_contract_quote(_merge(avail(model=None, lines=False), PRICE, NOW)).availability == "unavailable"
