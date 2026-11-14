# T06 backlog (not in decision v0)

**T05 (quantity resolver):** case 10 (round 1,000 L up to 84 cartons), case 9 (fractional quantity on a pack unit), case 11 (rounding pushes over the limit), case 2 (ambiguous quantity "some cream").

**State needed (T07 front door / audit):** case 50 idempotency, case 51 concurrent orders, case 52 human never answers, case 53 audit-write failure, D16 front-door refusal, D23 human answers as new audit events, D24 audit entry, D25 refusal shape.

**NICE rows:** 14 (price on comparison unit), 18 (Finnish holidays), 24 (currency not EUR), 26 (Lapland lead time), 31 (per-line decisions + order level), 33 (split across suppliers), 45-47/49 (prompt injection in product text, lookalike supplier; needs data we do not have), D27 alert batching, D21 labels beyond text.

**Contract gaps found while building the skeleton:**
- `ProductFacts` has no origin field, so the "Local" alternative label cannot work yet (`alternatives.is_local` reads `origin_country` if added).
- `Quote` has no explicit `deliverable` flag; v0 reads `availability == unavailable` with unknown quantity as UNDELIVERABLE and known quantity 0 as STOCK_NONE.

## T06.1 deferred (not done in the 15-minute pass)
- Item 7: merge the same product across unit spellings by product id (different unit kinds ask UNIT_MISMATCH).
- Item 8: alternatives must be in the same category as the ordered product (unknown category offers none).
- Item 9: allergen names vs the catalogue GS1 codes (AP peanuts, AM milk, AW gluten, ...): alias table in decision/, kept in sync with backend/app/catalogue.py.
- Contract gaps still open for T02.2 (origin, deliverable flag, min-order code, enum exports, Order shape, AuditEntry action).
