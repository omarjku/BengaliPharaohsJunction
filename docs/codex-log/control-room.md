# Codex log: control room (orchestrator)

The control room merges the rooms' branches and runs independent Codex checks. Raw outputs are in `control-room/`.

| # | When (Sat 14 Nov, Helsinki) | Model / effort | Ask | Result | Kept |
|---|---|---|---|---|---|
| 1 | ~03:20 | `gpt-6-luna` / high | Adversarial review of `omar/m1-integration` (agent flow, quantity, UI) | 4 findings: HIGH `/api/agent/run` let a caller act as any buyer; HIGH chef text could steer the Gemini parse (prompt injection); MED missing amounts rendered as "null null milk"; LOW unknown stock labelled "supplier delivers" | All 4 fixed: agent key + injection guard (Room 3, `7d5be18`), null/stock labels (Room 4, `a57d7cd`) |
| 2 | ~03:20 | `gpt-6-luna` / high | Independent second opinion on Zoha's PR #8 (`decide()`), without seeing Claude's review | 4 findings; 3 match Claude's reviewer independently (unavailable → AUTO, fail-closed crash on a naive datetime, regex DECLINE on normal chef text) plus duplicate ids where the last silently wins | Posted to the team board for Zoha (03:29); still open in `decision/`, so `decide()` isn't wired into the agent |
| 3 | ~04:10 | `gpt-5.6-terra` / ultra | Whole-backend audit | Hung waiting on stdin for 90+ min; killed, no result | Lesson: always run `codex exec … < /dev/null` (added to the rooms' playbook) |
| 4 | ~04:15 → 09:20 | `gpt-5.6-terra` / high | Judge-style criteria audit against the official challenge texts (first run hung on stdin; rerun with `< /dev/null`) | Weighted Valio score 8.0/10 (J3 9.0, J4 8.5); Gemini 8.5, Codex 7.0. Top gaps: inconsistent demo story across docs, no CRACI workflow, Gemini threshold not validated | Docs reconciliation (Room 1), a Gemini eval set (Room 3); CRACI needs Omar to sign up. Raw output in `control-room/criteria-judge-audit.md` |

Setup notes: on our ChatGPT login, the old model names (`gpt-5.5`, `gpt-5-codex` …) are rejected. The available ones are listed in `~/.codex/models_cache.json` (`gpt-reserve`, `gpt-6-luna`, `gpt-5.6-terra`, `gpt-5.6-luna`). Default set to `gpt-reserve` at `max`.
