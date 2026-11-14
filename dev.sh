#!/bin/bash
# One command for local dev: backend on :8000, frontend on :5173 (proxies /api to the backend).
# First run installs dependencies. Ctrl-C stops both.
set -e
cd "$(dirname "$0")"
[ -f .env ] || { echo "No .env: copy .env.example to .env and fill in the keys"; exit 1; }
[ -d backend/.venv ] || (cd backend && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt)  # run from backend/: requirements reference ../contracts
[ -d frontend/node_modules ] || (cd frontend && npm install --silent)
trap 'kill 0' EXIT
(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) &
(cd frontend && npm run dev -- --port 5173) &
wait
