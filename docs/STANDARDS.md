# Standards and mappings

This document describes the formats in the repository and a proposed mapping to Peppol. It is written from the current code.

The Peppol section is a mapping only. It is not implemented. The repository has no UBL serializer, Peppol endpoint, or Peppol transport.

## Where we stand against agent-commerce and interop standards

Checked on 15 Nov 2026 with a web search. Each status line is one sentence; the links go to the spec or the
owner's own page.

| Standard | What it is | Our front door | Why |
|---|---|---|---|
| [OpenAPI 3.1](https://spec.openapis.org/oas/v3.1.0) + [JSON Schema 2020-12](https://json-schema.org/draft/2020-12) | Describes an HTTP API and its message shapes | **Implemented**: [`schemas/openapi.json`](schemas/openapi.json) and one schema per contract | Any agent, in any language, can code against the door without our SDK (D7) |
| [MCP](https://modelcontextprotocol.io/specification/latest) (Model Context Protocol, spec 2026-07-28, Linux Foundation AAIF) | How an AI app gives a model tools and data | **Implemented**: [`mcp/`](../mcp/), a thin MCP server (official `mcp` 2.x SDK) over our REST API: search, quote, quantity, place order, read order. No approve tool. Tested end to end against the live Valio mock | It is the way most agents (Claude, ChatGPT, Gemini CLI, IDEs) plug in tools today, so "any buyer's agent can plug in" becomes literal |
| [A2A](https://a2a-protocol.org/) (Agent2Agent, v1.0, Linux Foundation) | Agent-to-agent messaging: agent cards, tasks, long-running work | **Next step, mapped in spirit**: our buyer agent → front door is an agent-to-agent hop, but over plain REST | Worth it when Valio's side is itself an agent that negotiates multi-step tasks; for fixed-price orders REST is simpler |
| [AP2](https://ap2-protocol.org/) (Agent Payments Protocol, Google, an A2A extension) | Signed "mandates" proving what the user authorised: intent, cart, payment | **Mapped, not implemented**: our `Mandate` is close to an AP2 intent mandate (limits set in advance, the buyer's own words kept); a confirmed order is close to a cart mandate | It is the closest public standard to our core idea: the buyer's rules are checked where the order lands. Our mandates are server-side and unsigned; the door's *decisions* are already Ed25519-signed (see Signed front-door statements) |
| [Visa Trusted Agent Protocol](https://investor.visa.com/news/news-details/2026/Visa-Opens-the-Door-to-AI-Driven-Shopping-for-Businesses-Worldwide/) (Visa Intelligent Commerce, pilot, Apr 2026) | Lets a merchant recognise a trusted agent and the user's spend controls behind it | **Not used, same direction** | It is part of the same trust-layer trend as AP2 and Mastercard Agent Pay, which carry the buyer's limits as signed mandates. Our server-side mandates and signed decisions point the same way. We have not checked TAP's message format |
| [ACP](https://www.agenticcommerce.dev/) (Agentic Commerce Protocol, OpenAI + Stripe) | Consumer checkout between an AI agent and a merchant, with delegated payment tokens | **Not used** | It targets consumer checkout and card payment; Valio Aimo is B2B on account, prices are fixed and payment rails are out of scope for this challenge |
| [UCP](https://developers.google.com/universal-commerce-protocol) (Universal Commerce Protocol, Google) | Discovery-to-checkout commerce capabilities, over REST, A2A or MCP, with AP2 for authorisation | **Not used, watch** | Consumer-retail first, like ACP; its "capabilities" idea would fit a Valio catalogue later |
| [Peppol BIS Order 3.0 / UBL 2.1](https://docs.peppol.eu/poacc/upgrade-3/syntax/Order/) | The EU's e-procurement order and order-response documents | **Mapped, not implemented** (see the mapping below) | This is how Finnish public kitchens and many businesses already send orders; a confirmed order should be exportable as a Peppol Order |
| [GS1](https://www.gs1.org/) (AllergenTypeCode, GTIN) | Shared product codes and identifiers | **Implemented** for allergens; **next step** for GTIN | We filter and refuse on GS1 allergen codes today; the slim catalogue doesn't carry GTINs yet (below) |
| [RFC 9421](https://www.rfc-editor.org/rfc/rfc9421) HTTP Message Signatures (and the IETF [Web Bot Auth](https://datatracker.ietf.org/wg/webbotauth/about/) drafts built on it) | Signs an HTTP request, so the receiver can verify who sent it and that it wasn't changed | **Next step** | It would replace our static `X-Agent-Key` shared secrets with a per-agent key pair and a signature on every order |

**Where we are on signed mandates.** The industry's trust layer is converging on signed mandates and agent spend controls:
AP2 and Mastercard Agent Pay use signed mandates, and Visa adds spend controls through its Trusted Agent Protocol (sources in [`docs/research/valio-context.md`](research/valio-context.md)).
We have one half of that. The door signs what it decided (an Ed25519 statement on every order response, verifiable
at `/.well-known/front-door-keys.json`), but the buyer's mandate is still trusted because it is stored at our end.

**Recommended next standard: RFC 9421 signed requests, then AP2-style signed mandates.** The weakest link today is
identity. An agent proves itself with a static shared secret, and the mandate is trusted because it is stored at
our end. Signing each `POST /api/orders` with RFC 9421 gives every agent its own key and makes each order
non-repudiable in the audit log, at the cost of a key directory and a signature check. It is a published RFC and it
needs no new payload format. Once agents are identified, the stored `Mandate` can be issued to the buyer as a
signed, expiring AP2-style intent mandate, and Valio could verify it without holding a copy. Peppol export comes
after that, for the order document itself.

## Published open formats

| Area | Current format | Location | Source or command |
|---|---|---|---|
| HTTP API | OpenAPI 3.1.0, generated by FastAPI | [`docs/schemas/openapi.json`](schemas/openapi.json) | `backend/.venv/bin/python docs/export_schemas.py` |
| Shared messages | JSON Schema output from Pydantic v2, using the draft 2020-12 vocabulary | [`docs/schemas/`](schemas/) | Same command |
| Python-side messages | Pydantic models, contract version `0.2` | [`contracts/trade_contracts/`](../contracts/trade_contracts/) | [`contracts/README.md`](../contracts/README.md) |

The six published contract shapes are `PurchaseRequest`, `Mandate`, `Quote`, `ProductFacts`, `Decision`, and `AuditEntry`.
The same six schemas are also exported as `contracts/schemas/*.schema.json`.

The contract base model rejects unknown fields. Top-level contracts carry `contract_version: "0.2"`. Contract datetimes are timezone-aware.

The OpenAPI export documents the route request models. The success responses currently use generic `object` or `array` schemas because the route handlers return `dict` and `list[dict]`. The shared response content is therefore documented more precisely by the standalone contract schemas and by the code.

Current routes include quote lookup, product search, quantity resolution, order placement, order approval or rejection, audit lookup, and the end-to-end agent run:

| Route | Purpose |
|---|---|
| `POST /api/quotes` | Price and availability for selected Valio product IDs |
| `GET /api/products/search`, `GET /api/products/{product_id}` | Catalogue search and facts |
| `POST /api/quantity/resolve` | Convert a human amount to sales units |
| `POST /api/orders` | Front-door order check and placement |
| `GET /api/orders/{order_id}`, `POST .../approve`, `POST .../reject` | Order review |
| `GET /api/audit` | Audit entries |
| `POST /api/agent/run` | Text to catalogue, quote, decision, order, and audit |

## Visibility of decisions and assumptions

- `PurchaseRequest.text` keeps the buyer's original words on agent runs; for a direct `POST /api/orders` the door writes a short summary of the lines instead.
- `Quote` records price, availability, quantity-known state, source, fetch time, validity, and cut-off.
- `Decision.reasons` is sorted by severity. Each reason has a code, plain message, facts, and an optional suggested fix.
- `Decision.alternatives` records proposed substitutes. `Decision.confidence` is the Gemini Decisions confidence of the weakest chosen line (agent runs only; the front door leaves it empty).
- `AuditEntry` stores the request, mandate, quotes, decision, and rejected options.
- The agent uses Gemini for request parsing, product matching and a Decisions-API confidence check on each chosen line. Quantity, price, stock, mandate, and order checks are deterministic. The front door checks again with fresh Valio quotes.
- A Terminal quantity reported as `999999` is represented as unknown, not unlimited.
- A `pending_approval` order is stored for human approval. A `refused` order is not stored, but the gate run is audited. A pending order that fails the re-check at approval stays stored, as `refused`.

## GS1 allergen data

`backend/app/catalogue.py` reads the Valio `synkkaData.classifications` entries whose name is `allergen`. It keeps the GS1-style `id` and maps the containment level into three lists:

| Source level | Runtime catalogue field |
|---|---|
| `CONTAINS` | `allergens.contains` |
| `MAY_CONTAIN` | `allergens.may_contain` |
| `FREE_FROM` | `allergens.free_from` |

Examples used by the code:

| Code | Label in the code |
|---|---|
| `AM` | milk |
| `AP` | peanuts |
| `AE` | egg |
| `AN` | tree nuts |
| `AW` | gluten (cereals) |
| `AY` | soy |

The full label map is in `catalogue.ALLERGEN_NAMES`. Codes not in that map remain codes. The code uses the [GS1 AllergenTypeCode vocabulary](https://ref.gs1.org/voc/AllergenTypeCode).

Search excludes `CONTAINS` allergens. With `strict_may_contain=true`, it also excludes `MAY_CONTAIN` allergens. The gate treats an excluded `CONTAINS` allergen as `ALLERGEN_CONTAINS` and `DECLINE`; an excluded `MAY_CONTAIN` allergen becomes `ALLERGEN_MAY_CONTAIN` and `ASK_HUMAN`.

Claims are separate from allergen levels. For example, lactose-free is the `FREE_FROM_LACTOSE` claim. Lactose-free milk may still have `AM` in `CONTAINS`.

The `ProductFacts` contract represents allergens as a name-to-status map. The current catalogue endpoint returns the code lists above. The backend does not currently convert the endpoint output into `ProductFacts`.

### Product identifiers and GTIN

The current catalogue and contracts carry Valio product IDs, not GTINs. Valio's product data schema (`valio_aimo_junction26_product_data_schema.json`, downloaded with the data, not in git) does define `gtin` and `salesUnitGtin` fields, but `backend/app/catalogue.py` does not copy them into the slim catalogue, so carrying them is a small change.

- Catalogue records keep Valio's product code as `id`.
- `ProductId` is a numeric string of one to twelve digits.
- `OrderLine`, `Quote`, and `ProductFacts` have `product_id`, but no `gtin`, EAN, or barcode field.

Therefore the current identifier can map to a seller identifier, but it must not be presented as a GTIN. A future UBL mapping can populate `cac:StandardItemIdentification/cbc:ID` with a real GTIN and `schemeID="0160"`; that data is not present today.

## Proposed Peppol BIS Order mapping

Target: [Peppol BIS Order 3.0, UBL `Order`](https://docs.peppol.eu/poacc/upgrade-3/2022-Q4/syntax/Order/) and [Peppol Order Response 3.0](https://docs.peppol.eu/poacc/upgrade-3/2022-Q4/syntax/OrderResponse/). The target uses the UBL 2.1 `Order` and `OrderResponse` vocabularies.

This table proposes where current fields could go. It does not add those fields to the API and does not claim Peppol conformance.

### Order header

| Current field | UBL / Peppol element | Proposed mapping and gap |
|---|---|---|
| `PurchaseRequest.id`; the stored order's `id` (`order_id` in responses) | `cbc:ID` | Use as the order document ID. Direct `OrderRequest` has no caller-supplied ID, so the identity rule is open. |
| `PurchaseRequest.created_at`; order creation time | `cbc:IssueDate`, optional `cbc:IssueTime` | Use the order creation time. Do not use `requested_date` as the issue date. |
| `OrderRequest.buyer_id`; `PurchaseRequest.buyer_id` | `cac:BuyerCustomerParty` | Candidate for a buyer party identifier. The value is an internal buyer ID. A Peppol endpoint ID, scheme, legal name, and address are not in the current model. |
| Valio seller context | `cac:SellerSupplierParty` | Required by Peppol. Seller party identifiers and legal party data are not in the current order contract. Add them before serialization. |
| `OrderRequest.requested_date`; `PurchaseRequest.needed_by` | `cac:Delivery/cac:RequestedDeliveryPeriod` | The application carries one date, not a period. A same-day `StartDate`/`EndDate` is a possible policy, but is not implemented. |
| No local field | `cbc:CustomizationID`, `cbc:ProfileID` | Serializer constants. Pin the exact Peppol release and profile (`order_only` or `ordering`) when implementation starts. |
| Valio quote currency | `cbc:DocumentCurrencyCode` | Use `EUR` under the current euro-price assumption. The canonical `Quote` has no currency field, so this assumption needs an explicit contract decision. |
| `PurchaseRequest.text` | `cbc:Note` | Optional free-text copy of the buyer's words. The structured line fields remain authoritative. |

### Lines, quote data, and totals

| Current field | UBL / Peppol element | Proposed mapping and gap |
|---|---|---|
| `OrderRequest.lines[].product_id`; `Quote.product_id` | `cac:OrderLine/cac:LineItem/cac:Item/cac:SellersItemIdentification/cbc:ID` | Map as the Valio seller product code. This is not a GTIN. |
| No current GTIN field | `cac:OrderLine/cac:LineItem/cac:Item/cac:StandardItemIdentification/cbc:ID`, `@schemeID="0160"` | No mapping is possible today. Add and validate a real GTIN first. |
| `Quote.product_name`; catalogue `name_en` or `name_fi` | `cac:Item/cbc:Name` | Map the selected catalogue name. |
| `OrderRequest.lines[].quantity`; gate line `quantity` | `cac:OrderLine/cac:LineItem/cbc:Quantity` | Quantity is in the product's Valio sales unit. It must be converted to a valid UBL `@unitCode`. |
| Valio `sales_unit`, exposed as `Quote.unit` or a line `unit` | `cbc:Quantity/@unitCode`; also `cac:Price/cbc:BaseQuantity/@unitCode` when used | Valio uses values such as `KI`, `ST`, and `KG`. Peppol expects UN/ECE Recommendation 20 codes. See the open mapping below. |
| `Quote.unit_price_cents`; line `unit_price_cents` | `cac:OrderLine/cac:LineItem/cac:Price/cbc:PriceAmount/@currencyID` | Divide integer cents by 100 and emit a UBL decimal amount. The current value is net of VAT and per sales unit. |
| Line `line_total_cents` | `cac:OrderLine/cac:LineItem/cbc:LineExtensionAmount/@currencyID` | Divide integer cents by 100. This is the net line amount. |
| `orders` response `total_cents` | `cac:AnticipatedMonetaryTotal/cbc:LineExtensionAmount/@currencyID` | Sum of the net line amounts, divided by 100. `TaxExclusiveAmount` could carry the same value while there are no allowances or charges, but this is not implemented. |
| `Quote.available_date` | Order Response `cac:Delivery/cac:PromisedDeliveryPeriod` | Candidate source for a promised date after acceptance. The current order response is JSON, not UBL. |
| `Quote.availability`, `Quote.quantity.known/value` | Order Response line quantity, `cbc:Note`, and response code | There is no one-to-one field for all current states. Unknown quantity must remain visible; it must not become a large UBL quantity. |
| `Quote.cut_off`, `Quote.valid_until`, `Quote.fetched_at`, `Quote.source` | No direct basic Order element | Keep in the JSON audit and use `cbc:Note` only for a short human explanation. A future extension needs a separate design. |
| `Decision.reasons` and `rejected_options` | `cbc:Note`; optional line `cbc:Note` | Preserve the human message in the document. `Reason.code`, facts, and suggested fixes have no direct basic Order field; keep the structured form in the audit contract. |
| `Decision.alternatives` | No direct basic Order field; possible `cac:SellerSubstitutedLineItem` for an actual accepted substitution | Current alternatives are suggestions, not seller substitutions. Do not serialize them as substitutions without a new decision. |

### Money convention

The contracts use integer cents, net of VAT. For example, `1400` means EUR 14.00 net. The live Valio adapter converts `catalogPrice` from euros into `unit_price_cents`. It also receives tax-inclusive price data, but the canonical `Quote` does not carry `price_with_tax` or `tax_rate`.

UBL carries decimal monetary amounts, such as `14.00`, with `currencyID="EUR"`. A serializer must divide cents by 100 and set the currency on `PriceAmount`, `LineExtensionAmount`, and monetary totals. VAT totals and tax-inclusive totals are not represented by the current order contracts.

### Order Response verdicts

Use the front-door `status` for this mapping. `Decision.outcome` explains the decision (`AUTO`, `ASK_HUMAN`, or `DECLINE`) but is not the same as the stored order status. For example, the gate can return `ASK_HUMAN` and still set status `refused` when no human approval can make the order deliverable.

The proposed whole-order mapping is:

| Current status | `cbc:OrderResponseCode` | Meaning and implementation note |
|---|---|---|
| `confirmed` | `AP` — Accepted | The front door accepted the order. Under the target rules, a whole-order accepted response must not contain response lines. |
| `pending_approval` | `AB` — Message acknowledgement | The order was received but is waiting for internal human approval. Use `CA` — Conditionally accepted — only if the business meaning becomes conditional acceptance with response lines. This choice is open. |
| `refused` | `RE` — Rejected | The front door refused the order. Under the target rules, a whole-order rejected response must not contain response lines. Put the reasons in `cbc:Note`. |
| `rejected` after human action | `RE` — Rejected | The approver rejected a previously pending local order. Keep the human action in the audit actor. |

For a Peppol `OrderResponse`, the response document would also need its own `cbc:ID`, `cbc:IssueDate`, `cbc:DocumentCurrencyCode`, `cac:OrderReference/cbc:ID`, seller party, and buyer party. These are not emitted by the current JSON response.

If `/api/agent/run` stops before an order is placed, its `order: null` result is an agent decision, not a Peppol response to a submitted order.

### Unit-code gap

The application uses Valio sales-unit values such as `KI`, `ST`, and `KG`. UBL `cbc:Quantity/@unitCode` uses [UN/ECE Recommendation 20](https://docs.peppol.eu/poacc/upgrade-3/2022-Q4/codelist/UNECERec20/), for example:

- `XCS` means case.
- `H87` means piece.
- `KGM` means kilogram.

Possible mappings are `KI` → `XCS`, `ST` → `H87`, and `KG` → `KGM`. These are candidates only. The code does not define this mapping, and `KI` must not be passed through as the UN/ECE code `KI`, which has a different meaning in that code list. Validate the mapping per product and sales unit before producing UBL.

## Signed front-door statements

Every order response (`POST /api/orders`, approve, reject, and the order inside `/api/agent/run`) carries
`signed_statement` and `signature`. A buyer's agent can check them without trusting the transport or doing a
manual check.

- **What is signed.** `signed_statement` = `{v: 1, iss: "valio-front-door", order_id, status, audit_id,
  total_cents, decision, quotes, lines}`. `lines` are the order lines `{product_id, quantity, unit,
  unit_price_cents, line_total_cents}`. Act only on the verified `signed_statement`; the response's top-level copies are
  unsigned conveniences. `decision` is the contract `Decision`. Each entry in `quotes` is what Valio's
  API reported at `fetched_at`: `product_id, unit_price_cents, unit, availability, available_quantity, cut_off,
  cut_off_passed, fetched_at, origin`. `origin` comes from Valio's catalogue.
- **Exact bytes.** UTF-8 JSON with keys sorted at every level, no whitespace (separators `,` and `:`),
  non-ASCII characters left as is, no NaN or Infinity. In Python:
  `json.dumps(s, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()`.
  Numbers use Python's formatting (`51.0` stays `51.0`), so a non-Python verifier should check through
  `POST /api/verify`, or format floats the same way. RFC 8785 (JCS) is the planned upgrade.
- **Algorithm and key.** Ed25519 (RFC 8032). `signature = {kid, alg: "Ed25519", value}`, where `value` is the
  64-byte signature in base64url without padding. The public key is published at
  `GET /.well-known/front-door-keys.json` as a JWK Set (RFC 8037: `kty: OKP, crv: Ed25519, x`), selected by `kid`.
  The private key comes from `FRONT_DOOR_SIGNING_KEY`: base64 of the 32-byte seed. If it is unset, the server uses
  an ephemeral development key and logs that.
- **Verify.** Either `POST /api/verify` with `{signed_statement, signature}` (returns `valid`), or offline:
  canonical bytes + JWK `x` + any Ed25519 library.
- **What it proves, and what it does not.** A valid signature proves that this Valio front door issued exactly
  this decision and these quote facts, unchanged. It does not prove that the warehouse physically holds the
  stock: the facts are what Valio's API reported at `fetched_at`.
- **Prior art.** This is a detached signature over canonical JSON, in the spirit of JWS (RFC 7515) and HTTP
  Message Signatures (RFC 9421). It signs the business statement rather than the HTTP message, so the statement
  can be stored and checked later.

## Next steps

1. Add an explicit GTIN field to the catalogue and `ProductFacts`, and validate the GS1 identifier before using `StandardItemIdentification`.
2. Add buyer and seller party identifiers, endpoint scheme IDs, legal names, and delivery data.
3. Define and test the Valio-to-UN/ECE unit map. Preserve both the raw Valio unit and the normalized UBL code.
4. Decide the exact-date policy and the `AB` versus `CA` meaning for pending approval.
5. Add a UBL serializer and validate `Order` and `OrderResponse` against the pinned Peppol release and Schematron rules.
6. Add typed success response models to FastAPI so the generated OpenAPI describes response bodies as well as request bodies.
7. Replace the current JSON-file, single-worker order and audit store with a durable transactional store before production. The code comments identify Postgres as the next step.

Reference code lists: [Peppol Order Response codes](https://docs.peppol.eu/poacc/upgrade-3/2022-Q4/codelist/UNCL4343-T76/) and [ISO 6523 ICD codes](https://docs.peppol.eu/poacc/upgrade-3/2022-Q4/codelist/ICD/).
