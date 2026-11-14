# Gemini opening: the coffee-milk story

Every number below is from `backend/eval/results.json` (recomputed with a short script), except the 0.72, which is
labelled "from our notes".

## What the data says

- Rows 25 and 26 ("1000 L lactose-free milk" and the Finnish "100 litraa laktoositonta maitoa" against Valio coffee milk 1 l
  lactose free UHT, a wrong product): `p_yes` = 0.115 for both. The app floors this to **11%** (`pct` in
  `frontend/src/copy.ts` uses `Math.floor`), so say "about 0.12" or "0.115", never "12%".
- Row 27 (coffee cream for lactose-free cream): 0.141. Row 24 (Starbucks coffee milk drink for coffee milk, wrong): 0.036.
- Row 10 (coffee milk when the chef asked for coffee milk, right): 0.907. Row 0 (plain lactose-free milk, right): 0.897.
- 33 cases (28 "is it the product", 5 "is it an acceptable substitute"): 15 right, 18 wrong. Wrong 0.01 to 0.26 (highest
  0.2566), right 0.67 to 0.97 (lowest 0.668). At 0.70: 14 handled alone, 0 wrong. At 0.80: 11 alone, 73% recall.
- The 0.72 is not in any saved file. It exists only as prose in `docs/GEMINI.md` and `docs/GEMINI-evidence.md`. Label it
  "from our notes".

## Honest framing (keep)

- 0.72 was above the 0.70 line, so calibration did not stop it. Our QA caught it. We then reworded the question.
- Both coffee numbers (0.72 and 0.115) are single-candidate calls. Only the wording changed. This is not the 0.51 versus
  0.95 batching story (separate; do not mix).
- The 33 cases include the trap, and the wording was tuned on them. It shows separation after tuning, not held-out proof.

## Opening, about 15 s spoken (about 55 words)

"Our agent once picked coffee milk for a 1,000-litre lactose-free milk order. Gemini scored it 0.72, from our notes, above
our 0.70 line, so our own QA caught it, not the calibration. We reworded the question; the same product now scores 0.115.
On our 33 labelled cases, no wrong product went through at 0.70."

## Opening, about 40 s spoken

"A chef orders 1,000 litres of lactose-free milk. For each product, Gemini Decisions answers one question: is this what was
asked for, as a probability. Early on, Valio coffee milk, the cheapest, scored 0.72, from our notes. That is above our 0.70
line, so it would have been ordered alone. Our QA caught it, not the calibration. We reworded the question and let
confidence, not price, pick the product. Now the same coffee milk scores 0.115, the app shows 11%, and plain
lactose-free milk scores 0.897. Anything under 0.70 goes to a human. We turned it into a labelled trap among 33 cases: wrong
products scored 0.26 or less, right ones 0.67 or more, and at 0.70 nothing wrong was ordered. We tuned on those same cases,
so held-out ones are the next step."

## The story in 5 plain sentences

1. A chef asks for 1,000 litres of lactose-free milk, and for each Valio product Gemini answers one yes/no question: is this
   what was asked for.
2. Valio coffee milk is lactose-free and the cheapest, and Gemini once gave it 0.72 (from our notes), just above our 0.70
   line, so it would have been ordered without asking.
3. Our own QA caught that, not the calibration, and we changed the question and made confidence lead over price.
4. The same wrong product now scores 0.115 (the app shows 11%) and plain lactose-free milk scores 0.897, so anything under
   0.70 goes to a human.
5. It is now a labelled trap among 33 cases, where wrong products score 0.26 or less, right ones 0.67 or more, and none of
   the wrong ones is ordered alone at 0.70.

## Placement

- `docs/SUBMISSION.md` line 67, the blank line right after the heading `## Best Use of Gemini: the four answers` (line 66),
  before the "Gemini proposes, code decides" paragraph at line 68. Insert the 15 s text as one bold line.
- First slide: use the 15 s text, headline "coffee milk 0.72 (from our notes) to 0.115".
- Video: the 15 s text as the first 10 s of the Gemini cut (after the hook if the same 2:00 video).
