# Valio front door: MCP server

The front door as [Model Context Protocol](https://modelcontextprotocol.io/) tools, so any buyer's agent can plug
in: Claude Desktop, Claude Code, ChatGPT, Gemini CLI, an IDE, or your own agent. It is a thin client over the
front door's REST API, so every rule still runs at the door: fresh Valio quotes, the buyer's stored mandate, the
audit log.

| Tool | Front door call | Key |
|---|---|---|
| `search_products(query, claims?, exclude_allergens?, limit?)` | `GET /api/products/search` | none |
| `get_quotes(product_ids, requested_date)` | `POST /api/quotes` | none |
| `resolve_quantity(product_id, amount, unit)` | `POST /api/quantity/resolve` | none |
| `place_order(requested_date, lines)` | `POST /api/orders` | `FRONT_DOOR_AGENT_KEY` |
| `get_order(order_id)` | `GET /api/orders/{id}` | `FRONT_DOOR_AGENT_KEY` (see below) |

There is deliberately **no approve tool**. When the door answers `pending_approval`, a human signs off with an
approver key in the web UI. An agent never can.

Built on the official Python SDK, `mcp` 2.x (`MCPServer`, which was called `FastMCP` in 1.x), over the stdio
transport. When the door refuses a call (401, 403, 422 and so on), its message is passed back to the agent as the
tool error.

## Run

```bash
cd mcp
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
FRONT_DOOR_URL=http://localhost:8000 FRONT_DOOR_AGENT_KEY=<an AGENT_KEYS key> .venv/bin/python server.py
```

`FRONT_DOOR_URL` defaults to `http://localhost:8000` (`./dev.sh`). Use
`https://valio-front-door-api.onrender.com` for the deployed door. The free tier takes about a minute to wake up.

To check it end to end, run `smoke_test.py`: it lists the tools, then runs milk through search → quote → quantity →
`place_order`. Tested on Sun 15 Nov 2026 against a local backend and the live Valio mock: 100 L of lactose-free
milk came back `confirmed`.

```bash
FRONT_DOOR_URL=http://localhost:8000 FRONT_DOOR_AGENT_KEY=<key> .venv/bin/python smoke_test.py
```

You can also browse the tools with the MCP inspector: `npx @modelcontextprotocol/inspector .venv/bin/python server.py`.

## Add it to Claude Desktop or Claude Code

Claude Desktop: add this to `claude_desktop_config.json`. For Claude Code, put the same `mcpServers` block in
`.mcp.json` at the project root.

```json
{
  "mcpServers": {
    "valio-front-door": {
      "command": "/absolute/path/to/BengaliPharaohsJunction/mcp/.venv/bin/python",
      "args": ["/absolute/path/to/BengaliPharaohsJunction/mcp/server.py"],
      "env": {
        "FRONT_DOOR_URL": "https://valio-front-door-api.onrender.com",
        "FRONT_DOOR_AGENT_KEY": "<your agent key>"
      }
    }
  }
}
```

Or in one command: `claude mcp add valio-front-door -e FRONT_DOOR_URL=... -e FRONT_DOOR_AGENT_KEY=... -- /abs/path/mcp/.venv/bin/python /abs/path/mcp/server.py`.

Then ask, for example: "Order 1000 L of lactose-free milk from Valio for Monday."

## Known gap

`GET /api/orders/{id}` accepts only an approver key today, so `get_order` with an agent key answers 401. The
backend needs to let an agent read its own buyer's orders (read-only). We won't give this server an approver key:
that key can approve orders, and approval must stay with a person.
