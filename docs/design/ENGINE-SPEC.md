# Engine spec: any input, a usable answer, at least twice as fast as the webshop

Owner: control room. Sat 14 Nov, 17:40. This is the target every Codex job and every battle test is measured against.

## The goal (Omar)
A head chef gets the ingredients into a confirmed or approvable cart **at least twice as fast as on Valio's webshop**, for any input, by text or voice. The webshop baseline is about 30–45 s per line: search, open the product, set the amount, add to cart. So a 6-line usual order takes about 3–4 minutes. Target: **one utterance plus one tap, under 60 s end to end**, and no dead ends.

## Every input gets exactly one of these outcomes, never anything else
1. **A cart** (confirmed, or held for one tap) with every assumption written on it.
2. **One precise question** with 2–4 tappable answers, in the right unit, about the single thing that blocks the cart.
3. **An answer**, for questions about the order, the kitchen, prices or availability, taken from real data.
4. **A friendly redirect**, for clearly non-food requests only; misheard or garbled speech gets "Sorry, I didn't catch that", never a refusal.
5. **A safe refusal with a fix**, for hard rules (allergen, cut-off passed, over limit → held), saying what would work.

Never: an empty cart without an explanation, "I can only help with Valio" for food talk, a language refusal, an order the chef didn't approve, or data called simulated when it's the chef's own.

## Three prongs, in this order, for every message
1. **Deterministic first (fast, exact, no model):**
   - numbers, units and pack sizes
   - dates in en/fi/sv plus weekday names ("next week" → next Monday)
   - catalogue search with synonyms (plant drinks, Finnish names)
   - the kitchen's standing orders and usuals
   - the conversation state (the current cart)
   - the front door's hard rules
2. **Gemini understanding (meaning):** one structured call with the message, the last turns, the current cart, the full profile (onboarding plus learned facts plus standing orders) and the kitchen context.
   - It returns a list of actions with slots, the interpretation (self-corrections resolved) and which slots it ASSUMED versus which the chef STATED.
   - Code validates every slot against the deterministic layer; Gemini can't invent ids, prices or amounts.
3. **The Gemini Decisions API (confidence):** one batched request scoring each interpretation, product match and assumed amount.
   - High confidence and stated by the chef: auto within limits.
   - Assumed, or below the threshold: held for one tap, or one question.

Assumptions never auto-confirm. Only the chef's own words or tap confirm. The voice model can't approve.

## The kitchen's knowledge, used everywhere
- **Onboarding** can be done by voice: "tell me everything about your restaurant" for up to 5 minutes. Gemini extracts every fact, including **standing orders (weekday plus lines)**, usual products, diets, allergens, suppliers' habits, delivery days, covers and budget comfort. The chef confirms "Here's what I'll remember". Nothing said is dropped: unparsed sentences are kept as notes, never thrown away.
- **Every path reads the profile:** text ask, menu, Talk (in its system prompt at session start) and the tools.
- **Source labels per fact:** "you told me (onboarding, 14 Nov)", "from your orders", "simulated demo history". Only the simulated history is called simulated.

## Battle tests (backend only, no browser)
- `scripts/edge_eval.py` with Gemini grading: about 154 cases plus Omar's two phone transcripts, multi-turn.
- `scripts/speed_bench.py` (new): scripted chef sessions (usual order plus extras, a menu for N, a correction mid-sentence, a question about the cart, an urgent order). It counts turns and taps to an approvable cart and the wall time, against the 30–45 s per line webshop estimate.
- **Gates for main:**
  - edge eval ≥ 85% overall and 100% on safety
  - no session in speed_bench needs more than 1 question
  - median time to an approvable cart under 20 s of backend time
  - the existing pytest suite stays green
