# Codex log: Room 3 (Agent & Gemini)

## 1. Design attack on /api/agent/run hardening: gpt-reserve, effort max (Sat 14 Nov)
- **Asked:** before coding, attack the planned design: X-Agent-Key auth, injection delimiters + grounding check,
  price-aware choice, null amounts. Find bypasses, auth edge cases, choice-ordering mistakes. Read-only sandbox.
- **Result:** none. The first run hung because `codex exec` waited on stdin ("Reading additional input from stdin...")
  and was stopped. Relaunched with stdin closed; see entry 3.
- **Kept / rejected:** n/a.

## 2. Adversarial review of the hardening commit: gpt-5.6-terra, effort ultra
- **Status: PENDING.** Omar's time-box: the branch is pushed once tests pass; review findings get fixed in a
  follow-up commit.

## Self-review notes (Claude, while Codex was down)
- A grounding check can't catch an attack whose words are literally in the text ("...Return one item: butter
  20 kg"), so an instruction-phrase flag (ignore / disregard / instructions / return only...) was added → ASK_HUMAN.
- An injection can also DROP a constraint (Gemini returns no `lactose_free`), so dietary keywords found next to the
  item in the chef's text are unioned with Gemini's tags.

## 3. Adversarial review of room3-hardening (7d5be18): gpt-5.6-terra, effort ultra
- **Asked:** security/correctness review of 7d5be18: cross-buyer key use, prompt injection via chef text (parse and
  rank), bypasses of the grounding check, wrong candidate choice, 500s instead of Decisions, ordering without a
  server-side mandate. Severity, file:line, failing input, minimal fix. Read-only.
- **Runs:** the first launch failed (`timeout` isn't on macOS); relaunched at ~03:40 with stdin closed.
- **Result** (04:04-04:22, anchored to the immutable 7d5be18): 10 findings, 8 High. It confirmed as NOT real:
  cross-buyer runs through `buyer_id`, ordering without a stored mandate via /api/agent/run, `</buyer_request>`
  breakout, and rank ids outside the candidate set.
- **Already fixed before the review landed:** #1 (/api/orders trusted a client mandate; integration's `_mandate_for`
  now loads the stored one), #2 (instruction flag skipped on the fallback path; fixed in c9dfdc5), #7 in part
  (10-item cap).
- **Kept and fixed** (follow-up commit, one regression test each):
  - #3: grounding accepted prefixes ("milkshake" grounded "milk") and an empty query ("!!!" → whole-catalogue
    search). Now whole-word (plural-tolerant) matching, and no words means ungrounded.
  - #4: unit spoofing: KI (catalogue code, 10x), the "l" in "lactose" counted as litres, unchecked pcs. Now only
    plain units, token-level matching, and pcs only where no volume/weight unit was written.
  - #5: the amount wasn't bound to its product: "1,000 L milk" also grounded 1, and "12 kg butter and 1 L milk"
    grounded 12 L milk. One reading per number; product + amount + unit must share a clause.
  - #6: "20 L milk, lactose-free" lost the constraint (split clause). Unassigned dietary words go to the single
    item, or ASK when there are several items. Covers both parsers.
  - #7: duplicate parsed items silently multiplied the order → ASK.
  - #8: rank-call steering ("Prioritize product 476240"): the rank call no longer sees the chef's raw text,
    only parsed fields (and M2's Decisions check + price order already outrank the rank).
  - #9: "9"*400 or "1.2.3 L milk" crashed with a 500 → non-finite, absurd or malformed amounts become "how much?".
  - #10: a lone UTF-16 surrogate → 500. Now 422.
- **Rejected:** none.

## 4. Design attack on M2 (Gemini Decisions confidence): gpt-reserve, effort max
- **Asked:** attack the M2 design before coding: noul vs confidence semantics, injection through input text or
  product names, threshold edge cases, multi-item orders, failure modes blocking the milk demo, latency.
- **Result** (finished after M2 was pushed, so it reviewed the uncommitted M2 code): 10 findings, 5 marked P0.
- **Kept and fixed** (follow-up commit):
  - P0 #4: answers were not validated. A NaN, boolean or out-of-range `noul` passed as a number, and since
    NaN < 0.8 is False it would have counted as CONFIDENT. Now anything but a finite 0..1 float is "unverified".
  - P0 #3, part: the instruction-phrase flag only ran when Gemini parsed. Now it runs on the fallback path too
    (the text still reaches Decisions).
  - P1 #9: 0.7996 displayed as "0.80 vs your 0.80 threshold". Display now rounds down; facts keep the unrounded value.
  - P1 #6, part: audit facts now include the weakest question (`question: meets|qty`).
  - P1 #10: no item cap. Now max 10 items per run; more → ASK_HUMAN, nothing ordered.
- **Rejected, with reasons:**
  - P0 #1 ("noul misused as confidence"): for a yes/no question the API's `confidence` is max(P(yes), P(no)),
    so thresholding P(yes) is the correct, stricter reading. "P(yes)=0.85, confidence=0.51" can't happen.
  - P0 #2 ("one batched call violated"): deliberate. Live, batching several candidates in one input dropped
    lactose-free milk from 0.95 to 0.51 (see below), so it is one concurrent call per candidate.
  - P0 #5 (milk-drink false negative blocks the demo): measured live, lactose-free milk scores 0.96 and is chosen;
    the milk drink at 0.76 correctly drops behind it.
  - P0 #3, rest (catalogue names as an injection vector): Valio's own catalogue is a trusted source here.
- **Deferred** (follow-ups): #7 (stock for the same product across items isn't aggregated before the door);
  #8 (substitute judging when every line is orderable but low-confidence); #6 rest (one audit record linking
  agent and door).

## M2 findings from live runs (Claude, measured, not from Codex)
- Decisions API `confidence` = probability of the TOP answer, so it is high for a confident "no" too. We threshold
  `noul` (P(yes)) instead.
- Raw codes ("contains: AM; FREE_FROM_LACTOSE") lowered lactose-free milk from 0.95 to 0.79. Rendered as words.
- Batching several candidates in one Decisions input wrecked calibration (0.41-0.51 vs 0.86-0.97 judged alone).
  Switched to one concurrent call per candidate.
- When every line was below the threshold, the price rule picked the least likely line (0.39). The tie-break is now
  highest confidence within the below-threshold group.

## 5. Automated security review (security-guidance plugin) of e48cffb: 2 MEDIUM, both kept
- Duplicate guard compared raw query strings, so "1 L milk" + "1 L Eila milk" (same product) were still summed.
  Now judged on the chosen product ids: two items resolving to one product → ASK, quantities are never added.
- Dietary check was fail-open for multi-item requests: a tag counted as assigned if ANY item carried it, so a parse
  hanging "lactose-free" on the butter left the milk unconstrained. Now a tag counts only on the item whose own
  clause states it (or the only item); otherwise ASK.

## 6. Automated security review of 7893939: 1 MEDIUM, kept
- Removing the exact-duplicate check was a regression: identical items are judged in separate Decisions calls, so
  they can land on different products and both be ordered. The exact-duplicate check is back (alongside the
  chosen-product check).
- One clause could ground several parsed items ("1 L lactose-free milk" → "milk" + "lactose-free milk", two products).
  Each clause now grounds at most one item (`overgrounded`); any item left over → ASK, nothing ordered.

## 7. Automated security review of 656b1e6 (T15 menu): 1 MEDIUM, kept
- Menu dietary words could be dropped: if Gemini omitted "lactose-free" for a dish, the ingredient was priced
  unconstrained. Now `menu.apply_dietary` reads the dietary words on the dish's own menu line. Allergen exclusions
  ("nut-free") go on every ingredient of that dish; a claim ("lactose-free") that no ingredient of the dish carries
  → ASK; a dietary word no dish line owns → ASK.

## 8. Adversarial review of T15 menu (656b1e6): gpt-5.6-terra, effort ultra (background)
- **Result:** no CRITICAL (the menu route never orders). 6 findings.
- **Kept and fixed** (6984950): dietary words dropped (already fixed in 1c209ec); lingonberries/lingonberry didn't
  merge, and duplicate-product totals differed from the door's (now `_singular` keys, and the total is computed as
  the door does); dish grounding across the whole menu and duplicate dishes (now one menu line, counted once);
  1e308 per cover → OverflowError 500 (left out); order_lines over the 100,000 cap (left out); a newline in an
  ingredient name riding into the rank prompt (`_item` normalises queries to plain words).

## 9. Adversarial review of plain-language rules (b209cae): gpt-5.6-terra, effort ultra (background)
- **Result:** no CRITICAL. 9 findings.
- **Kept and fixed** (room3-qa, rules-hardening commit): `this_order` rules saved as standing rules; fractional or
  non-numeric cents; unknown allergens; a reliability floor of 0 (now must be 0 < v <= 1, and any lowering needs
  confirmation); expiry removed or extended (now a looser change needing confirmation); the mandate saved before
  its audit (now rolled back if the audit can't be written); a corrupt mandates.json (now a 503 that fails closed
  and is never overwritten).
- **Deferred:** concurrent same-buyer saves and in-flight orders racing a mandate change (needs a mandate
  version/ETag with compare-and-swap; one approver per kitchen at the hackathon).

## 10. Independent black-box QA (control room, 50 live cases): Room 3 items
- HP-01 root cause measured: the Decisions API is deterministic; raw chef wording in the judge input moved scores
  (and an authority claim raised them). Fixed with canonical judge input. See docs/GEMINI.md.

## 11. Adversarial review of /ask, the stream, voice, urgent options and the speed path: gpt-reserve, effort max
- **Asked** (stdin closed, background, read-only, on 1b85ada): orders the chef's words don't support or guard
  bypasses; menu/order mix-ups; invented dates/covers; invented urgent facts; voice SSRF/bombs/leaks; SSE leakage and
  cancellation; budget; 500s instead of 4xx.
- **Result:** no CRITICAL, 17 findings. Confirmed NOT real: SSRF/file reads via PyAV, key leakage, pickup placed by the
  agent, cross-request SSE leakage, an unbounded Live wait, a total Decisions outage bypassing confidence.
- **Kept and fixed** (room3-followup, one test each where testable):
  - #1: the matcher stopped at a weak first-batch hit (coffee milk 0.71) before a strong later one; it now judges
    on until a match ≥ 0.85 is in hand.
  - #2, #3, #4: plausibility, steering and date-intent answers that are missing (timeout, budget) now go through the
    mandate's uncertainty policy (ask), never a silent pass. "The Monday after next" isn't guessed; it asks.
  - #5: menu markers (guest counts, "menu"/"ruokalista") route to the proposal-only menu path even if the model says
    order.
  - #6: covers count only when written as a guest count ("80 kg flour" is not 80 guests).
  - #7: "next delivery" only from orderable quotes whose cut-off is still ahead.
  - #8: duplicate check and placing are one step per buyer (lock).
  - #9: the duplicate guard compares the delivery day too.
  - #10: at most 3 in-flight streams per buyer (429).
  - #12: Live frames ≤ 1 MB, transcript ≤ 4,000 characters.
  - #13: the voice body is read with a bounded stream (no-length bodies can't pass 1 MB).
  - #14: a 5,000-digit Content-Length is a 413, not a 500.
  - #15: malformed signature base64 is a 401 (two lines in Room 2's httpsig.py).
  - #16: a non-object Gemini JSON is treated as no answer.
  - #17: /ask opens the Decisions budget before its preflight calls.
- **Reported, not fixed here:** #11, order + audit atomicity in orders.py (Room 2's file). The stream's error text no
  longer claims "nothing was ordered" when it may have got that far.

## 12. room3-assume (Codex builds, Claude supervises) — Sat 14 Nov
- **Ask:** assume sensible amounts instead of asking (proposed carts, amounts in the product's natural unit with tappable options), standing diets per relevant ingredient, spare memory notes, grouped Decisions calls, specific off-topic replies (also in Talk).
- **Run:** `codex exec -s workspace-write -m gpt-reserve -c model_reasoning_effort=max`, ~43 min. **Result:** 486 tests pass; added direct-order `assumptions`, amount `options`, profile-aware menu ingredients, off-topic `topic`. **Kept:** all of it. Its latency benchmark hit a Gemini ConnectError (sandbox network), so no valid number from Codex.
