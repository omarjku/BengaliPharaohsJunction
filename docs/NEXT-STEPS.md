# Next steps to production

## What's already there

- An open REST boundary: OpenAPI 3.1 and JSON Schemas.
- An MCP server, so any agent can use the same front door.
- Ed25519-signed decisions, with an optional RFC 9421 per-agent request-signing scheme.
- Push-to-talk voice, Talk (Gemini Live) and photo input, all on one pipeline.
- Buyer profiles, an append-only audit trail, and idempotent retries.

The limits are written as `ponytail:` comments in the code and in `docs/ASSUMPTIONS.md`.

## The path, in order

| # | Step | Why | What it takes |
|---|---|---|---|
| 1 | **A real Valio order endpoint** | The mock has none. A confirmed order is our record, not a Valio order | Valio's order API or sandbox, then submit only confirmed orders, with idempotency, acknowledgement, status and reconciliation |
| 2 | **Postgres instead of JSON files** | Orders, audit, mandates and profiles live in files on one disk, with an in-process lock (one worker) | A schema with migrations, row locks and transactions for budgets and approvals, an append-only audit with a hash chain, retention. Then more workers become safe |
| 3 | **Per-agent identity** | Shared `X-Agent-Key` secrets today. RFC 9421 signing exists but is optional | OAuth 2 client credentials or mTLS per agent, bound to a buyer, plus key rotation and revocation; make signing mandatory |
| 4 | **Signed quotes with expiry** | The door re-quotes live (correct, but chatty). A signed quote makes the fixed-price handoff verifiable | Agree a signature and key directory with Valio; verify and expire at the door; keep the signed payload in the audit |
| 5 | **Cross-language search with Gemini embeddings** | Keyword search misses a product named in the other language ("linssi" / red lentils) | Embed the catalogue's names once, add a vector index, and keep the Decisions judge on top |
| 6 | **Product images** | Valio's data carries media ids but no image files, so the UI can't show packs | Ask Valio for the media endpoint, then show the pack beside each line; photo input could then compare against it |
| 7 | **CI on CRACI** | CI (PR #34, built by Codex) isn't merged yet | Merge #34, switch its runner to CRACI, gate merges on the 434 backend tests and the eval |
| 8 | **Larger evals** | 33 judge cases, 3 photo checks, none for spare amounts | Borderline judge cases (0.4–0.8), 20–30 photos, a spare-amounts set; re-measure the threshold per buyer |
| 9 | **Peppol BIS Order / UBL export** | A standard order document for procurement systems | The mapping is in `docs/STANDARDS.md`; implement it and validate against the Peppol rules |
