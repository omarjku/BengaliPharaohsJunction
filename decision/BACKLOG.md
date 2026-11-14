# T06 backlog (not in decision v0)

**T05 (quantity resolver):** case 10 (round 1,000 L up to 84 cartons), case 9 (fractional quantity on a pack unit), case 11 (rounding pushes over the limit), case 2 (ambiguous quantity "some cream").

**State needed (T07 front door / audit):** case 50 idempotency, case 51 concurrent orders, case 52 human never answers, case 53 audit-write failure, D16 front-door refusal, D23 human answers as new audit events, D24 audit entry, D25 refusal shape.

**NICE rows:** 14 (price on comparison unit), 18 (Finnish holidays), 24 (currency not EUR), 26 (Lapland lead time), 31 (per-line decisions + order level), 33 (split across suppliers), 45-47/49 (prompt injection in product text, lookalike supplier; needs data we do not have), D27 alert batching, D21 labels beyond text.

**Contract gaps found while building the skeleton:**
- `ProductFacts` has no origin field, so the "Local" alternative label cannot work yet (`alternatives.is_local` reads `origin_country` if added).
- `Quote` has no explicit `deliverable` flag; v0 reads `availability == unavailable` with unknown quantity as UNDELIVERABLE and known quantity 0 as STOCK_NONE.
