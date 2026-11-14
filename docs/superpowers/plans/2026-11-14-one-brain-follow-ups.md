# One Brain Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Route pending-question replies through the v2 understanding call while preserving deterministic validation and assumption safety.

**Architecture:** Add bounded pending-question context and follow-up action types to `understand.py`. `ask.py` will peek the pending entry, interpret the answer once, execute validated date/amount/product/choice/confirm/reject actions through the existing v2 pipeline, and retain the entry for unrelated new requests. `_answer()` remains the no-Gemini fallback.

**Tech Stack:** Python, FastAPI, pytest, existing Gemini structured-output seam, existing catalogue/quantity/gate/order pipeline.

**Spec:** `docs/design/ENGINE-SPEC.md`

## Global Constraints

- Every input gets a cart, one precise question, a real-data answer, a friendly redirect, or a safe refusal with a fix.
- Deterministic validation remains authoritative for dates, units, catalogue matches, limits, and approval.
- Assumptions never auto-confirm; only chef words or an approval tap can confirm them.
- The existing safety tests in `backend/tests/test_assume.py` must remain green.

## Review Focus

- Approval clauses beginning with “no” must still confirm an assumed proposal: follow-up regression tests.
- Final self-corrections must use the final amount: understand and follow-up regression tests.
- An unrelated request must not consume the old pending question: follow-up regression test.
- A date phrase at the end of the week must resolve to a valid future date: date regression test.
- A missing weekday on a usual-order request must choose or ask from standing orders: standing-order regression tests.

### Task 1: Structured pending context

**Files:**
- Modify: `backend/app/understand.py`
- Test: `backend/tests/test_understand_v2.py`

- [ ] Extend the schema, payload, prompt, and normalizer for `confirm`, `answer`, and `reject` actions plus bounded pending context.
- [ ] Add fake-Gemini tests proving pending context is sent and answer actions are preserved.
- [ ] Run the focused understand tests.

### Task 2: Primary follow-up execution and standing orders

**Files:**
- Modify: `backend/app/ask.py`, `backend/app/conversation.py`
- Test: `backend/tests/test_ask.py`, `backend/tests/test_assume.py`

- [ ] Peek pending entries, call `understand()` once with the answer and context, and retain old entries for new requests.
- [ ] Validate and execute follow-up action slots using existing helpers and `_flow()` without `_product_words()` on the primary path.
- [ ] Extend date handling and no-weekday usual-order expansion.
- [ ] Add the requested phone-line regressions, confirmation variants, correction, unrelated request, and safety coverage.
- [ ] Run focused tests, then the complete backend suite.

No commit: the user explicitly requested an uncommitted worktree.
