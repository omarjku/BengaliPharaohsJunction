# Talk One Brain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. No sub-agents or commits are authorized for this task.

**Goal:** Make Gemini Live use the text chat agent's tools, knowledge, safety guard, and card results while meeting the voice latency checks.

**Architecture:** Keep the Live WebSocket/audio loop and interview branch. In order mode, import the chat agent's declarations and dispatcher, append its quoted kitchen data to the Live prompt, and adapt dispatcher results to the unchanged client protocol.

**Tech Stack:** Python, FastAPI WebSocket, Gemini Live, existing `chat_agent`/engine, pytest, macOS `say`/`afconvert`.

**Spec:** `docs/superpowers/specs/2026-11-14-talk-one-brain-design.md`

## Global Constraints

- Work only in `/Users/omar/Code/bpj-talk`, branch `talk-one-brain`.
- Do not commit or push; do not use sub-agents.
- Keep `chat_agent.py` changes to minimal exports only.
- Keep the client protocol and interview mode unchanged.
- Voice orders remain held via `via='voice'` and `ASSUMPTION_CONFIRM`; expose no approve tool.

## Review Focus

- A tool call before a user transcript arrives must still use a safe guard and never auto-approve.
- A dispatcher result with a card must remain a frontend-shaped `AskResponse`, while non-card tools stay compact.
- A follow-up turn must preserve the Live conversation and current order context.
- Interview setup/tools must remain byte-for-byte behaviorally equivalent.
- Live setup must use low thinking without breaking the configured model's accepted schema.

### Task 1: Lock order-mode parity and guard contracts

**Files:**
- Modify: `backend/tests/test_live.py`
- Modify: `backend/app/live.py` only if a minimal export alias is required
- Modify: `backend/app/chat_agent.py` only if a stable public alias is required

**Interfaces:**
- Consumes: existing `chat_agent.TOOLS`, `chat_agent._dispatch_tool`, `_tool_card`, and `_TURN`.
- Produces: tests that define tool-name parity, quoted data, voice hold, guard propagation, compact results, and unchanged interview tools.

- [ ] Write failing fake-Live tests for setup parity, quoted Helsinki data, direct dispatch, voice-origin holding, guard propagation, and card payload shape.
- [ ] Run the focused tests and verify they fail for the old `ask_agent` path.
- [ ] Implement the smallest order-mode reuse seam and preserve interview mode.
- [ ] Run the focused tests and verify they pass.

### Task 2: Add the speed path and real voice checker

**Files:**
- Modify: `backend/app/live.py`
- Modify: `scripts/talk_check.py`

**Interfaces:**
- Consumes: Task 1's direct Live dispatcher and existing WebSocket event protocol.
- Produces: filler-before-tool behavior, low-thinking setup, compact tool responses, and a CLI 3-turn smoke script with timing output.

- [ ] Add a failing test that requires the filler instruction/config and compact tool response.
- [ ] Run it red, then implement the minimum speed changes.
- [ ] Extend `scripts/talk_check.py` for the requested isolated local server and both buyers/flows, printing first-audio and spoken-result timings.
- [ ] Run the real local Gemini check on port 8795; iterate on model/tool behavior until the transcript and target timings are correct or record the exact blocker.

### Task 3: Full verification

**Files:**
- No additional files.

- [ ] Run the requested backend suite with the exact environment and command.
- [ ] If frontend files remain untouched, record frontend build/lint as not needed; otherwise run both.
- [ ] Review the diff for scope, protocol compatibility, and accidental edits; confirm no commit/push.
