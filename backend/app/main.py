"""Valio Aimo front door: API entry point. OpenAPI spec is served at /openapi.json, docs at /docs."""
import re
import threading
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from trade_contracts import Mandate

from . import agent, auth, menu, catalogue, config, gate, mandates, orders, quantity, signing, valio

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
# Auth (auth.py): X-Agent-Key places orders; X-Approver-Key reads / approves / rejects / audits. The buyer and the
# approver's name come from the key. ONE uvicorn worker only: orders.py keeps its lock and store in-process.
BuyerId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")]
OrderId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f-]{36}$")]  # uuid4
MAX_ORDER_LINES = gate.MAX_ORDER_LINES  # one source: the gate only proposes orders that fit these
MAX_BODY_BYTES = 64 * 1024  # a full order (50 lines) is ~3 KB
Agent = Annotated[auth.Principal, Depends(auth.agent)]
Approver = Annotated[auth.Principal, Depends(auth.approver)]


@app.middleware("http")
async def limit_body(request: Request, call_next):
    """Refuse oversized bodies before they are read. Bodies without a Content-Length (chunked) are refused too,
    since their size can't be checked up front; every normal JSON client sends one."""
    if request.method in ("POST", "PUT", "PATCH"):
        size = request.headers.get("content-length")
        if size is None and request.headers.get("transfer-encoding"):
            return JSONResponse({"detail": "Content-Length required"}, status_code=411)
        if size is not None and (not size.isdigit() or int(size) > MAX_BODY_BYTES):
            return JSONResponse({"detail": f"Request body over {MAX_BODY_BYTES} bytes"}, status_code=413)
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 without echoing the input back: a NaN in the body can't be JSON-encoded (it was a 500), and the
    client already has what it sent."""
    return JSONResponse({"detail": [{k: e[k] for k in ("type", "loc", "msg") if k in e} for e in exc.errors()]},
                        status_code=422)


class OrderLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: ProductId
    quantity: float = Field(gt=0, le=gate.MAX_LINE_QTY, allow_inf_nan=False,
                            description="In the product's sales unit (see the quote's sales_unit).")


class OrderRequest(BaseModel):
    """An order at fixed prices. Price and stock are re-read from Valio here; the client can't set them.
    The buyer is the one the X-Agent-Key belongs to; buyer_id is optional and must match it if sent.
    No mandate field: the order is judged by the buyer's mandate stored at Valio (sending one is a 422)."""
    model_config = ConfigDict(extra="forbid")
    buyer_id: BuyerId | None = None
    requested_date: date = Field(examples=["2026-11-16"])
    lines: list[OrderLine] = Field(min_length=1, max_length=MAX_ORDER_LINES)

    @field_validator("requested_date")
    @classmethod
    def near_today(cls, d: date) -> date:
        if d < date.today():
            raise ValueError("requested_date is in the past")
        return QuoteRequest.near_today(d)

    @model_validator(mode="after")
    def _consistent(self) -> "OrderRequest":
        if len({ln.product_id for ln in self.lines}) != len(self.lines):
            raise ValueError("each product_id may appear once per order")
        return self


def _mandate_for(who: auth.Principal, req: OrderRequest) -> Mandate | None:
    """The mandate this order is judged by: the key's buyer's, stored server-side. None → refused (MANDATE_MISSING)."""
    if (req.buyer_id or who.buyer_id) != who.buyer_id:
        raise HTTPException(403, detail="This agent key may only order for its own buyer")
    return mandates.get(who.buyer_id)


@app.post("/api/orders")
async def place_order(req: OrderRequest, who: Agent) -> dict:
    """Valio's front door (D2): re-checks the order against hard rules with fresh quotes. AUTO → confirmed,
    ASK_HUMAN → pending_approval, a hard violation or something Valio can't deliver → refused (nothing stored),
    always with reasons, suggested fixes and alternatives. Every run is audited. Needs X-Agent-Key."""
    mandate = _mandate_for(who, req)
    _catalogue_ready()
    return await orders.place(who.buyer_id, req.requested_date, req.lines, mandate)


@app.get("/api/orders/{order_id}")
def get_order(order_id: OrderId, who: Approver) -> dict:
    """One of the approver's buyer's orders. Needs X-Approver-Key."""
    return orders.get(order_id, who.buyer_id)


class SignOff(BaseModel):
    """Optional approve body. decided_at = the decision.decided_at the human was shown; send it so a click can
    only ever sign off that decision (409 if the order was re-decided since). Other fields are ignored."""
    decided_at: AwareDatetime | None = None


@app.post("/api/orders/{order_id}/approve")
async def approve_order(order_id: OrderId, who: Approver, body: SignOff | None = None) -> dict:
    """Human sign-off as the key's owner; re-runs the gate first (cut-offs pass, prices and stock change).
    Needs X-Approver-Key. The approver's name comes from the key, never the body."""
    _catalogue_ready()
    return await orders.approve(order_id, who, body.decided_at if body else None)


@app.post("/api/orders/{order_id}/reject")
async def reject_order(order_id: OrderId, who: Approver) -> dict:
    """Human refusal as the key's owner. Needs X-Approver-Key; a request body is ignored."""
    return await orders.reject(order_id, who)


@app.get("/api/audit")
def audit(who: Approver, buyer_id: BuyerId | None = None, limit: Annotated[int, Query(ge=1, le=1000)] = 100) -> list[dict]:
    """The approver's buyer's audit trail (contract AuditEntry objects), oldest first. buyer_id, if sent, must
    be that buyer. Needs X-Approver-Key."""
    if (buyer_id or who.buyer_id) != who.buyer_id:
        raise HTTPException(403, detail="This approver key may only read its own buyer's audit trail")
    return orders.audit_log(who.buyer_id, limit)


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signed_statement: dict
    signature: dict


@app.get("/.well-known/front-door-keys.json")
def front_door_keys() -> dict:
    """The front door's public signing key(s) as a JWK Set (RFC 8037, Ed25519), matched by `kid`."""
    return signing.jwks()


@app.post("/api/verify")
def verify_statement(req: VerifyRequest) -> dict:
    """Checks an order response's `signed_statement` + `signature`. valid=true proves this front door issued
    exactly that statement (decision + quote facts as Valio's API reported them at fetched_at); it does not prove
    the stock is physically there. Public: anyone holding a statement may check it."""
    ok = signing.verify(req.signed_statement, req.signature)
    return {"valid": ok, "kid": signing.KID,
            "meaning": "Issued by this Valio front door, unchanged." if ok else "Not issued by this front door, or changed."}


@app.get("/api/admin/audit")
def admin_audit(who: Annotated[auth.Principal, Depends(auth.valio_admin)], buyer_id: BuyerId | None = None,
                outcome: Literal["AUTO", "ASK_HUMAN", "DECLINE"] | None = None,
                limit: Annotated[int, Query(ge=1, le=1000)] = 100) -> list[dict]:
    """Valio's side of the audit trail: every buyer's entries (contract AuditEntry objects), oldest first,
    optionally for one buyer and/or one decision outcome. Needs X-Valio-Admin-Key; read-only."""
    return orders.audit_log(buyer_id, limit, outcome)


# --- Milestone 1 buyer agent: text -> catalogue -> Valio quote -> quantity -> decision -> front-door order -> audit.
class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000, examples=["1000 L lactose-free milk for Monday"])
    requested_date: date = Field(examples=["2026-11-16"])
    @field_validator("text")
    @classmethod
    def utf8(cls, t: str) -> str:
        t.encode("utf-8")  # a lone surrogate ("\ud800") raises here → 422, not a 500 when audited
        return t

    buyer_id: BuyerId | None = Field(default=None, examples=["lapland-kitchen"],
                                     description="Optional; the buyer is the X-Agent-Key's and this must match it.")

    @field_validator("requested_date")
    @classmethod
    def near_today(cls, d: date) -> date:
        return OrderRequest.near_today(d)


@app.post("/api/agent/run")
async def agent_run(req: AgentRunRequest, who: Agent) -> dict:
    """The buyer's agent end to end. Needs X-Agent-Key: the buyer comes from the key, and the mandate is loaded
    server-side for that buyer (never from the client).
    Returns {request, lines, decision, order, audit_id}: every candidate quoted (chosen or not, with why), a contract
    Decision, the front door's order response when an order was placed (else null), and the audit entry id."""
    if (req.buyer_id or who.buyer_id) != who.buyer_id:
        raise HTTPException(403, detail="This agent key may only run the agent for its own buyer")
    _catalogue_ready()
    return await agent.run(req.text, req.requested_date, who.buyer_id)


# --- T15 menu → cart: a proposal only (always ASK_HUMAN); the chef orders it by posting order_lines to /api/orders.
class MenuRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    menu_text: str = Field(min_length=1, max_length=4000,
                           examples=["Reindeer stew with mashed potatoes; lingonberry cheesecake"])
    covers: int = Field(ge=1, le=2000, examples=[80])
    requested_date: date = Field(examples=["2026-11-16"])

    @field_validator("menu_text")
    @classmethod
    def utf8(cls, t: str) -> str:
        return AgentRunRequest.utf8(t)

    @field_validator("requested_date")
    @classmethod
    def near_today(cls, d: date) -> date:
        return OrderRequest.near_today(d)


@app.post("/api/agent/menu")
async def agent_menu(req: MenuRequest, who: Agent) -> dict:
    """Menu + covers → a proposed cart. Needs X-Agent-Key (the buyer comes from the key; mandate server-side).
    Returns {menu, assumptions, ingredients, lines, cart_total_cents, order_lines, decision, audit_id}; the decision is
    always ASK_HUMAN (MENU_ASSUMPTIONS) and nothing is ordered here."""
    _catalogue_ready()
    return await menu.propose(req.menu_text, req.covers, req.requested_date, who.buyer_id)
