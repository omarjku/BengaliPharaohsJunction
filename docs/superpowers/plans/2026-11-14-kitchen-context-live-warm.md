# Kitchen Context and Live Warm Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make context-backed menu planning and safe Gemini Live pre-warming work together with focused regression coverage.

**Architecture:** Port the existing Room 2 kitchen history module and seed, then keep a small context-selection adapter in `ask.py` that feeds the existing `menu.propose` path and annotates its response. Extend `live.py` with warm-slot bookkeeping, first-message promotion, an idle timer, and a real-session timer while leaving the current tool and security paths intact.

**Tech Stack:** Python 3, FastAPI WebSockets, asyncio, pytest, existing Gemini/Valio adapters.

**Spec:** `docs/superpowers/specs/2026-11-14-kitchen-context-live-warm-design.md` plus the user request in this task.

## Global Constraints

- Full verification command: `cd backend && .venv/bin/python -m pytest -q tests` and exit code must be 0.
- Additive only; preserve the prior uncommitted worktree changes and do not commit or push.
- Do not touch `gate.py`, `orders.py`, `auth.py`, `mandates.py`, `profile.py`, `frontend/`, or `profile/`.
- Never print keys or other secrets.
- Existing non-warm Live protocol/security behavior remains unchanged.

## Review Focus

- Context exists but the requested weekday has no usable average: retain the guest-count question instead of guessing.
- Week request with partial weekday data: sum only usable weekday averages and say the assumption plainly.
- Explicit guest count supplied after a context default: explicit input wins and is not marked as kitchen-sourced.
- A warm socket receives only Gemini output: idle budget still closes it because only client audio/text starts real time.
- Two warm sockets promote concurrently when the real cap is full: exactly the promoting socket is refused with 4429 and warm sockets never block a cold real session.

### Task 1: Port kitchen context and wire context-backed menu requests

**Files:**
- Create: `backend/app/kitchen.py`
- Create: `backend/app/kitchen_seed.json`
- Modify: `backend/app/ask.py`
- Test: `backend/tests/test_kitchen_flow.py`

**Interfaces:**
- Consumes: Room 2 `kitchen.kitchen_context(buyer_id)` with `covers.avg_per_weekday`, `leftovers_recent`, and existing buyer-scoped history.
- Produces: context-backed menu responses with `covers_source`, `covers_assumption`, and `kitchen_leftovers`; explicit covers and no-context requests retain current behavior.

- [ ] **Step 1: Write failing tests**

  Add tests using a fake `ask.kitchen_context` and a fake `menu.propose` that prove:

  - `what do we need for Friday` uses that weekday's average, routes to the menu path, returns `covers_source == "kitchen"`, and includes `Using <n> covers: your usual Friday` plus recent leftovers without subtracting them.
  - `food for next week` uses the sum of usable weekday averages and marks the response as kitchen-sourced.
  - An empty context still returns the existing `For how many guests?` question.
  - An explicit `covers` override wins over the fake context.

- [ ] **Step 2: Run the focused tests and verify the expected RED failure**

  Run: `cd backend && .venv/bin/python -m pytest -q tests/test_kitchen_flow.py`

  Expected: failures because the current flow has no kitchen context adapter and no context response fields.

- [ ] **Step 3: Add Room 2 kitchen data and the minimal ask adapter**

  Port the existing `kitchen.py` and `kitchen_seed.json` from the available `origin/omar/m1-integration` ref. Import the module in `ask.py`, detect only food/menu/needs/week planning phrases, select a stated weekday average or the week's sum, and call the existing `menu.propose` only when a usable context cover count exists. Add the response metadata and leftover note; keep explicit covers authoritative and leave the current guest follow-up for no context.

- [ ] **Step 4: Run the focused kitchen tests and verify GREEN**

  Run: `cd backend && .venv/bin/python -m pytest -q tests/test_kitchen_flow.py tests/test_ask.py`

  Expected: all focused tests pass, including the pre-existing no-guest menu behavior.

### Task 2: Add warm Live lifecycle and concurrency tests

**Files:**
- Modify: `backend/app/live.py`
- Test: `backend/tests/test_live.py`

**Interfaces:**
- Consumes: the existing `session(ws)` auth/security flow and FakeLive setup socket.
- Produces: `warm: true` auth support, `WARM_IDLE_S`-controlled idle close, first-audio/text promotion, separate warm-cap bookkeeping, and unchanged non-warm behavior.

- [ ] **Step 1: Write failing tests**

  Extend `tests/test_live.py` with FakeLive coverage for warm idle close (code 1000 plus the exact idle error), first-message session-clock start, warm sockets not consuming the two-real-session cap, refusal when a warm socket promotes into a full real cap, and dropping the oldest socket when a fourth warm socket arrives.

- [ ] **Step 2: Run the focused Live tests and verify the expected RED failure**

  Run: `cd backend && .venv/bin/python -m pytest -q tests/test_live.py`

  Expected: the new tests fail because `warm` is currently ignored and there is no warm idle/promotion bookkeeping.

- [ ] **Step 3: Implement the minimal warm state machine in `live.py`**

  Keep auth, origin, signed-buyer, rate-limit, and setup checks in their current order. Register up to three warm slots per buyer after auth, close the oldest on a fourth, do not increment `_open` until the first validated audio/text message, and refuse promotion with `_close(..., 4429, ...)` if the real cap is full. Run a warm idle timer before promotion and start the existing `SESSION_S` wait only after promotion; retain the current non-warm timer and cleanup semantics.

- [ ] **Step 4: Run the Live tests and verify GREEN**

  Run: `cd backend && .venv/bin/python -m pytest -q tests/test_live.py`

  Expected: all existing and new Live tests pass.

### Task 3: Full verification and protected-file audit

**Files:**
- Verify: `backend/app/kitchen.py`, `backend/app/kitchen_seed.json`, `backend/app/ask.py`, `backend/app/live.py`, `backend/tests/test_kitchen_flow.py`, `backend/tests/test_live.py`

- [ ] **Step 1: Run the complete backend test suite**

  Run: `cd backend && .venv/bin/python -m pytest -q tests`

  Expected: exit code 0.

- [ ] **Step 2: Inspect the final diff and protected-file status**

  Run: `git diff --check && git diff --name-only && git status --short --untracked-files=all`

  Expected: only the requested backend/tests/docs plan files are changed or newly added, with no protected file edits, no key output, and no commit/push.
