"""Valio Aimo front door: API entry point. OpenAPI spec is served at /openapi.json, docs at /docs."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config

app = FastAPI(
    title="Valio Aimo Front Door",
    description="Open interface for external purchasing agents ordering from Valio Aimo (Junction 2026).",
    version="0.1.0",
)
app.add_middleware(CORSMiddleware, allow_origins=config.FRONTEND_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health() -> dict:
    """Liveness check; reports which keys are configured (never their values)."""
    return {
        "status": "ok",
        "valio_key_configured": bool(config.VALIO_API_KEY),
        "gemini_key_configured": bool(config.GEMINI_API_KEY),
    }
