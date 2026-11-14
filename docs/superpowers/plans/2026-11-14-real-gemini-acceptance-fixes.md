# Real Gemini Acceptance Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the v2 engine reach one honest, approvable cart in fewer turns for standing orders, changes, cart questions, product ties, mixed requests, menus, injections, and vague events.

**Architecture:** Keep deterministic parsing, catalogue resolution, Decisions confidence, and the front-door gate authoritative. Extend the existing understand → action → agent/menu pipelines so standing-order data is stated data, pending questions are superseded by new intent, cart answers use the compact chosen card, and partial menus expose coverage instead of claiming readiness.

**Tech Stack:** Python 3, FastAPI, pytest, existing fake-Gemini seams, catalogue/Valio fixtures, trade contracts.

**Spec:** `docs/design/ENGINE-SPEC.md`

## Global Constraints

- Every input gets a cart, one precise question, a real-data answer, a friendly redirect, or a safe refusal with a fix.
- Assumptions never auto-confirm. Only the chef's own words or an approval tap can confirm them.
- Standing-order quantities are the chef's own data and are not per-line clarification questions.
- Deterministic validation remains authoritative for dates, units, catalogue matches, limits, and approval.
- Injection content is untrusted data; pure injection is refused and flagged, while a legitimate order in the same message is still processed and held.
- Menu coverage is explicit: every ingredient is in the cart, in `check_lines`, or named as not found.
- The existing safety intent and complete pytest suite must remain green.

## Review Focus

- A saved Friday order with an extra unquantified product produces one combined held cart and at most one missing-value question.
- A replacement request supersedes a pending question and changes the current cart line rather than repeating the question.
- Cart questions report the chosen line quantity/status, never search candidates.
- Usual products, past orders, and above-threshold Decisions confidence prevent needless product-choice questions while leaving alternatives visible.
- Mixed legitimate order plus steering text strips only the steering clause; pure steering remains refused.

### Task 1: Acceptance checker contract fixes

**Files:**
- Modify: `scripts/acceptance_flows.py`
- Test: `scripts/tests/test_acceptance_flows.py`

**Interfaces:**
- Preserve the public `check_flow_turn()` and flow report format.
- F1 amount failure detection must only match product-search failure wording (`doesn't seem to stock` or `stock `), not every occurrence of “stock”.
- F9 must interpret a count-sales-unit milk line as the requested base volume (`1000 ST` of a 1 L product equals `1000 L`).
- F10 must accept the existing scale explanation with no cart.

- [ ] Write checker regressions for the three false negatives.
- [ ] Run the focused checker tests and verify they fail for the current implementation.
- [ ] Implement only the checker predicate changes.
- [ ] Run the focused checker tests and verify they pass.

### Task 2: Standing orders and pending-intent supersession

**Files:**
- Modify: `backend/app/understand.py`, `backend/app/ask.py`, `backend/app/conversation.py` only if state projection requires it.
- Test: `backend/tests/test_ask.py`, `backend/tests/test_understand_v2.py`, `backend/tests/test_assume.py`

**Interfaces:**
- `_expand_standing_order()` returns all saved lines plus named extras in one action; standing items retain their stored amount/unit without `amount_assumed`.
- `_parsed_action()` marks standing quantities as chef-stated data while preserving the no-auto-approval gate for assumptions elsewhere.
- `ask.ask()` keeps an interrupted pending entry when the new message is a real request, and consumes it only when the answer is actually for that question.

- [ ] Add fake-Gemini tests for all standing lines plus `plus pasta`/`add milk` in one cart, one approval hold, and one amount question only for a genuinely missing extra.
- [ ] Add a follow-up regression where “actually, oat milk instead” re-matches the current milk line and drops the moot pending question; assert an honest not-found path when no plant candidate exists.
- [ ] Run the new tests to verify they fail for per-line standing assumptions and repeated pending questions.
- [ ] Implement the smallest state/data-flow change that distinguishes saved quantities from inferred quantities and prioritizes new change/order actions.
- [ ] Run focused tests and the existing follow-up/safety tests.

### Task 3: Current-cart answers, product tie choices, and multi-intent replies

**Files:**
- Modify: `backend/app/ask.py`, `backend/app/agent.py`, `backend/app/understand.py`
- Test: `backend/tests/test_ask.py`, `backend/tests/test_assume.py`

**Interfaces:**
- `_cart_reply()` reads compact card `lines`/`order` chosen quantities and status, with no catalogue search.
- Product selection keeps up to three alternatives on the card and explains a usual/profile or sufficient-confidence winner instead of converting a grounded winner into a choice question.
- Independent `ask_kitchen` actions may accompany an order action and their reply is labelled simulated where the source is simulated context.

- [ ] Add fake-Gemini tests for “How much milk is in the cart?”, usual-product tie breaking, and order-plus-last-Friday guests.
- [ ] Run them red.
- [ ] Implement chosen-line quantity/status rendering, tie-basis reasoning, and reply aggregation without weakening approval safety.
- [ ] Run focused tests plus product-confidence and kitchen-context tests.

### Task 4: Injection splitting and safe legitimate-order handling

**Files:**
- Modify: `backend/app/ask.py`, `backend/app/agent.py`, `backend/app/menu.py` if shared guard text needs a safe helper.
- Test: `backend/tests/test_ask.py`, `backend/tests/test_front_door_security.py`, `backend/tests/test_assume.py`

**Interfaces:**
- A request containing a legitimate order and steering clause produces the legitimate cart with a visible ignored-instruction note and remains unconfirmed/held.
- A message with no legitimate order remains refused and flagged before ordering.
- Existing instruction/billing/authority safety tests remain unchanged in intent.

- [ ] Add mixed-order injection and pure-injection regressions with fake Gemini/Decisions.
- [ ] Run them red.
- [ ] Move request-level steering handling after safe intent extraction and strip only steering clauses from the text passed to product resolution; add the note to the response/decision.
- [ ] Run all front-door security tests and focused acceptance tests.

### Task 5: Complete menu coverage and vague-event choices

**Files:**
- Modify: `backend/app/menu.py`, `backend/app/diet.py`, `backend/app/ask.py`, `backend/app/conversation.py` if spoken coverage text needs a menu-specific branch.
- Test: `backend/tests/test_diet.py`, `backend/tests/test_menu.py`, `backend/tests/test_ask.py`

**Interfaces:**
- Vegan/naturally suitable ingredients such as plain wheat flour and olive oil are retained as cart or explicit check lines; only genuinely at-risk ingredients require dietary evidence.
- `cart_coverage` and the user-facing reply state exact in-cart/check/not-found coverage; partial coverage never says `Cart ready`.
- A vague event produces a single question with 3–4 tappable choices or a proposed menu.

- [ ] Add fake-Gemini menu tests covering all ingredients, plain flour/oil diet behavior, honest partial coverage, and party choices.
- [ ] Run them red.
- [ ] Implement diet risk defaults and coverage response changes, then add deterministic event-choice fallback.
- [ ] Run focused menu/diet/ask tests.

### Task 6: Full verification

**Files:**
- No production changes expected.

- [ ] Run `pytest` from `backend/` with `PYTHONPATH=$(pwd)/contracts:$(pwd)/compiler:$(pwd)/profile` using the requested venv.
- [ ] Run `pytest` for `scripts/tests/test_acceptance_flows.py` and the relevant backend regressions.
- [ ] Run a final diff/status review and report exactly twelve lines, including tests and the uncommitted status.

