"""MCP server for the Valio Aimo front door: any buyer's agent (Claude, ChatGPT, Gemini CLI, ...) can plug in.

A thin client over the front door's REST API, so every rule still runs at the door: fresh quotes, the buyer's
stored mandate, the audit log. There is deliberately no approve tool: sign-off stays with a human approver key.

Env: FRONT_DOOR_URL (default http://localhost:8000), FRONT_DOOR_AGENT_KEY (needed for place_order / get_order...).
Run: python server.py  (stdio transport)
"""
import asyncio
import os
import uuid

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError  # its message reaches the agent; other errors are masked

URL = os.getenv("FRONT_DOOR_URL", "http://localhost:8000").rstrip("/")
mcp = MCPServer("valio-front-door", instructions=(
    "Order from Valio Aimo through its front door. Search the catalogue, get live quotes, convert the buyer's amount "
    "into sales units, then place the order. The door re-checks everything against the buyer's mandate and answers "
    "confirmed, pending_approval (a human must sign off) or refused, always with reasons. Never guess: when the door "
    "or resolve_quantity says needs_confirmation, ask the buyer."))


async def _call(method: str, path: str, *, key: bool = False, **kw) -> dict | list:
    headers = {"User-Agent": "valio-front-door-mcp/0.1"}
    if key:
        if not (agent_key := os.getenv("FRONT_DOOR_AGENT_KEY")):
            raise ToolError("FRONT_DOOR_AGENT_KEY is not set, so this MCP server can't act for a buyer")
        headers["X-Agent-Key"] = agent_key
    async with httpx.AsyncClient(base_url=URL, timeout=60, headers=headers) as http:
        for attempt in range(3):  # retry rate limits and gateway errors; an Idempotency-Key makes a retry safe
            try:
                r = await http.request(method, path, **kw)
            except httpx.TransportError:
                if attempt == 2:
                    raise ToolError("Front door unreachable; nothing confirmed, retry later") from None
                await asyncio.sleep(2)
                continue
            if r.status_code not in (429, 502, 503, 504) or attempt == 2:
                break
            await asyncio.sleep(min(float(r.headers.get("Retry-After") or 2), 30))
    if r.status_code >= 400:  # the door's own message (422 field errors, 401/403, 503) is what the agent needs
        raise ToolError(f"Front door answered {r.status_code}: {r.text[:1000]}")
    return r.json()


@mcp.tool()
async def search_products(query: str, claims: list[str] | None = None, exclude_allergens: list[str] | None = None,
                          limit: int = 20) -> list:
    """Search Valio's catalogue (English and Finnish names, brand).
    claims: all must be present, e.g. ["FREE_FROM_LACTOSE", "VEGAN"].
    exclude_allergens: GS1 codes the product must not contain, e.g. ["AP"] peanuts, ["AW"] gluten, ["AM"] milk.
    Lactose-free milk still contains milk (AM): use the FREE_FROM_LACTOSE claim for lactose intolerance."""
    return await _call("GET", "/api/products/search", params={
        "q": query, "claims": claims or [], "exclude_allergens": exclude_allergens or [], "limit": limit})


@mcp.tool()
async def get_quotes(product_ids: list[str], requested_date: str) -> list:
    """Live price (EUR, net of VAT) and availability from Valio for up to 1000 product ids, for a delivery date
    (YYYY-MM-DD). Check order_cutoff (it may already have passed), quantity_known (Terminal products report
    unknown stock, not unlimited) and flags. Quote only products you found with search_products."""
    return await _call("POST", "/api/quotes", json={"product_ids": product_ids, "requested_date": requested_date})


@mcp.tool()
async def resolve_quantity(product_id: str, amount: float, unit: str) -> dict:
    """Convert the buyer's amount (unit L, dl, cl, ml, kg, g, pcs, or a product unit code like KI or ST) into the
    product's sales unit, rounded up to whole units and the lot size. If needs_confirmation is true, show the
    explanation to the buyer and ask before ordering."""
    return await _call("POST", "/api/quantity/resolve", json={"product_id": product_id, "amount": amount, "unit": unit})


@mcp.tool()
async def place_order(requested_date: str, lines: list[dict]) -> dict:
    """Place an order at Valio's front door for the buyer this server's agent key belongs to.
    lines: [{"product_id": "463335", "quantity": 1000}], quantity in the product's sales unit (from resolve_quantity).
    The door re-quotes, checks the buyer's stored mandate and returns status confirmed, pending_approval (a human
    approver must sign off; you cannot) or refused, with reasons, suggested fixes and alternatives."""
    # One fresh Idempotency-Key per call, reused by _call's retries: a retried POST can never order twice.
    return await _call("POST", "/api/orders", key=True, json={"requested_date": requested_date, "lines": lines},
                       headers={"Idempotency-Key": str(uuid.uuid4())})


@mcp.tool()
async def get_order(order_id: str) -> dict:
    """Read one of the buyer's orders (e.g. to see whether a pending order was approved). Uses the agent key."""
    return await _call("GET", f"/api/orders/{order_id}", key=True)


if __name__ == "__main__":
    mcp.run()
