# Gemini in Front Door

This document describes the Gemini calls that exist on the release branch. The API
key is read only by the backend; the browser receives transcripts, structured results,
and decision reasons, never the key. When a call is unavailable or malformed, the
caller either uses its documented deterministic fallback or returns an ask/retry
response. Prices, stock, quantities, dates, mandates, and approvals are not delegated
to Gemini.

## Models and call paths

The default model settings are in `backend/app/config.py`:

| Model | Code path | Gemini returns | What the code does with it |
|---|---|---|---|
| `gemini-4-hydrogen` | `agent.parse` | `{summary, items[]}`: catalogue query, amount, unit, dietary tags, source words, and purpose | Normalises and grounds each item in the chef's text, then runs deterministic catalogue search, quantity conversion, quotes, and gate checks. If unavailable, `agent.fallback_parse` and lexical search are used and the response says so. |
| `gemini-4-hydrogen` | `ask.classify` | `{intent: order\|menu\|unclear, covers, topic}` | Validates the guest count against the words actually written, routes to the order or proposal flow, and falls back to deterministic intent detection. |
| `gemini-4-hydrogen` | `understand.understand` | A list of validated actions with intent, slots, question/choices, answer, or reply | Supplies the v2 conversation router with the last turns, current card, profile, and pending question. Sanitisation and deterministic checks run before an action can change a cart. If it fails, the deterministic v1 fallback runs. |
| `gemini-4-hydrogen` | `menu.parse_menu` | Dishes and ingredients with per-cover amount, unit, dietary tags, and assumption text | Scales ingredients to the stated covers, applies profile/diet/pantry rules, quotes products, and always returns a proposal requiring chef confirmation. There is no menu-to-order fallback when the menu cannot be read. |
| `gemini-4-hydrogen` | `agent.assume_amount` | One proposed amount, natural unit, and short assumption | Validates the amount with the catalogue unit table and quantity resolver. It is held as an assumption; it never auto-orders. |
| `gemini-4-hydrogen` | `agent.spare_proposals` | A spare percentage (0–20) and reason per menu ingredient | Clamps the proposal, scales it by the kitchen's explicit spare level, accounts for pack rounding, and shows it on the proposal. Direct orders only offer spare as a visible suggestion. |
| `gemini-4-hydrogen` | `expand.queries` | Up to four short English/Finnish catalogue queries | Cleans, de-duplicates, and adds the queries to deterministic catalogue search; on failure it keeps the original query. |
| `gemini-4-hydrogen` | `diet.at_risk` | Risky ingredient/diet pairs plus conservative evidence (`safe_by_nature`, reason, certainty) | Uses the result only to identify checks. Missing or unusable output is strict: the product is not treated as safe by nature. Catalogue claims and allergens remain the evidence used for the final decision. |
| `gemini-4-hydrogen` | `profile.from_about` | Onboarding fields plus `unclear` sentences: kitchen, delivery days, standing orders, diets/allergens, usual products, budget, and notes | Validates and previews the facts. Nothing is saved until the approver confirms. Unmapped text is retained as notes. |
| `gemini-4-hydrogen` | `kitchen.log_from_text` | Validated kitchen-log entries and `unclear` text | Validates dates, covers, revenue, leftovers, and notes, then appends only valid entries to the buyer's kitchen log. |
| `gemini-4-hydrogen` | `rules.RestLLM` through `trade_compiler` | A proposed mandate matching the compiler's JSON schema | The compiler may retry once after schema validation, then falls back to an open-question mandate. The approver reviews the diff and must save it; this call cannot change a live mandate. |
| `gemini-4-hydrogen` | `vision._read` | `{kind, text, items, covers, unreadable, language, instructions}` for a JPEG/PNG/WEBP/HEIC photo | Strips instruction-like text, marks the photo suspicious when needed, returns only text, and sends no order. The UI passes the checked text to `/api/agent/ask`; pantry items are passed to a menu proposal for that request only. |
| `gemini-decision-1` | `agent.match` / `_judge_one` | Typed `noul` answers with a probability for `meets`, `qty`, or `sub` | Scores each catalogue candidate separately so calibration is preserved. The code uses the weakest relevant probability, ranks candidates by confidence, and only lets price/preferences break a near-tie. |
| `gemini-decision-1` | `agent.judge_line` | `meets` and `qty` probabilities for a chosen product/quantity | Judges the product without amounts and the quantity with the resolver explanation. A low or missing score holds the line for review. |
| `gemini-decision-1` | `agent.same_product` | Probability that the chef's source words and English catalogue term name the same product | Checks translations and inflected Finnish forms such as `voita`; a low or unavailable result asks instead of silently ordering. |
| `gemini-decision-1` | `agent.plausible` | Probability that the order size is believable for the kitchen | Only adds caution for an implausibly large quantity; it can never permit a hard-rule violation. |
| `gemini-decision-1` | `agent.steering` | Probability that raw text tries to change limits, delivery, billing, approvals, or authority | Runs on the untrusted raw request. At/above the configured threshold, the order is held and the instruction is ignored. |
| `gemini-decision-1` | `agent.date_intent` | Probability that the deterministic delivery date is the date the chef meant | Runs only when relative/date words are present and can only add a date question. |
| `gemini-decision-1` | `menu.check_assumptions` | `needed` and `amount` probabilities per menu ingredient | Uses the weaker probability to flag a recipe assumption for the chef. It never auto-confirms a menu cart. |
| `gemini-decision-1` | `rules.faithful` | Probability that each compiled rule says what the chef wrote | Low scores become open questions in the mandate preview; saving still requires the approver. |

All structured calls use JSON response schemas, temperature 0, untrusted text
delimiters, and a short successful-response cache. The Decisions calls use the
`/v1beta/decisions` endpoint, typed questions, a ten-minute cache, and per-request
budgets (`150` for an order-sized run and `600` for a menu). Calls are concurrent but
each candidate gets its own input; batching candidates into one calibrated question is
deliberately avoided.

## Gemini Live

`GEMINI_LISTEN_MODEL` defaults to `gemini-3.5-transcribe-live`.
`POST /api/voice/transcribe` decodes a browser recording to 16 kHz mono PCM, rejects
empty/silent/too-long input before the network call, and sends one manual-activity turn
to Gemini Live. The response is the chef's transcript plus the model and duration. The
code normalises spoken number words such as Finnish `Sata`/`Kymmenen` into digits where
possible, and the UI sends the transcript to `/api/agent/ask`. This route places
nothing.

`GEMINI_TALK_MODEL` defaults to `gemini-3.8-live`. WebSocket `/api/live` gives the live
model the kitchen profile and read-only/search tools plus `ask_agent`, which invokes the
same `/api/agent/ask` pipeline. It may also read the current order, kitchen context,
profile, and log a chef report. There is no approve tool: a human uses the approver-key
screen. Talk is limited to a five-minute session and two concurrent sessions per buyer.

`backend/scripts/voice_spike.py` is a standalone developer probe, not a serving route.
When invoked, it opens the same Gemini Live endpoint with the selected model (default
`gemini-3.8-live`) to inspect audio behaviour; it does not place orders or write app
state.

## What is measured, and what is not

The labelled product evaluation in `backend/eval/gemini_eval.py` contains 33 cases and
is run with real Valio catalogue products. The current documented demo threshold is
0.70 for the seeded demo buyers and their sandbox copies; unknown buyers use the
conservative 0.80 default. The checked traps include coffee milk versus milk, coffee cream versus cream,
sugar sachets for baking, dietary mismatches, and salted versus unsalted butter. The
repository contains the recorded evaluation output, but live acceptance numbers are
not inferred from it.

The latest real-Gemini release acceptance report is `/tmp/acceptance-release-1.md`:
7/12 flows passed. Failures included a 25 kg butter correction becoming pack count,
ambiguous usual-product selection, duplicate protection firing on questions/changes,
loss of an added item after a follow-up, and a party request without choices. TODO:
rerun the real-Gemini acceptance after the parallel release fixes; no post-fix score is
claimed in this document.

## Safety boundary

Gemini can add uncertainty; it cannot relax a mandate, invent a product id/price/stock,
override an allergen or cut-off, approve a cart, or change an approver-controlled rule.
Every response is validated by Python before it reaches the catalogue, quantity
resolver, Valio quote, gate, order store, or audit entry. A timeout, malformed answer,
budget exhaustion, or invalid probability is treated as unverified and follows the
buyer's uncertainty policy.

Further evidence and run logs: [`GEMINI-evidence.md`](GEMINI-evidence.md),
[`VOICE.md`](VOICE.md), [`backend/eval/`](../backend/eval/), and the photo fixtures in
[`demo-images/`](demo-images/).
