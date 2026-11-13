# Junction 2026: team kit (Omar + Zoha)

You are helping one member of a two-person team at **Junction 2026** (Hype Areena, Espoo, Fri 13 – Sun 15 Nov 2026, Helsinki time). Teammates: **Omar Kassem** and **Fathia Fairuz Zoha (Zoha)**. Goal: win. Pick a strong main challenge, stack tech-challenge prizes, ship a working demo, and submit on time.

## Context files
- `docs/briefing.md`: everything from the opening ceremony (deadlines, prizes, schedule, booth map, contradictions).
- `docs/action_items.md`: checklists for tonight, Saturday and Sunday.
- `docs/challenges/INDEX.md`: all 38 challenges with prizes, **judging weights** and resources; full pages in `docs/challenges/*.md`. Read the full page before advising on a challenge. (The Valio key and portal password are removed here: get them from the platform page and keep them in `.env`.)
- `docs/challenge-board.html`: the visual comparison of main challenges vs the Gemini prize (download and open in a browser).
- `board.sh`: the agent message board (below).

## Hard facts (verify in docs/briefing.md if in doubt)
- Draft submission due **Fri 23:55**. Final submission **Sun 10:00**. **Both teammates must attend peer review Sun 10:30**, or the team loses eligibility for the main prize.
- Video max **2:00**, public. Omar plans to make it with RAEA.
- All code must be written at the event. Submissions are MIT-licensed.
- Shortlist so far:
  - **Valio Aimo, Trusted Trade Agents** (€4,000). The end-to-end demo is 30% of the score.
  - **Best Use of Gemini API** tech challenge (€4,000).
  - AfterQuery, Break the Agent (€3,000 + work trial).
  - Cala, Make Unicorns Real (€5,000 travel prize).
- The Valio page includes a shared mock-API key and portal password. Every participant gets them, but keep them out of public repos and commits; use a `.env` file listed in `.gitignore`.

## How to work with your teammate's agent (message board)
The team coordinates through one **pinned GitHub issue called "Message Board"** in the team repo. Each person's Claude reads it and posts to it.
- Set your name once: `export AGENT_NAME="Zoha's agent"` (or `"Omar's agent"`).
- **Before starting any task:** run `./board.sh read`. Don't duplicate work someone has claimed.
- **Claim work:** `./board.sh post "CLAIM: <task>, branch <name>"`.
- **Finish work:** open a PR, then `./board.sh post "DONE: <task>, PR #<n>, <one-line summary>"`.
- **Review a teammate's PR:** use `gh pr review <n>`, then post on the board and **@mention the author** with concrete, file-and-line feedback. Example: `@zoha-handle #12 changes requested: X overflows at 390px (styles.css:23); fix: …`.
- **Blocked?** Post `BLOCKED: <what>, need @teammate`.
- Keep posts to 3 lines at most. Humans read the board too.
- Never post secrets (API keys, passwords) on the board or in commits.
