"""Settings from environment variables. Locally they come from the repo-root .env (git-ignored);
on Render they are set in the service's Environment tab."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

VALIO_BASE_URL = os.getenv("VALIO_BASE_URL", "https://junction26.valioaimo.fi")
VALIO_API_KEY = os.getenv("VALIO_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-4-hydrogen")
GEMINI_DECISION_MODEL = os.getenv("GEMINI_DECISION_MODEL", "gemini-decision-1")  # Decisions API
GEMINI_LISTEN_MODEL = os.getenv("GEMINI_LISTEN_MODEL", "gemini-3.5-transcribe-live")  # voice (Live API)
GEMINI_TALK_MODEL = os.getenv("GEMINI_TALK_MODEL", "gemini-3.8-live")  # Talk: the voice conversation (live.py)
TALK_ENABLED = os.getenv("TALK_ENABLED", "1") == "1"  # off → /api/live refuses; /api/health reports talk: false
# Comma-separated origins allowed to call the API (the frontend's URL on Render, plus local dev).
FRONTEND_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
# Front-door API keys, comma-separated `key=buyer_id[:name]`. Unset → the order/audit routes return 503 (never open).
# AGENT_KEYS: purchasing agents placing orders (X-Agent-Key). APPROVER_KEYS: humans signing off (X-Approver-Key).
AGENT_KEYS = os.getenv("AGENT_KEYS", "")
APPROVER_KEYS = os.getenv("APPROVER_KEYS", "")
# VALIO_ADMIN_KEYS: Valio staff reading every buyer's audit trail (X-Valio-Admin-Key), `key=valio[:name]`. Read-only.
VALIO_ADMIN_KEYS = os.getenv("VALIO_ADMIN_KEYS", "")
# Base64 of a 32-byte Ed25519 private key; signs every order response (signing.py). Unset → ephemeral dev key.
FRONT_DOOR_SIGNING_KEY = os.getenv("FRONT_DOOR_SIGNING_KEY", "")
# 1 enables POST /api/admin/demo/reset (archives orders / audit / idempotency keys, starts fresh). Off by default.
# Optional RFC 9421 request signing: comma list of `buyer:kid:base64pub` (raw 32-byte Ed25519 public keys). A buyer
# listed here must sign POST /api/orders and /api/agent/* (backend/app/httpsig.py); others work as before.
AGENT_SIGNING_KEYS = os.getenv("AGENT_SIGNING_KEYS", "")
DEMO_RESET_ENABLED = os.getenv("DEMO_RESET_ENABLED", "").lower() in ("1", "true", "yes")
# 1 enables the QR test-kitchen route; off by default so a deployment never opens anonymous buyers accidentally.
SANDBOX_ENABLED = os.getenv("SANDBOX_ENABLED", "") == "1"
# Where the front door keeps its state (orders, audit trail, idempotency keys; stored mandates once they leave the
# code). Default: the repo's data/. Point it at a mounted persistent disk (e.g. Render's /var/data) to keep state.
DATA_DIR = Path(os.getenv("DATA_DIR") or Path(__file__).resolve().parents[2] / "data")
# Set to 1 only behind a proxy that appends the client address to X-Forwarded-For (Render does): the rate limiter
# then uses that last hop as the caller's IP. Unset: the TCP peer address (a direct caller can't spoof it).
TRUST_X_FORWARDED_FOR = os.getenv("TRUST_X_FORWARDED_FOR", "").lower() in ("1", "true", "yes")
