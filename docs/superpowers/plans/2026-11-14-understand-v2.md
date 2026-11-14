# Understand v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a validated, context-aware understand layer and wire multi-action text and Talk requests through the existing safe purchasing pipelines.

**Architecture:** `understand.py` performs one cached structured reading or a regex fallback and returns sanitized actions. `ask.py` guards the raw request, executes actions independently, preserves legacy card fields, and records turns/cards. Existing agent/menu safety and Room 2 behavior remain the execution core.

**Tech Stack:** Python 3.14, asyncio, FastAPI, existing Gemini/Decisions adapters, pytest.

**Spec:** `docs/superpowers/specs/2026-11-14-understand-v2-design.md` and `docs/design/ENGINE-PLAN.md`.

## Global Constraints

- Full verification: `cd backend && .venv/bin/python -m pytest -q tests` with exit code 0.
- Do not touch `gate.py`, `orders.py`, `auth.py`, `mandates.py`, numbers, `frontend/`, or `profile/`.
- Do not change Room 2 diet/search parts of `menu.py`/`agent.py`.
- Never print keys; never commit `data/`; do not commit or push.
- Keep old response fields and follow-up behavior; all v2 response fields are additive.

## Review Focus

- A malformed or hostile Gemini action must fall back or be rejected without bypassing grounding; pin with schema-validation and injection tests in `test_understand_v2.py`.
- A correction containing both old and final amounts must execute only the final amount; pin with the butter and pizza-size tests.
- One failed action in a multi-action request must not cancel successful sibling actions; pin with a parallel gather test.
- A stale/foreign conversation file must not supply turns or a last card; pin with conversation TTL/ownership tests.
- A cart question must not invoke catalogue/order code and must answer only from the compact card; pin with the two cart-question tests.

### Task 1: Understand schema, validation, and fallback

**Files:**
- Create: `backend/app/understand.py`
- Test: `backend/tests/test_understand_v2.py`

**Interfaces:**
- Produces: `async understand(message: str, buyer_id: str, turns: list[dict], last_card: dict | None, today: date) -> dict` and `understand_fallback(...) -> dict`.
- Consumes: `agent._gemini`, `agent.UNTRUSTED`, `agent.DIETARY`, `profile.context`, `kitchen.kitchen_context`, and the existing date/cover fallback helpers.

- [ ] Write tests for the closed actions schema, context prompt, Helsinki date, thinking budget, date/guest/unit/diet validation, correction finalization, five-action cap, and Gemini-down fallback.
- [ ] Run `cd backend && .venv/bin/python -m pytest -q tests/test_understand_v2.py` and observe the expected missing-module failures.
- [ ] Implement the schema/prompt and compact context payload; use the existing `_gemini` cache with `{"thinkingBudget": 0}` and a compatibility call shape for current test fakes.
- [ ] Implement deterministic sanitization and fallback action construction; reject invalid dates/guests, map dietary labels, cap text, and turn more-than-five actions into one “which first?” question with three choices.
- [ ] Re-run the focused tests and verify they pass.

### Task 2: Conversation turns and compact cards

**Files:**
- Modify: `backend/app/conversation.py`
- Test: `backend/tests/test_understand_v2.py`

**Interfaces:**
- Produces: `turns(buyer_id)`, `last_card(buyer_id)`, and an atomic append/save helper under `DATA_DIR/conversations`.
- Consumes: the existing follow-up store and response bodies from `ask.py`.

- [ ] Add buyer-scoped JSON files, 30-minute TTL pruning, ten-turn retention, compact card projection, bounded text, and atomic `os.replace` writes without changing the follow-up `STORE` contract.
- [ ] Add tests for role/text/time order, expiry, bounded retention, card projection, and buyer-file isolation.
- [ ] Run the focused conversation tests before wiring callers.

### Task 3: v2 routing, parallel action execution, and response compatibility

**Files:**
- Modify: `backend/app/ask.py`
- Test: `backend/tests/test_understand_v2.py` plus existing ask tests

**Interfaces:**
- Consumes: `understand()` and conversation helpers.
- Produces: v2 `understood`, `reply`, `cards`, and `choices`; legacy first-card fields; action execution for order, meal/period plan, urgent, cart ask/change, kitchen log, greeting, out-of-scope, and unrealistic.

- [ ] Add red tests for every Room 3 transcript row: three-action parallel execution with an isolated failure, over-five question, final-amount/size corrections, kitchen answer/log, vegan meal cart, next-Monday period planning, cart questions without search, cart re-price, LEGO, 50-million guests, greeting, urgent today, fallback, injection stop, and old follow-ups.
- [ ] Run the focused tests and confirm they fail for the missing v2 route.
- [ ] Run steering/instruction/billing checks before understand; adapt sanitized order actions into `agent.run` pre-parsed items so the understand call is not duplicated by agent parsing, and adapt menu actions into the existing menu pipeline.
- [ ] Execute actions with `asyncio.gather` wrappers that convert individual exceptions to friendly error cards; merge the first card to the old top-level response and append the user/reply/card after completion.
- [ ] Implement card-only cart answers, changed-line re-pricing, kitchen logging, realistic choices, and date/guest questions while preserving `_finish` and follow-up IDs.
- [ ] Run `tests/test_understand_v2.py tests/test_ask.py tests/test_assume.py tests/test_live.py` and fix regressions without changing protected modules.

### Task 4: Decisions batching and Talk contract

**Files:**
- Modify: `backend/app/agent.py` (only Decisions-call grouping seams, not diet/search logic)
- Modify: `backend/app/live.py`
- Test: `backend/tests/test_understand_v2.py`, existing live tests

**Interfaces:**
- Produces: grouped steering/date/plausibility Decisions requests where input text is identical; Talk `say` prefers `reply` and its system prompt grounds cart answers in tool results.

- [ ] Add a grouping test showing identical guard input uses one `_decisions` request and keeps one candidate per input.
- [ ] Extend the existing grouping helper/call sites minimally, preserving calibration for distinct candidate inputs and existing Decisions fallbacks.
- [ ] Update `live.ask_agent` and `SYSTEM` additively; keep current kitchen tools/security/warm-session behavior.
- [ ] Run focused live/grouping tests.

### Task 5: Full verification and protected-file audit

**Files:**
- Verify only the requested backend files and tests.

- [ ] Run `cd backend && .venv/bin/python -m pytest -q tests`.
- [ ] Run `git diff --check`, inspect changed paths, confirm protected files and `data/` were not edited, and do not commit or push.

