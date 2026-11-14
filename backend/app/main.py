"""Valio Aimo front door: API entry point. OpenAPI spec is served at /openapi.json, docs at /docs."""
import re
import threading
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from trade_contracts import Mandate

from . import agent, catalogue, config, orders, quantity, valio

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


# --- Front door: orders + audit (T07). Responses: {order_id, status, audit_id, total_cents, lines, decision,
# rejected_options}; status is confirmed | pending_approval | refused | rejected; decision is a contract Decision.
BuyerId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")]
OrderId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f-]{36}$")]  # uuid4
MAX_ORDER_LINES = 50


class OrderLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: ProductId
    quantity: float = Field(gt=0, le=100_000, description="In the product's sales unit (see the quote's sales_unit).")


class OrderRequest(BaseModel):
    """An order at fixed prices. Price and stock are re-read from Valio here; the client can't set them."""
    model_config = ConfigDict(extra="forbid")
    buyer_id: BuyerId
    requested_date: date = Field(examples=["2026-11-16"])
    lines: list[OrderLine] = Field(min_length=1, max_length=MAX_ORDER_LINES)
    mandate: Mandate

    @field_validator("requested_date")
    @classmethod
    def near_today(cls, d: date) -> date:
        return QuoteRequest.near_today(d)

    @model_validator(mode="after")
    def _consistent(self) -> "OrderRequest":
        if len({ln.product_id for ln in self.lines}) != len(self.lines):
            raise ValueError("each product_id may appear once per order")
        if self.mandate.buyer_id != self.buyer_id:
            raise ValueError("mandate.buyer_id must match buyer_id")
        return self


class SignOff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approver: Annotated[str, StringConstraints(pattern=r"^[\w .'-]{1,64}$")] = Field(examples=["Chef Aino"])


@app.post("/api/orders")
async def place_order(req: OrderRequest) -> dict:
    """Valio's front door (D2): re-checks the order against hard rules with fresh quotes. AUTO → confirmed,
    ASK_HUMAN → pending_approval, a hard violation or something Valio can't deliver → refused (nothing stored),
    always with reasons, suggested fixes and alternatives. Every run is audited."""
    _catalogue_ready()
    return await orders.place(req.buyer_id, req.requested_date, req.lines, req.mandate)


@app.get("/api/orders/{order_id}")
async def get_order(order_id: OrderId) -> dict:
    return orders.get(order_id)


@app.post("/api/orders/{order_id}/approve")
async def approve_order(order_id: OrderId, body: SignOff) -> dict:
    """Human sign-off; re-runs the gate first (cut-offs pass, prices and stock change)."""
    _catalogue_ready()
    return await orders.approve(order_id, body.approver)


@app.post("/api/orders/{order_id}/reject")
async def reject_order(order_id: OrderId, body: SignOff) -> dict:
    return await orders.reject(order_id, body.approver)


@app.get("/api/audit")
def audit(buyer_id: BuyerId, limit: Annotated[int, Query(ge=1, le=1000)] = 100) -> list[dict]:
    """The buyer's audit trail (contract AuditEntry objects), oldest first."""
    return orders.audit_log(buyer_id, limit)


# --- Milestone 1 buyer agent: text -> catalogue -> Valio quote -> quantity -> decision -> front-door order -> audit.
class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000, examples=["1000 L lactose-free milk for Monday"])
    requested_date: date = Field(examples=["2026-11-16"])
    buyer_id: BuyerId = Field(examples=["lapland-kitchen"])

    @field_validator("requested_date")
    @classmethod
    def near_today(cls, d: date) -> date:
        return QuoteRequest.near_today(d)


@app.post("/api/agent/run")
async def agent_run(req: AgentRunRequest) -> dict:
    """The buyer's agent end to end. The mandate is loaded server-side for buyer_id (never from the client).
    Returns {request, lines, decision, order, audit_id}: every candidate quoted (chosen or not, with why), a contract
    Decision, the front door's order response when an order was placed (else null), and the audit entry id."""
    _catalogue_ready()
    return await agent.run(req.text, req.requested_date, req.buyer_id)
