# Chat Agent Safety Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep chat ordering at least as safe as the engine for Valio's milk example and preserve real proposal state on timeout.

**Architecture:** Keep the engine as the source of fit, quantity, price, and hold decisions. Pass the chef's raw turn text into chat-triggered engine Decisions checks, rank read-only chat search results with request fit/amount/availability before price, and make confirmation explicit rather than a confidence override.

**Tech Stack:** Python, asyncio, FastAPI, pytest, Gemini Decisions, Valio quote adapter.

**Spec:** User-provided urgent task in this conversation.

## Global Constraints

- Work only in `/Users/omar/Code/bpj-coffee`; do not commit or push.
- Original chef words are the source for steering, product-fit, plausibility, and confirmation safety.
- Existing hold and on-screen approval rules remain in force.
- Run the full backend suite and `git diff --check` before reporting.

## Review Focus

- A model-specific rewrite such as coffee milk must be judged against the chef's milk request and held as an assumption when unsupported.
- A follow-up “yes” selects a named suggestion but must not raise its confidence.
- A 19-second timeout after a card exists must report that card's real state.
- LEGO/MacBook requests must be declined before date clarification or tools.
- Search must prefer a fit-for-request, deliverable amount before a cheaper special-purpose variant.

### Task 1: Regression tests

**Files:**
- Modify: `backend/tests/test_chat_agent.py`
- Modify: `backend/tests/test_agent.py` if an engine-level raw-text seam needs direct coverage.

- [ ] Add failing tests for raw-word propagation/no `meant=1.0`, fit-first search, timeout state reporting, and early non-food decline.
- [ ] Run the focused tests and verify each fails for the current implementation.

### Task 2: Raw-word engine seam and confirmation safety

**Files:**
- Modify: `backend/app/chat_agent.py`
- Modify: `backend/app/agent.py` only if needed to carry an optional chat decision text into fit/plausibility checks.

- [ ] Store the chef's raw turn/request text in `_TURN` and pass it to `agent.run`/Decision checks.
- [ ] Treat an unsupported model-named product as an assumption; remove the confirmation-path confidence lift while preserving holds.
- [ ] Run the focused raw-word and confirmation tests.

### Task 3: Chat search, timeout, and non-food behavior

**Files:**
- Modify: `backend/app/chat_agent.py`

- [ ] Rank search results by request fit, amount/availability, then price, using the raw request where available.
- [ ] Format timeout replies from an existing proposal/order card instead of asking the chef to continue.
- [ ] Return the one-line Valio food-service scope reply before model/date handling for clear non-food requests.
- [ ] Run focused tests and then the full backend suite.

### Task 4: Real verification

**Files:**
- No source changes.

- [ ] Start a local server with a fresh temporary `DATA_DIR`, `SANDBOX_ENABLED=1`, and keys loaded without printing them.
- [ ] Run the exact Valio sentence for both requested buyers, follow the shown suggestion with “yes”, and run the LEGO request.
- [ ] Record first suggestion, confidence, final status, and the non-food reply; run `git diff --check`.
