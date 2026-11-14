import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "speed_bench.py"
SPEC = importlib.util.spec_from_file_location("speed_bench", SCRIPT)
speed_bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(speed_bench)


class FakeTransport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def __call__(self, method, url, body, headers, timeout):
        self.requests.append({"method": method, "url": url, "body": body, "headers": headers, "timeout": timeout})
        return next(self.responses)


def response(body, seconds=0.4, status=200):
    return speed_bench.HttpResponse(status=status, body=body, headers={}, seconds=seconds)


def test_session_uses_follow_up_contract_and_approver_key_for_tap():
    transport = FakeTransport([
        response({"question": "Which milk?", "conversation_id": "a" * 32,
                  "options": ["20 L milk", "40 L milk"]}),
        response({
            "order_id": "order-1",
            "status": "pending_approval",
            "order": {"order_id": "order-1", "status": "pending_approval"},
            "decision": {"decided_at": "2026-11-14T10:00:00Z"},
            "lines": [{"chosen": True, "product": {"name_en": "Valio milk"},
                       "quantity": {"quantity": 20, "sales_unit": "L"}}],
        }),
        response({"order_id": "order-1", "status": "confirmed"}),
    ])
    session = {
        "id": "milk",
        "turns": [{"text": "milk for Friday", "policy": {
            "answer": {"kind": "first_choice"}, "approve": True,
        }}],
        "expected": [{"words": ["milk"], "amount": 20, "unit": "L"}],
    }

    result = speed_bench.run_session(
        session,
        "http://example.test",
        "agent-secret",
        "approver-secret",
        transport=transport,
    )

    assert transport.requests[0]["body"] == {"text": "milk for Friday"}
    assert transport.requests[0]["headers"]["X-Agent-Key"] == "agent-secret"
    assert transport.requests[1]["body"] == {"follow_up": {"to": "a" * 32, "answer": "20 L milk"}}
    assert transport.requests[1]["headers"]["X-Agent-Key"] == "agent-secret"
    assert transport.requests[2]["url"].endswith("/api/orders/order-1/approve")
    assert transport.requests[2]["body"] == {"decided_at": "2026-11-14T10:00:00Z"}
    assert transport.requests[2]["headers"]["X-Approver-Key"] == "approver-secret"
    assert result["chef_turns"] == 2
    assert result["questions"] == 1
    assert result["taps"] == 2
    assert result["final_state"] == "confirmed"
    assert result["lines_in_cart"] == 1
    assert result["matched"] is True
    assert result["total_seconds"] == 1.2


def test_key_helpers_follow_edge_eval_env_format_without_exposing_values():
    values = {
        "AGENT_KEYS": "agent-one=other,agent-two=helsinki-bistro:Chef",
        "APPROVER_KEYS": "approver-one=other,approver-two=helsinki-bistro:Chef Aino",
    }

    assert speed_bench.agent_key(values, "helsinki-bistro") == "agent-two"
    assert speed_bench.approver_key(values, "helsinki-bistro") == "approver-two"


def test_cart_match_checks_product_words_and_requested_amounts():
    expected = [
        {"words": ["oat milk", "kaurajuoma"], "amount": 20, "unit": "L"},
        {"words": ["butter", "voi"], "amount": 5, "unit": "kg"},
    ]
    actual = [
        {"name": "Oat milk drink", "amount": 20, "unit": "L"},
        {"name": "Unsalted butter", "amount": 5, "unit": "kg"},
    ]

    assert speed_bench.cart_matches(actual, expected)
    assert not speed_bench.cart_matches(actual, [{"words": ["butter"], "amount": 6, "unit": "kg"}])


def test_sessions_cover_the_requested_battle_inputs_and_report_gates():
    required = [
        "usual Friday",
        "20 L lactose-free milk",
        "40 guests",
        "large pizza",
        "butter ASAP",
        "party of 30",
        "how much milk",
        "oat milk",
        "20 litraa maitoa",
        "how many did we serve last Friday",
    ]
    text = "\n".join(turn["text"] for session in speed_bench.SESSIONS for turn in session["turns"])
    assert len(speed_bench.SESSIONS) >= 10
    assert all(needle.lower() in text.lower() for needle in required)

    report = speed_bench.render_report({
        "meta": {"label": "test", "base": "http://example.test", "buyer": "buyer"},
        "sessions": [{
            "id": "one", "total_seconds": 5.0, "chef_turns": 1, "questions": 0,
            "taps": 0, "lines_in_cart": 1, "final_state": "confirmed", "matched": True,
            "speed_up": 10.0,
        }],
        "gates": {
            "questions": {"passed": True, "value": 0},
            "median_backend_seconds": {"passed": True, "value": 5.0},
            "median_speed_up": {"passed": True, "value": 10.0},
            "passed": True,
        },
    })
    assert "| one | 5.00 | 1 | 0 | 0 | 1 | confirmed | yes | 10.00x |" in report
    assert "Overall: PASS" in report
