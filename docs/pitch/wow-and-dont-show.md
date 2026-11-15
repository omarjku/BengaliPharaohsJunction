# Front Door v2: the wow moments, what not to show, and the truth appendix

## The wow moments, ranked

| Rank | Moment | Why it wins | Risk | Use it in |
|---|---|---|---|---|
| 1 | **One real take: photo → Gemini reads Finnish handwriting → Decisions score → HELD → the approval tap → "Signed by the front door ✓"** | J1 (30%) as a visible, continuous flow, plus J2, J3 and Gemini in about 40 s | Medium: rehearse it three times, and restart the whole take on any failure | Video beat 3 |
| 2 | **A judge taps Approve** after hearing the agent can't | J3 becomes something the judge did | Low | Live pitch |
| 3 | **The planted sticky note** flagged and ignored, while the food lines go through | Prompt injection made physical (J4, Gemini) | Medium: light and latency. Fall back to the typed line after 10 s | Video, live pitch |
| 4 | **"Gemini measures doubt; the mandate controls permission"**, over the coffee milk 0.115 / 0.897 gauge | The clearest "beyond an LLM" explanation, with an honest number | Low | Video beat 4, slide 4, pitch |
| 5 | **"Codex built it; Claude ran the room"**, with 47 "Built by Codex" commits scrolling | The Codex criterion, concretely | Low | Video beat 8, slide 6, pitch |
| 6 | **A Veo cold open with the "hi, Google judges" aside** | A wink to the Gemini judges that uses Google's own model | Veo access unverified; the UI on the phone must be a real screenshot | Video beat 1 **[ONLY IF VEO WORKS]** |
| 7 | **Talk in Finnish, held for a tap** | Gemini Live: native audio with tool calls | Not yet verified on a phone | Video beat 7 **[VERIFY VOICE ON PHONE]** |
| 8 | **CRACI: which build signed this order** | An original SBOM and provenance use | The endpoint currently returns `github_error` | **[ONLY IF CRACI LIVE]** |

## What not to show, and what not to say

**On stage**
- **No voice at the table.** The room is too loud; the live pitch uses the photo.
- **No free-form multi-turn chat:** the latest real-Gemini acceptance is 14 of 22 flows. Use only the scripted photo
  flow.
- **No menu-for-80** and **no compare view** as headlines.
- **No QR code for strangers** unless the team switches the option on.

**In the video**
- **No dead air,** and no extra features to fill time. Spare seconds go to explanations (decision 9).
- **No AI-invented UI.** A Veo shot can show a kitchen and a phone; the screen content must be a real screenshot.
- **No AI voices.** Omar and Zoha narrate.
- **No splicing inside the live take.** Speed-ups only during waits, shown with a ×4 badge.

**Words that overclaim**
- **Voice:** "spoken orders always wait for a tap" only after it's checked on a phone (it's on main since `6356334`).
- **CRACI:** never "SBOM for every build", "network trace", "provenance" or "which build signed" until the endpoint
  shows `"status": "ok"`. Until then, say only "CI runs on CRACI".
- **Numbers:**
  - Never "33 cases prove it". Say "tuned on that set; held-out next".
  - Never "€60 over" on the photo cart: the cart costs more than the €1,560 milk line.
- **Coffee milk:** "our QA caught it", not "calibration caught it".
- **Valio and production:** "Valio's challenge mock", never "live Valio prices", "real orders", "production",
  "bank", "same-hour delivery" or "live Cash & Carry stock".
- **The request:** "Valio's example request, recreated on a real list". The handwriting is real; the scenario is
  staged.
- **No speed claims** against the webshop (unmeasured).

**Hygiene**
- No keys, browser storage or terminal configuration on screen.
- Simulated history only with its label.
- Warm Render before every slot.

---

## Appendix A: lines that depend on something unverified

| Line | Where | Condition |
|---|---|---|
| The Veo cold open and the "Veo, via our Gemini key. Hi, Google judges." aside | Video beat 1 | **[ONLY IF VEO WORKS]**: Veo isn't in our verified model list. Fallback: RAEA graphic or a real phone shot, without the joke |
| "Anything spoken waits for a tap"; the Talk clip; "spoken order held, first audio 1.17 s" | Video beat 7; slide 4 | **[VERIFY VOICE ON PHONE]**: on main since `6356334`; 1.17 s is a dev measurement from `docs/CODEX.md` |
| "The live app publishes its own build's CRACI SBOM…"; the endpoint shot; slide 8 | Video beat 9; pitch 2:14; slide 8; CRACI Q&A | **[ONLY IF CRACI LIVE]**: the endpoint returns `github_error` today |
| A Decisions score visible on the chat card; the flagged note; the cart total | Video beat 3; pitch demo | True only if the take shows them. Fallback: the audit view's confidence for the same order |
| The QR code and "your own test kitchen, try to trick it" | Video end card; pitch close; slide 7 | **[OPTION]**: the team decides whether the live app is robust enough for strangers |
| "14 of 22 flows" on a slide | Slide 5 | **[OPTION]**: on the slide or in the notes |

**True on main (`6356334`):**
- the photo → Gemini OCR → Gemini chat agent → Decisions → front door path (`PhotoButton` → `send` →
  `/api/agent/chat`);
- signed decisions with the Valio verify;
- agent keys can't approve or cancel confirmed orders;
- MCP and OpenAPI;
- CI on CRACI;
- PRs #114–#117 merged;
- 47 "Built by Codex" commits;
- the 33-case evaluation;
- QR test kitchens (now 40 per IP per hour).

## Appendix B: stale numbers in the repo (not edited; for Omar to fix)

1. `docs/deck/index.html` slide 8: "30 hand-labelled cases" and "0.8 → 12" should be 33 and 11
   (`docs/GEMINI-opening.md`).
2. `docs/SUBMISSION.md` line 41: "On 30 labelled cases" should be 33.
3. `docs/VIDEO.md` shot 12: the caption "62 findings · 43 fixed" sits under a voiceover saying 112 and 79. The whole
   shot list is superseded by this v2.
4. `docs/DEMO-RUNBOOK.md` line 22 says the reset clears every buyer; `demo_prep.py` resets one buyer by default.
5. `docs/DEMO-RUNBOOK.md` step 1 and `docs/PITCH.md`: "Finnish voice → €156, ordered by itself" is now false. Voice
   orders are held since `6356334`.
6. `docs/CODEX.md` still says PR #116 is open, and that same-brain Talk is "not merged yet". Both merged (#116,
   #117).
7. `docs/pitch/*` on main holds the v1 files, which say 24 "Built by Codex" commits; main now has 29. Replace them with
   this v2 if the team adopts it.

## Appendix C: every number used, and its source

| Number | Source |
|---|---|
| "1,000 litres of lactose-free milk by Monday" | `docs/challenges/main_327_trusted-trade-agents.md` |
| 17,546 products | `docs/PITCH.md`, question 4 |
| Milk line €1,560; €1,500 per-order limit; peanut-free | `README.md`, `backend/app/mandates.py` |
| 0.70; 33 cases; 0 wrong automatic orders; 14 of 15 alone; tuned on the same set | `docs/GEMINI-opening.md`; `docs/testing/j1-j2-best-practices.md` |
| Coffee milk 0.115; lactose-free milk 0.897; 0.72 "from our notes" | `docs/GEMINI-opening.md` |
| Decisions 6/6 identical, about 0.5 s | `docs/SUBMISSION.md`, Gemini answer 4 |
| Spoken order held, first audio 1.17 s, card 6.87 s (dev) | `docs/CODEX.md`, same-brain Talk row |
| 14 of 22 acceptance flows (engine path) | `docs/testing/acceptance-integration-118a63b.md` |
| On/off test, 5 requests | `docs/GEMINI-ablation.md` |
| 47 commits on main say "Built by Codex" | `git log -i --grep="Built by Codex" origin/main` at `76f5a92` |
| PRs #114–#117 merged | `gh pr list` |
| QR kitchens: 24 h; 40 mints per IP per hour | `backend/app/sandbox.py`; `backend/app/ratelimit.py:19` on main |
| CRACI: the runner's API calls get 403; the app fetches the evidence; status today `github_error` | `docs/CRACI.md` on main; coordinator |
