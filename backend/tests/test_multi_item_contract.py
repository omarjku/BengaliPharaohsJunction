"""Regression tests for item-scoped order cards and chef-facing unit language."""

from trade_contracts import Alternative, ReasonCode as C

from app import agent, chat_agent, gate, live, quantity


def _item(query, amount, unit):
    return {"query": query, "amount": amount, "unit": unit}


def test_item_summary_covers_mixed_outcomes_without_cross_item_alternatives():
    request = {"items": [
        _item("potatoes", 70, "kg"), _item("salmon", 70, "kg"), _item("water bottles", 500, "pcs"),
        _item("mystery spice", 2, "kg"), _item("potatoes", 5, "kg"),
    ]}
    lines = [
        {"item": 0, "chosen": True, "product": {"id": "potato-1"}, "quantity": {"quantity": 1}},
        {"item": 1, "chosen": True, "product": {"id": "salmon-1"}, "quantity": {"quantity": 1}},
        {"item": 2, "chosen": False, "product": {"id": "water-1"}, "quantity": None},
        {"item": 4, "chosen": True, "product": {"id": "potato-1"}, "quantity": {"quantity": 1}},
    ]
    reasons = {
        1: [gate._r(C.STOCK_PARTIAL, gate.ASK, "Only 20 cases are available.", "salmon-1")],
        2: [gate._r(C.QTY_AMBIGUOUS, gate.ASK, "The case size is unknown.", "water-1")],
        3: [gate._r(C.UNKNOWN_PRODUCT, gate.ASK, "No match was found.")],
    }

    summaries = agent._item_summaries(request, lines, reasons, {1, 2, 3})

    assert [row["item"] for row in summaries] == [0, 1, 2, 3, 4]
    assert [row["status"] for row in summaries] == ["chosen", "out_of_stock", "needs_unit", "no_match", "chosen"]
    assert all(set(row) == {"item", "query", "amount", "unit", "status", "chosen_product_id", "reason", "summary"}
               for row in summaries)
    assert summaries[1]["chosen_product_id"] == "salmon-1"
    assert summaries[3]["chosen_product_id"] is None

    alternatives = [Alternative(item=0, product_id="potato-2", summary="Another potato")]
    assert alternatives[0].item == 0
    assert all(alternative.item == 0 for alternative in alternatives)


def test_chat_card_lines_keep_request_item_index():
    card = {"lines": [{"item": 3, "chosen": True, "product": {"id": "p", "name_en": "Product"},
                       "quantity": {"requested": {"amount": 2, "unit": "kg"}, "quantity": 2},
                       "quote": {"orderable": True}}]}

    assert chat_agent._card_lines(card)[0]["item"] == 3


def test_piece_count_to_known_case_size_is_held_and_spoken_without_codes():
    product = {"id": "water", "name_en": "Water bottles", "sales_unit": "KI", "base_unit": "ST",
               "lot_size": 1, "units": {"ST": 1, "KI": 24}, "volume": None, "net_weight": None}

    result = quantity.resolve(product, 500, "bottles")

    assert result["quantity"] == 21 and result["delivered"] == 504 and result["needs_confirmation"]
    assert "21 case" in result["explanation"] and "24 bottles" in result["explanation"]
    assert "KI" not in result["explanation"]


def test_piece_count_to_unknown_case_size_asks_in_words():
    product = {"id": "water", "name_en": "Water bottles", "sales_unit": "KI", "base_unit": "ST",
               "lot_size": 1, "units": {"ST": 1}, "volume": None, "net_weight": None}

    result = quantity.resolve(product, 500, "pcs")

    assert result["quantity"] is None and result["needs_confirmation"]
    assert "How many bottles per case do you want?" in result["explanation"]
    assert "KI" not in result["explanation"]


def test_live_setup_restricts_input_transcription_to_english_and_finnish():
    setup = live._setup("chef", "order")["setup"]

    assert setup["inputAudioTranscription"]["languageCodes"] == ["en-US", "fi-FI"]
    assert "English or Finnish" in live.SYSTEM
