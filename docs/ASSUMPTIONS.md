# Assumptions and data traps

This is the judge-facing record for J5. It describes the code as it is now.

D6 is the rule for uncertain data: show the problem to a human. Do not silently
guess. An `ASK_HUMAN` decision can still have `order: null`. Some problems,
such as a passed cut-off, cannot be fixed by approval, so the order is refused
after the reason is shown.

## Checked traps

### 1. The requested date is ignored by the mock API

**Data / behaviour.** `docs/valio-api-notes.md` reports identical mock answers
for different `requestedDate` values. The mock often returns Monday as the
available date. A past date is not an error at the mock API.

**Assumption.** Treat the date in the request as the buyer's intent, not as
proof that Valio scheduled that date. This is reported mock behaviour. It is
not verified as production Valio behaviour.

**Code / human path.** `backend/app/valio.py` sends `requestedDate` and keeps
the returned `availableDate`. `backend/app/gate.py` raises
`DATE_NOT_HONOURED` with `ASK_HUMAN` when the returned date is later than the
requested date. If the mock echoes the requested date, the code cannot detect
that the mock ignored it. Direct orders reject a past date in
`backend/app/main.py`.

Files: `docs/valio-api-notes.md`, `backend/app/valio.py`,
`backend/app/gate.py`, `backend/app/main.py`.

### 2. Terminal `999999` means unknown quantity

**Data / behaviour.** Terminal availability reports `availableAmount: 999999`.
It does not mean unlimited stock. The notes also report Stock values of
`9999999999`, described as a second effectively-unlimited sentinel. That
meaning is not verified by the backend.

**Assumption.** `999999` is an unknown quantity. For review, the larger Stock
value is an unverified sentinel, not a real stock promise. The backend does not
yet encode that assumption.

**Code / human path.** `backend/app/valio.py` maps exactly `999999` to
`available_amount: null`, sets `quantity_known: false`, and adds
`quantity_unknown`. `backend/app/gate.py` emits `QTY_UNKNOWN` according to the
mandate's uncertainty policy. The demo policy is `ASK`, so the default result
asks the human. An explicit `DECLINE` policy declines it; an explicit
`APPROVE` policy allows it. The code currently leaves `9999999999` as a known,
very large amount. It does not ask about that value.

Files: `docs/valio-api-notes.md`, `backend/app/valio.py`,
`backend/app/gate.py`, `backend/app/mandates.py`,
`contracts/trade_contracts/quote.py`.

### 3. A cut-off can be past while availability says Monday

**Data / behaviour.** The notes report Terminal products with a Thursday
cut-off and a Monday availability line. The pattern was systematic in the
sample. It may be a mock quirk. It is not verified outside that sample.

**Assumption.** A passed `closingTime` wins over a friendly availability date.
Approval cannot make an expired cut-off orderable.

**Code / human path.** `backend/app/valio.py` adds `cutoff_passed` from the
API clock. `backend/app/gate.py` checks the clock again and emits
`CUTOFF_PASSED` with a suggested fix. The `Decision` is `ASK_HUMAN`, but the
reason is in `NOT_APPROVABLE`, so the order status is `refused` and no order is
stored (the run is still audited). Approval re-runs the check with fresh quotes in `backend/app/orders.py`.

Files: `docs/valio-api-notes.md`, `docs/DECISIONS.md`,
`backend/app/valio.py`, `backend/app/gate.py`, `backend/app/orders.py`.

### 4. About 15% of sampled products are undeliverable

**Data / behaviour.** The notes report 46 of 300 sampled products, about 15%,
with no logistic model, no closing time, or no schedule line. This is a sample
rate, not a promise about every catalogue load.

**Assumption.** No usable logistic model or schedule line means the product
cannot be ordered now. The rate outside the sample is not verified.

**Code / human path.** `backend/app/valio.py` adds `undeliverable` when the
availability response has no model or schedule line. `backend/app/gate.py`
returns `UNDELIVERABLE`, offers an alternative where possible, and treats it
as `NOT_APPROVABLE`. The agent does not choose that candidate. The order is
refused rather than silently dropped.

Files: `docs/valio-api-notes.md`, `backend/app/valio.py`,
`backend/app/gate.py`, `backend/app/agent.py`.

### 5. Unknown product IDs are caught by the price response

**Data / behaviour.** An unknown product can look like an undeliverable
product in `/availability`. The notes report that only `/price` returns
`error: true` for the unknown ID.

**Assumption.** Availability alone is not enough to classify a product. The
price error and the static catalogue are the product-identity checks.

**Code / human path.** `backend/app/valio.py` calls both endpoints and adds
`unknown_product` when the price item has `error`. `backend/app/gate.py` also
checks the catalogue. It returns `UNKNOWN_PRODUCT`, with a reason and a fix;
the direct gate declines it; in the agent flow an item with no catalogue match
becomes `UNKNOWN_PRODUCT` with `ASK_HUMAN`. No order is placed. `/api/products/{product_id}` also returns 404 when the local
catalogue has no match.

Files: `docs/valio-api-notes.md`, `backend/app/valio.py`,
`backend/app/gate.py`, `backend/app/catalogue.py`, `backend/app/main.py`.

### 6. Money is integer net-of-VAT cents

**Data / behaviour.** Valio returns euro values. The shared contracts use
integer cents. The documented basis is the customer price excluding VAT.

**Assumption.** `catalogPrice` is the net-of-VAT unit price for this mock. The
code does not use `priceWithTax` for order totals. This basis should be
confirmed with Valio before production.

**Code / human path.** `contracts/trade_contracts/money.py` converts euro
values with `Decimal` and half-up rounding. `backend/app/valio.py` uses
`catalogPrice`. `backend/app/gate.py` calculates line totals in cents and
labels spend messages as net of VAT. Missing price becomes `PRICE_MISSING`
and `ASK_HUMAN`; it is not treated as zero.

Files: `contracts/README.md`, `contracts/trade_contracts/common.py`,
`contracts/trade_contracts/money.py`, `contracts/trade_contracts/quote.py`,
`backend/app/valio.py`, `backend/app/gate.py`.

### 7. Quantity conversion never invents a unit

**Data / behaviour.** Human quantities use `L`, `dl`, `cl`, `ml`, `kg`, `g`,
`pcs`, or `units`. Product data supplies a base unit, unit conversion table,
volume or net weight, and `allowedLotSize`.

**Assumption.** Volume is usable only from volume units (`LTR`, `CLT`, `MLT`).
Weight is usable only from `KGM` or `GRM`. A base `KG` is treated as one kg.
Piece counts are not inferred for products sold by weight. A case conversion
or an ambiguous pack name is an assumption, not a fact.

**Code / human path.** `backend/app/quantity.py` uses `Fraction`, not binary
float arithmetic. It returns `quantity: null` and `needs_confirmation: true`
when the conversion data is missing, contradictory, dimensionally wrong, or
the lot size is missing. It rounds up to whole sales units, except that `KG`
sales can remain continuous. `0.01` is treated as no real lot constraint.
Conversions that rely on a case, approximate piece weight, or another listed
assumption return a quantity but still set `needs_confirmation: true`.

The agent asks the human when the request has no usable amount or unit, or when
conversion returns no quantity. When a candidate is otherwise viable,
`needs_confirmation: true` becomes `QTY_AMBIGUOUS`. If another blocking reason
already rejects that candidate, that blocking reason is reported instead.
Direct `POST /api/orders` does not convert human units. Its `quantity` is
already in the product's sales unit, and the gate checks the lot and other
rules. For non-`KG` sales, the current lot step is derived from
`lot.numerator`; behavior for fractional non-`KG` lots is not verified.

Files: `backend/app/quantity.py`, `backend/app/agent.py`,
`backend/app/main.py`, `backend/app/gate.py`.

### 8. The API sales unit can differ from the catalogue file

**Data / behaviour.** The notes report three differences in 254 sampled
availability lines, such as `PAK` versus `KI`. The live API line is the
current sales-unit statement.

**Assumption.** A mismatch needs human confirmation. The code must not silently
rewrite a quantity from one sales unit to another.

**Code / human path.** `backend/app/valio.py` keeps the API `salesUnit` in the
quote. `backend/app/quantity.py` currently resolves from the catalogue's
sales unit. `backend/app/gate.py` compares both and emits `UNIT_MISMATCH` with
both values and `ASK_HUMAN`; it does not rewrite the quantity. This is a
known integration boundary, not a verified equivalence.

Files: `docs/valio-api-notes.md`, `backend/app/valio.py`,
`backend/app/quantity.py`, `backend/app/gate.py`.

### 9. Mandates live at Valio, never in the request

**Data / behaviour.** Neither `POST /api/agent/run` nor `POST /api/orders`
accepts a mandate. `OrderRequest` forbids extra fields, so sending one is a
`422`.

**Assumption.** The buyer's rules are Valio-side state, tied to the buyer that
the agent key belongs to. A compromised or buggy agent cannot loosen its own
limits.

**Code / human path.** `backend/app/mandates.py` holds one in-code demo
mandate (and the buyer's Gemini confidence threshold, which the v0.2 contract
has no field for). `backend/app/agent.py` and `backend/app/main.py` both load
it for the key's buyer. If it is missing, the agent adds `MANDATE_MISSING` and
asks the human, and the front door refuses the order with `MANDATE_MISSING`.
Both are audited.

Files: `backend/app/mandates.py`, `backend/app/agent.py`,
`backend/app/main.py`, `backend/app/orders.py`.

### 10. Demo API keys are placeholders, not credentials

**Data / behaviour.** `AGENT_KEYS` and `APPROVER_KEYS` use the configured
`key=buyer_id[:name]` format. `.env.example` contains dummy values.

**Assumption.** The example values are for local setup only. They must not be
used as secrets or copied into a submission.

**Code / human path.** `backend/app/config.py` defaults both variables to
empty. `backend/app/auth.py` returns `503` when the relevant key list is
unset, `401` for a missing or invalid key, and prevents an agent key from
approving. The approver's buyer and name come from the configured key, not the
request body.

Files: `.env.example`, `backend/app/config.py`, `backend/app/auth.py`.

### 11. `/api/agent/run` is called with an agent key

**Data / behaviour.** The agent route runs the whole flow and can place an
order through the front door, so it is a write path like `POST /api/orders`.

**Assumption.** The caller is a purchasing agent with an `X-Agent-Key`, and the
buyer comes from that key, not from the request body. (The key check on this
route is being added in parallel with these docs; if your checkout predates
it, the route still accepts `buyer_id` from the body.)

**Code / human path.** `backend/app/agent.py` loads the buyer's mandate
server-side. A missing mandate produces `MANDATE_MISSING` and no order. When a
mandate exists, the agent calls `orders.place()` directly, and the front-door
gate still re-checks every line with fresh quotes.

Files: `backend/app/main.py`, `backend/app/auth.py`, `backend/app/agent.py`,
`backend/app/mandates.py`, `backend/app/orders.py`.

### 12. Orders and audits are JSON files on ephemeral disk

**Data / behaviour.** Orders use `data/orders.json`. Audits append to
`data/audit.jsonl`. Render disk is ephemeral, and the files can grow without a
retention policy.

**Assumption.** File storage is acceptable for the demo only. Orders and audit
history may disappear when the instance is replaced or redeployed. This is
not durable production storage.

**Code / human path.** `backend/app/orders.py` loads an in-process order cache,
writes orders through a temporary file and `os.replace`, and appends audit
entries under a file lock. The audit keeps the reasons and rejected options
while the file exists. There is no database transaction, retention job, or
cross-instance store. The decision and audit are visible to the human, but
durability is not guaranteed.

Files: `backend/app/orders.py`, `backend/app/catalogue.py`,
`docs/DECISIONS.md`.

### 13. The storage and lock assume one worker

**Data / behaviour.** The order store and its `asyncio.Lock` are process-local.
The app comments require one Uvicorn worker. `dev.sh` starts one Uvicorn
command and does not configure multiple workers.

**Assumption.** One application process owns the order state. Multiple workers
or instances are not a supported consistency model.

**Code / human path.** `backend/app/orders.py` serializes decisions and retries
when the in-process spend state changes. That does not coordinate separate
workers. Running more than one worker could make budget and approval state
stale. A database transaction is the documented next step before scaling.

Files: `backend/app/main.py`, `backend/app/orders.py`, `dev.sh`,
`docs/DECISIONS.md`.

### 14. The reliability floor is a sign-off rule, not a hard rule

**Data / behaviour.** Valio's reliability file covers 4,425 of 17,546 products
(0–1, the share delivered on time). The demo mandate sets
`MIN_DELIVERY_RELIABILITY` 0.9 because Lapland deliveries are fragile.

**Assumption (decision D13).** Falling below the floor is a question for the
chef, never a refusal: a kitchen may knowingly accept a less reliable supplier.
It is a **sign-off rule**, like the auto-approve limit, per-line cap and weekly
budget. **Hard rules** refuse: an excluded allergen the product contains, a
missing required claim, a unit price over the maximum, a passed cut-off.

**Code / human path.** `backend/app/gate.py` returns `LOW_RELIABILITY` with
`ASK_HUMAN` below the floor. With no reliability record it returns
`DATA_MISSING` under the mandate's uncertainty policy (ask by default). The
front door holds the order as `pending_approval`. The agent prefers a product
without that concern, and says so in the chosen line's `why`. The rule is still
stored in `Mandate.hard_rules`, because the v0.2 contract has nowhere else to
put it.

Files: `backend/app/mandates.py`, `backend/app/gate.py`, `backend/app/agent.py`,
`docs/DECISIONS.md`.

## Open interface and operating model

Valio's mock has no order endpoint. The repository defines the order and human
approval surface as its own REST front door. It re-checks price, stock, cut-off,
quantity, and mandate rules before storing an order. This follows D2.

The public shapes are not a proprietary wire format:

- `docs/schemas/openapi.json` is exported as OpenAPI `3.1.0`.
- `docs/schemas/` contains one JSON Schema for each shared contract.
- `contracts/schemas/` contains the same contract schemas with their source
  filenames.
- The shared contracts use `contract_version` `0.2`, reject unknown fields,
  and make `Decision` reasons, suggested fixes, alternatives, and audit input
  explicit.

`docs/export_schemas.py` generates the API export and the contract files are
generated by `contracts/trade_contracts/export_schemas.py`. Regenerate both
exports after a contract change. The source files are
`contracts/README.md`, `contracts/trade_contracts/`,
`docs/export_schemas.py`, and `docs/schemas/`.

The Valio client also sends the required API header and a non-default
`User-Agent`, batches at the documented maximum of 1,000 products, and avoids
catalogue-wide API sweeps. Rate limits are undisclosed. An upstream failure
becomes `ENGINE_ERROR` and `ASK_HUMAN` in the agent flow, or a `503` from the
front door. Files: `docs/valio-api-notes.md`, `backend/app/valio.py`,
`backend/app/orders.py`.

## Credible next steps

These are not implemented claims:

- Confirm the requested-date, cut-off, and stock-sentinel semantics with Valio.
- Special-case the `9999999999` Stock value only after that confirmation.
- Resolve quantity against the live API sales unit, and add tests for fractional
  non-`KG` lot sizes.
- Move mandates from the in-code demo map to a database the buyer can edit,
  and add `min_confidence` to the `Mandate` contract.
- Move orders and audits to Postgres with transactions before adding workers or
  instances. Add retention and recovery rules.
- Replace example key values with rotated secrets managed outside the repo.
