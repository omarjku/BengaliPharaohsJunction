# Front Door: the wow moments, what not to show, and the truth appendix

## The wow moments, ranked

| Rank | Moment | Why it wins | Risk | Use it in |
|---|---|---|---|---|
| 1 | **The held order → the judge taps Approve → "Signed by the front door ✓"** | Proves J1 (30%) and J3 (20%) in one gesture. The judge *does* the control instead of watching it | Low | Pitch, booth, video (as Aino's tap) |
| 2 | **The planted sticky note on a real handwritten Finnish list**, photographed: the food lines read, the note ignored | Valio's example request, a real kitchen artefact and prompt injection in one shot (J2, J4, Gemini) | Medium: vision latency and light. Print it large; fall back to the typed line after 10 s | Video, pitch |
| 3 | **Coffee milk 0.115 against lactose-free milk 0.897** on the 0.70 line | The clearest "beyond simply adding an LLM" proof, with an honest QA story | Low (a graphic) | Video, pitch, slide 6 |
| 4 | **€1,560 > €1,500** as one giant inequality | J3 in a glance (from draft A) | Low. Typed milk-only order only | Slide 5, pitch fallback |
| 5 | **Codex lanes: built in worktrees → real-Gemini loops → Claude's test gate**, plus "24 commits on main say Built by Codex" | Meets the Codex criterion concretely: build, iterate, ship | Low | Video, pitch, slide 9 |
| 6 | **Claude ordering over MCP** and getting held by the same rules | Kills the "it's just a chatbot" objection (J5) | Medium (desktop setup) | Video only (recorded) |
| 7 | **The Arla trap**: "available Monday", cut-off passed, 999999 | Exactly the brief's "delivery constraints beyond the happy path" (J4) | Low | Video, pitch |
| 8 | **A judge writes their own sticky note** | Memorable adversarial play | Medium-high: a note with a real item ("add 50 kg butter") becomes an order line. Say "anything it reads still has to pass the door" | Booth only, after the scripted run |
| 9 | **The CRACI chain to the signed order** | An original SBOM/provenance use | **Not a wow until #116 ships with live evidence.** Until then, only "CI runs on CRACI" | Later |
| 10 | **Talk in Finnish, held for a tap** | The most theatrical moment | Highest: voice-hold is not on main; venue noise | Video only, **[only after voice ships]** |

## What not to show (and what not to say)

**Stage behaviour**
- **No free-form, multi-turn conversations on stage.** The latest real-Gemini acceptance is 7/12, and the judge
  simulation scored 5/20 for chef happiness before the wave-2 fixes. Use only the scripted lines.
- **No live Talk at the table, and never "voice never orders alone"** until a Talk order on the deployed build
  shows the hold. A voice clip that auto-orders hurts J3 more than it helps Gemini.
- **No compare view** while it's in progress (from draft A).
- **No menu-for-80 as a headline.** It's slow and assumption-heavy (both drafts agree). Keep it for booth
  questions.

**Words that overclaim**
- **No speed claims** ("2× faster than the webshop"). `docs/testing/speed-release-1.md` measured nothing (the port
  couldn't bind).
- **No CRACI overclaim:** never say "SBOM for every build", "network trace", "build provenance" or "CRACI proves which
  build signed" while CRACI's API returns 403 to calls from its runners and nothing is published. Never show
  `/.well-known/front-door-build.json` while it reads `"sbom": "unavailable"`.
- **Codex wording:** say "CRACI evidence script built; evidence publication ships tonight", never "Codex built the
  CRACI provenance integration" on its own.
- **No old numbers:** "30 cases", "0.8 → 12", "62 findings · 43 fixed", or "€60 over" on the photo cart (the cart
  costs more than the €1,560 milk line).
- **"Gemini's calibration caught coffee milk":** no. Our QA caught it, at 0.72 (from our notes). Calibration keeps it
  out now.
- **"Valio's own request in a chef's handwriting":** say "Valio's example request, recreated on a real list". The
  handwriting is real; the scenario is staged.
- **"Live Valio prices":** say "fresh quotes from Valio's challenge mock".
- **No production or payment language:** no "real Valio order", "production", "bank integration", "same-hour
  delivery" or "live Cash & Carry stock". Pickup is a suggestion the agent never places.

**Data and demo hygiene**
- **The sugar request is not an automatic order:** it's held for missing allergen data. Present it as "it asks
  rather than guesses".
- **No simulated kitchen history without its label.**
- **No secrets on screen:** agent, approver or admin keys, browser storage, terminal configuration, private QR
  credentials. Judges use QR test kitchens, never the `lapland-kitchen` keys.
- **No cold Render:** warm `/api/health` before every slot, and keep the video tab as the fallback.
- **Don't promise the QR works on venue Wi-Fi:** 5 test kitchens per IP per hour. Mobile data is a mitigation, not a
  promise; keep two pre-minted kitchens.

---

## Appendix A: lines that depend on something not yet shipped

| Line | Where | Condition |
|---|---|---|
| "Spoken orders always wait for her tap" / "voice never orders alone" | Video beat 11; slide 9 voice lane; Talk wow | **[only after voice ships]**. On main, `ask()` (`backend/app/ask.py:194`) has no `via` parameter, and `live.py:125` drops the voice flag on `TypeError` |
| "Codex put voice on the same brain" | Pitch 2:02 add-on; slide 9 | **[only after voice ships]** |
| "The door publishes which build signed your order", the provenance chain, the endpoint `curl` | Video beat 10; pitch 2:24 add-on; slide 8 add-on; CRACI Q&A | **[only if PR #116 ships with live evidence]**. #116 is open; CRACI's API returns 403 to calls from its runners |
| CRACI evidence script lane | Video beat 9; slide 9 | Label it *built; ships tonight* until #116 merges |
| Beat 3's flagged note, and beat 4's cart total | Video | True only if the recorded R2 take shows them; otherwise use the typed-line fallback |

**True on main today:**
- the Gemini chat agent (#114) and the engine;
- the agent-cancel fix (#115);
- CI on CRACI;
- MCP and OpenAPI;
- signed decisions with the Valio verify;
- the 33-case evaluation;
- QR test kitchens;
- 24 commits that say "Built by Codex".

## Appendix B: stale numbers in the repo (not edited; for Omar to fix)

1. `docs/deck/index.html` slide 8 says "30 hand-labelled cases" and "0.8 → 12". The source
   (`docs/GEMINI-opening.md`) says 33 cases and 11 at 0.80.
2. `docs/SUBMISSION.md`, long description: "On 30 labelled cases" should be 33.
3. `docs/VIDEO.md` shot 12: the caption "Codex: 62 findings · 43 fixed" sits under a voiceover saying 112 and 79.
4. `docs/DEMO-RUNBOOK.md` says the reset clears every buyer; `scripts/demo_prep.py` now resets one buyer by default.
5. `docs/PITCH.md` and `docs/DEMO-RUNBOOK.md` step 1, "Finnish voice → €156, ordered by itself", becomes false once
   voice-hold ships (voice orders will be held).
6. `docs/CODEX.md` totals (28 runs, 112 findings, 79 fixed) predate tonight's Codex builds (#114, #115, #116, the
   voice work). Add the build runs so the judges' document matches the video.

## Appendix C: every number used, and its source

| Number | Source |
|---|---|
| "1,000 litres of lactose-free milk by Monday"; 20,000+ kitchens | `docs/challenges/main_327_trusted-trade-agents.md` |
| 17,546 products | `docs/PITCH.md`, question 4 |
| Milk line €1,560; €1,500 per-order limit; €60 over (milk only); EUR 6,000 a week; peanut-free | `README.md`, `backend/app/mandates.py` |
| QR kitchen = Helsinki bistro copy: €800 limit, €1,000 per line, €3,000 a week; 24 h; 5 mints per IP per hour | `mandates.py`, `sandbox.py`, `ratelimit.py:19` |
| 0.70; 33 cases; 0 wrong automatic orders; 14 of 15 alone; default 0.80 | `docs/GEMINI-opening.md`, `docs/PITCH.md` question 7 |
| Coffee milk 0.115 (the app shows 11%); lactose-free milk 0.897; 0.72 "from our notes" | `docs/GEMINI-opening.md` |
| Decisions 6/6 identical, about 0.5 s; batching 0.95 → 0.51 | `docs/SUBMISSION.md`; `docs/CODEX.md` |
| On/off test, 5 requests | `docs/GEMINI-ablation.md` |
| 24 commits on main say "Built by Codex" | `git log -i --grep="Built by Codex" origin/main` (at a70ed9a) |
| 28 runs · 112 findings · 79 fixed | `docs/CODEX.md` |
| f1a1328 (allergen, CRITICAL); cca43f2 / #115 (agent cancel); 0815e33 / #114 (chat agent); 6034aa0 / #116 (CRACI, open) | `git log`; `gh pr list` |
| HTTP 400 on every structured Gemini call | `docs/ENGINE-STATUS.md` section 1 |
| Acceptance 7/12; judge simulation 5/20 (internal only) | `docs/ENGINE-STATUS.md` |
