import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "acceptance_flows.py"
SPEC = importlib.util.spec_from_file_location("acceptance_flows", SCRIPT)
acceptance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acceptance)


class FakeTransport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def __call__(self, method, url, body, headers, timeout):
        self.requests.append({"method": method, "url": url, "body": body,
                              "headers": headers, "timeout": timeout})
        return next(self.responses)


def response(body, seconds=0.25, status=200):
    return acceptance.HttpResponse(status=status, body=body, headers={}, seconds=seconds)


def milk_line(name="Eila lactose-free milk 1 l", amount=1000, unit="L"):
    return {"chosen": True, "product": {"name_en": name},
            "quantity": {"quantity": amount, "sales_unit": unit}}


def test_cli_defaults_and_flow_selection():
    options = acceptance.parse_args([])
    assert options.base == "http://127.0.0.1:8765"
    assert options.label == "local"
    assert options.only is None

    selected = acceptance.select_flows("F9")
    assert [flow["id"] for flow in selected] == ["F9"]


def test_cli_safe_label_and_no_match_return_failure_without_network(tmp_path, monkeypatch):
    assert acceptance.output_path("../ci run").name == "acceptance-ci-run.md"
    monkeypatch.setattr(acceptance, "ROOT", tmp_path)

    assert acceptance.main(["--only", "F99", "--label", "ci run"]) == 1
    assert (tmp_path / "docs/testing/acceptance-ci-run.md").exists()


def test_setup_echoes_preview_values_and_uses_approver_header_without_leaking_key():
    flow = {
        "id": "SETUP",
        "title": "setup",
        "buyer": "helsinki-bistro",
        "setup": {"about": "Our Friday order is milk."},
        "steps": [],
    }
    transport = FakeTransport([
        response({"stored": False, "proposed": [{"id": "staples", "value": ["milk"]}]}),
        response({"stored": True, "saved": ["staples"]}),
    ])

    result = acceptance.run_flow(
        flow,
        "http://example.test",
        {"agent": "agent-secret", "approver": "approver-secret"},
        transport=transport,
    )

    assert transport.requests[0]["body"] == {"about": "Our Friday order is milk."}
    assert transport.requests[0]["headers"] == {"X-Approver-Key": "approver-secret"}
    assert transport.requests[1]["body"] == {"answers": {"staples": ["milk"]}, "confirm": True}
    assert transport.requests[1]["headers"] == {"X-Approver-Key": "approver-secret"}
    report = acceptance.render_report({"meta": {"label": "test"}, "flows": [result]})
    assert "agent-secret" not in report and "approver-secret" not in report
    assert result["passed"] is True


def test_f2_uses_follow_up_contract_and_tolerates_natural_replies():
    standing = [
        milk_line("Eila milk 1 l", 20),
        {"chosen": True, "product": {"name_en": "Unsalted butter"},
         "quantity": {"quantity": 10, "sales_unit": "KG"}},
        {"chosen": True, "product": {"name_en": "Whipping cream"},
         "quantity": {"quantity": 5, "sales_unit": "L"}},
        milk_line("Eila milk 1 l", 12),
    ]
    oat = [
        milk_line("Oat drink 1 l", 12),
        standing[1], standing[2],
    ]
    transport = FakeTransport([
        response({"stored": False, "proposed": [{"id": "staples", "value": ["milk"]}]}),
        response({"stored": True}),
        response({"conversation_id": "c2", "requested_date": "2026-11-20",
                  "order": {"status": "pending_approval"}, "lines": standing,
                  "speak": "I added the usual Friday lines and the extra milk."}),
        response({"conversation_id": "c2", "requested_date": "2026-11-20",
                  "order": {"status": "pending_approval"}, "lines": oat,
                  "speak": "The extra milk is now an oat drink."}),
        response({"conversation_id": "c2", "lines": oat,
                  "speak": "There are 12 litres of oat drink in the cart."}),
        response({"conversation_id": "c2", "question": "Could you repeat that, please?"}),
        response({"conversation_id": "c2", "speak": "I did not catch that; please say it another way."}),
    ])

    result = acceptance.run_flow(
        acceptance.FLOWS_BY_ID["F2"],
        "http://example.test",
        {"agent": "agent-secret", "approver": "approver-secret"},
        transport=transport,
    )

    assert transport.requests[2]["body"] == {"text": acceptance.FLOWS_BY_ID["F2"]["steps"][0]["text"]}
    assert transport.requests[3]["body"] == {
        "follow_up": {"to": "c2", "answer": "Actually, I want oat milk instead of normal milk."}
    }
    assert transport.requests[3]["headers"] == {"X-Agent-Key": "agent-secret"}
    assert result["passed"] is True


def test_wrong_amount_fails_the_strict_cart_checker():
    transport = FakeTransport([response({
        "requested_date": "2026-11-16",
        "order": {"status": "pending_approval"},
        "lines": [{"chosen": True, "product": {"name_en": "Unsalted butter"},
                   "quantity": {"quantity": 20, "sales_unit": "KG"}}],
        "speak": "I have 20 kg of unsalted butter for Monday.",
    })])

    result = acceptance.run_flow(
        acceptance.FLOWS_BY_ID["F4"],
        "http://example.test",
        {"agent": "agent-secret", "approver": "approver-secret"},
        transport=transport,
    )

    assert result["passed"] is False
    assert "25" in " ".join(result["failures"])


def test_f6_accepts_a_friendly_redirect_without_a_cart():
    transport = FakeTransport([response({
        "intent": "unclear",
        "speak": "I can help with ingredients for your kitchen, but I cannot source a LEGO set.",
    })])

    result = acceptance.run_flow(
        acceptance.FLOWS_BY_ID["F6"],
        "http://example.test",
        {"agent": "agent-secret", "approver": "approver-secret"},
        transport=transport,
    )

    assert result["passed"] is True


def test_f1_amount_checker_does_not_reject_benign_stock_prose():
    record = {
        "reply": "The stock note is recorded; the pasta amount remains 3 kg.",
        "cart_lines": [{"name": "Pasta", "amount": 3, "unit": "kg"}],
    }

    passed, reason = acceptance._check_f1_amount(record, [])

    assert passed is True, reason


def test_f9_treats_count_sales_units_as_base_litres_for_a_one_litre_product():
    record = acceptance._record(
        "agent",
        "large_milk",
        "1000 L lactose-free milk for Monday",
        response({
            "status": "pending_approval",
            "total_cents": 156000,
            "lines": [{
                "chosen": True,
                "product": {"name_en": "Eila lactose-free milk 1 l"},
                "quantity": {"quantity": 1000, "sales_unit": "ST"},
            }],
        }),
    )

    passed, reason = acceptance._check_f9_large_milk(record)

    assert passed is True, reason


def test_f10_accepts_beyond_one_kitchen_scale_explanation_without_cart():
    record = acceptance._record(
        "agent",
        "fifty_million",
        "Food for 50 million people tomorrow",
        response({
            "question": "50,000,000 guests is beyond one kitchen; shall I plan for 500?",
        }),
    )

    passed, reason = acceptance.check_flow_turn("F10", "fifty_million", record)

    assert passed is True, reason


def test_f9_approves_with_approver_key_and_verifies_signed_statement():
    statement = {"v": 1, "order_id": "order-9", "status": "confirmed"}
    signature = {"kid": "front-door", "alg": "Ed25519", "value": "signature"}
    transport = FakeTransport([
        response({"conversation_id": "c9", "requested_date": "2026-11-16",
                  "decision": {"decided_at": "2026-11-14T10:00:00Z"},
                  "order_id": "order-9", "status": "pending_approval",
                  "order": {"order_id": "order-9", "status": "pending_approval",
                             "total_cents": 156000},
                  "total_cents": 156000, "lines": [milk_line()],
                  "speak": "This is held for approval at about EUR 1,560."}),
        response({"order_id": "order-9", "status": "confirmed",
                  "signed_statement": statement, "signature": signature,
                  "speak": "Approved by the chef."}),
        response({"valid": True, "kid": "front-door"}),
    ])

    result = acceptance.run_flow(
        acceptance.FLOWS_BY_ID["F9"],
        "http://example.test",
        {"agent": "agent-secret", "approver": "approver-secret"},
        transport=transport,
    )

    assert transport.requests[1]["url"].endswith("/api/orders/order-9/approve")
    assert transport.requests[1]["body"] == {"decided_at": "2026-11-14T10:00:00Z"}
    assert transport.requests[1]["headers"] == {"X-Approver-Key": "approver-secret"}
    assert transport.requests[2]["url"].endswith("/api/verify")
    assert transport.requests[2]["body"] == {"signed_statement": statement, "signature": signature}
    assert transport.requests[2]["headers"] == {}
    assert result["passed"] is True


def test_missing_conversation_id_fails_before_sending_a_follow_up():
    transport = FakeTransport([response({
        "stored": False, "proposed": [{"id": "staples", "value": ["milk"]}],
    }), response({
        "stored": True,
    }), response({
        "requested_date": "2026-11-20",
        "lines": [milk_line("Oat drink 1 l", 12)],
        "speak": "The cart is ready.",
    })])

    result = acceptance.run_flow(
        acceptance.FLOWS_BY_ID["F2"],
        "http://example.test",
        {"agent": "agent-secret", "approver": "approver-secret"},
        transport=transport,
    )

    assert len(transport.requests) == 3
    assert transport.requests[-1]["url"].endswith("/api/agent/ask")
    assert result["passed"] is False
    assert any("conversation_id" in failure for failure in result["failures"])


def test_rendered_report_has_transcript_amounts_status_and_pass_fail_table():
    transport = FakeTransport([response({
        "requested_date": "2026-11-16",
        "order": {"status": "pending_approval"},
        "lines": [{"chosen": True, "product": {"name_en": "Unsalted butter"},
                   "quantity": {"quantity": 25, "sales_unit": "KG"}}],
        "speak": "I have 25 kg of unsalted butter for Monday.",
    }, seconds=0.4)])
    result = acceptance.run_flow(
        acceptance.FLOWS_BY_ID["F4"],
        "http://example.test",
        {"agent": "agent-secret", "approver": "approver-secret"},
        transport=transport,
    )

    report = acceptance.render_report({"meta": {"label": "ci"}, "flows": [result]})
    assert "**Chef:**" in report
    assert "**Agent:**" in report
    assert "25 kg" in report
    assert "pending_approval" in report or "pending approval" in report
    assert "| F4 |" in report and "| PASS |" in report
    assert "agent-secret" not in report and "approver-secret" not in report


# --- F13–F22: scripted flows over HTTP ------------------------------------------------------------------------------
from datetime import date  # noqa: E402

KEYS = {"agent": "agent-secret", "approver": "approver-secret"}
FRIDAY_LINES = [{"text": "15 litres of milk", "quantity": 15, "unit": "l"},
                {"text": "8 kg unsalted butter", "quantity": 8, "unit": "kg"},
                {"text": "3 litres whipping cream", "quantity": 3, "unit": "l"}]


def agent_line(name, quantity, unit="ST"):
    return {"chosen": True, "product": {"name_en": name},
            "quantity": {"quantity": quantity, "sales_unit": unit, "delivered": quantity}}


def usual_cart(status="pending_approval", **extra):
    body = {"conversation_id": None, "requested_date": "2026-11-20", "order_id": "held-1",
            "order": {"order_id": "held-1", "status": status},
            "lines": [agent_line("Valio milk 1 l", 15), agent_line("Valio butter 500 g unsalted", 16),
                      agent_line("Whipping cream 1 l", 3)],
            "speak": "Needs your OK: your saved Friday order."}
    body.update(extra)
    return body


def record_for(check, body, expect=None, status=200, expect_status=200):
    record = acceptance._record("http", "step", "label", response(body, status=status))
    record["check"] = check
    record["cart_lines"] = acceptance._measured_lines(record["body"])
    if expect is not None:
        record["expect"] = expect
    if expect_status != 200:
        record["expect_status"] = expect_status
    return record


def run(flow_id, responses, keys=KEYS, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setattr(acceptance, "_today", lambda: date(2026, 11, 14))
    transport = FakeTransport(responses)
    result = acceptance.run_flow(acceptance.FLOWS_BY_ID[flow_id], "http://example.test", keys, transport=transport)
    return result, transport


def test_new_flows_are_registered_with_their_buyers():
    ids = [flow["id"] for flow in acceptance.select_flows("F13,F14,F15,F16,F17,F18,F19,F20,F21,F22")]
    assert ids == [f"F{n}" for n in range(13, 23)]
    assert acceptance.FLOWS_BY_ID["F15"]["buyer"] == "smoke-kitchen"
    assert all(acceptance.FLOWS_BY_ID[f]["sandbox"] for f in ("F14", "F19", "F20"))


def test_expected_error_status_passes_and_unexpected_success_fails():
    refused = record_for("status_only", {"detail": "approver key required"}, status=403, expect_status=(401, 403))
    assert acceptance.check_flow_turn("F19", "agent_key_approve", refused)[0] is True
    approved = record_for("status_only", {"status": "confirmed"}, expect_status=(401, 403))
    passed, reason = acceptance.check_flow_turn("F19", "agent_key_approve", approved)
    assert passed is False and "expected 401/403" in reason


def test_f13_walks_the_interview_confirms_the_preview_and_uses_the_saved_lines(monkeypatch):
    preview = {"stored": False, "proposed": [{"id": "standing_orders", "value": [{"weekday": "friday"}]},
                                             {"id": "cuisine", "value": "Finnish bistro"}]}
    result, transport = run("F13", [
        response({"buyer_id": "smoke-kitchen", "standing_orders": [{"weekday": "friday", "lines": []}]}),
        response({"buyer_id": "smoke-kitchen"}),  # DELETE friday
        response({"done": False, "topic": "kitchen", "question": "What kind of kitchen do you run?"}),
        response({"done": False, "topic": "standing_orders", "question": "What do you usually order?"}),
        response({"done": True, "preview": preview}),
        response({"stored": True, "profile": {"standing_orders": [{"weekday": "friday", "lines": FRIDAY_LINES}]}}),
        response(usual_cart()),
        response({"status": "rejected"}),
    ], monkeypatch=monkeypatch)

    assert result["passed"] is True, result["failures"]
    assert transport.requests[1]["method"] == "DELETE"
    assert transport.requests[1]["headers"] == {"X-Approver-Key": "approver-secret"}
    assert transport.requests[3]["body"]["answers"] == [
        {"topic": "kitchen", "text": acceptance.INTERVIEW_ANSWERS["kitchen"]}]
    assert transport.requests[5]["body"] == {"answers": {"standing_orders": [{"weekday": "friday"}],
                                                         "cuisine": "Finnish bistro"}, "confirm": True}
    assert transport.requests[6]["body"] == {"text": "I want my usual Friday order."}
    assert transport.requests[7]["url"].endswith("/api/orders/held-1/reject")


def test_interview_step_rejects_a_repeated_topic_and_a_double_question():
    repeat = record_for("interview_step", {"done": False, "topic": "kitchen", "question": "Seats?"},
                        expect={"answered": ["kitchen"]})
    assert acceptance.check_flow_turn("F13", "interview_2", repeat)[0] is False
    double = record_for("interview_step", {"done": False, "topic": "budget", "question": "Budget? And days?"},
                        expect={"answered": []})
    assert acceptance.check_flow_turn("F13", "interview_2", double)[0] is False


def test_usual_check_fails_on_missing_line_wrong_amount_unheld_or_confirmed_cart():
    expect = {"saved": FRIDAY_LINES}
    missing = usual_cart(lines=[agent_line("Valio butter 500 g unsalted", 16), agent_line("Whipping cream 1 l", 3)])
    assert "milk" in acceptance.check_flow_turn("F13", "u", record_for("usual_uses_saved", missing, expect))[1]
    short = usual_cart(lines=[agent_line("Valio milk 1 l", 15), agent_line("Valio butter 500 g unsalted", 8),
                              agent_line("Whipping cream 1 l", 3)])
    assert "amount" in acceptance.check_flow_turn("F13", "u", record_for("usual_uses_saved", short, expect))[1]
    confirmed = usual_cart(status="confirmed")
    assert acceptance.check_flow_turn("F13", "u", record_for("usual_uses_saved", confirmed, expect))[0] is False
    proposal = usual_cart(order=None, order_id=None, question="Which one did you mean: 1) butter; 2) cream?")
    passed, reason = acceptance.check_flow_turn("F13", "u", record_for("usual_uses_saved", proposal, expect))
    assert passed is False and "held" in reason
    assert acceptance.check_flow_turn("F13", "u", record_for("usual_uses_saved", usual_cart(), expect))[0] is True


def test_usual_check_allows_one_which_product_question_then_requires_the_full_cart():
    asking = usual_cart(conversation_id="c1",
                        lines=[agent_line("Valio butter 500 g unsalted", 16), agent_line("Whipping cream 1 l", 3)],
                        question="Which milk did you mean: 1) Valio skimmed milk; 2) Valio whole milk?")
    record = record_for("usual_uses_saved", asking, {"saved": FRIDAY_LINES})
    passed, reason = acceptance.check_flow_turn("F13", "u", record)
    assert passed is True and "asked which product" in reason
    assert acceptance._needs_choice(record) is True
    final = record_for("usual_uses_saved", asking, {"saved": FRIDAY_LINES, "final": True})
    assert acceptance.check_flow_turn("F13", "u", final)[0] is False
    milk_only = usual_cart(lines=[agent_line("Valio skimmed milk 1 l", 15)])
    answered = record_for("usual_uses_saved", milk_only,
                          {"saved": FRIDAY_LINES, "final": True, "prior_lines": record["cart_lines"]})
    assert acceptance.check_flow_turn("F13", "u", answered)[0] is True
    alone = record_for("usual_uses_saved", milk_only, {"saved": FRIDAY_LINES, "final": True})
    assert "butter" in acceptance.check_flow_turn("F13", "u", alone)[1]


def test_duplicate_guard_is_answered_once_and_a_repeat_fails():
    guard = usual_cart(conversation_id="c7", order=None, order_id=None,
                       question="You ordered this 3 minutes ago (order abc, confirmed). Order again? Nothing was ordered.")
    first = record_for("usual_uses_saved", guard, {"saved": FRIDAY_LINES})
    assert acceptance.check_flow_turn("F15", "u", first) == (True, "duplicate-order guard asked first")
    repeat = record_for("usual_uses_saved", guard, {"saved": FRIDAY_LINES, "past_guard": True})
    passed, reason = acceptance.check_flow_turn("F15", "u", repeat)
    assert passed is False and "repeated" in reason


def test_amounts_compare_through_pack_sizes_and_round_up_by_less_than_one_pack():
    butter = {"name": "Valio butter 500 g unsalted", "amount": 6, "unit": "ST"}
    assert acceptance._amount_ok(butter, 3, "kg") is True
    assert acceptance._amount_ok({**butter, "amount": 3}, 3, "kg") is False  # 1.5 kg, the old speed_bench misread
    assert acceptance._amount_ok({"name": "Mozzarella grated 2 kg", "amount": 2, "unit": "ST"}, 3, "kg") is True
    assert acceptance._amount_ok({"name": "Mozzarella grated 2 kg", "amount": 3, "unit": "ST"}, 3, "kg") is False
    assert acceptance._amount_ok({"name": "Cream", "amount": 9, "unit": "L"}, 9, "l") is True
    assert acceptance._amount_ok({"name": "Cream", "amount": 9, "unit": "ST"}, 9, "l") is None


def test_measured_lines_use_sales_quantity_not_delivered_amount():
    body = {"lines": [{"chosen": True, "product": {"name_en": "Valio butter 500 g unsalted"},
                       "quantity": {"quantity": 6, "sales_unit": "ST", "delivered": 3,
                                    "requested": {"amount": 3, "unit": "kg"}}}]}
    assert acceptance._measured_lines(body) == [{"name": "Valio butter 500 g unsalted", "amount": 6, "unit": "ST"}]


def test_f14_history_flow_uses_minted_keys_and_never_renders_them():
    own = {"fri": 87, "sat": 93}
    example = {"basis": "example", "labels": {"example": "Example history (simulated)"},
               "covers_by_weekday": {"mon": 40, "fri": 80}, "covers_source": {"mon": "example", "fri": "example"}}
    mixed = {"basis": "mixed", "covers_by_weekday": {"mon": 40, **own},
             "covers_source": {"mon": "example", "fri": "own", "sat": "own"}}
    cleared = {"basis": "own", "covers_by_weekday": {"mon": None, **own},
               "covers_source": {"mon": "own", "fri": "own", "sat": "own"}, "standing_orders": [], "usual_products": []}
    result, transport = run("F14", [
        response({"buyer_id": "try-0123abcd", "agent_key": "sandbox-agent", "approver_key": "sandbox-approver",
                  "expires_at": "2026-11-15T10:00:00+00:00"}),
        response(example), response(mixed), response(mixed), response(cleared), response(cleared),
    ], keys={})

    assert result["passed"] is True, result["failures"]
    assert transport.requests[0]["headers"] == {}
    assert transport.requests[1]["headers"] == {"X-Agent-Key": "sandbox-agent"}
    assert transport.requests[2]["headers"] == {"X-Approver-Key": "sandbox-approver"}
    assert transport.requests[2]["body"] == own
    report = acceptance.render_report({"meta": {"label": "t"}, "flows": [result]})
    assert "sandbox-agent" not in report and "sandbox-approver" not in report and "<redacted>" in report


def test_history_checks_catch_an_unlabelled_example_and_a_clear_that_leaves_example_data():
    unlabelled = record_for("history_example", {"basis": "example", "labels": {},
                                                "covers_by_weekday": {"fri": 80}, "covers_source": {"fri": "example"}})
    assert acceptance.check_flow_turn("F14", "h", unlabelled)[0] is False
    left = record_for("example_hidden", {"basis": "own", "covers_by_weekday": {"fri": 87},
                                         "covers_source": {"fri": "own"},
                                         "usual_products": [{"product_id": "1", "source": "example"}]},
                      {"covers": {"fri": 87}})
    passed, reason = acceptance.check_flow_turn("F14", "h", left)
    assert passed is False and "product 1" in reason


def test_f15_edit_must_replace_lines_and_the_usual_order_must_drop_milk(monkeypatch):
    profile = {"standing_orders": [{"weekday": "friday", "lines": acceptance.F15_LINES}]}
    with_milk = usual_cart(lines=[agent_line("Valio butter 500 g unsalted", 14), agent_line("Whipping cream 1 l", 9),
                                  agent_line("Mozzarella grated 2 kg", 2), agent_line("Valio milk 1 l", 15)])
    result, transport = run("F15", [response(profile), response(with_milk), response({"status": "rejected"})],
                            monkeypatch=monkeypatch)
    assert transport.requests[0]["url"].endswith("/api/profile/standing-orders/fri")
    assert transport.requests[0]["body"] == {"lines": acceptance.F15_LINES}
    assert result["passed"] is False and "milk" in " ".join(result["failures"])
    stale = record_for("standing_saved", {"standing_orders": [{"weekday": "friday", "lines": FRIDAY_LINES}]},
                       {"weekday": "friday", "lines": acceptance.F15_LINES})
    assert acceptance.check_flow_turn("F15", "edit_friday", stale)[0] is False


def test_f16_menu_lands_on_the_calendar_and_planning_orders_nothing(monkeypatch):
    friday = "2026-11-20"
    calendar = {"days": [{"date": friday, "entries": [
        {"kind": "weekly_menu", "name": acceptance.F16_MENU["name"], "covers": 40}]}]}
    plan = {"lines": [agent_line("Galbani mozzarella grated 2 kg", 2)], "order_lines": [],
            "decision": {"outcome": "ASK_HUMAN"}, "order": None}
    result, transport = run("F16", [
        response({**acceptance.F16_MENU, "weekday": "fri"}), response(calendar), response(plan), response(calendar),
    ], monkeypatch=monkeypatch)
    assert result["passed"] is True, result["failures"]
    assert transport.requests[1]["url"].endswith(f"/api/calendar?from={friday}&to={friday}")
    assert transport.requests[2]["url"].endswith(f"/api/menus/weekly/fri/plan?date={friday}")
    ordered = record_for("menu_plan", {**plan, "order": {"order_id": "x", "status": "confirmed"}},
                         {"families": ["mozzarella"]})
    assert acceptance.check_flow_turn("F16", "plan_menu", ordered)[0] is False
    held_back = record_for("menu_plan", {**plan, "lines": [agent_line("Tomato sauce 1 l", 5)],
                                         "speak": "Left out until you check them: Galbani Mozzarella grated 2 kg."},
                           {"families": ["mozzarella"]})
    assert acceptance.check_flow_turn("F16", "plan_menu", held_back)[0] is True
    forgotten = record_for("menu_plan", {**plan, "lines": [agent_line("Tomato sauce 1 l", 5)], "speak": "Proposal."},
                           {"families": ["mozzarella"]})
    assert acceptance.check_flow_turn("F16", "plan_menu", forgotten)[0] is False
    appeared = record_for("calendar_unchanged", {"days": [{"date": friday, "entries": [
        {"kind": "delivery_pending", "order_id": "new"}]}]}, {"date": friday, "before": []})
    assert acceptance.check_flow_turn("F16", "after", appeared)[0] is False


def test_f17_calendar_must_show_confirmed_and_waiting_orders_on_their_dates(monkeypatch):
    tue, wed = "2026-11-17", "2026-11-18"
    calendar = {"days": [
        {"date": tue, "entries": [{"kind": "delivery_confirmed", "order_id": "c1", "title": "Confirmed delivery"}]},
        {"date": wed, "entries": [{"kind": "delivery_pending", "order_id": "p1", "reason": "waiting for your OK"}]}]}
    result, transport = run("F17", [
        response([{"product_id": "464411", "unit_price_cents": 330, "orderable": True}]),
        response({"order_id": "c1", "status": "confirmed"}),
        response({"order_id": "p1", "status": "pending_approval"}),
        response(calendar),
        response({"status": "rejected"}),
    ], monkeypatch=monkeypatch)
    assert result["passed"] is True, result["failures"]
    assert transport.requests[2]["body"]["lines"][0]["quantity"] == 516  # €1,702.80: above €1,500, below €2,000
    swapped = {"days": [{"date": tue, "entries": [{"kind": "delivery_pending", "order_id": "p1", "title": "x"}]},
                        {"date": wed, "entries": [{"kind": "delivery_confirmed", "order_id": "c1"}]}]}
    record = record_for("calendar_orders", swapped, {"confirmed": [tue, "c1"], "pending": [wed, "p1"]})
    assert acceptance.check_flow_turn("F17", "calendar_orders", record)[0] is False
    unmarked = {"days": [calendar["days"][0], {"date": wed, "entries": [
        {"kind": "delivery_pending", "order_id": "p1", "title": "Delivery"}]}]}
    record = record_for("calendar_orders", unmarked, {"confirmed": [tue, "c1"], "pending": [wed, "p1"]})
    assert "waiting" in acceptance.check_flow_turn("F17", "calendar_orders", record)[1]


def f18_responses(place_after_skip_status=409):
    friday, skip_day = "2026-11-20", "2026-12-18"
    return [
        response({"standing_orders": [{"weekday": "friday", "lines": acceptance.F18_LINES}]}),
        response({"order_id": "r1", "requested_date": friday, "order": {"order_id": "r1", "status": "pending_approval"},
                  "lines": [agent_line("Valio butter 500 g unsalted", 12), agent_line("Whipping cream 1 l", 4)]}),
        response({"days": [{"date": friday, "entries": [{"kind": "recurring_order", "placed": True},
                                                        {"kind": "delivery_pending", "order_id": "r1"}]}]}),
        response({"status": "rejected"}),
        response({"weekday": "friday", "date": skip_day, "skipped": True}),
        response({"days": [{"date": skip_day, "entries": []}]}),
        response({"detail": "That recurring order was skipped for this date"}, status=place_after_skip_status),
    ]


def test_f18_recurring_order_is_held_through_the_front_door_and_skip_blocks_placing(monkeypatch):
    result, transport = run("F18", f18_responses(), monkeypatch=monkeypatch)
    assert result["passed"] is True, result["failures"]
    assert transport.requests[1]["url"].endswith("/api/calendar/recurring/fri/place?date=2026-11-20")
    assert transport.requests[4]["url"].endswith("/api/calendar/recurring/fri/skip?date=2026-12-18")
    assert transport.requests[4]["headers"] == {"X-Approver-Key": "approver-secret"}

    result, _ = run("F18", f18_responses(place_after_skip_status=200), monkeypatch=monkeypatch)
    assert result["passed"] is False and "expected 409" in " ".join(result["failures"])


def test_recurring_check_rejects_an_auto_confirmed_standing_order():
    body = {"order_id": "r1", "order": {"order_id": "r1", "status": "confirmed"},
            "lines": [agent_line("Valio butter 500 g unsalted", 12), agent_line("Whipping cream 1 l", 4)]}
    record = record_for("recurring_held", body, {"families": ["butter", "cream"]})
    assert acceptance.check_flow_turn("F18", "place_recurring", record)[0] is False


def f19_responses(agent_approve_status=403):
    return [
        response({"buyer_id": "try-89abcdef", "agent_key": "sb-agent", "approver_key": "sb-approver",
                  "expires_at": "2026-11-15T10:00:00+00:00"}),
        response([{"product_id": "464411", "unit_price_cents": 330, "orderable": True}]),
        response({"order_id": "o9", "status": "pending_approval",
                  "decision": {"decided_at": "2026-11-14T10:00:00Z"}}),
        response({"detail": "This key may not approve"}, status=agent_approve_status),
        response({"id": "o9", "status": "pending_approval"}),
        response({"order_id": "o9", "status": "confirmed", "signature": {"alg": "Ed25519"},
                  "signed_statement": {"signed_off_by": "try-89abcdef"}}),
    ]


def test_f19_agent_key_cannot_approve_but_the_approver_key_can(monkeypatch):
    result, transport = run("F19", f19_responses(), keys={}, monkeypatch=monkeypatch)
    assert result["passed"] is True, result["failures"]
    assert transport.requests[3]["headers"] == {"X-Approver-Key": "sb-agent"}
    assert transport.requests[5]["headers"] == {"X-Approver-Key": "sb-approver"}
    assert transport.requests[5]["body"] == {"decided_at": "2026-11-14T10:00:00Z"}

    result, _ = run("F19", f19_responses(agent_approve_status=200), keys={}, monkeypatch=monkeypatch)
    assert result["passed"] is False and "agent_key_approve" in " ".join(result["failures"])


def test_f20_isolation_checks_catch_leaked_profile_and_history():
    leaked = record_for("profile_isolated", {"buyer_id": "try-b", "standing_orders": [
        {"weekday": "friday", "lines": [{"text": "11 kg unsalted butter"}]}]},
        {"buyer": "try-b", "foreign_text": "11 kg unsalted butter", "foreign_order": "o1"})
    assert acceptance.check_flow_turn("F20", "b_profile", leaked)[0] is False
    order_leak = record_for("profile_isolated", {"buyer_id": "try-b", "recent_orders": [{"order_id": "o1"}]},
                            {"buyer": "try-b", "foreign_text": "11 kg unsalted butter", "foreign_order": "o1"})
    assert acceptance.check_flow_turn("F20", "b_profile", order_leak)[0] is False
    history = record_for("history_isolated", {"covers_by_weekday": {"fri": 71}, "covers_source": {"fri": "own"}},
                         {"day": "fri", "foreign": 71})
    assert acceptance.check_flow_turn("F20", "b_history", history)[0] is False


def test_sandbox_flows_run_without_env_keys_and_report_a_failed_mint(monkeypatch):
    monkeypatch.setattr(acceptance, "_today", lambda: date(2026, 11, 14))
    transport = FakeTransport([response({"detail": "Too many test kitchens"}, status=429)])
    results = acceptance.run_selected("http://example.test", {}, flows=[acceptance.FLOWS_BY_ID["F19"]],
                                      transport=transport)
    flow = results["flows"][0]
    assert len(transport.requests) == 1 and flow["passed"] is False
    assert "HTTP 429" in " ".join(flow["failures"]) and "missing" not in " ".join(flow["failures"])


def test_f21_order_contents_needs_the_real_lines_and_amounts(monkeypatch):
    placed = {"order_id": "o21", "requested_date": "2026-11-17", "order": {"order_id": "o21", "status": "confirmed"},
              "lines": [agent_line("Valio butter 500 g unsalted", 6), agent_line("Whipping cream 1 l", 2)],
              "speak": "Ordered: 3 kg butter and 2 L cream."}
    answer = {"speak": "Your order for Tuesday has 3 kg Valio butter (6 packs) and 2 L whipping cream."}
    result, transport = run("F21", [response(placed), response(answer)], monkeypatch=monkeypatch)
    assert result["passed"] is True, result["failures"]
    assert transport.requests[0]["body"]["text"].endswith("for Tuesday.")
    lines = acceptance._measured_lines(placed)
    empty = record_for("order_contents", {"speak": "Your cart is empty."}, {"lines": lines})
    assert acceptance.check_flow_turn("F21", "w", empty)[0] is False
    vague = record_for("order_contents", {"speak": "You have butter and cream."}, {"lines": lines})
    assert "amount" in acceptance.check_flow_turn("F21", "w", vague)[1]


def test_f22_three_intents_reads_every_card_and_lists_every_missing_part(monkeypatch):
    cards = [{"lines": [agent_line("Valio butter 500 g unsalted", 8)], "reply": "Added 4 kg butter."},
             {"reply": "Last Friday you served 112 guests."},
             {"lines": [agent_line("Whipping cream 1 l", 8)], "reply": "Cream is now 8 litres."}]
    good = {"lines": cards[0]["lines"], "reply": "Added 4 kg butter. 112 guests. Cream 8 L.", "cards": cards}
    result, transport = run("F22", [
        response({"order_id": "o", "order": {"order_id": "o", "status": "confirmed"},
                  "lines": [agent_line("Whipping cream 1 l", 5)]}),
        response(good),
    ], monkeypatch=monkeypatch)
    assert result["passed"] is True, result["failures"]
    assert "guests" in transport.requests[1]["body"]["text"]
    only_order = record_for("three_intents", {"lines": [agent_line("Valio butter 500 g unsalted", 4)],
                                              "question": "Which one did you mean: 1) Valio butter unsalted?"},
                            {"butter": 4, "cream": 8})
    passed, reason = acceptance.check_flow_turn("F22", "three_intents", only_order)
    assert passed is False
    assert "order part" in reason and "kitchen question" in reason and "change part" in reason
