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
