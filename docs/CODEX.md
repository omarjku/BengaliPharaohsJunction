# How Codex built, attacked, and shipped Front Door

Codex built the engine v2, the Gemini function-calling chat agent, kitchen and
calendar flows, voice-on-one-brain, CRACI evidence, and the safety fixes. It worked
in parallel worktrees with real Gemini loops: edit, run, measure, fix, and add a
regression. The current split is: **Codex built and attacked; Claude ran the room:
briefs, review, merge, test gate.**

PR #114 shipped the core and chat agent; PR #115 shipped agent cancel/change safety;
PR #116 shipped live CRACI evidence; and PR #117 merged voice-on-one-brain, voice
security, chat round 3, and the CRACI live-evidence plumbing. PRs #116 and #117 are
merged into `origin/main` and live. PR #118 then merged the audit fixes, Helsinki-time
date fix, and the J2 chat evaluation.

## Later Codex runs

The run names, model, and effort below come from the requested log headers; results
come from each `*-out.md`, the resulting git history, or are explicitly marked
incomplete. All these runs used `gpt-reserve` at high reasoning effort. Sandbox modes
were `danger-full-access` for `craci-live`, `j2-eval`, `vuln-fix`, `coffee-fix`, and
`j2-assume`; the others used `workspace-write`.

| Run | Result from the final report | Commit / status |
|---|---|---|
| `craci-live` | Live CRACI evidence fetch, cache/fallback, signing-key linkage; backend 714 passed + 1 skipped, scripts 55 passed. | `345084c`; merged by PR #117, live. |
| `voice-sec` | Spoken changes are held for a tap, voice cannot cancel, and transcript guards handle empty/stale input; backend 709 + 1 skipped, frontend 16 passed. | `dfdf0ce`; merged by PR #117, live. |
| `audit-fixes` | All eight requested audit fixes were implemented; 725 backend tests passed + 1 skipped. | `59b6fb9`; merged by PR #118, live. |
| `sunday-fix` | Helsinki-time past-date gate and date-independent tests; real Sunday and frozen Sat/Sun/Mon each reported 721 passed + 1 skipped. | `7b069ab`; merged by PR #118, live. |
| `j2-eval` | `/api/agent/chat` scored 97/164 (59.1%), median 3.85 s/turn, with 0 unsafe auto-orders; evaluator 18 passed. | `4387aef`; merged by PR #118, live. |
| `vuln-fix` | Upgraded FastAPI, Starlette, and cryptography; local report: 0 HIGH/CRITICAL, with remaining medium/moderate findings named. | `0e15435`; **next deploy**. |
| `readme-v2` | Rewrote the judge README, moved the reference, and added the CRACI slide; Markdown and 12-slide checks passed. | `e2ce472`; **next deploy**. |
| `craci-sign` | Added signed build provenance, build-bound `kid`, tamper coverage, and the order-card build line; backend 739 + 1 skipped and frontend build passed. | `1664f12`; **next deploy**. |
| `coffee-fix` | The requested `coffee-fix-out.md` is empty and its log has no final result; no shipped result is claimed. | No commit/result to map. |
| `j2-assume` | The log stopped during the 164-case rerun at 151/164; its `*-out.md` is empty, so no final score or shipped result is claimed. | No commit/result to map. |
| `docs-refresh` | Documentation-only run requested here; its `*-out.md` is empty until this refresh is finished. | No code ship; worktree only. |

The later audit was a five-worker Codex team (`w1`–`w5`) covering API compliance,
dataset/allergen and unit handling, scenario coverage, J2 safety, and documentation
truth. Its fixed production findings are represented by `59b6fb9` and the PR #118
merge; findings that were not built remain named in the audit notes.

## File → commit → Codex run

This map is the compact provenance view from `git log --format='%h %s' -- <file>` on
the integration branch. Entries marked **next deploy** are on integration, not
`origin/main`.

| Main shipped file | Commit | Codex run |
|---|---|---|
| `backend/app/chat_agent.py` | `0815e33`, `612b680`, `59b6fb9` | chat rounds 1/3, `audit-fixes` |
| `backend/app/live.py` | `69ff7c5`, `dfdf0ce` | same-brain Talk, `voice-sec` |
| `backend/app/craci_evidence.py` | `345084c`, `37af1c1` | `craci-live`, CRACI security follow-up |
| `backend/app/signing.py` | `4e2ef93`, `345084c`, `1664f12` | signed front door, `craci-live`, `craci-sign` (**next deploy** for the last commit) |
| `backend/app/orders.py` | `59b6fb9`, `1664f12` | `audit-fixes`, `craci-sign` (**next deploy** for the last commit) |
| `backend/app/catalogue.py` / `backend/app/gate.py` | `59b6fb9`, `7b069ab` | `audit-fixes`, `sunday-fix` |
| `backend/requirements.txt` | `0e15435` | `vuln-fix` (**next deploy**) |

From the Sun 15 Nov 01:50 Codex-built commit convention onward, Codex-built commits
carry a `Co-Authored-By: OpenAI Codex` trailer; earlier ones say **Built by Codex**
in the commit message. `git log --grep="OpenAI Codex"` and the earlier message search
are the direct history checks.

## How the collaboration worked

- Claude wrote narrow briefs and acceptance criteria; Codex worked only in its assigned
  worktree, and parallel agents did not share a working tree.
- The loop was real: run the chat/acceptance tools or a live service against Gemini,
  record latency, tool path, and card state, fix the root cause, and add a regression.
- Gemini interpreted chef language; deterministic code remained authoritative for
  catalogue facts, unit conversion, diet/allergen evidence, quotes, mandates,
  approval, and order state.
- Claude reviewed diffs, merged branches, and ran the test gate. Codex had no approval
  tool; unresolved findings were named and time-boxed.

“Claude builds, Codex attacks” described the first phase. It is retired: Codex built
and attacked, while Claude ran the room and the history shows which commits shipped.
