# Understand v2 engine design

## Intent

Give text and Talk one front-door interpretation step that can recognize several requests in one chef message, resolve dates and corrections, and provide enough context for safe execution. The existing catalogue, quantity, Decisions, gate, approval, and order/menu pipelines remain the enforcement core.

## Goals

- Make one cached Gemini structured-output reading per normal message, with the last turns, last compact card, profile, kitchen context, and Helsinki date.
- Validate Gemini data in code; route only sanitized actions, with a deterministic fallback when the reading is unavailable or invalid.
- Execute up to five independent actions in parallel and preserve the current order/menu response fields at the top level for the first action.
- Add cart questions, cart changes, kitchen logging, greetings, out-of-scope replies, and realistic handling of absurd scales without searching or ordering when those paths do not require it.
- Keep existing follow-up conversations, injection/steering checks, Room 2 diet/search/language behavior, and protected backend modules unchanged.

## Non-goals

- No changes to `gate.py`, `orders.py`, `auth.py`, `mandates.py`, `frontend/`, or `profile/`.
- No diet suitability, search expansion, alternatives-ranking, or language-lock changes in Room 2 code.
- No silent learning from `tell_kitchen`; logging is explicit and buyer-scoped.
- No commit, push, key output, or data-file commit.

## Chosen approach

`understand.py` owns the closed schema, context prompt, output validation, correction normalization, and offline fallback. `ask.py` runs the existing steering/instruction guards first, calls `understand()` once, then adapts each action to `agent.run`, `menu.propose`, `kitchen.log_from_text`, or a local card-only response. A single action keeps the legacy `order`/`menu`/`question`/`speak` fields; v2 metadata is additive. Multiple cards are returned in `cards`, while the first card is merged back to the top level.

Conversation history is a separate buyer-scoped atomic store under `DATA_DIR/conversations`, with 30-minute expiry and ten retained turns plus a compact last card. Talk continues to call `ask.ask`; its model summary prefers the new `reply` field and is explicitly told to ground cart answers in tool results.

## Validation and safety calls

Gemini output is treated as data. Dates are restricted to today through today + 60 days, guests to 1–2000, units and dietary tags to existing closed sets, and all user-facing text is length-capped and stripped of markup/control characters. Duplicate corrected items keep the final occurrence; explicit numeric corrections are normalized before grounding so superseded amounts cannot create extra order lines. The raw message still passes through the existing instruction, billing, steering, grounding, mandate, quantity, and front-door checks.

## Response contract

The response adds `understood` (`intent`, sanitized `slots`, `source`, and an interpretation note), `reply`, `cards`, and `choices`. Existing order/menu body fields remain present on the first card. Cardless actions return a friendly `reply`; amount choices continue to appear in the existing `options` field as well as the v2 `choices` shape.

