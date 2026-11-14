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
- **Status: PENDING** at the M2 push (04:15). Findings get fixed in a follow-up commit.

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
