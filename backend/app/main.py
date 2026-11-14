"""Valio Aimo front door: API entry point. OpenAPI spec is served at /openapi.json, docs at /docs."""
import re
import threading
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, StringConstraints, field_validator

from . import catalogue, config, quantity, valio

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Build/load the catalogue off the request path: first boot on Render downloads + indexes (~10-20 s).
    threading.Thread(target=catalogue.load, daemon=True).start()
    yield


app = FastAPI(
    lifespan=lifespan,
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
        "catalogue": catalogue.status(),
    }


ProductId = Annotated[str, StringConstraints(pattern=r"^\d{1,12}$")]  # Valio product codes are short digit strings
DATE_WINDOW_DAYS = 60


class QuoteRequest(BaseModel):
    product_ids: list[ProductId] = Field(min_length=1, max_length=valio.MAX_BATCH, examples=[["463335", "463038"]])
    requested_date: date = Field(examples=["2026-11-16"])

    @field_validator("requested_date")
    @classmethod
    def near_today(cls, d: date) -> date:
        if abs((d - date.today()).days) > DATE_WINDOW_DAYS:
            raise ValueError(f"requested_date must be within {DATE_WINDOW_DAYS} days of today")
        return d


@app.post("/api/quotes")
async def quotes(req: QuoteRequest) -> list[dict]:
    """Live price + availability from Valio for specific products, merged into one quote each,
    with explicit trap flags (cutoff_passed, quantity_unknown, undeliverable, out_of_stock, unknown_product)."""
    return await valio.get_quotes(req.product_ids, req.requested_date.isoformat())


def _catalogue_ready() -> None:
    st = catalogue.status()
    if not st["ready"]:
        raise HTTPException(503, detail=f"Catalogue loading{': ' + st['error'] if st['error'] else ''}; retry shortly")


Code = Annotated[str, StringConstraints(pattern=r"^[A-Z0-9_]{1,40}$")]  # claim / GS1 allergen codes


@app.get("/api/products/search")
def search_products(
    q: Annotated[str, Query(max_length=200)] = "",
    claims: Annotated[list[Code], Query(max_length=20)] = [],
    exclude_allergens: Annotated[list[Code], Query(max_length=20)] = [],
    strict_may_contain: bool = False,
    category: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict]:
    """Keyword search (English + Finnish names, brand) with hard filters.
    claims: all must be present (e.g. FREE_FROM_LACTOSE). exclude_allergens: GS1 codes (e.g. AM milk, AW gluten)
    the product must not CONTAIN (nor MAY_CONTAIN when strict_may_contain=true).
    Note: lactose-free milk still CONTAINS milk (AM); use the FREE_FROM_LACTOSE claim for lactose intolerance."""
    _catalogue_ready()
    return catalogue.search(q, claims, exclude_allergens, strict_may_contain, category, limit)


@app.get("/api/products/{product_id}")
def get_product(product_id: ProductId) -> dict:
    _catalogue_ready()
    if not (p := catalogue.get(product_id)):
        raise HTTPException(404, detail="Unknown product id")
    return p


class QuantityRequest(BaseModel):
    product_id: ProductId = Field(examples=["463335"])
    amount: float = Field(gt=0, le=1_000_000, allow_inf_nan=False, examples=[1000])
    unit: str = Field(max_length=5, examples=["L"])

    @field_validator("unit")
    @classmethod
    def known_unit(cls, u: str) -> str:
        if u.lower() not in quantity.MEASURES and not re.fullmatch(r"[A-Z]{2,4}", u):
            raise ValueError("unit must be one of L, dl, cl, ml, kg, g, pcs, units, or a product unit code like KI or ST")
        return u


@app.post("/api/quantity/resolve")
def resolve_quantity(req: QuantityRequest) -> dict:
    """Human amount ("1000 L", "40 kg", "12 pcs", "3 KI") → sales units to order, rounded up to whole units and
    the lot size, with over-delivery. Never guesses: missing or contradictory data gives quantity=null and
    needs_confirmation=true; a conversion that rests on an assumption gives an answer with needs_confirmation=true."""
    _catalogue_ready()
    if not (p := catalogue.get(req.product_id)):
        raise HTTPException(404, detail="Unknown product id")
    return quantity.resolve(p, req.amount, req.unit)
