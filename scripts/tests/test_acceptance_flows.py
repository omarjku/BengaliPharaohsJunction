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
