#!/usr/bin/env python3
"""Fail-loud Gemini REST canary: one Gemini 3 function round trip and one Decisions request."""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for package in ("contracts", "compiler", "profile", "backend"):
    sys.path.insert(0, str(ROOT / package))


def redacted(value) -> str:
    return re.sub(r"(?i)(x-goog-api-key|api[_-]?key)\s*[:=]\s*[^,\s}]+", r"\1=[redacted]", str(value))[:800]


async def call(client, url, key, body):
    response = await client.post(url, headers={"x-goog-api-key": key}, json=body)
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {redacted(response.text)}")
    return response.json()


async def main() -> int:
    from app import agent, config

    key = config.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not key:
        print("canary failed: GEMINI_API_KEY is not configured", file=sys.stderr)
        return 1
    client = agent._http()
    tool = {"functionDeclarations": [{"name": "canary_echo", "description": "Echo the supplied value.",
                                       "parameters": {"type": "OBJECT", "properties": {"value": {"type": "STRING"}},
                                                      "required": ["value"]}}]}
    first = {"role": "user", "parts": [{"text": "Call canary_echo with value hello."}]}
    try:
        first_response = await call(client, f"{agent.GEMINI_URL}/{config.GEMINI_MODEL}:generateContent", key,
                                    {"contents": [first], "tools": [tool],
                                     "generationConfig": {"thinkingConfig": {"thinkingLevel": "low"}}})
        model_content = first_response["candidates"][0]["content"]
        calls = [part["functionCall"] for part in model_content["parts"] if "functionCall" in part]
        if len(calls) != 1 or not calls[0].get("name"):
            raise RuntimeError("function-calling round trip returned no single function call")
        call_data = calls[0]
        function_response = {"name": call_data["name"], "response": {"value": "hello"}}
        if call_data.get("id") is not None:
            function_response["id"] = call_data["id"]
        second = await call(client, f"{agent.GEMINI_URL}/{config.GEMINI_MODEL}:generateContent", key,
                            {"contents": [first, model_content,
                                          {"role": "user", "parts": [{"functionResponse": function_response}]}],
                             "tools": [tool],
                             "generationConfig": {"thinkingConfig": {"thinkingLevel": "low"}}})
        if not second.get("candidates"):
            raise RuntimeError("function-calling response had no candidate")
        decisions = await call(client, agent.DECISIONS_URL, key,
                               {"model": config.GEMINI_DECISION_MODEL, "input": "Score the canary assumption.",
                                "questions": {"canary": {"type": "noul", "instructions": "Is 1+1=2?",
                                                           "criteria": {"true_description": "yes", "false_description": "no"}}}})
        if not isinstance(decisions.get("answers", {}).get("canary"), dict):
            raise RuntimeError("Decisions response did not contain canary answer")
    except Exception as exc:  # noqa: BLE001 - the canary must fail loudly
        print(f"canary failed: {redacted(exc)}", file=sys.stderr)
        return 1
    print(json.dumps({"function_call": call_data["name"], "decisions": decisions["answers"]["canary"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
