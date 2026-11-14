import asyncio
from datetime import date

from app import catalogue, expand, understand, valio
from app import product_info


TODAY = date(2026, 11, 14)


def run(coro):
    return asyncio.run(coro)


def test_decimal_amount_is_not_a_delivery_date():
    assert understand.resolve_date_from_text("2.5 kg butter", TODAY) is None
    assert understand.resolve_date_from_text("2.5.2027", TODAY) == date(2027, 5, 2)
    assert understand.resolve_date_from_text("2.5.2027 kg butter", TODAY) is None


def test_explicit_amounts_with_event_context_stay_order_items():
    action = understand._fallback_action(
        "140 kg butter and 100 L milk for Wednesday, we have a Christmas party", TODAY, None
    )
    assert action["intent"] == "order_items"
    assert [(item["amount"], item["unit"]) for item in action["slots"]["items"]] == [(140.0, "kg"), (100.0, "L")]


def test_impossible_food_request_is_out_of_scope():
    action = understand._fallback_action("Can you get me a unicorn and three dragons?", TODAY, None)
    assert action["intent"] == "out_of_scope"


def test_approval_intents_are_distinct():
    assert "product_info" in understand.INTENTS
    assert "approve_request" in understand.INTENTS
    action = understand._sanitize_action({
        "intent": "approve_request",
        "slots": {"items": [], "dishes": [], "guests": None, "date": None,
                  "diets": [], "exclusions": [], "language": "en"},
    }, "approve everything", TODAY)
    assert action["intent"] == "approve_request"
    assert understand._fallback_action("approve everything", TODAY, None)["intent"] == "approve_request"


def test_product_info_quotes_at_most_three_products_and_places_nothing(monkeypatch):
    products = [
        {"id": str(n), "name_en": f"Valio product {n}", "name_fi": None, "brand": "Valio",
         "allergens": {"contains": ["AM"] if n == 1 else [], "may_contain": [], "free_from": []}}
        for n in range(1, 5)
    ]
    seen = {}

    async def fake_expand(_query):
        return ["butter", "voi"]

    async def fake_quotes(ids, requested_date, customer="123", fresh=False):
        seen.update(ids=ids, requested_date=requested_date, customer=customer, fresh=fresh)
        return [{"product_id": pid, "price": 2.5, "currency": "EUR", "orderable": True,
                 "available_date": requested_date, "flags": []} for pid in ids]

    monkeypatch.setattr(expand, "queries", fake_expand)
    monkeypatch.setattr(catalogue, "search", lambda *args, **kwargs: products)
    monkeypatch.setattr(valio, "get_quotes", fake_quotes)

    result = run(product_info.answer("How much does butter cost per kilo? Don't order it", {
        "items": [{"name": "butter"}], "date": "2026-11-16", "language": "en"
    }, "chef"))

    assert len(result["products"]) == 3
    assert seen == {"ids": ["1", "2", "3"], "requested_date": "2026-11-16", "customer": "chef", "fresh": True}
    assert "milk" in result["products"][0]["allergens"]["contains"]
    assert "haven't ordered" in result["reply"]
