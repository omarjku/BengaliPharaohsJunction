# Next steps to production

## What's already there

- An open REST boundary: OpenAPI 3.1 and JSON Schemas.
- An MCP server, so any agent can use the same front door.
- Ed25519-signed order responses, with an optional RFC 9421 per-agent request-signing scheme.
- Push-to-talk voice, Talk (Gemini Live) and photo input, all on one pipeline.
- Buyer profiles, onboarding, standing orders, kitchen history/calendar, an append-only audit trail, and idempotent retries.
- A 24-hour QR test-kitchen sandbox when `SANDBOX_ENABLED=1`.

The limits are written as `ponytail:` comments in the code and in `docs/ASSUMPTIONS.md`.

The latest real-Gemini release acceptance is 7/12 flows passed. The report found five
release gaps: a 25 kg butter correction was treated as 25 packs, usual-product choice
was ambiguous, duplicate protection fired on questions and changes, a `plus ...` line
was lost after a follow-up, and a vague party request had no choices. TODO: rerun the
live acceptance after those fixes; this file does not claim a post-fix score.

## The path, in order

| # | Step | Why | What it takes |
|---|---|---|---|
| 1 | **A real Valio order endpoint** | The mock has none. A confirmed order is our record, not a Valio order | Valio's order API or sandbox, then submit only confirmed orders, with idempotency, acknowledgement, status and reconciliation |
| 2 | **Postgres instead of JSON files** | Orders, audit, mandates and profiles live in files on one disk, with an in-process lock (one worker) | A schema with migrations, row locks and transactions for budgets and approvals, an append-only audit with a hash chain, retention. Then more workers become safe |
| 3 | **Per-agent identity** | Shared `X-Agent-Key` secrets today. RFC 9421 signing exists but is optional | OAuth 2 client credentials or mTLS per agent, bound to a buyer, plus key rotation and revocation; make signing mandatory |
| 4 | **Signed quotes with expiry** | The door re-quotes live (correct, but chatty). A signed quote makes the fixed-price handoff verifiable | Agree a signature and key directory with Valio; verify and expire at the door; keep the signed payload in the audit |
| 5 | **Cross-language search with Gemini embeddings** | Keyword search misses a product named in the other language ("linssi" / red lentils) | Embed the catalogue's names once, add a vector index, and keep the Decisions judge on top |
| 6 | **Product images** | Valio's data carries media ids but no image files, so the UI can't show packs | Ask Valio for the media endpoint, then show the pack beside each line; photo input could then compare against it |
| 7 | **CI on CRACI** | CI is not verified on the release branch; the current offline suite is 634 passed, 21 failed, 1 skipped | Make the CI workflow run the required offline backend command, fix the existing menu/diet failures, then gate merges on the suite and the live eval |
| 8 | **Larger evals** | 33 judge cases, 3 hand-checked photo fixtures, and no labelled spare-amount set | Add borderline judge cases (0.4–0.8), 20–30 photo cases, and a spare-amount set; re-measure the threshold per buyer |
| 9 | **Peppol BIS Order / UBL export** | A standard order document for procurement systems | The mapping is in `docs/STANDARDS.md`; implement it and validate against the Peppol rules |
| 10 | **Bank and operations integrations** | Spending from the kitchen's bank via PSD2 account access is not built; the door-counter and POS history is still a simulated seed | Add PSD2 account access only with explicit kitchen consent, then replace the seed with authenticated door-counter and POS integrations |
