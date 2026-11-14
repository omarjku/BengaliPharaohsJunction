## Verdict

**Request changes.** There are paths to silent `AUTO` for contradictory quote data, a malformed input that breaks the fail-closed handler, and a broad text rule that can decline a clean order.

## Findings

1. **High — Explicitly unavailable product can be AUTO** — [rules.py](decision/trade_decision/rules.py:593)

   **Input:** Using the test builders, `run(quotes=[make_quote(availability="unavailable", stock=5000)])`. For the default 100-unit line, the decision can be `AUTO`: stock is sufficient, and `UNDELIVERABLE` is only emitted when the quantity is unknown.

   **Fix:** Treat `Availability.UNAVAILABLE` as undeliverable regardless of quantity, or ask on contradictory availability and stock fields.

2. **High — Conflicting duplicate records silently use the last value** — [engine.py](decision/trade_decision/engine.py:100)

   **Input:** Pass two `make_facts()` records for the same product, first with `allergens={"gluten": "CONTAINS"}`, then `{"gluten": "FREE_FROM"}`, with a gluten-excluding mandate. The dict comprehension keeps the second record, so the risky order may be `AUTO`. Reversing quote order can similarly hide a partial-stock or high-price quote.

   **Fix:** Detect duplicate product IDs and ask on conflicts, or resolve them conservatively.

3. **High — Fail-closed can itself raise on a naïve clock** — [engine.py](decision/trade_decision/engine.py:156)

   **Input:** `decide(make_request(), make_mandate(), None, [], [], now=datetime(2026, 11, 14, 9, 0))`. `merge_lines` raises, then `_fail_closed` builds a `Decision` with the same naïve `now`; `AwareDatetime` validation raises instead of returning `ASK_HUMAN`.

   **Fix:** Normalize or safely replace `now` in `_fail_closed` before constructing the decision.

4. **Medium — Negated limit-change text causes a false DECLINE** — [rules.py](decision/trade_decision/rules.py:256)

   **Input:** `run(request=make_request(text="No need to change the spending limit; order 100 L of milk."))`. The proximity regex matches “change … limit” despite the negation and declines the otherwise clean order.

   **Fix:** Detect an explicit affirmative request to alter mandate rules, including the target rule, rather than matching nearby keywords.