import importlib.util
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
