# Front Door technical reference

This is the operational reference moved out of the judge-facing README. It describes the `origin/main` interface.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `VALIO_API_KEY` | Key for Valio’s mock API. |
| `VALIO_BASE_URL` | Valio API base URL. |
| `GEMINI_API_KEY` | Enables Gemini parsing, catalogue ranking, Decisions confidence, OCR, and Live voice. |
| `FRONTEND_ORIGINS` | Comma-separated browser origins allowed by CORS. |
| `AGENT_KEYS` | Comma-separated `key=buyer_id[:name]` entries for purchasing agents. |
| `APPROVER_KEYS` | Comma-separated `key=buyer_id[:name]` entries for human approvers. |
| `VALIO_ADMIN_KEYS` | Comma-separated `key=valio[:name]` entries for read-only cross-buyer audit access. |
| `FRONT_DOOR_SIGNING_KEY` | Base64 32-byte Ed25519 seed for stable order-response signatures; unset uses an ephemeral key. |
| `AGENT_SIGNING_KEYS` | Optional `buyer:kid:base64pub` Ed25519 keys for RFC 9421-signed agent writes. |
| `DATA_DIR` | State directory for orders, audit, idempotency keys, mandates, and rules; on Render use persistent storage. |
| `TRUST_X_FORWARDED_FOR` | Set `1` behind a proxy that appends the client IP. |

Use long random values for front-door keys. An agent key cannot approve. Empty protected key sets return `503`.

## Authentication and signed requests

- Agent routes use `X-Agent-Key`; approver routes use `X-Approver-Key`; Valio staff use `X-Valio-Admin-Key`.
- `AGENT_SIGNING_KEYS` adds RFC 9421 signatures to `POST /api/orders` and `POST /api/agent/*` for the registered buyer.
- Signed writes carry `Content-Digest`, `Signature-Input`, and `Signature` headers. Missing, stale, replayed, or invalid signatures return `401` and are audited.
- `GET /.well-known/front-door-keys.json` publishes the door’s Ed25519 public key. `POST /api/verify` checks a returned signed order statement.

## Route map

| Method | Route | Purpose | Auth |
| --- | --- | --- | --- |
| `POST` | `/api/sandbox` | Mint a 24-hour temporary test kitchen when enabled. | none |
| `POST` | `/api/agent/chat` | Gemini function-calling chat brain over the deterministic order/menu engine. | agent |
| `POST` | `/api/agent/ask` / `/api/agent/ask/stream` | Text order or menu flow, direct or SSE-streamed. | agent |
| `POST` | `/api/agent/run` / `/api/agent/menu` | End-to-end buyer-agent run or menu proposal. | agent |
| `POST` | `/api/vision/read` | Photo to checked text; places nothing itself. | agent |
| `POST` | `/api/voice/transcribe` | Push-to-talk audio to transcript; places nothing itself. | agent |
| `WS` | `/api/live` | Gemini Live voice with read-only tools and `ask_agent`; no approve tool. | agent in-band |
| `GET` | `/api/profile`, `/api/kitchen/history`, `/api/kitchen/context` | Read buyer profile and kitchen context. | agent |
| `PUT` / `DELETE` | `/api/profile/standing-orders/{weekday}` | Save or remove a buyer-owned standing order. | approver |
| `GET` / `PUT` / `DELETE` | `/api/menus/weekly` | Read, edit, or remove weekly menus. | agent / approver |
| `GET` / `POST` | `/api/calendar` and recurring menu routes | Read, place, or skip recurring menu entries. | agent / approver |
| `POST` | `/api/orders` | Place an order; send an `Idempotency-Key`. | agent |
| `GET` | `/api/orders/{id}` | Read one buyer’s order. | agent / approver |
| `POST` | `/api/orders/{id}/approve` or `/reject` | Human approval or refusal. | approver |
| `GET` | `/api/audit` | Read that buyer’s audit trail. | approver |
| `POST` | `/api/mandate/compile` | Convert plain-language rules into a reviewable proposal. | approver |
| `GET` / `PUT` | `/api/mandate` | Read or save a confirmed mandate. | approver |
| `POST` | `/api/quotes` | Fetch current mock price and availability. | none |
| `GET` | `/api/products/search` or `/api/products/{product_id}` | Search or inspect catalogue facts. | none |
| `POST` | `/api/quantity/resolve` | Convert a requested amount into sales units. | none |
| `GET` | `/api/health` | Service and catalogue status. | none |
| `GET` | `/.well-known/front-door-keys.json` | Public Ed25519 keys and build evidence. | none |
| `GET` | `/.well-known/front-door-build.json` | Build, SBOM, vulnerability-count, and network-destination evidence. | none |
| `POST` | `/api/verify` | Verify a signed order statement. | none |
| `GET` | `/api/admin/audit` | Cross-buyer read-only audit for Valio staff. | admin |

## Retries and local checks

Reuse the same `Idempotency-Key` and body for a retry. Within 24 hours the original response is returned with `Idempotent-Replayed: true`. Rate limits are 30 requests/minute per agent key, 120/minute per human key, and 120/minute per IP; over-limit responses are `429` with `Retry-After`.

```bash
cd backend
GEMINI_API_KEY= PYTHONPATH=$(pwd)/../contracts:$(pwd)/../compiler:$(pwd)/../profile \
  .venv/bin/python -m pytest -q tests

cd frontend
npm run build && npm run lint
```

The backend test suite is offline: Valio and Gemini are faked by the tests. The live labelled evaluation is `backend/eval/gemini_eval.py` and contains 33 cases.
