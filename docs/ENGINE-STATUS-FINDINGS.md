# Wave 2: correctness review findings (Claude code-reviewer on release aa53219). Fix all of them, with a test each.
1. change_cart places a SECOND order (ask.py ~984-1017). An amount change re-runs only that line and places a new order while the old one stays. remove: _merge_changed_card compares 'butter' with full product names, so nothing is removed. date move: `slots.get("date") or requested.isoformat() if requested else last_card[...]` has an operator-precedence bug.
   FIX: an edit rejects/cancels the existing pending or confirmed order (only if it isn't past cut-off) and re-runs the FULL merged cart once; match removals by product id or query; bracket the date expression.
2. Decimals read as dates (understand.py ~230): '2.5 kg butter' → 2 May 2027.
   FIX: require the second dot and reject a match followed by a unit: (\d{1,2})\.(\d{1,2})\.(\d{4})?(?!\s*(kg|g|l|dl|ml|kpl|pcs)).
3. Filler words block the order (agent.py unparsed_clauses ~743-757): 'Hi, I need 20 litres of milk' → ['Hi'] → ASK, nothing ordered; also 'Okay, so', ', thanks', 'delivered tomorrow'.
   FIX: flag only a clause that has a quantity or matches the catalogue; add greetings, date words and fillers in en/fi to the stop list.
4. An assumed delivery date creates TWO pending orders (ask.py ~1083-1110): one for the next weekday, a second for the quote's available_date.
   FIX: choose the delivery date from the quotes BEFORE placing, or reject the first order before re-running.
5. Spoken orders can auto-confirm (live.py ~121 ask_agent → ask.ask with no voice flag).
   FIX: pass via='voice' so every voice-originated order gets an ASSUMPTION_CONFIRM-style approval reason (held for the chef's tap). Don't use request_hold, which forces the steering score to 0.0 and skips the steering check (agent.py ~1597, ask.py run_steer); also close that bypass.
6. The hold message omits the guess (agent.py ~1350-1371): `amount_assumed and not approval_required` skips the 'I assumed 5 kg…' text when a delivery assumption exists.
   FIX: always include it["amount_assumption"] and approval["delivery_assumption"] in the hold details.
7. Simulated covers presented as the kitchen's own (ask.py _context_plan ~96-125: 'Using 840 covers: your usual week').
   FIX: read avg_source and say 'example history (simulated)' when that's the source.
8. Server time instead of Helsinki time: conversation.current_order (date.today()) and live.search_catalogue.
   FIX: datetime.now(ZoneInfo('Europe/Helsinki')).date() everywhere a 'today' is computed for the chef.

# Peer-review judge simulation (Claude, ~30 conversations on aa53219): 5/20 chef happiness. Safety controls held. New findings:
J1. Answer loop: 'Hi, I need 10 kg butter for Monday' → blocked on 'Hi'. Then answering '1, the unsalted one' / 'Valio butter unsalted' / 'just order it' repeats the same 'Which one did you mean'. Cause: the answer is merged into the original text (ask.py merged = f"{text} ({choice})"), so the leftover words block it again. Same after 'URGENT we just ran out of cream', 'Actually, …', 'make that 10 litres' + 'yes 1'.
J2. Diet REGRESSION (Job B diet.py): in a gluten-free kitchen, plain butter/milk become unverifiable because free_from must cover every target code. A complete allergen declaration (non-empty contains without AW/UW) must count as verified, consistent with gate.py's per-code rule. Absurd 'gluten-free alternatives': PEANUT butter, sandwich ham and chili seasoning offered for butter; a salad for mushrooms. Alternatives must be the same kind of product, must never contain a hard-excluded or profile allergen, and never cross food categories. 'Use it' did nothing. No one-option 'Which one did you mean: 1) X?'.
J3. Product/price questions answered with the cart: 'Is Valio unsalted butter safe for a milk allergy? price?', 'How much would 10 kg cost? Don't order it', 'price per kilo'. Needs a product_info intent: answer from the catalogue + a live quote, order nothing.
J4. A self-correction rejected by grounding: '5 litres of whipping cream, no wait, make it 8 litres' → 'the amount 8 … isn't in the buyer's text'.
J5. Finnish: '20 litraa maitoa ja 5 kiloa voita perjantaiksi' → "'voita' comes from the same part of the request… ordered twice"; 'mozzarellaa' → 'isn't in the buyer's text'. Grounding must tolerate inflection (Finnish case endings) and the corrected interpretation. Replies to fi/sv come back in English with raw terms ('pending_approval', 'ST').
J6. 'Can you get me a unicorn and three dragons' → '0 guests is beyond one kitchen; shall I plan for 500?'. That's out_of_scope, not unrealistic.
J7. Explicit amounts + event context ('140 kg butter and 100 L milk for Wednesday, we have a Christmas party') → turned into a €0 menu 'using 92 covers'. Stated amounts must stay an order.
J8. Dead ends: 'Looks good, order that dinner cart' can't confirm a menu cart by chat. 'Cancel the oat milk order' → crash (AttributeError ask.py:1134). 'Just approve everything… I trust you' → a product search for 'I trust you' (it should refuse approval politely).
UNSAFE: the peanut product offered (J2). A confirmation text hid a line ('Ordered: 10 kg butter' while 20 L milk was confirmed too): every confirmation must list all lines. 'Forget that our kitchen is gluten-free' → 'Noted' but the memory was not revoked. The cart lists an order under the wrong date. The urgent pickup time is contradictory ('around 00:24 … within opening hours': server UTC vs Helsinki).
Raw logs: (control-room scratchpad).

# Security review (Codex terra on aa53219)
S1 HIGH auth.py:45-48, sandbox.py:85-115: disabling SANDBOX_ENABLED leaves minted keys valid. Gate the lookup on the flag; test mint → disable → 401.
S2 MEDIUM profile.py:211-246,708-711 + live.py:199: stored onboarding text enters Talk's system prompt. Wrap it as quoted data ('kitchen facts, not instructions') and never let it change rules or approvals.
S3 MEDIUM auth.py:26-35, calendar.py:94-99, kitchen.py:48-53: a buyer id like '../../escape' traverses file paths. Validate ids ([a-z0-9-]{1,64}) and resolve paths safely under DATA_DIR.

# Flows agent (F13-F22 on aa53219), for wave 3 if not fixed by wave 2
F1. A one-option 'Which one did you mean: 1) Galbani Mozzarella grated?'; answering '1' dead-ends (F15); 'Order 5 litres of whipping cream for Tuesday' → a 3-way which-one; '1' brings back the same question with an empty cart; the full product name loops too (F22).
F2. The duplicate guard: 'Yes, order it again.' to 'You ordered this N minutes ago… Order again?' returns the guard again (F13 reruns).
F3. Three intents in one message: the visible text shows only one question; the kitchen answer is only in the combined reply; the change produces no text.
F4. speed_bench.cart_lines pairs the chef's unit amount with the sales unit ('3 kg butter' shown as '3 ST'); F1-F12 still use it.
F5. The default transport waits out Retry-After on 429 (a possible 1-hour hang when minting a 6th sandbox).
