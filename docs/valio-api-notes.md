# Valio Aimo mock API: what works (tested Fri 13 Nov, 22:00)

**Auth:** header `X-API-Key: $VALIO_API_KEY` (key in your local `.env`, never commit it). `Authorization: Bearer` returns 401.
**Base URL:** `https://junction26.valioaimo.fi` · docs at `/docs` (behind the resource-portal password from the challenge page).
**Speed:** ~0.1 s per call. Rate limits exist but aren't disclosed. Don't poll the whole catalogue: filter with the static data first, then query.

| Endpoint | What it gives |
|---|---|
| `GET /api/ping` | `{"status":"ok"}` |
| `POST /api/availability` | per product: `closingTime` (order cut-off), `salesBlock`, `logisticModel` (Stock / Terminal), `scheduleLines[0].availableAmount` + `availableDate` |
| `POST /api/price` | `catalogPrice`, `priceWithTax`, `comparisonPrice` per L/KG, `tax`, `listPrice`, `netPriceFound` (customer price), `error` |
| `GET /api/{products,delivery-reliability,carbon-footprint}/download` | the static files (follow redirect, `curl -L`) |

Request body for both POSTs: `{"customer":"123","requestedDate":"YYYY-MM-DD","products":["460013",...]}` (1–1000 ids; customer doesn't matter in the mock).

**There is no order endpoint.** Placing an order (and the human approval step) is ours to define. That's the "interface and operating model" the brief asks for.

## Static data (`data/`, git-ignored; get the files from Omar or the download endpoints)
- 17,546 products, 349 categories, 648 suppliers; English names on all but 2.
- Allergens (GS1 codes with `CONTAINS` / `MAY_CONTAIN` / `FREE_FROM`) and claims: FREE_FROM_LACTOSE 4,178 · FREE_FROM_GLUTEN 3,049 · VEGAN 2,959.
- Carbon footprint (kg CO2-eq/kg): 11,033 products. Delivery reliability (0–1): 4,425 products.
- **Only 189 products have built-in substitutes**, so substitution needs our own logic (allergens + claims + category + Gemini).
- `allowedLotSize`: order quantity must be a multiple of it.

## Their example request, run for real
"1,000 L lactose-free milk by Monday 16 Nov":

| id | product | model | cut-off | available | €/unit | €/L |
|---|---|---|---|---|---|---|
| 463335 | Valio Eila 3% milk drink 1 L | Stock | Sun 15 Nov 17:00 | plenty | 1.40 (net price) | **1.40** |
| 463038 | Valio Eila semi-skimmed 10 L novobox | Terminal | **Thu 12 Nov 15:00 (already passed)** | 999999 = unknown | 31.31 | 1.57 |
| 462775 | Arla Milkdrink 1 L fat-free | Stock | Sun 17:00 | **51 only** | 2.57 | 2.57 |
| 462921 | Valio Eila organic 1 L | Terminal | Thu 12 Nov 15:00 (passed) | unknown | 10.97 | 2.19 |

**Traps the agent must catch (exception handling, 15%):**
1. Availability lines can say "Monday" while `closingTime` is already in the past, so the item can't actually be ordered for Monday.
2. Partial stock (51 of 1,000).
3. Terminal products report `999999`, which means *unknown*, not *infinite*. That's the "trust protocol" problem.

Right answer: 1,000 × 463335 = **€1,400**, order before Sun 17:00 → above a typical auto-approve limit, so it goes to the human with this comparison.

## Verified behaviour (300-product sample: 100 from big-manufacturer vendors + 200 random; 3 requested dates; Fri 13 Nov 22:58)
Raw responses: `data/api-samples/sample_1311.json` (git-ignored; ask Omar).

**Confirmed**
- **`User-Agent` required:** Python's default client gets **HTTP 403 "error code 1010"** (Cloudflare). Send your own `User-Agent` (e.g. `BengaliPharaohs-Junction2026/0.1`). curl works by default.
- **Terminal ⇔ `999999`:** 143/143 Terminal lines show 999999 (= unknown). Stock shows real numbers (102) or **0** (9).
- **~15% of products are undeliverable** (46/300): no `logisticModel`, no `closingTime`, empty `scheduleLines`.
- **Unknown product ids look exactly like undeliverable ones** in `/availability` (no error). Only `/price` flags them (`"error": true`). Validate ids against the product file.
- **The requested date is ignored right now:** asking for the 10th, 14th or 16th returns identical answers; every available product says `availableDate` = **Mon 16 Nov**. Requesting a past date isn't an error.
- **Cut-off pattern:** Stock = 17:00 the day before (some 13:00, 3 days before). **Terminal = 12:00–16:00 four days before.** So for Monday, **every Terminal product's cut-off already passed (Thu)**, yet it still says "available Monday". Systematic, not a one-off. → **Ask Valio:** deliberate trap, or mock simplification?
- Stock lines with amount 0 have **no `availableDate`** at all.
- **Prices:** no errors in the sample. **Customer net price is rare (6/300 = 2%)**, 22–53% below list when present. `comparisonPrice` missing for 17% (mostly KG, some L). **VAT matches the file's `vatCode` 248/248.**
- **`salesBlock` was never true** in the sample.
- **Lot size:** 96% of products have `allowedLotSize` 0.01 (no real constraint); a few have 1.5, 2, 3, 5, 10.
- **Units:** 3/254 lines report a different `salesUnit` than the product file (e.g. PAK vs KI). Trust the API line, flag the difference.

**Refuted**
- "VALO supplier-direct products = Terminal": **not supported.** Big-manufacturer vendors split 57 Terminal / 25 Stock / 18 undeliverable, similar to other vendors.
