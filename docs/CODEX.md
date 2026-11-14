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
| `gpt-reserve` | max | Drafts and design attacks |
| `gpt-5.6-terra` | ultra (once high) | Adversarial reviews and the docs fact-check |
| `gpt-6-luna` | high | Control-room reviews: the integration branch, and a blind second opinion on PR #8 |

## Run by run

"Kept" means fixed in our code, or (for docs) the claim was corrected.

| Room | Run | Model | Findings | Kept | Rejected | Other | Fix commit |
|---|---|---|---|---|---|---|---|
| 1 docs | Draft README, ASSUMPTIONS, STANDARDS, NEXT-STEPS (4 runs) | reserve/max | 4 drafts | 4 drafts, fact-checked | 2 claims removed | 3 fixes by Claude | `5ed1e86` |
| 1 docs | Fact-check every doc claim against the code | terra/ultra | 14 | 12 | 2 | | `019fd67` |
| 1 docs | Review of the M2 ranking and "why" text | terra/ultra | 5 | 4 (1 code bug) | 1 | | `019fd67` |
| 2 front door | Adversarial review of the front door | terra/ultra | 7 | 2 | 1 (by team decision D13) | 1 already fixed, 2 deferred, 1 forwarded | `7c2e3bb` |
| 2 front door | Adversarial review of splits and substitutes | terra/ultra | 7 | 6 | 1 | | `aea3c82` |
| 3 agent | Adversarial review of the agent hardening (`7d5be18`) | terra/ultra | 10 (8 High) | 8 | 0 | 3 already fixed (one also kept) | `e48cffb` |
| 3 agent | Design attack on Gemini Decisions confidence | reserve/max | 10 (5 "P0") | 5 | 4, with measurements | 3 deferred | `c9dfdc5` |
| 4 UI | Draft the auth UI (keys panel, headers, errors) | reserve/max | 1 feature | Most of it | 4 parts rewritten | | `a57d7cd` |
| 4 UI | Adversarial review of `frontend/src` | terra/ultra | 4 | 2 | 1 | 1 forwarded to backend | `a57d7cd` |
| 4 UI | Review of the M2 UI diff | terra/high | 1 | 0 | 1 (stale branch) | | none |
| control room | Adversarial review of `omar/m1-integration` | luna/high | 4 (2 High) | 4 | 0 | | `7d5be18`, `a57d7cd` |
| control room | Blind second opinion on PR #8 | luna/high | 4 | 3 matched Claude's | 0 | open in `decision/` | none yet |
| control room | Judge-style audit against the official challenge texts | terra/high | score 8.0/10 for Valio; 3 top gaps | 2 acted on (docs reconciled, Gemini eval set) | | 1 needs Omar (CRACI sign-up) | this commit |

**Totals across the nine review and fact-check runs** (not counting PR #8 or the judge audit):
- 62 findings: 43 kept and fixed, 11 rejected with a reason, 4 already fixed, 5 deferred to production next steps,
  2 forwarded to another room. A finding that was partly fixed and partly deferred counts once in each.
- 4 more findings came from the PR #8 second opinion, and 3 of them matched Claude's independently.
- The judge audit scored the Valio entry 8.0/10 and named three gaps. The first, "demo truth is inconsistent", is
  why every doc now tells the same milk story.
- 6 drafts: 4 docs and 1 UI feature (plus a second draft that was stopped). All were kept after Claude's
  corrections.

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
