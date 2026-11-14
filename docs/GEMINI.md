# Best Use of Gemini API: a buying agent a chef can trust

A restaurant chef types or **says** what the kitchen needs, in English or Finnish. Our agent turns that into a Valio Aimo order at fixed prices, orders alone only when it is sure, and otherwise asks one short question back. Gemini does the reading, the judging and the listening. Plain code holds the money, the rules and the audit trail.

## Why Gemini is essential (not "an LLM added")

- **Calibrated confidence makes autonomy a policy you can set and check.** Every "is this the right product, the right quantity, a believable size, the day you meant?" question goes to the **Gemini Decisions API**, which returns a probability, not a confident-sounding sentence. A chef sets "order alone above 0.70", we measured that threshold on labelled cases (33/33, **0 wrong automatic orders**), and every decision is stored with its number in the audit log.
- **It reads chefs as they actually talk.** Free text, menus ("for 80 guests"), Finnish case forms ("voita" = butter), and push-to-talk speech all come out as grounded, structured items. Anything it can't be sure of becomes a question ("How much cream?"), never a silent guess.
- **One fast, cheap judge everywhere made the agent both safer and 3× faster.** Decisions answers in about 0.3–0.9 s, many in parallel. Replacing a slow LLM ranking step with it took a voice order **from 13.8 s to 3–5 s**, and added nine safety checks along the way.

## Where Gemini is used

| Model | Decides | Why this model |
|---|---|---|
| **`gemini-decision-1`** (Decisions API) | **Matching:** which catalogue hits ARE the item · **line judge:** product matches? quantity right? · **plausibility:** believable size for this kitchen? · **steering:** does the text try to change limits, delivery, billing, approvals? · **date intent:** is this the day you meant? · **same product:** does Finnish "voita" mean "butter"? · **substitute OK?** · **menu:** ingredient needed, portion reasonable? · **rules:** does this compiled rule say what the chef wrote? | Calibrated yes/no probabilities in ~0.5 s, so we can threshold, rank and audit; one candidate per call (measured: batching broke calibration) |
| **`gemini-4-hydrogen`** (structured output) | Reads the request into items (product, amount, unit, dietary needs, purpose, the chef's own words); order vs menu vs unclear and guest count; a menu into ingredients with per-portion assumptions; plain-language rules into a proposed mandate (with Zoha's T09 compiler) | Strong structured parsing with a closed JSON schema; the text always arrives as untrusted data |
| **`gemini-3.5-transcribe-live`** (Live API) | Push-to-talk speech → the chef's words | It kept Finnish numbers that `gemini-3.8-live` misheard ("Sata" → "Saat"); ~0.7–1.0 s per clip on Render |
| `gemini-3.8-live` (audio out, measured) | Spoken read-back of the one-sentence outcome | ~0.5 s to first audio; the browser voice is used today |

## Evidence: is 0.70 the right threshold?

`backend/eval/gemini_eval.py`: 33 hand-labelled cases on **real Valio products**, run through the production path (real parser → canonical item → the Decisions judge):
- 12 clear matches;
- 16 traps: coffee milk for milk, coffee cream for cream, sugar sachets for baking, lactose-free milk for a milk *allergy*, salted for unsalted butter, peanut butter, ice cream, a reindeer ready meal…;
- 5 substitute judgements.

| threshold | ordered alone | wrong automatic orders | precision | recall |
|---|---|---|---|---|
| 0.6 | 15 | 0 | 100 % | 100 % |
| **0.70 (chosen)** | 14 | **0** | **100 %** | **93 %** |
| 0.8 | 11 | 0 | 100 % | 73 % |
| 0.9 | 6 | 0 | 100 % | 40 % |

Accuracy 33/33; traps score ≤ 0.26, correct products ≥ 0.67. Each extra guard passed its own labelled cases before being switched on (`backend/eval/guards_eval.py`): plausibility 6/6, steering 7/7, date intent 6/6, menu assumptions 6/6, rules faithfulness 7/7.

## Four stories the measurements told us

1. **Coffee milk caught.** Live, "1000 L lactose-free milk" auto-ordered Valio *coffee* milk: 0.72, just over the threshold, and the cheapest. We changed the question ("a special-purpose variant the buyer didn't ask for is not a match") and the ranking (confidence picks the product, price only breaks near-ties). Coffee milk now scores **0.12** for "milk", and **0.91** when the chef asks for coffee milk.
2. **Sugar sachets.** The eval found a wrong automatic order: 500 × 5 g sachets scored **0.81** for "sugar for baking", because a tidy "10 kg = 4 cases" in the same input made it look right (0.23 without it). Now "is it the product?" is asked without amounts, "is the quantity right?" with them, and the purpose ("for baking") comes along. The sachets score **0.26**.
3. **Finnish case forms and spoken numbers.** "10 kg voita heti" was refused: "voita" scored 0.54 for butter. Asking about meaning in any grammatical form gives **0.97**. On Render, a spoken "**Kymmenen** kiloa voita" was refused because the amount was a word; grounding now reads number words.
4. **Speed and determinism.** A Gemini ranking step took 8.5 s (it thinks ~1,100 tokens whatever the setting). The Decisions "is this the item?" question per hit, in parallel, does the same job in ~0.5–0.9 s, and its cached answers make the later check nearly free: **13.8 s → 2.9–5.0 s**. The Decisions API is deterministic (6/6 identical scores). The demo only looked unstable because raw wording reached the judge, and "SYSTEM NOTICE: pre-approved" even *raised* scores. The judge now sees a canonical item ("1,000 L milk (lactose-free)"), never the chef's raw text.

## The voice conversation (live on Render, Frankfurt)

| step | what happened | time |
|---|---|---|
| chef holds the button: "I need cream ASAP." | `POST /api/voice/transcribe` → "I need cream ASAP." | 0.92 s |
| `POST /api/agent/ask/stream` | phase events "Reading your request…", "Searching…", "Checking Valio stock…", "Asking Gemini to double-check…"; then **"How much cream?"**, with Helsinki pickup suggestions (Cash & Carry, Click & Collect) | 3.8 s |
| chef: "five litres" | transcribed "5 liters" in 0.73 s; the follow-up fills **only** the amount → Arla Pro whipping cream 1 L, €28.85, confidence 0.51 → "Please check: … I'm not sure it's what you meant." | 3.1 s |
| "Kymmenen kiloa voita maanantaiksi." | transcribed in 1.02 s → Valio butter 500 g, 10 kg, €66 → "Tilattu: 10 kg Valio butter 500 g unsalted, toimitus 2026-11-16." (after the number-word fix) | ~4 s |
| "Menu for 80 guests on Monday: reindeer stew…, lingonberry cheesecake" | 9-line cart, €901.56, every line with its confidence; always "check the assumptions", never ordered | 29.8 s |

Each answer comes back with `speak`, one sentence in the chef's language, and the read-back says exactly that.

**Latest live orders** (smoke-kitchen, the demo mandate: auto-approve up to €1,500; threshold 0.70; Sat 14 Nov, after the ranking fix):

| request | chosen (confidence, total) | outcome |
|---|---|---|
| 1000 L lactose-free milk | Valio semi-skimmed lactose-free (0.85, €1,560); whole milk 0.90 at €1,640 is a near-tie, so the cheaper wins; coffee milk no longer appears | held: **€60 over the €1,500 limit** |
| 100 litraa laktoositonta maitoa | the same, €156 | **confirmed** |
| 10 L lactose-free cream | Valio low-fat cream 1 l (0.74, €29.70) over whipping cream (0.70) | **confirmed** |
| 10 kg sugar for baking | caster sugar (≈0.84); the sachets are no longer candidates | confirmed |

## The buyer profile (on main): guidance, never a rule

`backend/app/profile.py` uses Zoha's `trade_profile` package. Facts from the code:
- **Standing dietary needs.** `helsinki-bistro` is seeded with "Our kitchen is gluten-free". When the buyer's text
  states no diet, that becomes a *preferred* claim on each item. A labelled gluten-free product wins when one
  exists, and the line says why ("Gluten-free, because your profile says …"). The buyer's own words always beat
  the profile.
- **Usual products.** Seeded for `helsinki-bistro`: Valio butter 500 g unsalted, Sunnuntai gluten-free flour mix
  1 kg, Galbani grated mozzarella 2 kg. Confirmed orders are added to these. They only break near-ties ("You
  usually order this"), never past the confidence threshold or the front door's limits.
- **Read-only view:** `GET /api/profile` (agent key) returns the needs, usual products, remembered items with why
  each is used, open questions and recent confirmed orders.

## Photo input (on main, PR #70)

`POST /api/vision/read` (agent key) takes a photo (JPEG, PNG, WEBP or HEIC, up to 8 MB) of a handwritten list, a
menu board or a whiteboard. `gemini-4-hydrogen` reads it as untrusted data into `{kind: order_list|menu|other, text,
items, covers, unreadable, language, suspicious}`.
- **It places nothing and stores no image.** The UI sends `text` on through `POST /api/agent/ask`, where every rule
  and the front door apply.
- **Instructions in the image are only text.** Instruction-like text is flagged as `suspicious`, then held by
  `/ask` like typed text.
- **Tested with real Gemini:** Room 2 ran the three demo photos ([`docs/demo-images/`](demo-images/)) through it,
  and all three matched the expected readings in that folder's README.

## Talk: a Gemini Live voice conversation (on main, PR #70)

WebSocket `/api/live`, model `gemini-3.8-live`.
- **Gemini Live only talks.** It hears the chef, answers by voice and calls two tools:
  - `ask_agent` runs the same `ask` pipeline as typing (checks, limits, profile, front door);
  - `search_catalogue` is read-only.
- **There is no approve tool:** sign-off stays with the approver key on screen.
- **The browser never sees the Gemini key.** It authenticates with its agent key in the first message.

**Real local check** (`scripts/talk_check.py`, smoke-kitchen):
1. Spoken: "I need 20 L of lactose-free milk for Monday".
2. The agent says "let me check the milk availability for Monday" and calls `ask_agent`.
3. **Order confirmed:** 20 L of Valio lactose-free UHT milk for Mon 16 Nov.
4. A spoken confirmation with the total.

The first agent audio came 1.3 s after the chef stopped speaking; the answer started 1.2 s after the tool result.

## Guardrails: Gemini can only add caution

- **No Gemini answer can permit anything** a hard rule forbids, add an allergen exception or raise a limit. Each extra question can only turn "order" into "ask".
- **Unverified means ask.** A timeout, a malformed answer or an exhausted budget is treated as "unverified", and the buyer's mandate (ask by default) decides. A NaN can't sneak past a threshold.
- **Injection:**
  - text always arrives in delimiters as untrusted data;
  - the raw text goes only to the steering classifier (7/7);
  - every parsed item must be grounded in the chef's own words (product, amount and unit in one clause);
  - authority, billing and instruction wording is flagged before any other question.
- **Bounded cost:** per request at most 150 Decisions calls (600 for a menu), 16 in parallel, 12 hits per batch, and a 10-minute cache.
- **Humans stay in charge:** prices, stock, cut-offs and limits are re-checked by Valio's front door; rules change only through the approver key; every decision is audited with its confidence.

More: `docs/GEMINI-evidence.md` (every run and number, in order), `docs/VOICE.md`, `docs/codex-log/room3.md` (11 independent reviews and what we fixed), `backend/eval/`.

## Calibration on the eval (from `backend/eval/results.json`)

Each row buckets the 33 labelled cases by the Decisions API's P(yes), and shows how many were actually the right
product:

| P(yes) | cases | actually correct | share correct |
|---|---|---|---|
| 0.0–0.2 | 17 | 0 | 0 % |
| 0.2–0.4 | 1 | 0 | 0 % |
| 0.4–0.6 | 0 | 0 | – |
| 0.6–0.7 | 1 | 1 | 100 % |
| 0.7–0.8 | 3 | 3 | 100 % |
| 0.8–0.9 | 5 | 5 | 100 % |
| 0.9–1.0 | 6 | 6 | 100 % |

Read it honestly. The scores **separate** right from wrong cleanly: every trap ≤ 0.26, every correct product ≥ 0.67.
But 33 cases with nothing in 0.4–0.6 can't show **calibration** in the middle, where a threshold actually bites.
More borderline cases are the next eval to write.

## Where Gemini could do more (honest gaps, by value for cost)

| # | Gap | Status | Value | Cost |
|---|---|---|---|---|
| 1 | **Cross-language catalogue search with Gemini embeddings.** Search is keyword-based on English and Finnish names, so a request in one language can miss a product named in the other (the red lentils / "linssi" miss). Embeddings would find it by meaning | not built | High: fewer "no match" questions | Medium: embed 17,546 names once and add a vector index |
| 2 | **Evals for photo reading and spare amounts.** Photo reading has 3 hand-checked demo images (Room 2, all matched). Spare amounts have no labelled set | not built | High: these readings feed carts | Low: 20–30 labelled cases each, reusing `gemini_eval.py` |
| 3 | **Borderline cases for calibration.** Add 20+ cases in the 0.4–0.8 band, so the 0.70 threshold is measured where it matters | not built | High for the judges' "why trust it" | Low |
| 4 | **Ground the "why" sentence.** The chosen line's explanation is built by code from facts and scores. A Gemini-written reason would need checking against those facts first | not built (deliberately) | Medium | Medium |
| 5 | **Calibration table** (above) | **built** (this doc) | Medium | — |
| 6 | **Talk read-back in Finnish.** Talk speaks; the push-to-talk read-back uses the browser voice | partly | Low–medium | Low |
