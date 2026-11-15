from datetime import datetime, timedelta

from app import catalogue, conversation, orders


def test_current_order_lists_only_waiting_orders_and_counts_confirmed_history(monkeypatch):
    today = datetime.now(conversation.HELSINKI).date()
    store = {
        "held": {"id": "held", "buyer_id": "chef", "status": "pending_approval", "requested_date": today.isoformat(),
                 "lines": [{"product_id": "milk", "quantity": 2, "unit": "L"}], "total_cents": 1200},
        "open": {"id": "open", "buyer_id": "chef", "status": "open", "requested_date": today.isoformat(),
                 "lines": [{"product_id": "tomatoes", "quantity": 3, "unit": "kg"}], "total_cents": 900},
        "old-held": {"id": "old-held", "buyer_id": "chef", "status": "pending_approval",
                     "requested_date": (today - timedelta(days=1)).isoformat(), "lines": [], "total_cents": 0},
        "confirmed": {"id": "confirmed", "buyer_id": "chef", "status": "confirmed", "requested_date": today.isoformat(),
                      "lines": [{"product_id": "trout", "quantity": 1, "unit": "kg"}], "total_cents": 2400},
        "old-confirmed": {"id": "old-confirmed", "buyer_id": "chef", "status": "confirmed",
                          "requested_date": (today - timedelta(days=1)).isoformat(), "lines": [], "total_cents": 0},
    }
    monkeypatch.setattr(orders, "_store", lambda: store)
    monkeypatch.setattr(catalogue, "get", lambda product_id: {"milk": {"name_en": "Milk"},
                                                                 "tomatoes": {"name_en": "Tomatoes"},
                                                                 "trout": {"name_en": "Trout"}}.get(product_id))

    result = conversation.current_order("chef")

    assert [row["order_id"] for row in result["orders"]] == ["held", "open"]
    assert {line["name"] for row in result["orders"] for line in row["lines"]} == {"Milk", "Tomatoes"}
    assert result["waiting_count"] == 2
    assert result["confirmed_count"] == 1  # only upcoming confirmed orders; past ones live in History
    assert [row["requested_date"] for row in result["confirmed_upcoming"]] and "History" in result["confirmed_note"]
    assert result["total_cents"] == 2100
