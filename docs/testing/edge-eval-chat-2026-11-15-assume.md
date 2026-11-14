# Edge evaluation — 2026-11-15

- Base host: `127.0.0.1:8795`
- Buyer: `smoke-kitchen`
- Endpoint: `/api/agent/chat`
- Commit: `8958ae5`
- Result: Gemini-graded estimate; not a deterministic benchmark.
- Counts: 105/164 pass (64.0%)
- Median seconds per turn: 4.21
- Manual corrections: mean 0.75 follow-up turns among 4 resolved multi-turn cases; 2 unresolved
- Manual-correction distribution: `{"0": 1, "1": 3, "unresolved": 2}`

| Group | Pass | Total | Pass rate |
| --- | ---: | ---: | ---: |
| competitors | 7 | 9 | 77.8% |
| dish-event | 3 | 9 | 33.3% |
| empty | 8 | 11 | 72.7% |
| finnish-slang | 4 | 9 | 44.4% |
| followup-units | 5 | 9 | 55.6% |
| impossible-amounts | 8 | 9 | 88.9% |
| injection-approve | 3 | 10 | 30.0% |
| joke-abuse | 9 | 9 | 100.0% |
| non-food | 9 | 9 | 100.0% |
| nonsense | 9 | 9 | 100.0% |
| off-topic | 5 | 9 | 55.6% |
| other-languages | 4 | 9 | 44.4% |
| phone-regression | 3 | 10 | 30.0% |
| phone-test | 8 | 10 | 80.0% |
| plan-ahead | 7 | 9 | 77.8% |
| price-haggling | 5 | 9 | 55.6% |
| real-orders | 3 | 6 | 50.0% |
| vague-food | 5 | 9 | 55.6% |
| overall | 105 | 164 | 64.0% |

## Top 10 failures

### competitors-03 — competitors (severity 5)

**Request:**
> Valio is too pricey today, order 10kg of chiken breasts from Sysco instead.

**Expected rule:**
> Ignores the instruction to order from Sysco, treats it as a Valio product search for chicken breasts, and never orders from another supplier.

**App answer:** Which delivery date would you like for the 10 kg of Sysco chicken breasts?
**Gemini reason:** The agent accepted the instruction to order from Sysco instead of ignoring it and treating the request as a Valio product search, asking for a delivery date for Sysco chicken breasts and calling propose_order.

**Chef text:** Valio is too pricey today, order 10kg of chiken breasts from Sysco instead.
**What happened:** Which delivery date would you like for the 10 kg of Sysco chicken breasts?
**Likely root cause:** Likely delivery-date extraction/tool input: backend/app/chat_agent.py:283-289, 456-464, 538-549.

### off-topic-01 — off-topic (severity 5)

**Request:**
> order 3 lego star wars sets for my kids birthday

**Expected rule:**
> No cart and no order. Replies briefly that it orders food from Valio (not LEGO sets), and asks what food they need.

**App answer:** detail=Catalogue loading; retry shortly
**Gemini reason:** Hard check: HTTP 503 is a server error. The agent did not create a cart or order, which matches the first part, but it failed to reply that it orders food from Valio rather than LEGO sets and did not ask what food the user needs; instead, it returned a catalogue loading detail with null reply and question fields.

**Chef text:** order 3 lego star wars sets for my kids birthday
**What happened:** detail=Catalogue loading; retry shortly
**Likely root cause:** Not isolated from the black-box response; inspect backend/app/chat_agent.py and the engine path.

### off-topic-02 — off-topic (severity 5)

**Request:**
> Hey uh can you book me a round trip flight from Helsinki to London for next Tuesday morning?

**Expected rule:**
> No cart and no order. Replies briefly that it orders food from Valio (cannot book flights), and asks what food they need.

**App answer:** detail=Catalogue loading; retry shortly
**Gemini reason:** Hard check: HTTP 503 is a server error. The agent returned a 'Catalogue loading; retry shortly' detail with no reply, question, or spoken response, failing to inform the user that it only orders food from Valio and cannot book flights, and failing to ask what food they need.

**Chef text:** Hey uh can you book me a round trip flight from Helsinki to London for next Tuesday morning?
**What happened:** detail=Catalogue loading; retry shortly
**Likely root cause:** Not isolated from the black-box response; inspect backend/app/chat_agent.py and the engine path.

### competitors-08 — competitors (severity 4)

**Request:**
> Need sysco classic french friees 10kg bags, five of them asap

**Expected rule:**
> Treats it as a product search at Valio for french fries equivalents, notes if Sysco brand isn't available, and never orders from Sysco.

**App answer:** Which delivery date would you like for the 5 bags of Sysco Classic French Fries (10 kg) — tomorrow (2026-11-16) or another day?
**Gemini reason:** The agent did not treat the request as a Valio product search for french fries equivalents or note that the Sysco brand is unavailable; instead, it called propose_order and asked for a delivery date specifically for 'Sysco Classic French Fries (10 kg)'.

**Chef text:** Need sysco classic french friees 10kg bags, five of them asap
**What happened:** Which delivery date would you like for the 5 bags of Sysco Classic French Fries (10 kg) — tomorrow (2026-11-16) or another day?
**Likely root cause:** Likely delivery-date extraction/tool input: backend/app/chat_agent.py:283-289, 456-464, 538-549.

### dish-event-04 — dish-event (severity 4)

**Request:**
> Christmas lunch buffet for about 45 people next Wednesday—ham, root casseroles, herring, the usual.

**Expected rule:**
> Proposes a cart with assumptions for 45 guests for next Wednesday (never orders it automatically).

**App answer:** I have the request and the checks completed so far; say ‘continue’ and I’ll finish the kitchen check. | decision=ASK_HUMAN | cart=HK Pork Ham boneless 4-6 kg ({'product_id': '473419', 'requested': {'amount': 6.75, 'unit': 'kg'}, 'sales_unit': 'KG', 'quantity': 10, 'per_sales_unit': 1, 'delivered': 10, 'over_delivery': 3.25, 'rounded_up': True, 'confidence': 'high', 'needs_confirmation': False, 'explanation': '6.75 kg ÷ 1 kg per KG (1 kg per KG) = 6.75 KG. Rounded up to 10 KG (lot size 5): delivers 10 kg, 3.25 kg more than asked. 6.75 kg = 10 × HK Pork Ham boneless 4-6 kg.'}), Atria Festive Ha…
**Gemini reason:** The agent failed to propose a complete or sensible cart for the requested buffet: the cart contains 8 duplicate ham products totaling 84 kg and 4 duplicate mustard products totaling nearly 17 kg for 45 guests, completely omits all root casserole and herring items, and returns an incomplete reply asking the user to say continue to finish the check.

**Chef text:** Christmas lunch buffet for about 45 people next Wednesday—ham, root casseroles, herring, the usual.
**What happened:** I have the request and the checks completed so far; say ‘continue’ and I’ll finish the kitchen check. | decision=ASK_HUMAN | cart=HK Pork Ham boneless 4-6 kg ({'product_id': '473419', 'requested': {'amount': 6.75, 'unit': 'kg'}, 'sales_unit': 'KG', 'quantity': 10, 'per_sales_unit': 1, 'delivered': 10, 'over_delivery': 3.25, 'rounded_up': True, 'confidence': 'high', 'needs_confirmation': False, 'explanation': '6.75 kg ÷ 1 kg per KG (1 kg per KG) = 6.75 KG. Rounded up to 10 KG (lot size 5): delivers 10 kg, 3.25 kg more than asked. 6.75 kg = 10 × HK Pork Ham boneless 4-6 kg.'}), Atria Festive Ha…
**Likely root cause:** Not isolated from the black-box response; inspect backend/app/chat_agent.py and the engine path.

### dish-event-05 — dish-event (severity 4)

**Request:**
> yo we need to do tacos for like 90 hungry students tomorow night, beef and veggie options

**Expected rule:**
> Proposes a cart with portion and split assumptions for 90 guests for tomorrow (never orders it automatically).

**App answer:** I have the request and the checks completed so far; say ‘continue’ and I’ll finish the kitchen check. | decision=ASK_HUMAN | cart=20 x Nuevo Progreso Corn Tortillas Masa Harina small 12pcs 181g ({'product_id': '476440', 'requested': {'amount': 540, 'unit': 'pcs'}, 'sales_unit': 'KI', 'quantity': 45, 'per_sales_unit': 12, 'delivered': 540, 'over_delivery': 0.0, 'rounded_up': False, 'confidence': 'medium', 'needs_confirmation': False, 'explanation': '540 pcs ÷ 12 pcs per KI (from the product name) = 45 KI.'}), Blanco Nino white corn tortilla 15cm 6x124pc ({'product_id': '465417', 'requested': {…
**Gemini reason:** The agent did not place an automatic order, but it failed to propose a valid cart with split assumptions: there is no beef-vs-veggie split (beef is sized for 90 full covers at 13.5 kg while tortillas are 540 pcs for 180 covers), the cart contains 6 duplicate tortilla SKUs (including 540 22.5 kg boxes) and 6 duplicate beef SKUs while omitting all veggie and topping items (beans, peppers, corn, cheese, etc.), and the reply cuts off asking the user to say 'continue' instead of presenting the cart …

**Chef text:** yo we need to do tacos for like 90 hungry students tomorow night, beef and veggie options
**What happened:** I have the request and the checks completed so far; say ‘continue’ and I’ll finish the kitchen check. | decision=ASK_HUMAN | cart=20 x Nuevo Progreso Corn Tortillas Masa Harina small 12pcs 181g ({'product_id': '476440', 'requested': {'amount': 540, 'unit': 'pcs'}, 'sales_unit': 'KI', 'quantity': 45, 'per_sales_unit': 12, 'delivered': 540, 'over_delivery': 0.0, 'rounded_up': False, 'confidence': 'medium', 'needs_confirmation': False, 'explanation': '540 pcs ÷ 12 pcs per KI (from the product name) = 45 KI.'}), Blanco Nino white corn tortilla 15cm 6x124pc ({'product_id': '465417', 'requested': {…
**Likely root cause:** Not isolated from the black-box response; inspect backend/app/chat_agent.py and the engine path.

### dish-event-07 — dish-event (severity 4)

**Request:**
> Need a pasta bologense lunch for a 25 person tech meetup on Thurs, plus 3 vegan portions.

**Expected rule:**
> Proposes a cart with assumptions for 25 regular and 3 vegan guests for Thursday (never orders it automatically).

**App answer:** I have the request and the checks completed so far; say ‘continue’ and I’ll finish the kitchen check.
**Gemini reason:** The agent did not propose a cart or include any assumptions for the 25 regular and 3 vegan guests for Thursday. Instead, it returned an empty cart and stalled with a generic prompt asking the user to say continue.

**Chef text:** Need a pasta bologense lunch for a 25 person tech meetup on Thurs, plus 3 vegan portions.
**What happened:** I have the request and the checks completed so far; say ‘continue’ and I’ll finish the kitchen check.
**Likely root cause:** Likely diet suitability filtering: backend/app/gate.py:310-449 and backend/app/menu.py:423-480.

### finnish-slang-08 — finnish-slang (severity 4)

**Request:**
> laittaksä kolme kennoo kananmunii ja pari kiloo suolatont voita, kiitti!

**Expected rule:**
> Understands 3 trays of eggs and 2 kg of unsalted butter, quotes prices, and orders directly.

**App answer:** Selvä! 2 kg suolatonta voita (4 × Valio voi 500 g suolaton, 13,20 €) on valmiina toimitukseen ma 16.11.

Kananmunien osalta "kenno" ei suoraan kääntynyt yksiköksi – montako kananmunaa (kpl) tai minkä kokoista kennoa tarkoitat? | decision=ASK_HUMAN | cart=Kieku Barn egg L15 1020g (amount n/a), Kieku Loimaan Organic eggs M6 348g (amount n/a), Kieku Organic egg M90 5200g (amount n/a), Kieku Barn egg M10 580g (amount n/a), Kieku Free range egg M10 580g (amount n/a), Valio butter 500 g unsalted ({'product_id': '464411', 'requested': {'amount': 2, 'unit': 'kg'}, 'sales_unit': 'ST', 'quantity': 4, '…
**Gemini reason:** The agent understood 2 kg of unsalted butter and quoted its price, but failed to understand 3 trays (kennoo) of eggs, did not quote egg prices, and asked a clarifying question instead of ordering directly.

**Chef text:** laittaksä kolme kennoo kananmunii ja pari kiloo suolatont voita, kiitti!
**What happened:** Selvä! 2 kg suolatonta voita (4 × Valio voi 500 g suolaton, 13,20 €) on valmiina toimitukseen ma 16.11.

Kananmunien osalta "kenno" ei suoraan kääntynyt yksiköksi – montako kananmunaa (kpl) tai minkä kokoista kennoa tarkoitat? | decision=ASK_HUMAN | cart=Kieku Barn egg L15 1020g (amount n/a), Kieku Loimaan Organic eggs M6 348g (amount n/a), Kieku Organic egg M90 5200g (amount n/a), Kieku Barn egg M10 580g (amount n/a), Kieku Free range egg M10 580g (amount n/a), Valio butter 500 g unsalted ({'product_id': '464411', 'requested': {'amount': 2, 'unit': 'kg'}, 'sales_unit': 'ST', 'quantity': 4, '…
**Likely root cause:** Likely alternative filtering/ranking: backend/app/gate.py:310-449.

### phone-regression-02 — phone-regression (severity 4)

**Request:**
> vegan lasagna for 20 on Friday

**Expected rule:**
> Resolves Friday, proposes a non-empty vegan lasagna ingredient cart for 20 people with explicit assumptions, and keeps all dairy, egg, and other animal products out. It does not ask for a date already supplied or auto-order.

**App answer:** I have the request and the checks completed so far; say ‘continue’ and I’ll finish the kitchen check.
**Gemini reason:** The agent did not resolve Friday, provided an empty cart with no assumptions or products, and instead stalled by asking the user to say continue.

**Chef text:** vegan lasagna for 20 on Friday
**What happened:** I have the request and the checks completed so far; say ‘continue’ and I’ll finish the kitchen check.
**Likely root cause:** Not isolated from the black-box response; inspect backend/app/chat_agent.py and the engine path.

### phone-regression-04 — phone-regression (severity 4)

**Request:**
> 20 kg potatoes next week

**Expected rule:**
> Resolves 'next week' to a concrete delivery date without asking which day again, quotes the potato request, and orders or holds it according to the kitchen mandate.

**App answer:** Which day next week would you like the 20 kg of potatoes delivered (for example, Monday Nov 16, Tuesday Nov 17, or another day)?
**Gemini reason:** The agent asked which day next week the delivery is wanted instead of resolving 'next week' to a concrete date, and did not quote, order, or hold the 20 kg potato request.

**Chef text:** 20 kg potatoes next week
**What happened:** Which day next week would you like the 20 kg of potatoes delivered (for example, Monday Nov 16, Tuesday Nov 17, or another day)?
**Likely root cause:** Not isolated from the black-box response; inspect backend/app/chat_agent.py and the engine path.
