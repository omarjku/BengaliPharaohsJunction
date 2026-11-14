# Edge-eval release-1 triage

## Run status

- Corpus validation: `scripts/edge_eval.py --dry-run --label release-1` passed; 154 cases were selected.
- Live run requested: `scripts/edge_eval.py --base http://127.0.0.1:8780 --label release-1`.
- Live blocker: the real backend completed startup but the sandbox rejected its TCP bind on `127.0.0.1:8780` (and `0.0.0.0:8780`) with `Operation not permitted`. No live pass/fail count is claimed here.
- Ranking below is therefore a release-triage hypothesis, grounded in `/tmp/acceptance-release-1.md` (7/12) and the prior `docs/testing/edge-eval-2026-11-14.md` baseline (47/144, 32.6%).

The number is global priority; entries are grouped by likely owning file. Examples are the smallest reproductions from the supplied acceptance transcript or the existing edge corpus.

## `backend/app/quantity.py` and `backend/app/agent.py`

1. **Requested weight is treated as sales-unit count.** `25 kg butter` became 25 × 500 g = 12.5 kg instead of one 25 kg requested line (acceptance F4). Likely boundary: the parsed `kg` request is lost or a resolved quantity is overwritten with the candidate's `ST` count. Recheck `quantity.resolve()` output and the final line quantity after product selection.

2. **Pack/case conversion is not enforced consistently for ordinary products.** The same failure mode can under-deliver or over-deliver when a product is sold in `ST`/`KI`; the edge corpus stresses `50 kg Valio butter`, `10 cases oat milk`, and `3 trays eggs`. Likely boundary: `agent.py` quantity assembly versus `quantity.py`'s `sales_unit`, `base_unit`, and lot-size conversion.

## `backend/app/agent.py`

3. **Usual/standing product does not win when the noun is ambiguous.** Instead of choosing the kitchen's normal butter, the agent asks `butter unsalted / salted / Arla` (acceptance F4/F5; also `phone-06`). The candidate path has standing-product support, but it is not reliably applied before the generic alternatives/clarification gate.

4. **Duplicate-order protection fires for information and edits.** `What's my usual order?` and `Actually, I want oat milk instead of normal milk.` produced `You ordered this 1 minute ago` (acceptance F1/F2). `recent_duplicate()` is reached for messages that are not repeat-order intents; the guard needs a stronger question/change/new-request exclusion than `_AGAIN` alone.

5. **Spoken self-corrections retain the first amount or leave a contradictory candidate.** `20 kilos of butter, no wait, make it 25, for Monday` returned a clarification while the cart showed 25 × 500 g (acceptance F4). The latest correction must replace the earlier amount before candidate matching, quantity resolution, and duplicate checks.

6. **Alternatives are ranked as a broad catalogue list instead of a kitchen-safe default.** The same generic ambiguity appears for milk, salmon, cream, and butter; prior edge failures include `Best price for 40kg washed potatoes?` and competitor/price-haggling cases. Likely boundary: candidate ranking/decision alternatives in `agent.py`, including fixed-price handling and “usual” preference weighting.

## `backend/app/ask.py` and `backend/app/conversation.py`

7. **Continuation state replaces a multi-item request instead of preserving it.** `I want my usual order plus some pasta` followed by `end of the week` then lost pasta; `plus milk` followed by an oat-milk change lost the held/proposed standing lines (acceptance F1/F2). The follow-up must merge the answered slot into the original request, not re-run only the latest text.

8. **A follow-up answer is misclassified as a new order/question.** `end of the week` repeated a product-choice question instead of filling the delivery date (acceptance F1). The `pending`/`supersedes`/`_primary_follow_up` path needs to distinguish a slot answer from a product change while retaining the stored request.

9. **Generic vague requests have no answerable choices or proposal fallback.** `stuff for a party of 30 on Saturday` ended with `What kind of food would you like...` and no choices/cart (acceptance F11). When intent is unclear but guest count/date are known, `_finish()` should hand off to a bounded set of kitchen options or a stated-assumption proposal.

10. **Delivery-date parsing and follow-up resolution disagree on fuzzy/typo dates.** `end of the week`, `tomorow`, `Thurs`, and `thursady delvery` can re-open `For which delivery day?` even when the chef supplied a usable day (acceptance F1; `phone-03`, `dish-event-05`, `real-orders-03`). Check `date_from_text()`, `conversation.date_answer()`, and the stored `requested` value as one contract.

11. **Bare/ambiguous unit replies are accepted without enough context.** The prior `followup-units` group was 0/9; examples include `five`, `2 kg`, `uhh maybe 10 boxes?`, and `a couple of those big jugs`. The continuation parser needs to preserve the asked unit, reject incompatible units, and expose the exact conversion/pack assumption before ordering.

## `backend/app/understand.py`

12. **Multi-item extraction drops one item or its quantity.** The 5-line order omitted the 360 free-range eggs and did not quote a total (prior edge `real-orders-04`); `real-orders-02` also dropped the explicit 25 kg flour. The structured action/request must retain every product, amount, qualifier, and delivery date through the handoff to `agent.run()`.

13. **Mixed intents are not split into an order plus a kitchen-history answer.** `Order 10 kg butter for Monday, and how many guests did we serve last Friday?` returned only the butter clarification (acceptance F5). The order should proceed while the factual kitchen question is answered, or both should be represented explicitly without losing either.

14. **Recurring/standing-order language is treated as a normal one-time order.** Prior failures include `recurring order ... every Monday morning` and `biweekly standing order ... every second Wednesday`; the agent created a normal/pending cart without explaining the one-time limitation. `understand.py` must preserve schedule intent so the front door can ask to prepare one cart instead of silently inventing automation.

## `backend/app/menu.py`, `backend/app/kitchen.py`, and `backend/app/profile.py`

15. **Kitchen-sense/menu proposals are brittle for vague parties, language variants, and profile history.** The prior baseline had 0/9 for `vague-food`, `finnish-slang`, and `other-languages`; examples include `quick pasta special`, `finger food for a staff party`, Spanish `mantequiya`, German `Donnersttag`, and the history question `What's my usual order?`. Likely seams are menu ingredient generation, kitchen/profile source precedence, and preserving stated assumptions/choices when no exact product is named.

## Suggested verification order

1. Re-run the four acceptance reproductions first: `25 kg butter`; usual order plus `pasta`; usual order plus milk then oat-milk change; and party of 30 Saturday.
2. Then sample one case from `followup-units`, `real-orders`, `price-haggling`, `plan-ahead`, `vague-food`, `finnish-slang`, and `other-languages` before trusting a new full edge score.
