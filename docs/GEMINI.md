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

## Photo input (pending merge, Room 2 + Room 4)

A chef photographs a handwritten list, a chalkboard menu or a whiteboard. Gemini reads it into the same structured
items as typed text, and from there the normal pipeline runs: grounding, Decisions judge, Valio quotes, the front
door. A photo is treated like the chef's own words, so a menu photo always asks, like a pasted menu. Test images:
[`docs/demo-images/`](demo-images/). The model, the route and the live numbers go here after the merge.

## Talk: a Gemini Live voice conversation (pending merge, Room 3 + Room 4)

A spoken back-and-forth instead of push-to-talk: the chef talks, the agent answers aloud and asks its one
follow-up question ("How much butter?"), and the order goes through the same front door. The models, latency and
live results go here after the merge.

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
