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
- **Status: PENDING** at push; it was coded in parallel because of the time-box.

## M2 findings from live runs (Claude, measured, not from Codex)
- Decisions API `confidence` = probability of the TOP answer, so it is high for a confident "no" too. We threshold
  `noul` (P(yes)) instead.
- Raw codes ("contains: AM; FREE_FROM_LACTOSE") lowered lactose-free milk from 0.95 to 0.79. Rendered as words.
- Batching several candidates in one Decisions input wrecked calibration (0.41-0.51 vs 0.86-0.97 judged alone).
  Switched to one concurrent call per candidate.
- When every line was below the threshold, the price rule picked the least likely line (0.39). The tie-break is now
  highest confidence within the below-threshold group.
