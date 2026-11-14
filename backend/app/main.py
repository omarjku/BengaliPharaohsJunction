"""Valio Aimo front door: API entry point. OpenAPI spec is served at /openapi.json, docs at /docs."""
from fastapi import FastAPI
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

from . import config, valio

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


class QuoteRequest(BaseModel):
    product_ids: list[str] = Field(min_length=1, max_length=valio.MAX_BATCH, examples=[["463335", "463038"]])
    requested_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", examples=["2026-11-16"])


@app.post("/api/quotes")
async def quotes(req: QuoteRequest) -> list[dict]:
    """Live price + availability from Valio for specific products, merged into one quote each,
    with explicit trap flags (cutoff_passed, quantity_unknown, undeliverable, out_of_stock, unknown_product)."""
    return await valio.get_quotes(req.product_ids, req.requested_date)
