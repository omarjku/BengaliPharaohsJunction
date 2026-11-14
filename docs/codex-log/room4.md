# Codex log: Room 4 (UI), branch `room4-auth`

## 2026-11-14 · Run 1: draft the auth UI + Codex findings
- **Command:** `codex exec -s workspace-write -m gpt-reserve -c model_reasoning_effort=max` (codex-cli 0.169.0)
- **Cost:** 135,379 tokens, 9 min 20 s
- **Ask:** in `frontend/src` only:
  - a Keys panel (agent key and approver key, stored in localStorage with try/catch) and an in-module key store in `api.ts`;
  - `X-Agent-Key` sent on run, `X-Approver-Key` on approve, reject and audit;
  - chef-readable 401/403/503 errors;
  - the approver-name input removed (the name now comes from the key);
  - audit fetched without `buyer_id`;
  - `RequestItem.amount`/`unit` and `Line.quantity` made nullable;
  - the stock label changed to "Stock availability unknown";
  - `mock.ts` brought into line.
- **Result:** every point was implemented, and build and lint passed.
- **Kept:** the key store, the headers, the auth error messages, approve/reject without a body, the hint when there is no approver key, the nullable types and their rendering, the label, and the mock updates.
- **Changed or rejected:**
  - The audit log refetched on every keystroke in either key field. Keys now apply on a "Save keys" submit.
  - localStorage loading had been a side effect inside a `useState` initializer in `App.tsx`. Loading and saving moved into `api.ts`, and keys are trimmed on save.
  - The 401/403 message for agent calls dropped the backend detail, so the reason was lost. The detail is kept now.
  - A three-way ternary for item text became `[amount, unit, query].filter(x => x !== null).join(' ')`.

## 2026-11-14 · Run 2: adversarial review of `frontend/src`
- **Command:** `codex exec -s read-only -m gpt-5.6-terra -c model_reasoning_effort=ultra -o review-out.md`
- **Cost:** 179,599 tokens
- **Ask:** hunt for real defects only, in five areas:
  - response fields the backend can omit, null, or rename;
  - auth headers and key leaks, and behaviour when localStorage throws;
  - React state bugs and races;
  - mock mode leaking into prod builds;
  - layout at 375px.
- **Findings and what I did:**
  1. **High:** `POST /api/agent/run` has no agent-key check and trusts `buyer_id` (`backend/app/main.py:252`). **Real, but backend.** Left to the backend owners (the control room says it lands within the hour) and flagged to the control room. The UI already sends `X-Agent-Key`.
  2. **Medium:** `VITE_MOCK=1` turns on mocks in a production build. **Rejected:** that is the intended switch for a mock deploy. Production builds without it contain no fixtures (checked by grepping the bundle).
  3. **Low:** the health request in `App.tsx` was never cancelled, so in StrictMode a late failure could overwrite a success. **Fixed:** a cancelled flag, and the error is cleared on success.
  4. **Low:** `AuditLog.actorLabel` split on `:`, but approver names may contain `:`. **Fixed:** an anchored regex, `^human:(.+?)(?::(approve|reject))?$`, so the action is read from the end.
- No issues in the other areas: no null mismatches, no keys in URLs or error text, localStorage failures handled, no double submit, and focus and aria-live intact.

## 2026-11-14 · Run 3 (M2, background, didn't block): review of the M2 UI diff
- **Command:** `codex exec -s read-only -m gpt-5.6-terra -c model_reasoning_effort=high`
- **Cost:** 72,044 tokens
- **Ask:** check the new rendering against the backend shapes:
  - substitutes and `alternative_order` (`gate.py`, `orders.py`);
  - line and decision confidence (`agent.py`);
  - the "Use this order" re-POST (body, `X-Agent-Key`);
  - React state bugs.
- **Finding:** `line.facts` isn't emitted by `agent.py`, so it would never render. **Rejected as out of date:** Codex reviewed the branch before `origin/omar/m1-integration` was merged in. After the merge, Room 1's PR #15 emits `facts: {delivery_reliability, carbon_kg_per_kg, origin}` (`agent.py:396`), which is exactly what the UI reads.
- Nothing else found: no null crashes, the request body and headers are right, no double submit or stale order.
- **Drafting:** I wrote this change myself, not Codex.
