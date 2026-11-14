# Text Chat Gemini Agent Implementation Plan

> **For agentic workers:** Native execution in this worktree; no sub-agents and no commit per the user request.

**Goal:** Make text chat a Gemini tool-calling agent with grounded cards, safe fallback, and the existing approval UI.

**Architecture:** Add `backend/app/chat_agent.py` with a bounded `generateContent` loop and thin adapters over existing pipelines. Add `/api/agent/chat`, switch the text composer to it, and normalize cards at the UI boundary.

**Tech Stack:** FastAPI/Python, Gemini REST `generateContent`, existing async engine, React/TypeScript/Vite.

**Spec:** `docs/superpowers/specs/2026-11-14-chat-agent-design.md`

## Global Constraints

- Work only in `/Users/omar/Code/bpj-chat`, branch `chat-agent`.
- Keep `/api/agent/ask` unchanged.
- At most 6 Gemini tool calls per message and 25 seconds total.
- No approval tool; order cards require an actual tool result.
- Use Helsinki date and quoted kitchen data; never let data become instructions.

## Review Focus

- Gemini emits prose claiming an order without a tool result → no order card.
- Gemini asks to approve → no approval action is dispatched.
- A tool/API failure → `/api/agent/ask` fallback still answers.
- A follow-up repeats a request → duplicate guard is bypassed only through the existing conversation context.
- A pending/confirmed order change → old order is rejected only through existing change logic before the merged cart is rerun.

### Task 1: Backend chat loop and tools

**Files:** Create `backend/app/chat_agent.py`; test `backend/tests/test_chat_agent.py`.

- [ ] Write fake-Gemini tests for tool dispatch, approval refusal, grounded cards, and fallback.
- [ ] Run them red.
- [ ] Implement schemas, prompt/data envelope, REST loop, tool dispatch, compact history recording, card normalization, timeout, and `/ask` fallback seam.
- [ ] Run the focused tests green.

### Task 2: HTTP endpoint and CLI

**Files:** Modify `backend/app/main.py`, `scripts/chat.py`; test endpoint behavior in `backend/tests/test_chat_agent.py`.

- [ ] Add `ChatRequest` and `POST /api/agent/chat` with the agent dependency/rate limiting.
- [ ] Make CLI `--mode chat` the default and retain `--mode ask`.
- [ ] Run focused backend tests and a CLI smoke invocation.

### Task 3: Frontend response adapter

**Files:** Modify `frontend/src/api.ts`, `frontend/src/App.tsx`, `frontend/src/types.ts`.

- [ ] Add the chat API type/function and use it for text sends.
- [ ] Convert returned full cards into the existing `AskResponse` union for current card components; show `reply` as the agent bubble.
- [ ] Run frontend lint and build.

### Task 4: Full verification and real loop

- [ ] Run the required offline suite exactly.
- [ ] Run frontend lint/build.
- [ ] Run the six requested real scripts, iterate only on prompt/tool behavior, and record latency and excerpts.
- [ ] Self-review the diff and report unverified/unsafe items.
