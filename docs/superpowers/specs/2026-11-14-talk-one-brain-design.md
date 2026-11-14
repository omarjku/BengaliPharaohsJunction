# Talk One Brain Design

## Intent

Make Talk/Gemini Live use the same Gemini function-calling brain as text chat, so voice orders, assumptions, kitchen facts, cards, and safety behavior stay aligned while keeping the existing WebSocket client protocol and interview mode.

## Goals and constraints

- Order-mode Live uses `chat_agent.TOOLS`, `chat_agent._dispatch_tool`, and the same quoted kitchen data (profile/standing orders, current orders, kitchen context, Helsinki date).
- Voice order execution is always held through the voice origin marker and retains the per-turn steering/auto-approval guard.
- No approve tool is exposed; interview mode remains on `interview.TOOLS` and its existing session behavior.
- Keep `transcript`, `tool`, `result`, `audio`, `interrupted`, and `turn_complete` event shapes unchanged.
- Minimize `chat_agent.py` changes to stable exports only; do not change the text-chat loop.
- Reduce latency with a short pre-tool filler, compact tool responses, low Live thinking, and the fast order-engine settings already supported by the engine.

## Approaches

1. Call the HTTP chat endpoint from Live: rejected because it adds a second model turn and cannot preserve Live-native tool timing.
2. Duplicate the chat registry and dispatch logic in Live: rejected because it recreates the drift that caused the bug.
3. Reuse the chat registry and dispatcher directly from Live: selected because it gives exact tool parity with the smallest change; Live remains responsible for audio, transcripts, protocol events, and interview mode.

## Design

`live.py` imports the chat agent and aliases its tool declarations for order-mode setup. Its Live system prompt remains voice-specific but appends `chat_agent._quoted_data(...)` as quoted data and describes the shared tools. On each order-mode Live tool call, it sets the chat agent's per-turn guard from the chef transcript, dispatches through `_dispatch_tool`, returns a compact tool result to Gemini, and emits the raw returned card as the existing `result.payload` when present. The voice dispatch passes the voice origin to the order engine so `ASSUMPTION_CONFIRM` holds every voice order.

The check script runs the requested three-turn smoke flow and the Helsinki standing-order flow against an isolated local server, printing transcripts, tool events, card statuses, and end-to-end timings.

## Non-goals

No frontend protocol changes, no new approval action, no replacement of interview behavior, no commits or pushes, and no unrelated refactors.
