#!/usr/bin/env python3
"""End-to-end check for the text kitchen interview and saved Friday standing order."""
import argparse
import json
import os
import sys
import urllib.request


def _env_key(variable: str, buyer: str) -> str:
    value = os.environ.get(variable, "")
    if value:
        return value
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        line = next(line for line in open(env_path, encoding="utf-8") if line.startswith(variable + "="))
    except (OSError, StopIteration):
        return ""
    for entry in line.split("=", 1)[1].strip().split(","):
        key, _, owner = entry.partition("=")
        if owner.split(":", 1)[0] == buyer:
            return key
    return ""


def _request(base: str, path: str, payload: dict | None, headers: dict) -> dict:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(base + path, data=body, headers={**headers, "Content-Type": "application/json"},
                                     method="POST" if body is not None else "GET")
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8777")
    parser.add_argument("--buyer", default="smoke-kitchen")
    parser.add_argument("--in-process", action="store_true", help="use the FastAPI app directly when sockets are unavailable")
    args = parser.parse_args()
    agent_key = _env_key("AGENT_KEYS", args.buyer)
    approver_key = _env_key("APPROVER_KEYS", args.buyer)
    if not agent_key or not approver_key:
        raise SystemExit(f"could not find keys for {args.buyer}; set AGENT_KEYS and APPROVER_KEYS or pass .env keys")
    agent_headers = {"X-Agent-Key": agent_key}
    approver_headers = {"X-Approver-Key": approver_key}
    if args.in_process:
        from fastapi.testclient import TestClient
        from app import catalogue
        from app.main import app

        catalogue.load()
        client = TestClient(app)

        def request(path, payload, headers):
            response = client.request("POST" if payload is not None else "GET", path, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    else:
        def request(path, payload, headers):
            return _request(args.base, path, payload, headers)

    answers = []
    responses = []
    realistic = {
        "kitchen": "We are a 60-seat gluten-free bistro in Helsinki.",
        "delivery_days": "We can receive deliveries Monday through Friday.",
        "standing_orders": "Our usual Friday order is 20 L milk, 10 kg butter, and 5 L cream.",
        "dietary_allergens": "The kitchen is gluten-free and has a peanut allergy.",
        "usual_products": "We usually buy Valio milk, Valio butter, and Valio cream.",
        "budget": "A typical order budget is 1,500 euros.",
        "anything_else": "That is all.",
    }
    for _ in range(8):
        response = request("/api/profile/interview/next", {"answers": answers}, agent_headers)
        responses.append(response)
        if response.get("done"):
            break
        topic = response.get("topic")
        if topic not in realistic:
            raise AssertionError(f"unexpected interview topic: {topic!r}")
        answers.append({"topic": topic, "text": realistic[topic]})
    else:
        raise AssertionError("interview did not finish")

    preview = responses[-1]["preview"]
    proposed = {item["id"]: item["value"] for item in preview["proposed"]}
    assert proposed["covers"] == 60, proposed
    assert proposed["delivery_days"] == ["monday", "tuesday", "wednesday", "thursday", "friday"], proposed
    assert "peanuts" in proposed["allergens"], proposed
    assert proposed["spend_comfort"] == 1500, proposed
    friday = next(order for order in proposed["standing_orders"] if order["weekday"] == "friday")
    assert {line["text"] for line in friday["lines"]} == {"20 L milk", "10 kg butter", "5 L cream"}, friday

    saved = request("/api/profile/onboarding", {"answers": proposed, "confirm": True}, approver_headers)
    assert saved["stored"] is True, saved
    profile = request("/api/profile", None, agent_headers)
    history = request("/api/kitchen/history", None, agent_headers)
    profile_friday = next(order for order in profile["standing_orders"] if order["weekday"] == "friday")
    history_friday = next(order for order in history["standing_orders"] if order["weekday"] == "friday")
    for row in (profile_friday, history_friday):
        assert {line["text"] for line in row["lines"]} == {"20 L milk", "10 kg butter", "5 L cream"}, row

    usual = request("/api/agent/ask", {"text": "my usual Friday order"}, agent_headers)
    cards = usual.get("_v2", {}).get("cards", [])
    rendered = json.dumps(usual, ensure_ascii=False).lower()
    assert all(term in rendered for term in ("20 l", "10 kg", "5 l", "milk", "butter", "cream")), usual
    assert not any(card.get("question") for card in cards), usual
    print(json.dumps({"preview": proposed, "profile_friday": profile_friday, "history_friday": history_friday,
                      "usual_status": usual.get("status"), "usual_cards": len(cards)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        print(f"HTTP {error.code}: {detail}", file=sys.stderr)
        raise
