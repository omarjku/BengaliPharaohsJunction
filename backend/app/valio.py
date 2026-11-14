"""Client for Valio Aimo's mock API: availability + price merged into one quote per product.

Behaviour verified against the live API (docs/valio-api-notes.md):
- Requests need `X-API-Key` AND a non-default `User-Agent` (Cloudflare returns 403 / error 1010 otherwise).
- Max 1000 products per call; don't sweep the catalogue (undisclosed rate limits).
- Terminal products report availableAmount 999999 = quantity UNKNOWN, not infinite.
- Unknown product ids look like undeliverable ones in /availability; only /price flags them (`error: true`).
- `closingTime` can already be in the past while the line still says "available" (e.g. Terminal for Monday).
"""
import time
from datetime import datetime

import httpx

from . import config

USER_AGENT = "BengaliPharaohs-Junction2026/0.1 (+https://github.com/omarjku/BengaliPharaohsJunction)"
MAX_BATCH = 1000
UNKNOWN_QTY = 999999.0
CACHE_TTL_S = 60  # ponytail: in-process dict cache, fine for one Render instance; use Redis/Postgres if we scale out

_cache: dict[tuple[str, str], tuple[float, dict]] = {}


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
    todo = [i for i in ids if not ((c := _cache.get((i, requested_date))) and fresh - c[0] < CACHE_TTL_S)]

    if todo:
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

    return [_cache[(i, requested_date)][1] for i in ids if (i, requested_date) in _cache]


async def ping() -> bool:
    async with _client() as http:
        r = await http.get("/api/ping")
        return r.status_code == 200
