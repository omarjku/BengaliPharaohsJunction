# Submission checklist (Zoha's list), audited Sun 15 Nov ~15:00

Status per item: ✅ done · ❌ not done · 👤 needs a human. Evidence is a file, a PR or a command. I checked these
against the repo on `origin/omar/m1-integration` @ 7b8c8f2, not against earlier docs. Following Omar's "stop
testing" rule, nothing was run against the live API in this audit; the "live" items say so.

## Platform and process

| Item | Status | Evidence, or exactly what is missing |
|---|---|---|
| Draft submitted on the platform | 👤 | Can't be seen from the repo. Omar or Zoha confirm on the Junction platform |
| PR #67 (chat bubbles, Valio palette, landing transition) | ❌ | `gh pr view 67`: **OPEN**, not merged. Merge it, or close it if the redesign landed another way |
| PR #34 (CI, built by Codex, ready for CRACI) | ❌ | `gh pr view 34`: **OPEN**. CI isn't running on main, so **don't tick CRACI** |
| `scripts/release_check.py` after the last merges | ✅ (earlier commit) | **30/30 PASS on the live API at commit 82177d8** (Sat 14 Nov, about 14:25 Helsinki), per the control room. Re-run once after the 16:00 backend freeze, since later merges aren't covered |
| Backend tests | ✅ (reported) | 434 pass, per the control room after PR #70. Not re-run here |
| Credits form | 👤 | Human |
| Challenges ticked, draft switched to FINAL before Sun 10:00 | 👤 | Tick Valio + Gemini + Codex. Not CRACI unless #34 merges and CI runs |
| Rehearsal, timed | 👤 | Not done yet. Use `docs/DEMO-RUNBOOK.md` |
| `scripts/demo_prep.py` at T−30 | 👤 | Runbook says so. Remember it resets every buyer |
| Phone mic permission tested | 👤 | Runbook T−30 step 3 |
| Fallback video ready | ✅ / 👤 | Draft v3 (`video/out/front-door-draft-v3-share.mp4`, 1:55, captions only) exists. The final cut gets recorded tonight |
| Both at peer review Sun 10:30 | 👤 | Human. Missing it loses main-prize eligibility |
| Q&A answers | ✅ | `docs/PITCH.md`: questions 0–10, including the coffee-milk QA catch |

## Valio criteria

| Item | Status | Evidence, or what is missing |
|---|---|---|
| **J1** full demo twice on the live link | 👤 | Tonight, on the final UI. Each beat in `docs/DEMO-RUNBOOK.md` was measured on Render or a local backend on Sat–Sun, but not after the redesign |
| **J2** one line on matching accuracy | ✅, with one docs bug | `backend/eval/results.json`: **33 labelled cases** with real Valio products: 28 "is it the product", 5 substitutes, 15 correct and 18 traps. At **0.70**: 14 handled alone, **0 wrong automatic orders**, 93 % recall. Every trap scored ≤ 0.26, every correct line ≥ 0.67. The coffee-milk catch is in GEMINI.md story 1. **Bug, fixed in this branch:** GEMINI-evidence.md's threshold section still said 30 cases with 0.80 "current" |
| **J3** mandate | ✅ | `backend/app/mandates.py` (server-side, stored at Valio's side). The client can't send one (422) |
| **J3** human-only approval | ✅ | `auth.approver` (agent keys can't approve). Talk has no approve tool (`backend/app/live.py` TOOLS). Photo and voice routes place nothing |
| **J3** signed audit | ⚠️ partly | Order *responses* are Ed25519-signed (`signing.py`, `/.well-known/front-door-keys.json`, `POST /api/verify`). The **audit log itself is append-only JSON, not signed or hash-chained**. Say "signed decisions, audited", not "signed audit" |
| **J3** Valio audit view | ✅ | `GET /api/admin/audit`, `frontend/src/Valio.tsx`, screens in `docs/design/screens/final/8-valio-*` |
| **J4** cut-off passed | ✅ | `gate.py` CUTOFF_PASSED, never approvable |
| **J4** unknown stock | ✅ | `valio.py` (999999 = unknown) → `gate.py` QTY_UNKNOWN |
| **J4** short stock | ✅ | `gate.py` STOCK_PARTIAL plus split proposal (`alternative_order`) |
| **J4** injection | ✅ | `agent.py` steering classifier, instruction phrases, grounding; `vision.py` `suspicious` for photos. Planted-photo handling is on main (PR #80 list) |
| **J4** substitutes | ✅ | `gate._alternatives` (allergen-safe, same category, claims kept) |
| **J4** Helsinki urgent | ✅ | `backend/app/urgent.py`, Helsinki only, suggestions only |
| **J5** README correct | ⚠️ | Mostly current. Gaps: the photo, profile and onboarding routes are missing from the export (next row) |
| **J5** OpenAPI export | ✅ (regenerated in `room1-gaps`) | `docs/schemas/openapi.json` was stale (no profile, onboarding or vision routes). It now has 27 paths. Re-run `backend/.venv/bin/python docs/export_schemas.py` after the freeze. `/api/live` is a WebSocket, so OpenAPI never lists it |
| **J5** ASSUMPTIONS, NEXT-STEPS | ✅ | NEXT-STEPS tightened in this branch |
| **J5** `decision/` described honestly | ✅ | README J3: "the standalone reference decision engine … live decisions in `agent.py` and `gate.py`" |

## Gemini and Codex

| Item | Status | Evidence, or what is missing |
|---|---|---|
| Gemini submission text answers the four questions | ✅ (this branch) | `docs/SUBMISSION.md` → "Best Use of Gemini: the four answers", rewritten from the code |
| GEMINI.md and GEMINI-evidence.md match the live app | 👤 | Code facts checked. Live numbers are from Sat–Sun runs and not re-run (no testing). Re-check the milk line once tonight |
| Codex claims in SUBMISSION.md match `docs/codex-log` | ✅ (`room1-gaps`) | Recounted from the logs: **28 runs, 112 findings, 79 kept/fixed**, 12 rejected, 10 deferred, 2 forwarded, 6 already fixed (statuses overlap). SUBMISSION, CODEX.md, PITCH, DECK, VIDEO and the deck HTML now say this. The deck PDF needs its re-export after the frontend freeze |
| CRACI | ❌ | Only if #34 merges and CI really runs there. Not today |

## Submission assets

| Item | Status | Evidence, or what is missing |
|---|---|---|
| Video public, 2:00 max, captions | ❌ / 👤 | Draft v3 is 1:55 with burned-in captions. The final cut on the redesigned UI is tonight (`docs/VIDEO.md` "Final cut"). Upload public; captions `.srt` |
| Deck PDF re-exported | ❌ | `docs/deck/` still has pre-redesign screenshots. Swap in `docs/design/screens/final/`, capture photo, Talk and compare, then `node docs/deck/export.mjs` |
| SUBMISSION.md text blocks | ⚠️ | The Gemini answers are updated (this branch). The short and long descriptions don't mention photo input, Talk, the profile or the compare view yet. The Codex numbers are stale |
| Links checked | 👤 | Repo, `valio-front-door.onrender.com`, `/docs`, the video link |
| Render warm, keys work | 👤 | `demo_prep.py` at T−30 |
| Judge access | 👤 | Plan in SUBMISSION.md. No judge keys created yet; Omar decides |
