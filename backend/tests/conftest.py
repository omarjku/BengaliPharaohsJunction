"""Shared offline fixture for the front door: a tiny catalogue + a fake Valio (no network)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app import catalogue, config, orders, valio

NOW = datetime.now(timezone.utc)
REQ = date.today() + timedelta(days=2)
FUTURE = (NOW + timedelta(days=1)).isoformat()
PAST = (NOW - timedelta(days=2)).isoformat()


def product(pid, name, unit="ST", lot=0.01, claims=("FREE_FROM_LACTOSE",), contains=("AM",), may=(), rel=1.0,
            category="10400", subs=()):
    return {"id": pid, "name_en": name, "name_fi": None, "brand": "Valio", "category": category, "sales_unit": unit,
            "lot_size": lot, "claims": list(claims), "allergens": {"contains": list(contains), "may_contain": list(may),
            "free_from": []}, "substitutes": list(subs), "delivery_reliability": rel}


def quote(pid, model="Stock", amount=5000.0, cutoff=None, price=1.4, unit="ST", error=False, avail_date=None):
    """A real valio._merge quote, so the gate sees exactly what the live adapter produces."""
    a = {"productId": pid, "salesBlock": False, "scheduleLines": []}
    if model:
        a.update(logisticModel=model, closingTime=cutoff or FUTURE, scheduleLines=[{
            "salesBlock": False, "availableAmount": amount, "salesUnit": unit,
            "availableDate": (avail_date or REQ).isoformat()}])
    p = {"productId": pid, "error": True} if error else {
        "productId": pid, "catalogPrice": {"value": price} if price is not None else None, "netPriceFound": True,
        "comparisonPrice": {"value": price}, "comparisonUnit": "L"}
    return valio._merge(a, p, NOW)


class Shop:
    def __init__(self):
        self.products = {p["id"]: p for p in [
            product("463335", "Eila milk 1 l"),
            product("463038", "Eila milk 10 l novobox", unit="KI"),
            product("462775", "Arla milk 1 l"),
            product("476240", "Eila milk drink 1 l alt"),
            product("100", "Peanut snack", category="200", claims=(), contains=("AP",)),
            product("101", "Choc bar", category="200", claims=(), contains=(), may=("AP",)),
            product("102", "Butter block", lot=2.0),
            product("103", "Mystery item", category="300", claims=(), contains=()),
            product("104", "Sold out milk"),
            product("105", "Undeliverable milk"),
            product("106", "Unreliable milk", rel=0.5),
        ]}
        self.quotes = {
            "463335": quote("463335"),
            "463038": quote("463038", "Terminal", 999999.0, PAST, price=31.31, unit="KI"),
            "462775": quote("462775", amount=51.0, price=2.57),
            "476240": quote("476240", price=1.2),
            "100": quote("100"), "101": quote("101"), "102": quote("102"), "103": quote("103"),
            "104": quote("104", amount=0.0), "105": quote("105", model=None), "106": quote("106"),
        }
        self.calls = []
        self.fresh = []

    async def get_quotes(self, ids, requested_date, customer="123", fresh=False):
        self.calls.append(list(ids))
        self.fresh.append(fresh)
        return [self.quotes.get(i) or quote(i, model=None, error=True) for i in ids]


@pytest.fixture
def shop(monkeypatch, tmp_path):
    s = Shop()
    monkeypatch.setattr(catalogue, "_products", s.products)
    monkeypatch.setattr(catalogue, "_ready", type("E", (), {"is_set": lambda self: True})())
    monkeypatch.setattr(valio, "get_quotes", s.get_quotes)
    monkeypatch.setattr(orders, "AUDIT_FILE", tmp_path / "audit.jsonl")
    monkeypatch.setattr(orders, "ORDERS_FILE", tmp_path / "orders.json")
    monkeypatch.setattr(orders, "_orders", None)
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-chef=chef,agent-other=other")
    monkeypatch.setattr(config, "APPROVER_KEYS", "appr-chef=chef:Chef Aino,appr-other=other:Olli")
    return s
