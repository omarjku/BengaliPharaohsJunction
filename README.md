# Bengali Pharaohs: Junction 2026

Team: Omar Kassem + Fathia Fairuz Zoha. Junction 2026, Espoo, 13–15 Nov 2026.

**Status (Fri evening):** choosing our main challenge. We're entering the **Best Use of Gemini API** tech challenge either way.

## Start here
- `CLAUDE.md`: context and team rules. If you use Claude Code, it reads this automatically.
- `docs/briefing.md`: deadlines, prizes, schedule, booth map.
- `docs/challenges/INDEX.md`: all 38 challenges with judging weights.
- `docs/challenge-board.html`: download and open in a browser to compare challenges visually.
- `docs/action_items.md`: checklists.

## Deadlines
Draft **Fri 23:55** · Final **Sun 10:00** · Peer review **Sun 10:30** (both of us must be there).

## Run locally
```bash
cp .env.example .env    # then fill in VALIO_API_KEY and GEMINI_API_KEY
./dev.sh                # backend http://localhost:8000 (API docs at /docs), frontend http://localhost:5173
```
- `backend/`: Python FastAPI. The OpenAPI spec is generated at `/openapi.json`.
- `frontend/`: Vite + React + TypeScript. In production it calls the backend at `VITE_API_URL`.
- Calls to Valio's API must send a `User-Agent` header (see `docs/valio-api-notes.md`).

## Front door auth (backend)
The order routes need API keys from env (see `.env.example`), as comma-separated `key=buyer_id[:name]` lists:
- `AGENT_KEYS`: the buyer's purchasing agent sends `X-Agent-Key` to `POST /api/orders`. The buyer comes from the key (a different body `buyer_id` is 403) and the order is judged by that buyer's mandate stored server-side (`backend/app/mandates.py`, demo buyer `lapland-kitchen`); a `mandate` in the body is a 422, and a buyer with no stored mandate is refused with `MANDATE_MISSING`. Approve re-checks against the buyer's current stored mandate.
- `APPROVER_KEYS`: a human sends `X-Approver-Key` to `GET /api/orders/{id}`, `POST /api/orders/{id}/approve|reject` and `GET /api/audit`, for their own buyer only. `signed_off_by` is the key's name, never the body. Agent keys never approve.
- Neither set: those routes answer 503 (the door is never open by default).
- Run **one** uvicorn worker (`uvicorn app.main:app`, no `--workers N`): the order lock and store are in-process.

## Agent message board
We coordinate through the pinned **Message Board** issue. Each person's Claude reads it before starting work and posts claims, PRs and review requests there. Run `./board.sh` for usage.

## Secrets
Never commit keys. Copy `.env.example` to `.env` (gitignored) and fill in `VALIO_API_KEY` / `GEMINI_API_KEY` locally.
