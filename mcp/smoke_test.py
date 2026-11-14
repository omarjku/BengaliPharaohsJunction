"""End-to-end check of the MCP server against a running front door, the way an agent would use it.

Run: FRONT_DOOR_URL=http://localhost:8000 FRONT_DOOR_AGENT_KEY=... python smoke_test.py
Lists the tools, then milk: search → quote → quantity → place_order. Exits non-zero on any failure.
"""
import asyncio
import json
import os
import sys
from datetime import date, timedelta

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=[os.path.join(HERE, "server.py")], env=dict(os.environ))
    async with stdio_client(params) as (read, write), ClientSession(read, write) as s:
        await s.initialize()
        tools = sorted(t.name for t in (await s.list_tools()).tools)
        assert tools == ["get_order", "get_quotes", "place_order", "resolve_quantity", "search_products"], tools

        async def call(name, **args):
            r = await s.call_tool(name, args)
            assert not r.is_error, f"{name}: {r.content[0].text}"
            out = json.loads(r.content[0].text) if len(r.content) == 1 else [json.loads(c.text) for c in r.content]
            print(f"{name} ok")
            return out

        hits = await call("search_products", query="milk", claims=["FREE_FROM_LACTOSE"], limit=5)
        assert hits, "no lactose-free milk found"
        monday = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)
        await call("get_quotes", product_ids=[h["id"] for h in hits], requested_date=monday.isoformat())
        qty = await call("resolve_quantity", product_id="463335", amount=100, unit="L")
        assert qty["quantity"] == 100, qty
        order = await call("place_order", requested_date=monday.isoformat(),
                           lines=[{"product_id": "463335", "quantity": qty["quantity"]}])
        print("order:", order["status"], [r["code"] for r in order["decision"]["reasons"]])
        assert order["status"] in ("confirmed", "pending_approval", "refused")


asyncio.run(main())
