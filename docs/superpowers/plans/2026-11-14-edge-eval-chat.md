# Edge Chat Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an honest current Gemini-graded J1/J2 estimate from `/api/agent/chat`, including regression coverage, manual corrections, latency, and failure analysis.

**Architecture:** Keep `/api/agent/ask` as a compatible transport and add a chat transport/normalizer in `scripts/edge_eval.py`. Grade the normalized observable answer after each turn, then render endpoint-specific JSON and Markdown reports. Add only corpus and evaluator tests; the backend remains unchanged.

**Tech Stack:** Python stdlib HTTP client, pytest, JSON/Markdown reports, local uvicorn, real Gemini.

**Spec:** `docs/superpowers/specs/2026-11-14-edge-eval-chat-design.md`

## Global Constraints

- Work only inside `/Users/omar/Code/bpj-eval`.
- Do not commit or push.
- Never print or persist API keys.
- Use a fresh `DATA_DIR`, `SANDBOX_ENABLED=1`, and the main repo `.env` only for the real local run.
- No Valio catalogue sweeps.

## Review Focus

- Chat follow-up payloads must distinguish a new text turn from an answer to a pending question: test both shapes.
- Chat cards must retain product names, amounts, assumptions, decisions, and order status in the grading view: test normalization.
- A multi-turn case that passes on its first response must report zero corrections: test the metric.
- A multi-turn case that never passes must be visible as unresolved and must not bias the resolved mean: test the metric.
- Reports must keep the full selected-case denominator and top-ten failure details: test rendering.

### Task 1: Chat transport and metrics

**Files:**
- Modify: `scripts/edge_eval.py`
- Test: `scripts/tests/test_edge_eval.py`

**Interfaces:**
- Produces `chat_payload(text, conversation_id=None, pending=False)`, `chat_front_door(...)`, `compact_chat_answer(...)`, `manual_correction_metrics(...)`, and `latency_metrics(...)`.

- [ ] **Step 1: Write failing tests** for chat payload shapes, chat response normalization, zero/one/unresolved manual corrections, and median turn latency.
- [ ] **Step 2: Run `pytest scripts/tests/test_edge_eval.py -q` and verify the new tests fail for missing interfaces.**
- [ ] **Step 3: Implement the smallest endpoint adapter, normalized chat view, per-turn grading data, and metrics.** Add `--endpoint {chat,ask}` with default `chat`; use endpoint-specific output stems (`edge-eval-chat-<date>` by default).
- [ ] **Step 4: Run `pytest scripts/tests/test_edge_eval.py -q` and verify it passes.**

### Task 2: Regression corpus and report rendering

**Files:**
- Modify: `docs/testing/edge-cases.json`
- Modify: `scripts/edge_eval.py`
- Test: `scripts/tests/test_edge_eval.py`

- [ ] **Step 1: Write a corpus test** asserting the new phone-regression IDs are unique and each has a non-empty written pass rule.
- [ ] **Step 2: Run the focused test and verify it fails before the cases exist.**
- [ ] **Step 3: Add the exact phone regression cases and render endpoint, latency, manual-correction, Gemini-estimate, chef-text, outcome, and likely-root-cause fields; cap failure detail at the top ten.**
- [ ] **Step 4: Run the focused script tests and the corpus validation dry run.**

### Task 3: Real local evaluation and verification

**Files:**
- Create: `docs/testing/edge-eval-chat-2026-11-14.json`
- Create: `docs/testing/edge-eval-chat-2026-11-14.md`

- [ ] **Step 1: Start uvicorn from this worktree on a free port with a fresh temporary `DATA_DIR`, `SANDBOX_ENABLED=1`, and the main repo `.env`; keep keys out of output.**
- [ ] **Step 2: Run the full corpus through `--endpoint chat`; if runtime exceeds 40 minutes, run every group with a bounded `--limit` and document that limitation.**
- [ ] **Step 3: Inspect JSON/Markdown for denominator, group totals, endpoint/commit, manual-correction distribution, median latency, and ten failure entries.**
- [ ] **Step 4: Run the backend gate with `PYTHONPATH=<worktree>/contracts:<worktree>/compiler:<worktree>/profile`, `GEMINI_API_KEY=` and the repository’s offline test command.**
