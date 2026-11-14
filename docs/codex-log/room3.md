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
