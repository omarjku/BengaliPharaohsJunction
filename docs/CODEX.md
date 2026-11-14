# How Codex helped build, iterate and ship

We are two people (Omar Kassem, Fathia Fairuz Zoha). Over the weekend four "rooms" (parallel Claude Code sessions:
docs, front door, agent, UI) built the Valio front door. Every room used Codex CLI 0.169.0 next to Claude.
This page is compiled from the per-room logs in [`docs/codex-log/`](codex-log/), the git history and the team
Message Board. Every number below can be traced to one of those.

## How the work was split

**Claude builds, Codex attacks and cross-checks.**
- Claude Code wrote most of the code and wrote every fix.
- Codex did three jobs:
  - **Drafts** (`gpt-reserve`, effort max, `workspace-write`): first versions of docs and a UI feature. Claude then
    checked every claim or line before keeping it.
  - **Design attacks** (`gpt-reserve`, max, read-only), before coding: "here is the plan; find the bypasses".
  - **Adversarial reviews** (`gpt-5.6-terra`, effort ultra or high, read-only), after coding: "find real defects,
    with file:line and a failing input". A run was anchored to a commit hash where possible, so findings didn't
    drift while other rooms kept pushing.
- After Omar's time-box rule, **Codex never blocked a push**. Branches went out once tests passed. Review findings
  landed in follow-up commits, each with a regression test that fails on the old code.

**Independent agreement.** On Zoha's PR #8 (the decision step), Claude and Codex (`gpt-6-luna`, run blind in the
control room) reviewed separately and both asked for changes. Codex reported 4 findings, and 3 of them matched
Claude's reviewer independently:
1. A sales-blocked product with a normal-looking stock number was ordered automatically.
2. The fail-closed fallback itself crashed on a timezone-naive `now`.
3. A regex DECLINEd ordinary chef text such as "keep it within budget".

Its fourth finding was that duplicate product ids silently overwrote each other. Claude found five more on its own. All of them were posted on the Message Board for Zoha (Sat 14 Nov, 03:29). At
the last board update they were still open in `decision/`, so `decide()` is not wired into the live agent until
they land.

## Models

| Model | Effort | Used for |
|---|---|---|
| `gpt-reserve` | max | 11 runs: drafts, design attacks and the `/ask` review |
| `gpt-5.6-terra` | ultra (once high) | 15 runs: adversarial reviews, the docs fact-check and the judge audit |
| `gpt-6-luna` | high | 2 runs: the integration-branch review and the blind second opinion on PR #8 |

## Run by run

The table contains all 28 numbered Codex runs in the room logs after excluding the three automated security
reviews by the security-guidance plugin, the Claude black-box QA entry, and Claude self-review notes. The raw files
in `control-room/` are outputs for the control-room rows, not extra runs. "Not stated" means the log gives no
number.

"Kept" means fixed in our code, or (for docs) the claim was corrected.

| Room | Run | Model | Ask | Findings | Kept/fixed | Rejected | Other | Fix commit |
|---|---|---|---|---|---|---|---|---|
| 1 docs | #1 | `gpt-reserve` / max | Draft `README.md` | not a review | most, number not stated | not stated | — | `5ed1e86` |
| 1 docs | #2 | `gpt-reserve` / max | Draft `ASSUMPTIONS.md` | not a review (13 traps) | kept after code check | 1 claim | — | `5ed1e86` |
| 1 docs | #3 | `gpt-reserve` / max | Draft `STANDARDS.md` | not a review | kept | — | — | `5ed1e86` |
| 1 docs | #4 | `gpt-reserve` / max | Draft `NEXT-STEPS.md` | not a review | kept | — | — | `5ed1e86` |
| 1 docs | #5 | `gpt-5.6-terra` / ultra | Fact-check every doc claim against the code | 14 | 12 | 2 | — | `019fd67` |
| 1 docs | #6 | `gpt-reserve` / max | Draft the M2 `agent.py` change | not a review | — | stopped as stale | Claude wrote the change | not stated |
| 1 docs | #7 | `gpt-5.6-terra` / ultra | Review the M2 ranking and "why" text | 5 | 4 | 1 | — | `019fd67` |
| 2 front door | #1 | `gpt-reserve` / max | Draft stored-mandate change | no result | — | — | never ran (`exit 127`); rerun | — |
| 2 front door | #2 | `gpt-reserve` / max | Same draft prompt | no result | — | — | hung; no edits | — |
| 2 front door | #3 | `gpt-5.6-terra` / ultra | Adversarial review of the front door | 7 | 2 | 1 | already fixed: 1; deferred: 2; forwarded: 1 | `7c2e3bb` |
| 2 front door | #4 | `gpt-5.6-terra` / ultra | Adversarial review of splits and substitutes | 7 | 6 | 1 | — | `aea3c82` |
| 2 front door | #5 | `gpt-5.6-terra` / ultra | Adversarial review of the trust pieces | 3 | 1 | — | noted, not fixed: 2 | `room2-qa` |
| 2 front door | #6 | `gpt-5.6-terra` / ultra | Adversarial review of idempotency, rate limits and `DATA_DIR` | 5 | 5 | — | already fixed: 1 (overlap); deferred: 1 | `room2-qa` follow-up |
| 2 front door | #7 | `gpt-5.6-terra` / ultra | Whole-backend adversarial audit | 6 | 3 | 1 | deferred: 2 | `room2-qa2` |
| 3 agent | #1 | `gpt-reserve` / max | Design attack on `/api/agent/run` hardening | not stated (result: none) | n/a | n/a | first launch hung; see #3 | — |
| 3 agent | #2 | `gpt-5.6-terra` / ultra | Adversarial review of the hardening commit | not stated (pending) | — | — | pending | — |
| 3 agent | #3 | `gpt-5.6-terra` / ultra | Adversarial review of the agent hardening (`7d5be18`) | 10 (8 High) | 8 | 0 | already fixed: 3 (one also kept) | `e48cffb` |
| 3 agent | #4 | `gpt-reserve` / max | Design attack on Gemini Decisions confidence | 10 (5 "P0") | 5 | 4 | deferred: 3 | `c9dfdc5` |
| 3 agent | #8 | `gpt-5.6-terra` / ultra | Adversarial review of T15 menu (`656b1e6`) | 6 | 4 | — | already fixed: 1 (included in kept); left out: 2 | `6984950` |
| 3 agent | #9 | `gpt-5.6-terra` / ultra | Adversarial review of plain-language rules (`b209cae`) | 9 | 7 | — | deferred: 2 | `room3-qa` |
| 3 agent | #11 | `gpt-reserve` / max | Adversarial review of `/ask`, stream, voice and urgent paths | 17 | 16 | — | reported, not fixed here: 1 (Room 2) | `room3-followup` |
| 4 UI | #1 | `gpt-reserve` / max | Draft the auth UI | not a review (1 feature) | most of it | — | 4 parts rewritten | `a57d7cd` |
| 4 UI | #2 | `gpt-5.6-terra` / ultra | Adversarial review of `frontend/src` | 4 | 2 | 1 | forwarded to backend: 1 | `a57d7cd` |
| 4 UI | #3 | `gpt-5.6-terra` / high | Review of the M2 UI diff | 1 | 0 | 1 | stale branch | none |
| control room | #1 | `gpt-6-luna` / high | Adversarial review of `omar/m1-integration` | 4 (2 High) | 4 | 0 | — | `7d5be18`, `a57d7cd` |
| control room | #2 | `gpt-6-luna` / high | Blind second opinion on PR #8 | 4 | 0 | 0 | 4 open in `decision/`; 3 matched Claude | none yet |
| control room | #3 | `gpt-5.6-terra` / ultra | Whole-backend audit | not stated (hung; no result) | — | — | hung for 90+ minutes | — |
| control room | #4 | `gpt-5.6-terra` / high | Judge-style audit against the official challenge texts | not a finding count (3 top gaps) | 2 acted on | — | 1 needs Omar (CRACI sign-up); score 8.0/10 | this commit |

**Totals from the 16 review and fact-check runs with numeric finding counts** (including the PR #8 second opinion;
the judge audit is separate):
- **112 findings:** 79 kept/fixed, 12 rejected, 10 deferred, 2 explicitly forwarded, and 6 already fixed. These
  statuses overlap where the logs say they do: some already-fixed items are also listed under kept/fixed, and one
  finding is partly fixed and deferred.
- Other exact statuses are 2 noted but not fixed (Room 2 #5), 2 left out (Room 3 #8), 4 still open in `decision/`
  (control room #2), and 1 reported to Room 2 but not fixed here (Room 3 #11).
- Three other review entries give no numeric finding count: Room 3 #1 (result none), Room 3 #2 (pending), and
  control-room #3 (hung/no result). The judge audit reports 3 top gaps, 2 acted on and 1 needing Omar; it does not
  give a finding total.
- The non-review entries include 6 draft attempts: 4 docs, the stopped M2 agent draft and 1 UI feature. The four
  docs and UI feature were kept after Claude's corrections; the M2 draft was stopped as stale.

Six more launches failed before doing anything: 2 in Room 2, 2 in Room 3 and 2 in the control room (one hung for over
90 minutes). The causes were `timeout` missing on macOS, and `codex exec` waiting on stdin when it was started from a
background shell. **What we learned: always run `codex exec ... < /dev/null`.** It is now in every room's playbook.

## Real bugs Codex caught that we fixed

Each item has a regression test.
- **Prompt-injection and grounding bypasses** in the buyer agent (`e48cffb`):
  - "milkshake" grounded "milk";
  - an empty query searched the whole catalogue;
  - the "l" in "lactose" counted as litres, and a catalogue unit (KI, 10x) could be spoofed;
  - "12 kg butter and 1 L milk" grounded 12 L of milk;
  - "20 L milk, lactose-free" lost the constraint;
  - duplicate items multiplied the order;
  - the rank call could be steered by the chef's text;
  - "9"×400 and a lone surrogate character crashed the route with a 500.
- **Decisions API answers weren't validated** (`c9dfdc5`). A NaN confidence counted as confident, because
  `NaN < 0.8` is false. The instruction-phrase flag also skipped the fallback path.
- **Stale approval** (`7c2e3bb`): a human could sign off on terms they never saw. Approve now returns 409 if
  anything changed during the re-check. The gate also refuses past dates, whoever calls it.
- **Unsafe substitutes and broken splits** (`aea3c82`):
  - free-from-only allergen data was counted as known;
  - `None == None` matched categories;
  - a zero-price substitute was offered;
  - split orders couldn't be re-posted and could exceed the route limits.
- **UI** (`a57d7cd`): a health-request race under React StrictMode, and approver names containing `:` broke the
  audit labels.
- **Docs that drifted from the code** (`019fd67`). The docs said Decisions confidence wasn't implemented, and that
  `/api/orders` took a mandate in the body. The exported `openapi.json` was also stale.

## What we rejected, and why

Codex was wrong often enough that every finding was checked against the code or a live measurement first.
- **"`noul` is misused as confidence"** (Room 3). For a yes/no question the API's `confidence` is
  max(P(yes), P(no)), so thresholding P(yes) is the correct and stricter reading.
- **"Use one batched Decisions call"**. Measured live, batching dropped lactose-free milk from 0.95 to 0.51. We
  kept one call per candidate.
- **"The reliability floor is approvable"** (Room 2). Correct as a description, but the team decided it should be
  approvable (D13: the chef may knowingly accept a less reliable supplier).
- **"`VITE_MOCK=1` enables mocks in production"** (Room 4). That is the intended switch for a mock deploy. A grep of
  the production bundle confirmed it holds no fixtures.
- **Stale-branch findings**. For example, "`line.facts` is never emitted" was reviewed before the merge that adds
  it.

## What we would do differently

Start every review from an immutable commit hash, close stdin from the start, and run the doc fact-check after the
last code merge rather than in parallel with it: most of the fact-check's 14 findings were drift, not mistakes.
