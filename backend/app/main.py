"""Valio Aimo front door: API entry point. OpenAPI spec is served at /openapi.json, docs at /docs."""
import asyncio
import hashlib
import json
import logging
import math
import os
import re
import threading
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import (AwareDatetime, BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StringConstraints,
                      field_validator, model_validator)
from trade_contracts import Mandate

from . import (agent, ask, auth, catalogue, calendar as kitchen_calendar, chat_agent, config, gate, httpsig, interview, kitchen,
               live, mandates, menu, orders, profile, progress, quantity, ratelimit, rules, sandbox, signing, valio, vision,
               voice)

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


@app.post("/api/sandbox")
def create_sandbox(request: Request) -> dict:
    """Mint a 24-hour QR test kitchen; its credentials are returned only in this response."""
    if not config.SANDBOX_ENABLED:
        raise HTTPException(404, detail="Test kitchens are switched off")
    if (wait := ratelimit.wait_s("sandbox", ratelimit.client_ip(request))) > 0:
        raise HTTPException(429, detail="Too many test kitchens from this network, try again in a while",
                            headers={"Retry-After": str(math.ceil(wait))})
    return sandbox.mint()


@app.get("/api/health")
def health() -> dict:
    """Liveness check; reports which keys are configured (never their values) and the deployed git commit
    (RENDER_GIT_COMMIT, set by Render on every deploy), so a release check knows exactly what is live."""
    return {
        "status": "ok",
        "commit": os.getenv("RENDER_GIT_COMMIT") or None,
        "valio_key_configured": bool(config.VALIO_API_KEY),
        "gemini_key_configured": bool(config.GEMINI_API_KEY),
        "talk": config.TALK_ENABLED and bool(config.GEMINI_API_KEY),
        "catalogue": catalogue.status(),
    }


ProductId = Annotated[str, StringConstraints(pattern=r"^\d{1,12}$")]  # Valio product codes are short digit strings
DATE_WINDOW_DAYS = 60
KitchenDate = date


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
    with explicit trap flags (cutoff_passed, quantity_unknown, quantity_unreported, undeliverable, out_of_stock,
    unknown_product). Money: `unit_price_cents` (integer, net of VAT); `price` is the same in euros, kept for
    compatibility."""
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
Agent = Annotated[auth.Principal, Depends(httpsig.signed_agent)]  # + RFC 9421 if the buyer registered a key
Approver = Annotated[auth.Principal, Depends(auth.approver)]


@app.middleware("http")
async def limit_body(request: Request, call_next):
    """Refuse oversized bodies before they are read. Bodies without a Content-Length (chunked) are refused too,
    since their size can't be checked up front; every normal JSON client sends one."""
    if request.method in ("POST", "PUT", "PATCH"):
        size = request.headers.get("content-length")
        if size is None and request.headers.get("transfer-encoding"):
            return JSONResponse({"detail": "Content-Length required"}, status_code=411)
        cap = {"/api/voice/transcribe": voice.MAX_BYTES,  # audio clips; photos (+ multipart overhead)
               "/api/vision/read": vision.MAX_BYTES + 64 * 1024}.get(request.url.path, MAX_BODY_BYTES)
        if size is not None and (not size.isdigit() or len(size) > 12 or int(size) > cap):  # no 5,000-digit int()
            return JSONResponse({"detail": f"Request body over {cap} bytes"}, status_code=413)
    return await call_next(request)


app.middleware("http")(ratelimit.middleware)  # per key / per IP token buckets → 429 + Retry-After
IdemKey = Annotated[str | None, Header(pattern=r"^[\x21-\x7e]{1,255}$",
                                       description="Optional. Retrying with the same key and body returns the "
                                                   "original response instead of acting twice (24 h).")]


async def _once(response: Response, who: auth.Principal, scope: str, key: str | None, request: dict, run) -> dict:
    """Run `run` once per Idempotency-Key, scoped to the credential + route; `request` = the effective action (so
    equivalent bodies match). A replay says so in Idempotent-Replayed. Quota per buyer.
    ponytail: a crash between the order write and the key write can still lose the key; one DB transaction fixes it."""
    if key is None:
        return await run()
    body, replayed = await orders.idempotent(who.buyer_id, f"{scope}:{who.key_id}:{key}", hashlib.sha256(signing.canonical(request)).hexdigest(), run)
    if replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return body


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 without echoing the input back: a NaN in the body can't be JSON-encoded (it was a 500), and the
    client already has what it sent. A client trying to send its own mandate is audited as a security event."""
    if any(e.get("type") == "extra_forbidden" and "mandate" in e.get("loc", ()) for e in exc.errors()):
        owner = auth._owner(k) if (k := request.headers.get("x-agent-key")) else None
        await asyncio.to_thread(orders.security_event, "client_sent_mandate", f"{request.method} {request.url.path}",
                                ratelimit.client_ip(request), buyer_id=owner[1] if owner else None,
                                detail="the order is judged by the buyer's stored mandate; a mandate in the body is refused")
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


def _cross_buyer(request: Request, who: auth.Principal, claimed: str) -> HTTPException:
    """A key used for another buyer's data: audited (QA round 2 N14), then 403."""
    orders.security_event("cross_buyer_attempt", f"{request.method} {request.url.path}", ratelimit.client_ip(request),
                          buyer_id=None, caller_buyer_id=who.buyer_id, target_buyer_id=claimed)  # Valio-only
    return HTTPException(403, detail="This key may only act for its own buyer")


def _mandate_for(request: Request, who: auth.Principal, req: OrderRequest) -> Mandate | None:
    """The mandate this order is judged by: the key's buyer's, stored server-side. None → refused (MANDATE_MISSING)."""
    if (req.buyer_id or who.buyer_id) != who.buyer_id:
        raise _cross_buyer(request, who, req.buyer_id)
    return mandates.get(who.buyer_id)


@app.post("/api/orders")
async def place_order(req: OrderRequest, who: Agent, request: Request, response: Response, idempotency_key: IdemKey = None) -> dict:
    """Valio's front door (D2): re-checks the order against hard rules with fresh quotes. AUTO → confirmed,
    ASK_HUMAN → pending_approval, a hard violation or something Valio can't deliver → refused (nothing stored),
    always with reasons, suggested fixes and alternatives. Every run is audited. Needs X-Agent-Key."""
    mandate = _mandate_for(request, who, req)

    async def act():  # readiness only matters for a new action; a stored replay is served during catalogue startup
        _catalogue_ready()
        return await orders.place(who.buyer_id, req.requested_date, req.lines, mandate, actor=who)
    effective = {"requested_date": req.requested_date.isoformat(), "lines": [ln.model_dump() for ln in req.lines]}
    return await _once(response, who, f"agent:{who.buyer_id}:orders", idempotency_key, effective, act)


@app.get("/api/orders/{order_id}")
def get_order(order_id: OrderId, who: Annotated[auth.Principal, Depends(auth.order_reader)]) -> dict:
    """One of the caller's buyer's orders (read-only). X-Approver-Key, or X-Agent-Key so an agent can follow an
    order it placed. Another buyer's order is 404, like an unknown id, so ids don't leak."""
    return orders.get(order_id, who.buyer_id)


class SignOff(BaseModel):
    """Optional approve body. decided_at = the decision.decided_at the human was shown; send it so a click can
    only ever sign off that decision (409 if the order was re-decided since). Other fields are ignored."""
    decided_at: AwareDatetime | None = None


@app.post("/api/orders/{order_id}/approve")
async def approve_order(order_id: OrderId, who: Approver, response: Response, body: SignOff | None = None,
                        idempotency_key: IdemKey = None) -> dict:
    """Human sign-off as the key's owner; re-runs the gate first (cut-offs pass, prices and stock change).
    Needs X-Approver-Key. The approver's name comes from the key, never the body."""
    seen = body.decided_at if body else None

    async def act():
        _catalogue_ready()
        return await orders.approve(order_id, who, seen)
    return await _once(response, who, f"approver:{who.buyer_id}:approve:{order_id}", idempotency_key,
                       {"decided_at": seen.isoformat() if seen else None}, act)


@app.post("/api/orders/{order_id}/reject")
async def reject_order(order_id: OrderId, who: Approver, response: Response, idempotency_key: IdemKey = None) -> dict:
    """Human refusal as the key's owner. Needs X-Approver-Key; a request body is ignored."""
    return await _once(response, who, f"approver:{who.buyer_id}:reject:{order_id}", idempotency_key, {},
                       lambda: orders.reject(order_id, who))


@app.get("/api/audit")
def audit(who: Approver, request: Request, buyer_id: BuyerId | None = None,
          limit: Annotated[int, Query(ge=1, le=1000)] = 100) -> list[dict]:
    """The approver's buyer's audit trail (contract AuditEntry objects), oldest first. buyer_id, if sent, must
    be that buyer. Needs X-Approver-Key."""
    if (buyer_id or who.buyer_id) != who.buyer_id:
        raise _cross_buyer(request, who, buyer_id)
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


class DemoReset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    restore_mandate: bool = False
    buyer_id: BuyerId | None = Field(default=None, description="Reset only this buyer (e.g. judge-kitchen); omit for all.")


def _demo_status() -> dict:
    return {"demo_reset_enabled": config.DEMO_RESET_ENABLED, "signing_kid": signing.KID, "buyers": orders.budgets()}


@app.get("/api/admin/demo/status")
def demo_status(who: Annotated[auth.Principal, Depends(auth.valio_admin)]) -> dict:
    """Pre-demo checklist data: weekly budget used / left and confidence threshold per buyer, signing key id.
    Needs X-Valio-Admin-Key; read-only."""
    return _demo_status()


@app.post("/api/admin/demo/reset")
async def demo_reset(who: Annotated[auth.Principal, Depends(auth.valio_admin)], body: DemoReset | None = None) -> dict:
    """Archive orders, audit trail and idempotency keys to DATA_DIR/archive/<timestamp>/ and start empty (nothing is
    deleted); saved mandates stay unless restore_mandate=true. Only when DEMO_RESET_ENABLED=1. Needs X-Valio-Admin-Key."""
    if not config.DEMO_RESET_ENABLED:
        raise HTTPException(404, detail="Demo reset is not enabled on this server")
    restore = bool(body and body.restore_mandate)
    done = (await orders.demo_reset_buyer(who.name, body.buyer_id, restore) if body and body.buyer_id
            else await orders.demo_reset(who.name, restore))
    profile.reset(body.buyer_id if body and body.buyer_id else None)  # remembered preferences back to the seeds
    kitchen.reset(body.buyer_id if body and body.buyer_id else None)
    return {**done, **_demo_status()}


@app.get("/api/admin/audit")
def admin_audit(who: Annotated[auth.Principal, Depends(auth.valio_admin)], buyer_id: BuyerId | None = None,
                outcome: Literal["AUTO", "ASK_HUMAN", "DECLINE"] | None = None,
                status: Literal["confirmed", "pending_approval", "refused", "rejected"] | None = None,
                limit: Annotated[int, Query(ge=1, le=1000)] = 100) -> list[dict]:
    """Valio's side of the audit trail: every buyer's entries (contract AuditEntry + `front_door` annotation:
    action, status after the event, signed_off_by) and refused-access security events, oldest first. Filters: one
    buyer, a decision outcome, and/or the order status (status=refused finds every refusal, whatever its outcome).
    Needs X-Valio-Admin-Key; read-only."""
    return orders.audit_log(buyer_id, limit, outcome, status)


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
    token = auth.CURRENT_AGENT.set(who)
    try:
        return await agent.run(req.text, req.requested_date, who.buyer_id)
    finally:
        auth.CURRENT_AGENT.reset(token)


# --- T15 menu → cart: a proposal only (always ASK_HUMAN); the chef orders it by posting order_lines to /api/orders.
class PortionOverride(BaseModel):
    """The chef's own portion for one ingredient (the menu screen's editable grams per portion)."""
    model_config = ConfigDict(extra="forbid")
    ingredient: str = Field(min_length=1, max_length=80, examples=["butter"])
    per_cover: float | None = Field(default=None, gt=0, le=5000, examples=[25])
    unit: Literal["L", "dl", "cl", "ml", "kg", "g", "pcs"] | None = Field(default=None, examples=["g"])
    dish: str | None = Field(default=None, max_length=120, description="Only in this dish; default: every dish.")
    spare_percent: float | None = Field(default=None, ge=0, le=20, description="The chef's spare for this ingredient.")
    include: bool | None = Field(default=None, description="true: buy it even though the kitchen says it has it.")

    @model_validator(mode="after")
    def _something(self):
        if (self.per_cover is None) != (self.unit is None):
            raise ValueError("per_cover and unit go together")
        if self.per_cover is None and self.spare_percent is None and self.include is None:
            raise ValueError("set per_cover + unit, spare_percent or include")
        return self


class MenuRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    menu_text: str = Field(min_length=1, max_length=4000,
                           examples=["Reindeer stew with mashed potatoes; lingonberry cheesecake"])
    covers: int = Field(ge=1, le=2000, examples=[80])
    requested_date: date = Field(examples=["2026-11-16"])
    overrides: list[PortionOverride] = Field(default_factory=list, max_length=40)
    have: list[Annotated[str, StringConstraints(min_length=1, max_length=60)]] | None = Field(default=None, max_length=60, description="What the kitchen already has (this request only): a menu cart leaves it out. Never applied to direct orders.")

    @field_validator("menu_text")
    @classmethod
    def utf8(cls, t: str) -> str:
        return AgentRunRequest.utf8(t)

    @field_validator("requested_date")
    @classmethod
    def near_today(cls, d: date) -> date:
        return OrderRequest.near_today(d)


@app.post("/api/agent/menu")
async def agent_menu(req: MenuRequest, who: Agent, request: Request,
                     x_approver_key: Annotated[str | None, Header()] = None) -> dict:
    """Menu + covers → a proposed cart. Needs X-Agent-Key (the buyer comes from the key; mandate server-side).
    Returns {menu, assumptions, ingredients, lines, cart_total_cents, order_lines, decision, audit_id}; the decision is
    always ASK_HUMAN (MENU_ASSUMPTIONS) and nothing is ordered here."""
    _catalogue_ready()
    # Portions count as "set by the chef" (not doubted) only with the same buyer's approver key too; an agent-only
    # request's overrides are marked "agent" and still checked by Gemini Decisions (security review).
    chef = False
    if req.overrides and x_approver_key:  # the guarded check audits a refused key and keeps its 401/403
        chef_key = auth._guarded(request, "X-Approver-Key", x_approver_key, auth._approver)
        if chef_key.buyer_id != who.buyer_id:  # another kitchen's approver: refused and audited, never downgraded
            orders.security_event("key_used_outside_its_role", f"{request.method} {request.url.path}",
                                  ratelimit.client_ip(request), buyer_id=chef_key.buyer_id, header="X-Approver-Key",
                                  key_role="approver", http_status=403)
            raise HTTPException(403, detail="That approver key belongs to another kitchen.")
        chef = True
    return await menu.propose(req.menu_text, req.covers, req.requested_date, who.buyer_id,
                              overrides=[o.model_dump() for o in req.overrides], by_chef=chef, have=req.have)


# --- Delivery calendar and buyer-owned weekly menus. Menus edit with the approver key; planning and calendar reads
# use the same agent key as the front door and never place an order by themselves.
@app.get("/api/menus/weekly")
def get_weekly_menus(who: Agent) -> list[dict]:
    return kitchen_calendar.weekly_menus(who.buyer_id)


@app.put("/api/menus/weekly/{weekday}")
def put_weekly_menu(weekday: str, req: kitchen_calendar.WeeklyMenuInput, who: Approver) -> dict:
    return kitchen_calendar.save_weekly_menu(who.buyer_id, weekday, req)


@app.delete("/api/menus/weekly/{weekday}")
def delete_weekly_menu(weekday: str, who: Approver) -> dict:
    return kitchen_calendar.delete_weekly_menu(who.buyer_id, weekday)


@app.post("/api/menus/weekly/{weekday}/plan")
async def plan_weekly_menu(weekday: str, who: Agent, target_date: date = Query(..., alias="date")) -> dict:
    return await kitchen_calendar.plan_weekly_menu(who.buyer_id, weekday, target_date)


@app.get("/api/calendar")
def get_calendar(who: Agent, start: date = Query(..., alias="from"), end: date = Query(..., alias="to")) -> dict:
    return kitchen_calendar.calendar_view(who.buyer_id, start, end)


@app.post("/api/calendar/recurring/{weekday}/place")
async def place_recurring(weekday: str, who: Agent, target_date: date = Query(..., alias="date")) -> dict:
    return await kitchen_calendar.place_recurring(who.buyer_id, weekday, target_date)


@app.post("/api/calendar/recurring/{weekday}/skip")
def skip_recurring(weekday: str, who: Approver, target_date: date = Query(..., alias="date")) -> dict:
    return kitchen_calendar.skip_recurring(who.buyer_id, weekday, target_date)


# --- The chef's rules in plain language (T09 compiler). Human acts: X-Approver-Key only; an agent key can never
# change its own limits. Compile proposes, PUT saves; the agent and the front door read the saved mandate at once.
class CompileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4000, examples=[
        "Never anything with peanuts. Auto-approve up to €1,500 per order, €6,000 a week. Prefer Finnish."])

    @field_validator("text")
    @classmethod
    def utf8(cls, t: str) -> str:
        return AgentRunRequest.utf8(t)


MANDATE_CAPS = {"hard_rules": 50, "blocklist": 1000, "guidance": 50, "open_questions": 20}  # bounded stored rules


class SaveMandateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mandate: Mandate
    confirm_large_change: bool = False

    @model_validator(mode="after")
    def _capped(self) -> "SaveMandateRequest":
        for field, cap in MANDATE_CAPS.items():
            if len(getattr(self.mandate, field)) > cap:
                raise ValueError(f"mandate.{field} may have at most {cap} entries")
        return self


@app.post("/api/mandate/compile")
async def compile_mandate_route(req: CompileRequest, who: Approver) -> dict:
    """Plain-language rules → {proposed_mandate, diff_from_current, open_questions, assumptions, used_fallback,
    injection_flagged}. Nothing is saved. Needs X-Approver-Key."""
    return await rules.compile_rules(req.text, who)


def _if_match(value: str | None) -> str | None:
    return value.removeprefix("W/").strip().strip('"') if value else None


MemoryId = Annotated[str, StringConstraints(pattern=r"^mem_[0-9a-f]{12}$")]


class RememberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["usual_product"] = "usual_product"
    product_id: ProductId
    scope: Literal["this_order", "always"] = "always"
    text: str | None = Field(default=None, max_length=200)


@app.delete("/api/profile/memories/{memory_id}")
def forget_memory(memory_id: MemoryId, who: Approver) -> dict:
    """Forget one remembered preference (the memory panel's revoke button). Needs X-Approver-Key: forgetting a
    kitchen preference is the human's call, never the agent's. 404 for an unknown id, one already forgotten, or
    another buyer's. A forgotten seeded memory stays forgotten across restarts; the demo reset restores it.
    → the updated profile (same shape as GET /api/profile)."""
    try:
        profile.revoke(who.buyer_id, memory_id)
    except KeyError:
        raise HTTPException(404, detail="No such remembered preference for this kitchen.") from None
    return profile.context(who.buyer_id)


@app.post("/api/profile/memories")
def remember(req: RememberRequest, who: Approver) -> dict:
    """'Remember this': the chef keeps a product they chose (e.g. a pricier option guests like), for this order only
    (today's orders) or always. Needs X-Approver-Key. It only breaks near-ties between equally good matches: never past
    the confidence threshold or the front door's limits. 422 if the product isn't in the catalogue.
    → {memory, profile}."""
    _catalogue_ready()
    try:
        memory = profile.remember(who.buyer_id, req.product_id, req.scope, req.text)
    except ValueError as e:
        raise HTTPException(422, detail=str(e)) from None
    return {"memory": memory, "profile": profile.context(who.buyer_id)}


class OnboardingRequest(BaseModel):
    """answers: {question id: value}; about: free text or dictated speech for Gemini to fill the answers from.
    Without confirm=true nothing is stored: the response is a preview to show and edit."""
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, Any] | None = Field(default=None, max_length=20)
    about: str | None = Field(default=None, max_length=6000)
    confirm: bool = False


class InterviewAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=6_000)


class InterviewNextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: list[InterviewAnswer] = Field(default_factory=list, max_length=50)


@app.get("/api/profile/onboarding")
def get_onboarding(who: Agent) -> dict:
    """First-run questions about the kitchen → {onboarded, questions: [{id, question, input: text|choice|multi,
    options?, answer?}]}. Answers are guidance for the agent, never rules. Needs X-Agent-Key."""
    return profile.onboarding(who.buyer_id)


@app.post("/api/profile/onboarding")
async def post_onboarding(req: OnboardingRequest, who: Approver) -> dict:
    """The human sets up the kitchen (X-Approver-Key). `about` → Gemini fills the answers (the text is untrusted data).
    Without confirm: a PREVIEW {stored: false, proposed: [{id, question, value}], unclear, hints}. With confirm=true and
    `answers`: stored as profile memories → {stored: true, saved, hints, onboarding, profile}. Nothing here becomes a
    rule or changes the mandate (hints point to the Rules screen). Bad values → 422 {errors: {id: reason}}."""
    if not req.answers and not req.about:
        raise HTTPException(422, detail="Send `answers` and/or `about`.")
    answers, errors = profile.validate(req.answers or {})
    if errors:
        raise HTTPException(422, detail={"errors": errors})
    if req.confirm:
        if not answers:
            raise HTTPException(422, detail="To store, send the `answers` you accept (from the preview) with confirm=true.")
        saved = await asyncio.to_thread(profile.save_onboarding, who.buyer_id, answers)
        return {"stored": True, "saved": saved, "hints": profile.hints(answers),
                "onboarding": profile.onboarding(who.buyer_id), "profile": profile.context(who.buyer_id)}
    proposed, unclear = (await profile.from_about(req.about)) if req.about else ({}, [])
    proposed = {**proposed, **answers}  # what the chef typed beats what Gemini read
    questions = {q["id"]: q["question"] for q in profile.onboarding(who.buyer_id)["questions"]}
    return {"stored": False, "proposed": [{"id": k, "question": questions.get(k, "What else should I remember about your kitchen?"), "value": v}
                                           for k, v in proposed.items()],
            "unclear": unclear, "hints": profile.hints(proposed)}


@app.post("/api/profile/interview/next")
async def interview_next(req: InterviewNextRequest, who: Agent) -> dict:
    """Advance the short, stateless kitchen interview. Agent-key access is read-only; confirmation remains on onboarding."""
    try:
        return await interview.next_step(who.buyer_id, [answer.model_dump() for answer in req.answers])
    except ValueError as e:
        raise HTTPException(422, detail=str(e)) from None


@app.get("/api/profile")
def get_profile(who: Agent) -> dict:
    """The calling buyer's profile, read-only (guidance, never rules): standing dietary needs with the reason, usual
    product ids, the remembered items with why each is used, open questions, recent confirmed orders."""
    return profile.context(who.buyer_id)


class KitchenCoversRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mon: StrictInt | None = Field(default=None, ge=0, le=5000)
    tue: StrictInt | None = Field(default=None, ge=0, le=5000)
    wed: StrictInt | None = Field(default=None, ge=0, le=5000)
    thu: StrictInt | None = Field(default=None, ge=0, le=5000)
    fri: StrictInt | None = Field(default=None, ge=0, le=5000)
    sat: StrictInt | None = Field(default=None, ge=0, le=5000)
    sun: StrictInt | None = Field(default=None, ge=0, le=5000)


class StandingOrderLineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=200)
    product_id: ProductId | None = None
    quantity: StrictFloat | StrictInt | None = Field(default=None, gt=0, le=1_000_000, allow_inf_nan=False)
    unit: str | None = Field(default=None, max_length=20)


class StandingOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lines: list[StandingOrderLineRequest] = Field(min_length=1, max_length=50)


@app.get("/api/kitchen/history")
def get_kitchen_history(who: Agent) -> dict:
    return kitchen.history(who.buyer_id)


@app.put("/api/kitchen/history/covers")
def put_kitchen_covers(req: KitchenCoversRequest, who: Approver) -> dict:
    covers = {key: getattr(req, key) for key in kitchen.DAY_KEYS if key in req.model_fields_set}
    if not covers:
        raise HTTPException(422, detail="Send at least one weekday cover count.")
    if any(value is None for value in covers.values()):
        raise HTTPException(422, detail="Cover counts must be integers.")
    return kitchen.save_covers(who.buyer_id, covers)


@app.post("/api/kitchen/history/clear-example")
def post_clear_kitchen_example(who: Approver) -> dict:
    return kitchen.clear_example(who.buyer_id)


@app.put("/api/profile/standing-orders/{weekday}")
def put_standing_order(weekday: str, req: StandingOrderRequest, who: Approver) -> dict:
    try:
        profile.update_standing_order(who.buyer_id, weekday, [line.model_dump(exclude_none=True) for line in req.lines])
    except ValueError as e:
        raise HTTPException(422, detail=str(e)) from None
    return profile.context(who.buyer_id)


@app.delete("/api/profile/standing-orders/{weekday}")
def delete_standing_order(weekday: str, who: Approver) -> dict:
    try:
        profile.delete_standing_order(who.buyer_id, weekday)
    except ValueError as e:
        raise HTTPException(422, detail=str(e)) from None
    except KeyError:
        raise HTTPException(404, detail="No standing order for that weekday.") from None
    return profile.context(who.buyer_id)


class KitchenLogRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)
    date: KitchenDate | None = None

    @field_validator("text")
    @classmethod
    def utf8(cls, t: str) -> str:
        return AgentRunRequest.utf8(t)


@app.post("/api/kitchen/log")
async def post_kitchen_log(req: KitchenLogRequest, who: Agent) -> dict:
    return await kitchen.log_from_text(who.buyer_id, req.text, req.date)


@app.get("/api/kitchen/context")
def get_kitchen_context(who: Agent) -> dict:
    return kitchen.kitchen_context(who.buyer_id)


@app.get("/api/mandate")
def get_mandate(who: Approver, response: Response) -> dict | None:
    """The mandate in force for the approver's buyer (saved, else the seeded default); its version is the ETag
    header (send it back as If-Match when saving). Needs X-Approver-Key."""
    m = mandates.get(who.buyer_id)
    if m:
        response.headers["ETag"] = f'"{mandates.version(m)}"'
    return m.model_dump(mode="json") if m else None


@app.put("/api/mandate")
def save_mandate(req: SaveMandateRequest, who: Approver, response: Response,
                 if_match: Annotated[str | None, Header(max_length=200)] = None) -> dict:
    """Save the confirmed mandate for the approver's buyer → {mandate, changes, audit_id, version}. With If-Match
    (the ETag from GET), a save over rules someone else changed meanwhile is 412, never a silent overwrite. 422 while
    open questions remain; 409 for big loosenings unless confirm_large_change=true. Audited. Needs X-Approver-Key."""
    out = rules.save(req.mandate, req.confirm_large_change, who, _if_match(if_match))
    response.headers["ETag"] = f'"{out["version"]}"'
    if if_match is None:  # QA round 2 N11: still accepted (scripts), but never silently
        note = ("Saved without If-Match: a concurrent change could have been overwritten. Send the ETag from "
                "GET /api/mandate as If-Match.")
        logging.getLogger(__name__).warning("mandate for %s saved without If-Match", who.buyer_id)
        response.headers["Warning"] = f'299 - "{note}"'
        out = {**out, "warning": note}
    return out


# --- One input for everyone: order, menu or unclear, routed by Gemini; date and guests read from the text.
class FollowUp(BaseModel):
    """The chef's answer to the question a previous /ask returned (its conversation_id, valid ~10 min)."""
    model_config = ConfigDict(extra="forbid")
    to: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
    answer: str = Field(min_length=1, max_length=500, examples=["five litres"])

    @field_validator("answer")
    @classmethod
    def utf8(cls, t: str) -> str:
        return AgentRunRequest.utf8(t)


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(default="", max_length=4000, examples=["milk and 30 croissants for tomorrow"])
    requested_date: date | None = Field(default=None, description="Optional when the text states a day.")
    follow_up: FollowUp | None = Field(default=None, description="Answer a question instead of a new request.")
    have: list[Annotated[str, StringConstraints(min_length=1, max_length=60)]] | None = Field(default=None, max_length=60, description="What the kitchen already has (this request only): a menu cart leaves it out. Never applied to direct orders.")

    @field_validator("text")
    @classmethod
    def utf8(cls, t: str) -> str:
        return AgentRunRequest.utf8(t)

    @model_validator(mode="after")
    def _something(self) -> "AskRequest":
        if not self.text.strip() and self.follow_up is None:
            raise ValueError("send text, or follow_up with the answer to a question")
        return self


class ChatRequest(AskRequest):
    """A text turn for the Gemini tool-calling chat agent; its follow-up shape matches /ask."""


@app.post("/api/agent/ask")
async def agent_ask(req: AskRequest, who: Agent) -> dict:
    """Free text → {intent: order|menu|unclear, covers, requested_date, date_source: request|text|null,
    question: str|null, ...the /api/agent/run body (order) or the /api/agent/menu body (menu)}. When a question is
    asked (no date, menu without guests, unclear, conflicting dates), only `decision` (ASK_HUMAN) follows and nothing
    runs. Needs X-Agent-Key."""
    _catalogue_ready()
    token = auth.CURRENT_AGENT.set(who)
    try:
        return await ask.ask(req.text, req.requested_date, who.buyer_id, req.follow_up and req.follow_up.model_dump(),
                             req.have)
    finally:
        auth.CURRENT_AGENT.reset(token)


@app.post("/api/agent/chat")
async def agent_chat(req: ChatRequest, who: Agent) -> dict:
    """Gemini text chat with grounded function calls; provider protocol failures are surfaced as provider_call_ok=false."""
    _catalogue_ready()
    token = auth.CURRENT_AGENT.set(who)
    try:
        return await chat_agent.chat(req.text, who.buyer_id, req.requested_date,
                                     req.follow_up and req.follow_up.model_dump(), req.have)
    finally:
        auth.CURRENT_AGENT.reset(token)


# --- Talk: a spoken conversation over Gemini Live (live.py). Auth is the first message: browsers can't set headers.
@app.websocket("/api/live")
async def talk(ws: WebSocket) -> None:
    await live.session(ws)


# --- Voice: push-to-talk audio → the chef's words (Gemini Live via our backend; the key never reaches the browser).
@app.post("/api/voice/transcribe")
async def voice_transcribe(request: Request, who: Agent) -> dict:
    """Body: the raw recording (Content-Type audio/webm, audio/ogg, audio/mp4, audio/wav...; at most 1 MB / 30 s).
    → {text, seconds, model}. The UI shows the text and sends it to POST /api/agent/ask; nothing is ordered here.
    Needs X-Agent-Key; rate-limited like agent runs."""
    body = bytearray()
    async for chunk in request.stream():  # bounded read: a body without a length header can't grow past the cap
        body += chunk
        if len(body) > voice.MAX_BYTES:
            raise HTTPException(413, detail=f"Recordings may be at most {voice.MAX_BYTES // 1000} KB.")
    return await voice.transcribe(bytes(body), request.headers.get("content-type", ""))


@app.post("/api/vision/read")
async def vision_read(request: Request, who: Agent) -> dict:
    """A photo of a handwritten shopping list, a menu board or a whiteboard of menu ideas (multipart field `image`,
    or the raw image as the body; JPEG / PNG / WEBP / HEIC, at most 8 MB) → {kind: order_list|menu|other, text,
    items, covers, unreadable, language, suspicious, message, model}. Gemini reads the image as untrusted DATA:
    instruction-like text in it is only text. This route places NOTHING and stores no image: the UI sends `text` on
    through POST /api/agent/ask, where every rule and the front door apply. Needs X-Agent-Key; rate-limited."""
    body = bytearray()
    async for chunk in request.stream():  # bounded read, as for voice
        body += chunk
        if len(body) > vision.MAX_BYTES + 64 * 1024:
            raise HTTPException(413, detail=f"Photos may be at most {vision.MAX_BYTES // 1_000_000} MB.")
    return await vision.read(bytes(body), request.headers.get("content-type", ""))


_STREAM_TASKS: set = set()
MAX_STREAMS_PER_BUYER = 3  # disconnected streams keep working to the end, so cap them (Codex #10)


@app.post("/api/agent/ask/stream")
async def agent_ask_stream(req: AskRequest, who: Agent) -> StreamingResponse:
    """POST /api/agent/ask, streamed as Server-Sent Events so the UI can show progress while it works:
    `event: phase` {phase, text} (understanding, searching, stock, judging, planning, ordering) as each step starts,
    then one `event: result` with exactly the /api/agent/ask body, or `event: error` {status, detail}.
    Needs X-Agent-Key."""
    _catalogue_ready()
    if sum(1 for t in _STREAM_TASKS if getattr(t, "buyer_id", None) == who.buyer_id) >= MAX_STREAMS_PER_BUYER:
        raise HTTPException(429, detail="Too many requests still running for this kitchen; wait for them to finish.")
    queue: asyncio.Queue = asyncio.Queue()

    async def work():
        progress.set_sink(queue.put_nowait)  # inside the task's own context: only this request's phases
        token = auth.CURRENT_AGENT.set(who)
        try:
            queue.put_nowait(("result", await ask.ask(req.text, req.requested_date, who.buyer_id,
                                                      req.follow_up and req.follow_up.model_dump(), req.have)))
        except HTTPException as e:
            queue.put_nowait(("error", {"status": e.status_code, "detail": e.detail}))
        except Exception:  # noqa: BLE001 - details stay in the server log
            logging.getLogger(__name__).exception("ask stream failed")
            queue.put_nowait(("error", {"status": 500, "detail": "Something went wrong. Check your orders before "
                                                                 "trying again."}))  # it may have got as far as an order
        finally:
            auth.CURRENT_AGENT.reset(token)

    async def events():
        # A disconnect never cancels the work: cancelling mid-order could store an order without its audit entry.
        # The task finishes on its own (bounded like any /ask); the stream just stops forwarding. It is held in
        # _STREAM_TASKS until done, so it can't be garbage-collected mid-run.
        task = asyncio.create_task(work())
        task.buyer_id = who.buyer_id
        _STREAM_TASKS.add(task)
        task.add_done_callback(_STREAM_TASKS.discard)
        while True:
            item = await queue.get()
            kind, data = item if isinstance(item, tuple) else ("phase", item)
            yield f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
            if kind != "phase":
                return
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
