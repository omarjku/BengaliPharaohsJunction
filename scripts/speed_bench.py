#!/usr/bin/env python3
"""Measure how quickly scripted chef requests reach a usable cart over the backend API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import edge_eval  # noqa: E402  (reuse its env and /ask payload conventions)


DEFAULT_BASE = "http://127.0.0.1:8765"
DEFAULT_BUYER = "helsinki-bistro"
REQUEST_TIMEOUT = 150


class HttpResponse:
    def __init__(self, status: int | None, body: Any, headers: Any, seconds: float, exception: bool = False):
        self.status = status
        self.body = body
        self.headers = headers
        self.seconds = seconds
        self.exception = exception


def _response_from_transport(value: Any) -> HttpResponse:
    """Accept the native response object and a small tuple seam for tests."""
    if isinstance(value, HttpResponse):
        return value
    if isinstance(value, tuple):
        status, body, *rest = value
        headers = rest[0] if rest else {}
        seconds = rest[1] if len(rest) > 1 else 0.0
        return HttpResponse(status, body, headers, float(seconds))
    raise TypeError("transport must return HttpResponse or (status, body, headers, seconds)")


def _urlopen_transport(method: str, url: str, body: Any, headers: dict[str, str], timeout: int) -> HttpResponse:
    raw = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        method=method,
        data=raw,
        headers={"Content-Type": "application/json", "User-Agent": "speed-bench/1", **headers},
    )
    started = time.monotonic()
    status: int | None = None
    response_headers: Any = {}
    answer: Any = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = response.status
                response_headers = response.headers
                answer = edge_eval.json_body(response.read())
        except urllib.error.HTTPError as error:
            status = error.code
            response_headers = error.headers
            try:
                answer = edge_eval.json_body(error.read())
            except Exception:
                answer = {"detail": "HTTP error body could not be read."}
        except Exception as error:
            return HttpResponse(
                None,
                {"detail": f"Python exception: {type(error).__name__}"},
                {},
                round(time.monotonic() - started, 3),
                exception=True,
            )
        if status != 429 or attempt:
            break
        try:
            delay = max(0.0, float((response_headers or {}).get("Retry-After", "1")))
        except (TypeError, ValueError):
            delay = 1.0
        time.sleep(delay)
    return HttpResponse(status, answer, response_headers, round(time.monotonic() - started, 3))


class HttpClient:
    """Small injectable HTTP client; the default transport never starts a server."""

    def __init__(self, base: str, transport: Callable[..., Any] | None = None):
        self.base = base.rstrip("/")
        self.transport = transport or _urlopen_transport

    def request(self, method: str, path: str, body: Any, headers: dict[str, str]) -> HttpResponse:
        result = self.transport(method, self.base + path, body, headers, REQUEST_TIMEOUT)
        return _response_from_transport(result)

    def ask(self, key: str, text: str, conversation_id: str | None = None) -> HttpResponse:
        return self.request("POST", "/api/agent/ask", edge_eval.ask_payload(text, conversation_id), {"X-Agent-Key": key})

    def approve(self, key: str, order_id: str, decided_at: str | None = None) -> HttpResponse:
        body = {"decided_at": decided_at} if decided_at else None
        return self.request("POST", f"/api/orders/{order_id}/approve", body, {"X-Approver-Key": key})


def read_env(path: Path) -> dict[str, str]:
    return edge_eval.read_env(path)


def env_entries(values: dict[str, str], name: str) -> list[tuple[str, str]]:
    return edge_eval.env_entries(values, name)


def agent_key(values: dict[str, str], buyer: str) -> str:
    return edge_eval.agent_key(values, buyer)


def approver_key(values: dict[str, str], buyer: str) -> str:
    return next((key for key, owner in env_entries(values, "APPROVER_KEYS") if owner == buyer), "")


def _say(value: str, approve: bool = False) -> dict[str, Any]:
    return {"answer": {"kind": "say", "value": value}, "tap": "approve" if approve else None}


def _first_choice(approve: bool = False) -> dict[str, Any]:
    return {"answer": {"kind": "first_choice"}, "tap": "approve" if approve else None}


def _approve() -> dict[str, Any]:
    return {"tap": "approve"}


SESSIONS: list[dict[str, Any]] = [
    {
        "id": "usual-friday-plus-milk",
        "turns": [{
            "text": "I want to do our usual Friday order. But I also want to add milk.",
            "policy": _say("12 L milk", approve=True),
        }],
        "expected": [
            {"words": ["butter"], "amount": None},
            {"words": ["flour"], "amount": None},
            {"words": ["mozzarella"], "amount": None},
            {"words": ["milk", "maito"], "amount": 12, "unit": "L"},
        ],
    },
    {
        "id": "three-stated-lines",
        "turns": [{
            "text": "20 L lactose-free milk, 10 kg butter and 5 L cream for Friday",
            "policy": _approve(),
        }],
        "expected": [
            {"words": ["milk", "maito"], "amount": 20, "unit": "L"},
            {"words": ["butter", "voi"], "amount": 10, "unit": "kg"},
            {"words": ["cream"], "amount": 5, "unit": "L"},
        ],
    },
    {
        "id": "menu-for-forty",
        "turns": [{
            "text": "Menu for 40 guests on Friday: salmon soup, blueberry pie",
            "policy": _first_choice(),
        }],
        "expected": [
            {"words": ["salmon"], "amount": None},
            {"words": ["blueberry"], "amount": None},
        ],
    },
    {
        "id": "self-correction",
        "turns": [{
            "text": "a large pizza, no wait, medium... make it 20 kg flour, no, 25",
            "policy": _say("Friday", approve=True),
        }],
        "expected": [{"words": ["flour"], "amount": 25, "unit": "kg"}],
    },
    {
        "id": "urgent-butter-helsinki",
        "turns": [{
            "text": "butter ASAP",
            "policy": _say("5 kg butter", approve=True),
        }],
        "expected": [{"words": ["butter", "voi"], "amount": 5, "unit": "kg"}],
    },
    {
        "id": "vague-party",
        "turns": [{
            "text": "stuff for a party of 30 on Saturday",
            "policy": {},
        }],
        "expected": [],
    },
    {
        "id": "cart-question-after-ordering",
        "turns": [
            {"text": "20 L milk for Friday", "policy": _approve()},
            {"text": "how much milk is in my order?", "policy": {}},
        ],
        "expected": [{"words": ["milk", "maito"], "amount": 20, "unit": "L"}],
    },
    {
        "id": "product-swap-mid-order",
        "turns": [{
            "text": "20 L milk for Friday; make the milk oat milk",
            "policy": _approve(),
        }],
        "expected": [{"words": ["oat milk", "kaurajuoma"], "amount": 20, "unit": "L"}],
    },
    {
        "id": "finnish-order",
        "turns": [{
            "text": "20 litraa maitoa ja 5 kiloa voita perjantaiksi",
            "policy": _approve(),
        }],
        "expected": [
            {"words": ["milk", "maito"], "amount": 20, "unit": "L"},
            {"words": ["butter", "voi"], "amount": 5, "unit": "kg"},
        ],
    },
    {
        "id": "order-and-history-question",
        "turns": [{
            "text": "order 10 kg butter for Monday and how many did we serve last Friday?",
            "policy": _approve(),
        }],
        "expected": [{"words": ["butter", "voi"], "amount": 10, "unit": "kg"}],
    },
]


def _safe_call(call: Callable[[], HttpResponse]) -> HttpResponse:
    try:
        return _response_from_transport(call())
    except Exception as error:
        return HttpResponse(None, {"detail": f"Python exception: {type(error).__name__}"}, {}, 0.0, exception=True)


def _body(response: HttpResponse) -> dict[str, Any]:
    return response.body if isinstance(response.body, dict) else {}


def _question(body: dict[str, Any]) -> bool:
    return bool(isinstance(body.get("question"), str) and body["question"].strip())


def _order(body: dict[str, Any]) -> dict[str, Any]:
    return body.get("order") if isinstance(body.get("order"), dict) else {}


def _status(body: dict[str, Any]) -> str | None:
    order = _order(body)
    status = order.get("status") or body.get("status")
    return status if isinstance(status, str) else None


def _state(body: dict[str, Any], response: HttpResponse, previous: str | None) -> str:
    if response.exception or response.status is None or response.status >= 400:
        return "error"
    status = _status(body)
    if status == "confirmed":
        return "confirmed"
    if status == "pending_approval":
        return "pending approval"
    if status in {"refused", "rejected"} or (body.get("decision") or {}).get("outcome") == "DECLINE":
        return "refused"
    if body.get("order_lines") or (body.get("intent") == "menu" and body.get("lines")):
        return "pending approval"
    if _question(body):
        return "question"
    return previous or "question"


def _line_id(line: dict[str, Any]) -> str | None:
    product = line.get("product") if isinstance(line.get("product"), dict) else {}
    value = product.get("id") or line.get("product_id")
    return str(value) if value is not None else None


def _line_name(line: dict[str, Any]) -> str | None:
    product = line.get("product") if isinstance(line.get("product"), dict) else {}
    value = (product.get("name_en") or product.get("name") or product.get("name_fi") or line.get("name")
             or line.get("product_name") or product.get("id") or line.get("product_id"))
    return str(value) if value is not None else None


def _line_measure(line: dict[str, Any]) -> tuple[float | int | None, str | None]:
    quantity = line.get("quantity")
    if isinstance(quantity, dict):
        amount = (quantity.get("delivered") if quantity.get("delivered") is not None else
                  quantity.get("amount") if quantity.get("amount") is not None else quantity.get("quantity"))
        unit = (quantity.get("unit") or quantity.get("measure_unit") or quantity.get("sales_unit") or
                line.get("unit") or line.get("sales_unit"))
    else:
        amount = quantity if quantity is not None else line.get("amount")
        unit = line.get("unit") or line.get("sales_unit")
    if isinstance(amount, str):
        match = re.search(r"-?\d+(?:[.,]\d+)?", amount.replace(" ", ""))
        amount = float(match.group(0).replace(",", ".")) if match else None
    if isinstance(amount, float) and amount.is_integer():
        amount = int(amount)
    return amount, str(unit) if unit else None


def cart_lines(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Return selected cart lines without retaining the full backend response."""
    if not isinstance(body, dict):
        return []
    compact = body.get("cart_lines")
    if isinstance(compact, list):
        return [line for line in compact if isinstance(line, dict)]

    candidates = [line for line in body.get("lines") or [] if isinstance(line, dict)]
    sources = {_line_id(line): line for line in candidates if _line_id(line)}
    order = _order(body)
    order_candidates = [line for line in order.get("lines") or [] if isinstance(line, dict)]
    menu_candidates = [line for line in body.get("order_lines") or [] if isinstance(line, dict)]
    selected = order_candidates or menu_candidates
    if selected:
        result = []
        for line in selected:
            source = sources.get(_line_id(line), {})
            name = _line_name(source) or _line_name(line)
            amount, unit = _line_measure(source) if source else _line_measure(line)
            if name is not None:
                result.append({"name": name, "amount": amount, "unit": unit})
        return result

    result = []
    for line in candidates:
        if line.get("chosen") is False:
            continue
        name = _line_name(line)
        if name is not None:
            amount, unit = _line_measure(line)
            result.append({"name": name, "amount": amount, "unit": unit})
    return result


def _normal_unit(value: Any) -> str | None:
    if value is None:
        return None
    unit = str(value).strip().casefold()
    return {
        "l": "l", "liter": "l", "litre": "l", "liters": "l", "litres": "l", "litraa": "l",
        "kg": "kg", "kilo": "kg", "kiloa": "kg", "kilos": "kg", "kilogram": "kg", "kilograms": "kg",
        "pcs": "pcs", "pc": "pcs", "piece": "pcs", "pieces": "pcs", "st": "pcs", "kpl": "pcs",
    }.get(unit, unit)


def cart_matches(actual: Iterable[dict[str, Any]], expected: Iterable[dict[str, Any]], require_exact: bool = False) -> bool:
    actual_lines = list(actual)
    expected_lines = list(expected)
    if not expected_lines:
        return not actual_lines
    remaining = actual_lines[:]
    for item in expected_lines:
        words = item.get("words") or item.get("word") or []
        if isinstance(words, str):
            words = [words]
        found = None
        for index, line in enumerate(remaining):
            name = str(line.get("name") or "").casefold()
            if not any(str(word).casefold() in name for word in words):
                continue
            if item.get("amount") is not None:
                try:
                    if abs(float(line.get("amount")) - float(item["amount"])) > 1e-6:
                        continue
                except (TypeError, ValueError):
                    continue
            if item.get("unit") is not None and _normal_unit(line.get("unit")) != _normal_unit(item["unit"]):
                continue
            found = index
            break
        if found is None:
            return False
        remaining.pop(found)
    return not remaining if require_exact else True


def _first_choice(body: dict[str, Any]) -> str:
    options = body.get("options")
    if not isinstance(options, list) or not options:
        steps = body.get("next_steps")
        if isinstance(steps, list) and steps and isinstance(steps[0], dict):
            options = steps[0].get("options")
    if isinstance(options, list) and options:
        choice = options[0]
        if isinstance(choice, dict):
            choice = next((choice.get(key) for key in ("answer", "label", "text", "value", "name")
                           if choice.get(key) is not None), None)
        if choice is not None:
            return re.sub(r"^\s*(?:1[.)]|first)\s*", "", str(choice), flags=re.I).strip()
    return "1"


def _answer_policy(policy: Any, body: dict[str, Any]) -> tuple[str | None, bool]:
    if isinstance(policy, str):
        if policy in {"first_choice", "pick_first"}:
            return _first_choice(body), True
        if policy in {"tap_approve", "approve"}:
            return None, False
        if policy.startswith("say:"):
            return policy[4:].strip(), False
        return None, False
    if not isinstance(policy, dict):
        return None, False
    spec = policy.get("answer")
    if isinstance(spec, str):
        if spec in {"first_choice", "pick_first"}:
            return _first_choice(body), True
        return spec, False
    if isinstance(spec, dict):
        kind = spec.get("kind") or spec.get("action")
        if kind in {"first_choice", "pick_first"}:
            return _first_choice(body), True
        if kind in {"say", "answer"}:
            return str(spec.get("value") or spec.get("answer") or ""), False
    return None, False


def _tap_approve(policy: Any) -> bool:
    if isinstance(policy, str):
        return policy in {"tap_approve", "approve"}
    return isinstance(policy, dict) and (policy.get("tap") in {"approve", "tap_approve"} or policy.get("approve") is True)


def _order_id(body: dict[str, Any]) -> str | None:
    order = _order(body)
    for value in (body.get("order_id"), order.get("order_id"), order.get("id"), body.get("id")):
        if value:
            return str(value)
    return None


def _decided_at(body: dict[str, Any]) -> str | None:
    order = _order(body)
    for source in (body, order):
        decision = source.get("decision") if isinstance(source.get("decision"), dict) else {}
        if decision.get("decided_at"):
            return str(decision["decided_at"])
    return None


def run_session(
    session: dict[str, Any],
    base: str,
    agent_secret: str,
    approver_secret: str,
    transport: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    client = HttpClient(base, transport=transport)
    total_seconds = 0.0
    turn_seconds: list[float] = []
    chef_turns = 0
    questions = 0
    taps = 0
    final_state: str | None = None
    pending_conversation: str | None = None
    saved_lines: list[dict[str, Any]] = []
    approvable_seconds: float | None = None
    error_type: str | None = None

    def observe(response: HttpResponse) -> dict[str, Any]:
        nonlocal total_seconds, questions, final_state, saved_lines, approvable_seconds, error_type
        total_seconds += max(0.0, float(response.seconds))
        body = _body(response)
        if _question(body):
            questions += 1
        if response.exception or response.status is None or response.status >= 400:
            error_type = (body.get("detail") if isinstance(body.get("detail"), str) else "HTTP error")
        lines = cart_lines(body)
        if lines:
            saved_lines = lines
        final_state = _state(body, response, final_state)
        if approvable_seconds is None and final_state in {"confirmed", "pending approval"}:
            approvable_seconds = total_seconds
        return body

    for turn in session.get("turns", []):
        if not isinstance(turn, dict):
            continue
        started_turn = total_seconds
        text = str(turn.get("text") or "")
        response = _safe_call(lambda: client.ask(agent_secret, text, pending_conversation))
        pending_conversation = None
        chef_turns += 1
        body = observe(response)

        answer, is_tap = _answer_policy(turn.get("policy"), body)
        conversation_id = body.get("conversation_id") if isinstance(body.get("conversation_id"), str) else None
        if answer is not None and conversation_id:
            follow_up = _safe_call(lambda: client.ask(agent_secret, answer, conversation_id))
            chef_turns += 1
            if is_tap:
                taps += 1
            body = observe(follow_up)
            conversation_id = body.get("conversation_id") if isinstance(body.get("conversation_id"), str) else None
        if conversation_id:
            pending_conversation = conversation_id

        if _tap_approve(turn.get("policy")):
            order_id = _order_id(body)
            if order_id and _status(body) == "pending_approval":
                taps += 1
                approved = _safe_call(lambda: client.approve(approver_secret, order_id, _decided_at(body)))
                body = observe(approved)
                pending_conversation = (body.get("conversation_id")
                                        if isinstance(body.get("conversation_id"), str) else pending_conversation)
        turn_seconds.append(round(total_seconds - started_turn, 3))

    lines_in_cart = len(saved_lines)
    expected = session.get("expected") or []
    matched = cart_matches(saved_lines, expected, require_exact=bool(session.get("exact_expected")))
    baseline_seconds = lines_in_cart * 35.0 + 20.0
    denominator = total_seconds + chef_turns * 4.0 + taps * 1.5
    speed_up = baseline_seconds / denominator if denominator > 0 else 0.0
    result = {
        "id": session.get("id", "session"),
        "turn_seconds": turn_seconds,
        "total_seconds": round(total_seconds, 3),
        "backend_seconds": round(total_seconds, 3),
        "approvable_seconds": None if approvable_seconds is None else round(approvable_seconds, 3),
        "chef_turns": chef_turns,
        "questions": questions,
        "taps": taps,
        "final_state": final_state or "error",
        "cart_lines": saved_lines,
        "lines_in_cart": lines_in_cart,
        "matched": bool(matched),
        "baseline_seconds": baseline_seconds,
        "speed_up": round(speed_up, 3),
    }
    if error_type:
        result["error"] = error_type[:240]
    return result


def run_benchmark(
    base: str,
    buyer: str,
    agent_secret: str,
    approver_secret: str,
    sessions: Iterable[dict[str, Any]] = SESSIONS,
    transport: Callable[..., Any] | None = None,
    label: str = "",
) -> dict[str, Any]:
    session_results = [run_session(session, base, agent_secret, approver_secret, transport=transport)
                       for session in sessions]
    question_values = [result["questions"] for result in session_results]
    approvable = [result["approvable_seconds"] for result in session_results
                  if result["approvable_seconds"] is not None]
    speed_values = [result["speed_up"] for result in session_results]
    median_backend = median(approvable) if approvable else None
    median_speed = median(speed_values) if speed_values else None
    questions_passed = all(value <= 1 for value in question_values)
    backend_passed = median_backend is not None and median_backend < 20.0
    speed_passed = median_speed is not None and median_speed >= 2.0
    gates = {
        "questions_per_session": {"passed": questions_passed, "value": max(question_values, default=0), "threshold": 1},
        "median_backend_seconds": {"passed": backend_passed, "value": median_backend, "threshold": 20},
        "median_speed_up": {"passed": speed_passed, "value": median_speed, "threshold": 2},
        "approvable_sessions": len(approvable),
        "passed": questions_passed and backend_passed and speed_passed,
    }
    return {
        "meta": {"label": label, "base": base.rstrip("/"), "buyer": buyer},
        "sessions": session_results,
        "gates": gates,
    }


def _gate(results: dict[str, Any], *names: str) -> dict[str, Any]:
    gates = results.get("gates") or {}
    for name in names:
        value = gates.get(name)
        if isinstance(value, dict):
            return value
    return {"passed": False, "value": None}


def _display_value(value: Any, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


def render_report(results: dict[str, Any]) -> str:
    meta = results.get("meta") or {}
    sessions = results.get("sessions") or []
    lines = [
        f"# Speed bench — {meta.get('label', '')}",
        "",
        f"- Base: `{meta.get('base', '')}`",
        f"- Buyer: `{meta.get('buyer', '')}`",
        "",
        "| Session | Time (s) | Turns | Questions | Taps | Lines | Final state | Matched? | Speed-up |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | :---: | ---: |",
    ]
    for result in sessions:
        matched = "yes" if result.get("matched") else "no"
        speed = "—" if result.get("speed_up") is None else f"{float(result['speed_up']):.2f}x"
        lines.append(
            f"| {result.get('id', '')} | {float(result.get('total_seconds', 0)):.2f} | "
            f"{result.get('chef_turns', 0)} | {result.get('questions', 0)} | {result.get('taps', 0)} | "
            f"{result.get('lines_in_cart', 0)} | {result.get('final_state', 'error')} | {matched} | {speed} |"
        )

    question_gate = _gate(results, "questions_per_session", "questions")
    backend_gate = _gate(results, "median_backend_seconds", "median_backend_time")
    speed_gate = _gate(results, "median_speed_up", "speed_up")
    overall = bool((results.get("gates") or {}).get("passed"))
    lines += [
        "",
        "## Gates",
        "",
        f"- Questions per session ≤ 1: {'PASS' if question_gate.get('passed') else 'FAIL'} "
        f"(max {_display_value(question_gate.get('value'))})",
        f"- Median backend time to an approvable cart < 20 s: {'PASS' if backend_gate.get('passed') else 'FAIL'} "
        f"({_display_value(backend_gate.get('value'), ' s')})",
        f"- Median speed-up ≥ 2x: {'PASS' if speed_gate.get('passed') else 'FAIL'} "
        f"({_display_value(speed_gate.get('value'), 'x')})",
        "",
        f"Overall: {'PASS' if overall else 'FAIL'}",
    ]
    return "\n".join(lines) + "\n"


def _safe_label(label: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", label.strip()).strip(".-")
    return clean or "local"


def output_paths(label: str) -> tuple[Path, Path]:
    stem = ROOT / "docs/testing" / f"speed-bench-{_safe_label(label)}"
    return Path(str(stem) + ".md"), Path(str(stem) + ".json")


def save_results(results: dict[str, Any], label: str) -> tuple[Path, Path]:
    markdown_path, json_path = output_paths(label)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_report(results), encoding="utf-8")
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return markdown_path, json_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--buyer", default=DEFAULT_BUYER)
    parser.add_argument("--label", default="local", metavar="TAG")
    parser.add_argument("--env", default=os.environ.get("ENV_FILE", str(ROOT / ".env")))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    base = options.base.rstrip("/")
    values = read_env(Path(options.env))
    agent_secret = agent_key(values, options.buyer)
    approver_secret = approver_key(values, options.buyer)
    if not agent_secret:
        raise SystemExit(f"no agent key for buyer {options.buyer!r} in {options.env}")
    if not approver_secret:
        raise SystemExit(f"no approver key for buyer {options.buyer!r} in {options.env}")
    results = run_benchmark(base, options.buyer, agent_secret, approver_secret, label=options.label)
    markdown_path, json_path = save_results(results, options.label)
    gates = results["gates"]
    median_speed = gates["median_speed_up"]["value"]
    print(f"speed-bench {options.buyer}: median speed-up {_display_value(median_speed, 'x')}; "
          f"{'PASS' if gates['passed'] else 'FAIL'}; saved {markdown_path.name} and {json_path.name}")
    return 0 if gates["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
