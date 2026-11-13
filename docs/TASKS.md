# 🧩 Task breakdown (built from docs/DECISIONS.md)

**No owners yet.** Anyone can take any task: post `CLAIM [J..]: T## <name>, branch <name>` on the board first, and read the board before claiming. Sizes: **S** ≈ 1 h · **M** ≈ 2–3 h · **L** ≈ 4–6 h (rough).
🔒 = blocked on an OPEN decision or a booth answer.

## Milestone 1: J1 thin slice (first; nothing else until this runs)
**Done when** the milk example runs live: text request → catalogue → Valio availability + price → decision → order or ask human → audit log, in a web page.

| ID | Task | Serves | Size | Depends on |
|---|---|---|---|---|
| T01 | Repo skeleton: Python backend + TypeScript web frontend, `.env` loading, one-command run | J1 | S | — |
| T02 | Shared contracts v0: `PurchaseRequest`, `Quote`, `Decision`, `AuditEntry` (JSON shapes both sides code against; Zoha's agent offered to push these early) | J1, J5 | S | — |
| T03 | Valio API client: `X-API-Key` + **User-Agent**, availability + price in one batch (≤1000 ids), validate unknown ids via `/price`, small cache | J1, J4 | S | T01 |
| T04 | Catalogue loader + search: names (fi/en), category, allergens (CONTAINS / MAY_CONTAIN / FREE_FROM), claims, units, carbon, reliability | J1, J2 | M | T01 |
| T05 | Quantity resolver: "1,000 L" → sales units via units / comparison unit; flags ambiguity instead of guessing | J2 | M | T04 |
| T06 | Decision step v0 (plain rules: cut-off, availability, spend threshold) → AUTO / ASK HUMAN / DECLINE + reasons | J3 | S | T02, T03 |
| T07 | Order record + audit log (append-only; human-readable + JSON; **includes rejected options**) | J3, J5 | M | T02 |
| T08 | Minimal web UI: request → options → approval card → log | J1 | M | T03–T07 |

## Milestone 2: Core features (from decisions D1, D3, D5, D6)
| ID | Task | Serves | Size | Depends on |
|---|---|---|---|---|
| T09 | Mandate compiler (Gemini): buyer's plain-language rules → mandate JSON; asks open questions instead of guessing | J2, J3 | M | T02 |
| T10 | 🔒 Gemini **Decisions API** guardrail: calibrated confidence for "meets the constraint?", "safe substitute?", ranking; below threshold → ask human | J3, Gemini | M | T06, T09 · **access unverified (DeepMind booth)** |
| T11 | Trap handling per D6 (**bring it up, never silently reject**): passed cut-off, Terminal unknown qty, undeliverable, partial stock, unit mismatch, each with why + alternatives | J4 | M | T06 · Valio booth answer may change details |
| T12 | Substitution finder: allergen-safe (FREE_FROM vs MAY_CONTAIN), claims, category; good / better / best with reasons | J4, J2 | M | T04 |
| T13 | Buyer profile: onboarding questions + past orders + remembered answers; **preferences scoped** (this order vs always) | J2 | M | T02 |
| T14 | Lapland restaurant persona: delivery-reliability weighting, Finnish-origin preference, seeded profile + order history for the demo | J2 | S | T04, T13 |
| T15 | Menu-to-cart: menu text → dishes → ingredients (Gemini; editable assumptions) → scale to covers → catalogue match → cart with a "why" per line; Lapland reliability limits shown | J1, J2, J4 | L | T04, T05, T12 |

## Milestone 3: Voice + frontend (D4, D8)
| ID | Task | Serves | Size | Depends on |
|---|---|---|---|---|
| T16 | Voice-to-voice (Gemini Live API) in the web app: speak a request or new menu; agent reads back qty + date; **asks by voice when unsure** | J1, J2, Gemini | L | T08, T10 |
| T17 | Distinct visual design (our design notes; **not the copy-paste demo look**) | J1 (demo) | M | T08 |

## Milestone 4: Openness, prizes, submission
| ID | Task | Serves | Size | Depends on |
|---|---|---|---|---|
| T18 | 🔒 Publish the standard: JSON Schemas for the contracts + README (assumptions, path to production); REST/OpenAPI vs MCP per D7 | J5 | M | **D7 OPEN** |
| T19 | CRACI: CI on GitHub Actions `runs-on: craci` | CRACI prize | S | T01 |
| T20 | Codex review pass (cherry on top, at the end) | Codex prize | S | late |
| T21 | Demo script + peer-review Q&A prep (**name the criterion out loud**) | all | S | M2 |
| T22 | 2-min video **with RAEA** | submission | M | M2–M3 |
| T23 | Pitch deck PDF | submission | M | M2 |
| T24 | Final submission form (description, public repo, demo link, video) + make repo public | submission | S | all |

## Still OPEN (decide together; these block tasks above)
- **D2** where guardrails live (affects T06 / T10 and possibly a Valio-side gate task)
- **D7** standard format (blocks T18)
- **D8** hosting for the live demo link + storage for profile and audit log
- **D10** Gemma offline (later)
- **D12** demo + video format
- **D11** owners
- **Timeline:** "tomorrow" in the meeting = Saturday?
