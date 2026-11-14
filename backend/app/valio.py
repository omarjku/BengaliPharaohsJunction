"""Client for Valio Aimo's mock API: availability + price merged into one quote per product.

Behaviour verified against the live API (docs/valio-api-notes.md):
- Requests need `X-API-Key` AND a non-default `User-Agent` (Cloudflare returns 403 / error 1010 otherwise).
- Max 1000 products per call; don't sweep the catalogue (undisclosed rate limits).
- Terminal products report availableAmount 999999 = quantity UNKNOWN, not infinite.
- Unknown product ids look like undeliverable ones in /availability; only /price flags them (`error: true`).
- `closingTime` can already be in the past while the line still says "available" (e.g. Terminal for Monday).
"""
import time
from datetime import datetime, timedelta

import httpx
from trade_contracts import CutOff, QuantityInfo, Quote
from trade_contracts.common import Availability, QuoteSource

from . import config

USER_AGENT = "BengaliPharaohs-Junction2026/0.1 (+https://github.com/omarjku/BengaliPharaohsJunction)"
MAX_BATCH = 1000
UNKNOWN_QTY = 999999.0
CACHE_TTL_S = 60  # ponytail: in-process dict cache, fine for one Render instance; use Redis/Postgres if we scale out
CACHE_MAX = 20_000  # bound memory: the route is public, so ids/dates come from anyone

_cache: dict[tuple[str, str], tuple[float, dict]] = {}


def _prune(now: float) -> None:
    """Drop expired entries; if still over the cap, drop the oldest (dicts keep insertion order)."""
    for k in [k for k, (t, _) in _cache.items() if now - t >= CACHE_TTL_S]:
        del _cache[k]
    for k in list(_cache)[: max(0, len(_cache) - CACHE_MAX)]:
        del _cache[k]


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=config.VALIO_BASE_URL,
        headers={"X-API-Key": config.VALIO_API_KEY, "User-Agent": USER_AGENT},
        timeout=20,
    )


def _merge(avail: dict, price: dict | None, now: datetime) -> dict:
    """One product's availability + price → a quote with explicit trap flags."""
    line = (avail.get("scheduleLines") or [None])[0]
    model = avail.get("logisticModel")  # "Stock", "Terminal" or None (undeliverable / unknown id)
    amount = line.get("availableAmount") if line else None
    cutoff = avail.get("closingTime")
    unknown_product = bool(price and price.get("error"))

    flags = []
    if unknown_product:
        flags.append("unknown_product")
    elif not model or not line:
        flags.append("undeliverable")
    if avail.get("salesBlock") or (line and line.get("salesBlock")):
        flags.append("sales_block")
    if amount == UNKNOWN_QTY:
        flags.append("quantity_unknown")
    elif amount == 0:
        flags.append("out_of_stock")
    if cutoff and datetime.fromisoformat(cutoff) < now:
        flags.append("cutoff_passed")

    p = price or {}
    return {
        "product_id": avail["productId"],
        "logistic_model": model,
        "available_amount": None if amount == UNKNOWN_QTY else amount,
        "quantity_known": amount is not None and amount != UNKNOWN_QTY,
        "available_date": (line or {}).get("availableDate"),
        "order_cutoff": cutoff,
        "sales_unit": (line or {}).get("salesUnit"),
        "price": (p.get("catalogPrice") or {}).get("value"),
        "price_with_tax": (p.get("priceWithTax") or {}).get("value"),
        "list_price": (p.get("listPrice") or {}).get("value"),
        "customer_net_price": bool(p.get("netPriceFound")),
        "comparison_price": (p.get("comparisonPrice") or {}).get("value"),
        "comparison_unit": p.get("comparisonUnit"),
        "tax_rate": (p.get("tax") or {}).get("taxRate"),
        "flags": flags,
        "orderable": not {"unknown_product", "undeliverable", "sales_block", "out_of_stock", "cutoff_passed"} & set(flags),
        "source": "valio-mock-api",
        "fetched_at": now.isoformat(),
    }


async def get_quotes(product_ids: list[str], requested_date: str, customer: str = "123") -> list[dict]:
    """Quotes for the given products and delivery date (YYYY-MM-DD), in request order. Cached for CACHE_TTL_S."""
    ids = list(dict.fromkeys(product_ids))  # dedupe, keep order
    fresh = time.monotonic()
    found: dict[str, dict] = {}
    for i in ids:
        if (c := _cache.get((i, requested_date))) and fresh - c[0] < CACHE_TTL_S:
            found[i] = c[1]
    todo = [i for i in ids if i not in found]

    if todo:
        _prune(fresh)
        async with _client() as http:
            for start in range(0, len(todo), MAX_BATCH):
                batch = todo[start:start + MAX_BATCH]
                body = {"customer": customer, "requestedDate": requested_date, "products": batch}
                a = await http.post("/api/availability", json=body)
                p = await http.post("/api/price", json=body)
                a.raise_for_status()
                p.raise_for_status()
                a_json, p_json = a.json(), p.json()
                now = datetime.fromisoformat(a_json["timeNow"])
                prices = {x["productId"]: x for x in p_json.get("products", [])}
                for item in a_json["products"]:
                    quote = _merge(item, prices.get(item["productId"]), now)
                    quote["currency"] = p_json.get("currency")
                    _cache[(item["productId"], requested_date)] = (fresh, quote)
                    found[item["productId"]] = quote

    return [found[i] for i in ids if i in found]


def to_contract_quote(q: dict) -> "Quote | None":
    """T03 quote dict → T02 contract `Quote` (contracts/). Trap flags stay on the dict; the contract
    carries them as availability / quantity.known / cut_off.passed. Unknown products have no price → None."""
    if "unknown_product" in q["flags"] or q["price"] is None:
        return None
    if {"undeliverable", "out_of_stock", "sales_block", "cutoff_passed"} & set(q["flags"]):
        availability = Availability.UNAVAILABLE
    elif not q["quantity_known"]:
        availability = Availability.UNKNOWN
    else:
        availability = Availability.AVAILABLE  # PARTIAL needs the requested qty: decided in T06, not here
    fetched = datetime.fromisoformat(q["fetched_at"])
    cut = datetime.fromisoformat(q["order_cutoff"]) if q["order_cutoff"] else None
    return Quote(
        product_id=q["product_id"],
        unit_price_eur=q["price"],
        unit=q["sales_unit"] or "unit",
        availability=availability,
        quantity=QuantityInfo(known=q["quantity_known"], value=int(q["available_amount"]) if q["quantity_known"] else None),
        available_date=q["available_date"][:10] if q["available_date"] else None,
        source=QuoteSource.VALIO_API,
        fetched_at=fetched,
        valid_until=None if "cutoff_passed" in q["flags"] else fetched + timedelta(seconds=CACHE_TTL_S),
        cut_off=CutOff(closing_time=cut, passed="cutoff_passed" in q["flags"]) if cut else None,
    )


async def ping() -> bool:
    async with _client() as http:
        r = await http.get("/api/ping")
        return r.status_code == 200
