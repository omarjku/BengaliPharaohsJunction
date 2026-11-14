# Engine status, for Zoha's agent (Sat 14 Nov, about 21:00 Helsinki)

Omar wants us working on the engine together from different angles so it lands faster. This page says what's built, where, what's broken, who is fixing what right now, and where your agent can help **without colliding**.

## 1. What's live vs what isn't
- **Live on main / Render** is the OLD engine: keyword router plus regex follow-ups.
  - Omar's 19:00 test on main ("40 kg brown rice and enough tomato for pizza for 60 pizzas") shows the old behaviour: "Which one did you mean?" loops on "2" and "3", one-option questions, and choices mixing tomatoes and rice.
  - These are fixed or being fixed on the release branch, not on main.
- **Branch `release`** (pushed, about e59f211; not merged to main) holds the new engine and features:
  - **one brain:** every turn, replies included, goes through `backend/app/understand.py`, one Gemini call with the conversation, cart, profile and kitchen context
  - the Gemini schema fix (`agent._api_schema`; before it, every structured Gemini call silently failed with HTTP 400 and fell back to regex)
  - standing orders as one cart
  - the kitchen interview (voice and text) and editable history (example data labelled)
  - the calendar with weekly menus
  - QR sandboxes (`POST /api/sandbox`, `#try`)
  - the diet levels (`diet.py`) and search expansion (`expand.py`)
  - Talk transcript cleanup and a `current_order` tool
  - Zoha's #110 merged in

  656 backend tests pass; the frontend builds and lints.
- **The merge gate:** 22 real-Gemini conversations (`scripts/acceptance_flows.py`, F1–F22) plus safety tests. Nothing goes to main until they pass.

## 2. Measured quality (real Gemini, local backend)
| Run | Result |
|---|---|
| F1–F12 on the one-brain engine before the squad fixes | 7/12 |
| F13–F22 (new features) on aa53219 | 7/10 |
| Claude "peer-review judge" simulation, about 30 conversations | 5/20 chef happiness. Safety held; ordering UX poor |
| Independent code review | 8 correctness bugs (listed in section 3) |
| Codex security review | 1 HIGH, 2 MEDIUM (listed in section 3) |

## 3. Known problems being fixed RIGHT NOW (wave 2: 4 Codex agents, each owns files)
| Agent | Files | Fixes |
|---|---|---|
| w2-21 | `agent.py`, `diet.py` (+ alternatives in `gate.py`) | filler words ("Hi, …", "thanks") blocking orders; grounding vs self-corrections and Finnish inflection (voita, mozzarellaa); a gluten-free kitchen unable to order plain butter (diet regression); unsafe alternatives (peanut butter offered for butter); one-option "Which one did you mean: 1) X?" |
| w2-22 | `ask.py` | the answer loop ("1"/"2"/"3" → the same question); change_cart placing a second order; double pending orders; "order that cart"; cancel crash (ask.py ~1134); "approve everything" → polite refusal; "forget gluten-free" really revokes; product_info wiring |
| w2-23 | `understand.py`, new `product_info.py` | price/allergen questions without ordering; "2.5 kg" read as a date; unicorns = off-topic; stated amounts + event context stay an order; confirmation phrases |
| w2-24 | `live.py`, `conversation.py`, `urgent.py`, `auth.py`, `sandbox.py` | voice orders always held; Helsinki time; replies in the chef's language with human words; confirmations listing all lines; sandbox keys dying when disabled; buyer-id path safety; onboarding text as data in prompts |

Full findings: `docs/ENGINE-STATUS-FINDINGS.md` (same PR).

## 4. Where your agent can help without collisions (pick any; please claim on the board first)
1. **Frontend question rendering (high value, no overlap):** Omar's screenshot shows the choice chips of a "Which one did you mean?" question mixing items (Tomato NL/BE/ES, Rice brown, Tomato Finland). Check `Conversation.tsx` / `RunResult.tsx`: chips must belong to the ONE line being asked about, show the line name ("Which tomatoes for the pizzas?"), and answering a chip must send it as that line's choice. Also show "One thing first" only once. Branch from `origin/release`, frontend files only.
2. **Independent live testing (high value):**
   - Run `scripts/acceptance_flows.py` and your own judge-style conversations against a local backend on branch `release`, after wave 2 merges (I'll post "WAVE 2 MERGED").
   - Report failures on the board with the exact chef line and reply.
   - Setup: `cd backend && DATA_DIR=$(mktemp -d) SANDBOX_ENABLED=1 PYTHONPATH=$(pwd)/../contracts:$(pwd)/../compiler:$(pwd)/../profile .venv/bin/python -m uvicorn app.main:app --port 8765`, with `.env` and `data/catalogue_slim.json` present.
   - Run tests offline with `GEMINI_API_KEY=` (a live key makes some tests non-hermetic).
3. **Catalogue and allergen data sanity:** spot-check 20 common kitchen products (butter, milk, cream, flour, rice, tomatoes, pasta, cheese) for their allergen declarations and pack sizes in `data/catalogue_slim.json` versus how `diet.py`, `quantity.py` and `gate.py` interpret them. Report surprises.
4. **Your judging plan items** (deck, docs truth pass, Codex and Gemini slides) stay yours.

Please don't edit `agent.py`, `ask.py`, `understand.py`, `diet.py`, `live.py` or `conversation.py` until "WAVE 2 MERGED" is on the board; four agents are in them.
