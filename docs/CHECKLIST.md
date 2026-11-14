# Submission checklist (Zoha's list), release-branch truth pass, Sat 14 Nov 2026

Status per item: ✅ done · ❌ not done · 👤 needs a human. Evidence is a file, a PR or a command. I checked these
against the checked-out release branch at `aa53219`, not against earlier docs. The
latest real-Gemini acceptance evidence is `/tmp/acceptance-release-1.md` (7/12); no
post-fix live run was available during this docs pass. TODO: refresh the live rows
after the parallel release fixes land.

## Platform and process

| Item | Status | Evidence, or exactly what is missing |
|---|---|---|
| Draft submitted on the platform | 👤 | Can't be seen from the repo. Omar or Zoha confirm on the Junction platform |
| PR #67 (chat bubbles, Valio palette, landing transition) | 👤 | Remote PR state is not established by the repository. Confirm whether the release UI already includes the work or merge the required PR |
| PR #34 (CI, built by Codex, ready for CRACI) | 👤 | Remote PR/CI state is not established by the repository. Confirm the workflow and do not tick CRACI until it actually runs |
| `scripts/release_check.py` after the last merges | 👤 | **30/30 PASS on the live API at commit 82177d8** (Sat 14 Nov, about 14:25 Helsinki) is earlier evidence only; later merges and the current acceptance failures are not covered. TODO: rerun on the final release commit |
| Backend tests | ❌ | Required offline command currently reports **634 passed, 21 failed, 1 skipped**. The failures are in existing menu/diet paths, including `ReasonCode.COVERAGE_LOW` missing from the current contracts; this docs task does not modify those owned files. |
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
| **J1** full demo twice on the live link | ❌ | Latest real-Gemini acceptance is **7/12** in `/tmp/acceptance-release-1.md`. Failures: standing-order plus-item follow-up, 25 kg butter correction, usual-product choice, duplicate guard on questions/changes, and party choices. TODO: rerun after fixes |
| **J2** one line on matching accuracy | ✅, with one docs bug | `backend/eval/results.json`: **33 labelled cases** with real Valio products: 28 "is it the product", 5 substitutes, 15 correct and 18 traps. At **0.70**: 14 handled alone, **0 wrong automatic orders**, 93 % recall. Every trap scored ≤ 0.26, every correct line ≥ 0.67. The coffee-milk catch is in GEMINI.md story 1. **Bug, fixed in this branch:** GEMINI-evidence.md's threshold section still said 30 cases with 0.80 "current" |
| **J3** mandate | ✅ | `backend/app/mandates.py` and `DATA_DIR/mandates.json` (server-side). The client can't send one (422) |
| **J3** human-only approval | ✅ | `auth.approver` (agent keys can't approve). Talk has no approve tool (`backend/app/live.py` TOOLS). Photo and voice routes place nothing |
| **J3** signed audit | ⚠️ partly | Order *responses* are Ed25519-signed (`signing.py`, `/.well-known/front-door-keys.json`, `POST /api/verify`). The **audit log itself is append-only JSON, not signed or hash-chained**. Say "signed decisions, audited", not "signed audit" |
| **J3** Valio audit view | ✅ | `GET /api/admin/audit`, `frontend/src/Valio.tsx`, screens in `docs/design/screens/final/8-valio-*` |
| **J4** cut-off passed | ✅ | `gate.py` CUTOFF_PASSED, never approvable |
| **J4** unknown stock | ✅ | `valio.py` (999999 = unknown) → `gate.py` QTY_UNKNOWN |
| **J4** short stock | ✅ | `gate.py` STOCK_PARTIAL plus split proposal (`alternative_order`) |
| **J4** injection | ✅ | `agent.py` steering classifier, instruction phrases, grounding; `vision.py` strips planted instruction-like photo text and marks `suspicious` |
| **J4** substitutes | ✅ | `gate._alternatives` (allergen-safe, same category, claims kept) |
| **J4** Helsinki urgent | ✅ | `backend/app/urgent.py`, Helsinki only, suggestions only |
| **J5** README correct | ✅ (this pass) | Features, sandbox QR flow, local commands, current routes, and the 7/12 live acceptance status are documented in `README.md` |
| **J5** OpenAPI export | ✅ (repo evidence) | `docs/schemas/openapi.json` has 27 HTTP paths, including profile, onboarding, and vision. `/api/live` is a WebSocket, so OpenAPI never lists it. TODO: regenerate after any final route change |
| **J5** ASSUMPTIONS, NEXT-STEPS | ✅ (this pass) | `NEXT-STEPS.md` reflects the current JSON-file/single-worker boundary and the release acceptance TODO |
| **J5** `decision/` described honestly | ✅ | README J3: "the standalone reference decision engine … live decisions in `agent.py` and `gate.py`" |

## Gemini and Codex

| Item | Status | Evidence, or what is missing |
|---|---|---|
| Gemini submission text answers the four questions | ✅ (this branch) | `docs/SUBMISSION.md` → "Best Use of Gemini: the four answers", rewritten from the code |
| GEMINI.md and GEMINI-evidence.md match the live app | ⚠️ | `GEMINI.md` now inventories every current Gemini call and model. `GEMINI-evidence.md` contains older run evidence; TODO: reconcile it with a post-fix real-Gemini run |
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
