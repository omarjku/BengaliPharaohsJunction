# M1 end-to-end: live run (Sat 14 Nov 2026, ~03:10 Helsinki)

`POST /api/agent/run` with `{text, requested_date, buyer_id}`. It runs request → Gemini parse → catalogue search → Gemini match → live Valio quote → quantity → decision → front-door order (or ask the human) → audit. Real Valio mock API and real Gemini (`gemini-4-hydrogen`, the default for `GEMINI_MODEL`), buyer `lapland-kitchen` (server-side mandate in `backend/app/mandates.py`: peanut-free, auto-approve up to EUR 1,500/order, EUR 2,000 per line, EUR 6,000/week). Delivery date: Monday 2026-11-16.

## 1. "1000 L lactose-free milk for Monday": ordered, held for sign-off (11 s)

Gemini parsed it as `milk, 1000 L, claims [FREE_FROM_LACTOSE]` and picked the real milks out of the keyword hits (keyword search alone ranks "milk ice cream" first). Five candidates were quoted:

| product | Valio | quantity | line total | |
|---|---|---|---|---|
| 464768 12 x Arla whole milk drink 1 L lactose free | Terminal, cut-off 12 Nov 15:00 **passed**, stock 999999 = **unknown** | can't convert L → KI | | rejected |
| **464201 Valio semi-skimmed milk 1 l lactose free UHT** | Stock, cut-off 15 Nov 17:00 | 1,000 L ÷ 1 L per ST = **1,000 ST** | **EUR 1,560.00** | **chosen** |
| 464073 Valio whole milk 1 l lactose free UHT | Stock | 1,000 ST | EUR 1,640.00 | alternative |
| 464119 Valio skimmed milk 1 l lactose free UHT | Terminal, cut-off passed, stock unknown | | | rejected |
| 463335 Valio Eila 3 % milk drink 1 l lactose free | Stock | 1,000 ST | EUR 1,400.00 | alternative |

The agent's own decision was AUTO, so it placed the order through the front door, which re-quoted it and returned **`pending_approval`, ASK_HUMAN, `SPEND_OVER_LIMIT`**: "This order is EUR 1,560.00 (net of VAT), above your EUR 1,500.00 auto-approve limit." The two orderable alternatives ride along for the approver (Eila at EUR 1,400 would fit the limit). The audit log has two entries: `buyer_agent` (AUTO, the chef's words, two rejected Terminal options) then `valio_front_door` (ASK_HUMAN). `audit_id` is the door's entry.

## 2. Trap: "60 L Arla lactose-free whole milk drink for Monday": not ordered, human asked (4 s)

The only match is 464768, a Terminal product. The response is **ASK_HUMAN, `order: null`**, with three reasons:
- `QTY_AMBIGUOUS`: "Can't convert 60 L into KI: no volume is recorded for this product. Please confirm the quantity in KI."
- `CUTOFF_PASSED`: the cut-off (2026-11-12 15:00) has passed, so it can't be ordered for 2026-11-16.
- `QTY_UNKNOWN`: Valio can't confirm stock (Terminal, 999999 = unknown).

Alternatives come from the front door's substitute finder (same category and dietary claims, re-quoted, all orderable for Monday): 464237 Valio coffee milk 1 l lactose free (EUR 1.30/ST), 463335 Eila 3 % milk drink (EUR 1.40/ST), 464201 semi-skimmed (EUR 1.56/ST). Audited as one `buyer_agent` ASK_HUMAN entry.

## Rules the flow follows
- **Gemini is used twice**: to parse the text into items (structured output; dietary words come from a closed enum that code maps to claims or allergen codes), and to judge which catalogue hits really are the product. Without a key or on failure, a regex parser and plain search order take over; `request.summary` starts with `[fallback parser, Gemini unavailable]` and a `LOW_CONFIDENCE` INFO reason is added.
- **Choosing a line**: hard checks are `gate.check_line`, the same checks the door runs. Lines with a blocking problem (cut-off, out of stock, undeliverable, partial stock, no price, hard DECLINE) or an unresolved quantity are never chosen. Among the rest, the agent prefers no quantity assumption, then fewer concerns, then Gemini's rank. Price is not part of the ranking.
- **Order or ask**: problems the door can't see (no match, missing amount, a quantity that needs confirming, a whole item with nothing orderable, no mandate) stop the run before any order. Everything else goes to the door, whose verdict (confirmed / pending_approval / refused) becomes the response's `decision`.
- Never a 500: Valio or door failure → `ENGINE_ERROR` ASK_HUMAN, nothing ordered.
