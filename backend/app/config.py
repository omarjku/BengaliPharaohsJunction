"""Settings from environment variables. Locally they come from the repo-root .env (git-ignored);
on Render they are set in the service's Environment tab."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

VALIO_BASE_URL = os.getenv("VALIO_BASE_URL", "https://junction26.valioaimo.fi")
VALIO_API_KEY = os.getenv("VALIO_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Comma-separated origins allowed to call the API (the frontend's URL on Render, plus local dev).
FRONTEND_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
# Front-door API keys, comma-separated `key=buyer_id[:name]`. Unset → the order/audit routes return 503 (never open).
# AGENT_KEYS: purchasing agents placing orders (X-Agent-Key). APPROVER_KEYS: humans signing off (X-Approver-Key).
AGENT_KEYS = os.getenv("AGENT_KEYS", "")
APPROVER_KEYS = os.getenv("APPROVER_KEYS", "")
