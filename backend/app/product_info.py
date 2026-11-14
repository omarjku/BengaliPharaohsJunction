"""Read-only product answers for price, allergen, and availability questions."""
from datetime import date, datetime
import re
from zoneinfo import ZoneInfo

from . import catalogue, expand, valio


_HELSINKI = ZoneInfo("Europe/Helsinki")
_INFO_WORDS = {"price", "prices", "cost", "costs", "how", "much", "per", "kilo", "kg", "litre", "liter",
               "availability", "available", "stock", "allergen", "allergy", "allergies", "safe", "for", "a",
               "an", "the", "is", "does", "would", "contains", "don't", "do", "not", "order", "it"}


def _query(text: str, slots: dict) -> str:
    items = slots.get("items") if isinstance(slots, dict) else None
    names = [item.get("name") for item in items or [] if isinstance(item, dict) and item.get("name")]
    if names:
        return " ".join(str(name).strip() for name in names[:3])
    cleaned = str(text or "")
    cleaned = re.sub(r"\b(?:for|with)\s+(?:a\s+)?(?:milk|peanut|nut|gluten|dairy|egg|soy|fish)\s+allerg(?:y|ies)\b", " ", cleaned, flags=re.I)
    words = cleaned.replace("?", " ").split()
    return " ".join(word for word in words if word.lower().strip(",.!;:") not in _INFO_WORDS).strip()


def _plain_allergens(product: dict) -> dict[str, list[str]]:
    raw = product.get("allergens") if isinstance(product, dict) else {}
    raw = raw if isinstance(raw, dict) else {}

    def words(key: str) -> list[str]:
        return [catalogue.ALLERGEN_NAMES.get(str(code).upper(), str(code)) for code in raw.get(key) or []]

    return {"contains": words("contains"), "may_contain": words("may_contain"), "free_from": words("free_from")}


def _price_text(quote: dict | None) -> str:
    if not quote or quote.get("price") is None:
        return "price unavailable"
    return f"€{float(quote['price']):.2f} per sales unit"


def _availability_text(quote: dict | None) -> str:
    if not quote:
        return "availability unavailable"
    if quote.get("orderable"):
        return f"available for {quote.get('available_date') or 'the requested date'}"
    flags = ", ".join(str(flag).replace("_", " ") for flag in quote.get("flags") or [])
    return f"not currently orderable{f' ({flags})' if flags else ''}"


def _allergen_text(allergens: dict[str, list[str]]) -> str:
    parts = []
    if allergens["contains"]:
        parts.append("contains " + ", ".join(allergens["contains"]))
    if allergens["may_contain"]:
        parts.append("may contain " + ", ".join(allergens["may_contain"]))
    if allergens["free_from"]:
        parts.append("declared free from " + ", ".join(allergens["free_from"]))
    return "; ".join(parts) if parts else "no allergen declaration listed"


def _requested_date(slots: dict) -> str:
    value = slots.get("date") if isinstance(slots, dict) else None
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError):
        return datetime.now(_HELSINKI).date().isoformat()


async def answer(text: str, slots: dict, buyer_id: str) -> dict:
    """Answer from catalogue and live Valio quotes; this function never creates or changes an order."""
    query = _query(text, slots or {})
    queries = [query] if query else []
    try:
        queries.extend(await expand.queries(query))
    except Exception:
        pass
    try:
        queries.extend(catalogue.synonym_queries(query))
    except Exception:
        pass

    found = {}
    for candidate in dict.fromkeys(q for q in queries if q):
        try:
            for product in catalogue.search(candidate, limit=20):
                if product.get("id") not in found:
                    found[product["id"]] = product
        except Exception:
            continue
        if len(found) >= 3:
            break
    selected = list(found.values())[:3]
    requested_date = _requested_date(slots or {})
    quotes = {}
    if selected:
        try:
            rows = await valio.get_quotes([str(product["id"]) for product in selected], requested_date,
                                          customer=buyer_id, fresh=True)
            quotes = {str(row.get("product_id")): row for row in rows if isinstance(row, dict)}
        except Exception:
            quotes = {}

    products = []
    details = []
    for product in selected:
        product_id = str(product["id"])
        name = product.get("name_en") or product.get("name_fi") or product_id
        allergens = _plain_allergens(product)
        quote = quotes.get(product_id)
        products.append({"id": product_id, "name": name, "price": quote.get("price") if quote else None,
                         "unit_price_cents": quote.get("unit_price_cents") if quote else None,
                         "currency": quote.get("currency") if quote else "EUR", "available": bool(quote and quote.get("orderable")),
                         "available_date": quote.get("available_date") if quote else None, "allergens": allergens})
        details.append(f"{name}: {_price_text(quote)}; {_availability_text(quote)}; allergens: {_allergen_text(allergens)}")

    if details:
        reply = " ".join(details)
    else:
        reply = f"I couldn't find a catalogue product for {query or 'that request'}."
    return {"reply": reply + " I haven't ordered anything.", "products": products}
