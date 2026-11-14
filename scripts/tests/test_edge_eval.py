import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "edge_eval.py"
SPEC = importlib.util.spec_from_file_location("edge_eval", SCRIPT)
edge_eval = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(edge_eval)


def test_continuation_payload_uses_the_public_follow_up_contract():
    """Changing a continuation back to text/conversation_id must fail this test."""
    assert edge_eval.ask_payload("ten litres", "a" * 32) == {
        "follow_up": {"to": "a" * 32, "answer": "ten litres"}
    }


def test_first_turn_payload_keeps_the_existing_text_contract():
    """Changing a new request into a follow-up must fail this test."""
    assert edge_eval.ask_payload("ten litres") == {"text": "ten litres"}


def test_rendered_report_counts_every_input_case_when_only_some_are_graded():
    """Dropping ungraded cases from a report must fail this test."""
    cases = [{"id": f"case-{index}", "group": "phone", "text": "hello", "expect": "reply"}
             for index in range(1, 155)]
    grades = [{"id": f"case-{index}", "verdict": "pass", "severity": None, "reason": "ok"}
              for index in range(1, 48)]
    rendered = edge_eval.render_report({"meta": {}}, cases, [], grades)

    assert "- Counts: 47/154 pass (30.5%)" in rendered
    assert "| phone | 47 | 154 | 30.5% |" in rendered
    assert "| overall | 47 | 154 | 30.5% |" in rendered


def test_run_case_uses_the_buyer_key_and_keeps_metadata_for_every_turn(monkeypatch):
    """Dropping a turn's status, timing, or answer must fail this test."""
    calls = []
    responses = iter([
        {"http_status": 200, "seconds": 0.1, "conversation_id": "a" * 32, "answer": {"question": "How many?"}},
        {"http_status": 200, "seconds": 0.2, "conversation_id": None, "answer": {"speak": "Ordered"}},
    ])

    def ask(base, key, text, conversation_id=None):
        calls.append((base, key, text, conversation_id))
        return next(responses)

    monkeypatch.setattr(edge_eval, "ask_front_door", ask)
    result = edge_eval.run_case("http://example.test", "buyer-key", {"turns": ["milk", "ten litres"]})

    assert calls == [
        ("http://example.test", "buyer-key", "milk", None),
        ("http://example.test", "buyer-key", "ten litres", "a" * 32),
    ]
    assert result["turns"] == [
        {"text": "milk", "http_status": 200, "seconds": 0.1, "conversation_id": "a" * 32,
         "answer": {"question": "How many?"}},
        {"text": "ten litres", "http_status": 200, "seconds": 0.2, "conversation_id": None,
         "answer": {"speak": "Ordered"}},
    ]


def test_ask_front_door_sends_buyer_key_and_follow_up_body(monkeypatch):
    """Changing the header or continuation body must fail this test."""
    seen = {}

    class Response:
        status = 200
        headers = {}

        def read(self):
            return b'{"conversation_id": "a"}'

        def __enter__(self):
            return self

        def __exit__(self, *unused):
            return False

    def open_request(request, timeout):
        seen["headers"] = dict(request.header_items())
        seen["body"] = json.loads(request.data)
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(edge_eval.urllib.request, "urlopen", open_request)
    edge_eval.ask_front_door("http://example.test", "buyer-key", "ten litres", "a" * 32)

    assert seen["headers"]["X-agent-key"] == "buyer-key"
    assert seen["body"] == {"follow_up": {"to": "a" * 32, "answer": "ten litres"}}
    assert seen["timeout"] == 150


def test_run_case_records_a_protocol_failure_when_a_turn_has_no_conversation_id(monkeypatch):
    """Fabricating a continuation id instead of stopping must fail this test."""
    calls = []

    def ask(base, key, text, conversation_id=None):
        calls.append((text, conversation_id))
        return {"http_status": 200, "seconds": 0.1, "conversation_id": None, "answer": {"speak": "Done"}}

    monkeypatch.setattr(edge_eval, "ask_front_door", ask)
    result = edge_eval.run_case("http://example.test", "buyer-key", {"turns": ["milk", "ten litres"]})

    assert calls == [("milk", None)]
    assert result["exception"] is True
    assert result["protocol_failure"] is True
    assert result["turns"][-1]["http_status"] is None
    assert "conversation_id" in result["turns"][-1]["answer"]["detail"]


def test_a_failed_earlier_turn_forces_a_hard_failure_and_is_in_the_summary():
    """Checking only the final turn must fail this test."""
    answer = {"http_status": 200, "answer": {"speak": "Ordered"}, "turns": [
        {"text": "milk", "http_status": 500, "seconds": 0.1, "answer": {"detail": "upstream down"}},
        {"text": "ten litres", "http_status": 200, "seconds": 0.2, "answer": {"speak": "Ordered"}},
    ]}

    assert edge_eval.hard_failure({"group": "phone"}, answer) == "Hard check: turn 1 returned HTTP 500."
    assert "failed turns=turn 1 HTTP 500: upstream down" in edge_eval.answer_summary(answer)


def test_run_case_marks_first_turn_server_failures(monkeypatch):
    """Ignoring a first-turn 5xx must fail this test."""
    monkeypatch.setattr(edge_eval, "ask_front_door", lambda *args: {
        "http_status": 503, "seconds": 0.1, "conversation_id": None, "answer": {"detail": "unavailable"}
    })

    result = edge_eval.run_case("http://example.test", "buyer-key", {"text": "milk"})

    assert edge_eval.hard_failure({"group": "phone"}, result) == "Hard check: HTTP 503 is a server error."


def test_run_case_marks_continuation_server_failures(monkeypatch):
    """Ignoring a continuation 5xx because its first turn succeeded must fail this test."""
    responses = iter([
        {"http_status": 200, "seconds": 0.1, "conversation_id": "a" * 32, "answer": {"question": "How many?"}},
        {"http_status": 502, "seconds": 0.2, "conversation_id": None, "answer": {"detail": "gateway down"}},
    ])
    monkeypatch.setattr(edge_eval, "ask_front_door", lambda *args: next(responses))

    result = edge_eval.run_case("http://example.test", "buyer-key", {"turns": ["milk", "ten litres"]})

    assert result["turns"][1]["http_status"] == 502
    assert edge_eval.hard_failure({"group": "phone"}, result) == "Hard check: turn 2 returned HTTP 502."


def test_dry_run_does_not_open_network_or_write_files(tmp_path, monkeypatch, capsys):
    """Adding transport or report writes to dry-run must fail this test."""
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{ "id": "phone-01", "group": "phone", "text": "hello"}]))
    monkeypatch.setattr(edge_eval.sys, "argv", ["edge_eval.py", "--dry-run", "--cases", str(cases)])
    monkeypatch.setattr(edge_eval.urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(edge_eval, "save", lambda *args: (_ for _ in ()).throw(AssertionError()))

    assert edge_eval.main() == 0
    assert "1 cases ready; no network calls or files written" in capsys.readouterr().out


def test_default_output_label_is_local(monkeypatch):
    """Removing the local default risks replacing the committed baseline."""
    monkeypatch.setattr(edge_eval.sys, "argv", ["edge_eval.py"])
    assert edge_eval.parse_args().label == "local"


def test_chat_payload_distinguishes_new_turn_from_pending_answer():
    assert edge_eval.chat_payload("milk") == {"text": "milk"}
    assert edge_eval.chat_payload("ten litres", "a" * 32) == {
        "text": "ten litres", "conversation_id": "a" * 32
    }
    assert edge_eval.chat_payload("2", "a" * 32, pending=True) == {
        "follow_up": {"to": "a" * 32, "answer": "2"}, "conversation_id": "a" * 32
    }


def test_compact_chat_answer_keeps_observable_card_facts():
    answer = edge_eval.compact_chat_answer({
        "reply": "I proposed vegan lasagna.", "question": None,
        "conversation_id": "a" * 32, "tools_used": ["plan_menu"],
        "cards": [{
            "status": "pending_approval",
            "lines": [{"product": "Vegan lasagna sheets", "literal_amount": "20 kg",
                       "sales_unit_quantity": 8, "sales_unit": "KI", "line_total_cents": 12000}],
            "assumptions": [{"text": "20 portions", "p_yes": 0.91, "kept": True}],
            "order": {"status": "pending_approval", "total_cents": 12000},
            "decision": {"outcome": "ASK_HUMAN", "reasons": [{"code": "SPEND", "message": "Over limit"}],
                         "alternatives": [{"product_id": "p2", "summary": "Another sheet"}]}
        }]
    })

    assert answer["speak"] == "I proposed vegan lasagna."
    assert answer["order_status"] == "pending_approval"
    assert answer["cart_lines"] == [{"name": "Vegan lasagna sheets", "amount": "20 kg"}]
    assert answer["assumptions"] == [{"text": "20 portions", "p_yes": 0.91, "kept": True}]
    assert answer["decision"]["outcome"] == "ASK_HUMAN"
    assert answer["tools_used"] == ["plan_menu"]


def test_chat_front_door_uses_chat_path_and_public_payload(monkeypatch):
    seen = {}

    class Response:
        status = 200
        headers = {}

        def read(self):
            return json.dumps({"reply": "Which milk?", "conversation_id": "a" * 32,
                               "question": "Which milk?", "cards": []}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *unused):
            return False

    def open_request(request, timeout):
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        seen["body"] = json.loads(request.data)
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(edge_eval.urllib.request, "urlopen", open_request)
    result = edge_eval.chat_front_door("http://example.test", "buyer-key", "2", "a" * 32, pending=True)

    assert seen["url"] == "http://example.test/api/agent/chat"
    assert seen["headers"]["X-agent-key"] == "buyer-key"
    assert seen["body"] == {"follow_up": {"to": "a" * 32, "answer": "2"}, "conversation_id": "a" * 32}
    assert seen["timeout"] == 150
    assert result["conversation_id"] == "a" * 32


def test_manual_correction_metrics_reports_zero_one_and_unresolved():
    answers = [
        {"id": "first", "turns": [{"seconds": 1.0}, {"seconds": 2.0}]},
        {"id": "second", "turns": [{"seconds": 1.0}, {"seconds": 2.0}]},
        {"id": "never", "turns": [{"seconds": 1.0}, {"seconds": 2.0}, {"seconds": 3.0}]},
    ]
    turn_grades = {
        "first": [{"verdict": "pass"}, {"verdict": "pass"}],
        "second": [{"verdict": "fail"}, {"verdict": "pass"}],
        "never": [{"verdict": "fail"}, {"verdict": "fail"}, {"verdict": "fail"}],
    }

    metric = edge_eval.manual_correction_metrics(answers, turn_grades)

    assert metric["cases"] == 3
    assert metric["resolved"] == 2
    assert metric["unresolved"] == 1
    assert metric["mean"] == 0.5
    assert metric["distribution"] == {"0": 1, "1": 1, "unresolved": 1}


def test_latency_metrics_uses_every_turn_median():
    assert edge_eval.latency_metrics([
        {"seconds": 8.0, "turns": [{"seconds": 2.0}, {"seconds": 6.0}]},
        {"seconds": 4.0},
    ]) == {"turns": 3, "median_seconds_per_turn": 4.0}


def test_default_endpoint_is_chat_and_ask_remains_selectable(monkeypatch):
    monkeypatch.setattr(edge_eval.sys, "argv", ["edge_eval.py"])
    assert edge_eval.parse_args().endpoint == "chat"
    monkeypatch.setattr(edge_eval.sys, "argv", ["edge_eval.py", "--endpoint", "ask"])
    assert edge_eval.parse_args().endpoint == "ask"


def test_phone_regression_cases_have_unique_ids_and_written_pass_rules():
    cases = json.loads((SCRIPT.parents[1] / "docs/testing/edge-cases.json").read_text())
    regression = [case for case in cases if case.get("group") == "phone-regression"]

    assert len(regression) == 10
    assert len({case["id"] for case in regression}) == len(regression)
    assert all(case.get("expect", "").strip() for case in regression)
