# Kitchen-context planning and Gemini Live warm sessions

## Intent

Use the buyer's existing kitchen history as a transparent default for event/week menu requests without silently changing explicit guest counts, and make the existing Gemini Live connection warm-up safe under idle, concurrency, and promotion limits.

## Goals

- Expose Room 2's buyer-scoped `kitchen_context()` and use weekday averages or the week's sum when a planning request has no guest count.
- Keep the assumption visible in plain language, identify `covers_source: "kitchen"`, mention recent leftovers without subtracting them, and let explicit guest counts remain authoritative.
- Accept `warm: true` on Live auth, open Gemini at auth, send the existing `ready` event, expire an untouched warm session after 60 seconds, and start `SESSION_S` only at its first audio/text message.
- Keep origin checks, auth-first behavior, signed-buyer refusal, rate limits, shielded tool work, and the existing non-warm protocol unchanged.

## Non-goals

- No automatic leftover subtraction, ordering from a menu proposal, new frontend protocol, or changes to protected backend modules.
- No changes to `frontend/`, `profile/`, `gate.py`, `orders.py`, `auth.py`, `mandates.py`, or `profile.py`.

## Approaches

The kitchen module is ported from the already-present `origin/omar/m1-integration` ref because the managed worktree cannot write Git's `FETCH_HEAD`/`ORIG_HEAD`; the merge command was attempted and failed before changing files. Context selection stays in `ask.py`, where the existing menu pipeline already handles parsing, pricing, assumptions, and explicit covers. Warm-session state stays in `live.py`, with separate warm slots and real-session counts so promotion is the only point where a warm socket consumes the per-buyer cap.

## Response shape

Context-backed menu responses retain the current menu response and add:

- `covers_source: "kitchen"`
- `covers_assumption`: a sentence such as `Using 80 covers: your usual Friday.`
- `kitchen_leftovers`: the recent context leftovers, with a note that they were not subtracted automatically

Explicit covers skip these context defaults; a buyer with no usable covers context still receives the current `For how many guests?` follow-up.
