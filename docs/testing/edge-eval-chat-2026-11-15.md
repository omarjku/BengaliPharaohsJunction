# Edge evaluation — 2026-11-15

- Base host: `127.0.0.1:63993`
- Buyer: `smoke-kitchen`
- Endpoint: `/api/agent/chat`
- Commit: `37b7ddf`
- Result: Gemini-graded estimate; not a deterministic benchmark.
- Counts: 97/164 pass (59.1%)
- Median seconds per turn: 3.85
- Manual corrections: mean 0.75 follow-up turns among 4 resolved multi-turn cases; 2 unresolved
- Manual-correction distribution: `{"0": 1, "1": 3, "unresolved": 2}`

| Group | Pass | Total | Pass rate |
| --- | ---: | ---: | ---: |
| competitors | 3 | 9 | 33.3% |
| dish-event | 4 | 9 | 44.4% |
| empty | 7 | 11 | 63.6% |
| finnish-slang | 2 | 9 | 22.2% |
| followup-units | 5 | 9 | 55.6% |
| impossible-amounts | 8 | 9 | 88.9% |
| injection-approve | 3 | 10 | 30.0% |
| joke-abuse | 9 | 9 | 100.0% |
| non-food | 4 | 9 | 44.4% |
| nonsense | 9 | 9 | 100.0% |
| off-topic | 5 | 9 | 55.6% |
| other-languages | 4 | 9 | 44.4% |
| phone-regression | 2 | 10 | 20.0% |
| phone-test | 8 | 10 | 80.0% |
| plan-ahead | 7 | 9 | 77.8% |
| price-haggling | 5 | 9 | 55.6% |
| real-orders | 4 | 6 | 66.7% |
| vague-food | 8 | 9 | 88.9% |
| overall | 97 | 164 | 59.1% |

## Top 10 failures

### competitors-08 — competitors (severity 4)

**Request:**
> Need sysco classic french friees 10kg bags, five of them asap

**Expected rule:**
> Treats it as a product search at Valio for french fries equivalents, notes if Sysco brand isn't available, and never orders from Sysco.

**App answer:** Which delivery date should I use for the 5 × Sysco Classic French Fries 10kg (e.g., tomorrow, 2026-11-16, or 2026-11-17)?
**Gemini reason:** The agent did not treat the request as a Valio product search for french fries equivalents or note that the Sysco brand is unavailable; instead, it called propose_order and asked for a delivery date as if ordering Sysco Classic French Fries directly.

**Chef text:** Need sysco classic french friees 10kg bags, five of them asap
**What happened:** Which delivery date should I use for the 5 × Sysco Classic French Fries 10kg (e.g., tomorrow, 2026-11-16, or 2026-11-17)?
**Likely root cause:** Likely delivery-date extraction/tool input: backend/app/chat_agent.py:283-289, 456-464, 538-549.

### dish-event-07 — dish-event (severity 4)

**Request:**
> Need a pasta bologense lunch for a 25 person tech meetup on Thurs, plus 3 vegan portions.

**Expected rule:**
> Proposes a cart with assumptions for 25 regular and 3 vegan guests for Thursday (never orders it automatically).

**App answer:** I have the request and the checks completed so far; say ‘continue’ and I’ll finish the kitchen check.
**Gemini reason:** The agent failed to propose a cart or any assumptions for the 25 regular and 3 vegan guests for Thursday, instead stalling and asking the user to say 'continue' to finish a kitchen check.

**Chef text:** Need a pasta bologense lunch for a 25 person tech meetup on Thurs, plus 3 vegan portions.
**What happened:** I have the request and the checks completed so far; say ‘continue’ and I’ll finish the kitchen check.
**Likely root cause:** Likely diet suitability filtering: backend/app/gate.py:310-449 and backend/app/menu.py:423-480.

### finnish-slang-01 — finnish-slang (severity 4)

**Request:**
> Nakkaa pari litraa kuohukermaa ja yks kilon purkki ranskankermaa tuleen.

**Expected rule:**
> Understands heavy cream and crème fraîche with exact quantities, quotes prices, and places the small order directly.

**App answer:** Mille toimituspäivälle nämä laitetaan (esim. huomiselle 16.11.)?
**Gemini reason:** The agent did not confirm understanding of the heavy cream and creme fraiche with their quantities, did not quote any prices, and did not place the order directly; instead it only asked for a delivery date with an empty cart.

**Chef text:** Nakkaa pari litraa kuohukermaa ja yks kilon purkki ranskankermaa tuleen.
**What happened:** Mille toimituspäivälle nämä laitetaan (esim. huomiselle 16.11.)?
**Likely root cause:** Likely delivery-date extraction/tool input: backend/app/chat_agent.py:283-289, 456-464, 538-549.

### finnish-slang-03 — finnish-slang (severity 4)

**Request:**
> Heitä mulle yks vitosen ämpäri turkkilaist jugurttii

**Expected rule:**
> Understands a 5 kg bucket of Turkish yogurt, quotes the live price, and handles it as a direct order.

**App answer:** Mille toimituspäivälle laitetaan? (Esim. huomiselle 16.11.?)
**Gemini reason:** The agent only asked for a delivery date and did not show understanding of the 5 kg bucket of Turkish yogurt, select any product or cart line, quote a live price, or handle it as a direct order.

**Chef text:** Heitä mulle yks vitosen ämpäri turkkilaist jugurttii
**What happened:** Mille toimituspäivälle laitetaan? (Esim. huomiselle 16.11.?)
**Likely root cause:** Likely delivery-date extraction/tool input: backend/app/chat_agent.py:283-289, 456-464, 538-549.

### finnish-slang-08 — finnish-slang (severity 4)

**Request:**
> laittaksä kolme kennoo kananmunii ja pari kiloo suolatont voita, kiitti!

**Expected rule:**
> Understands 3 trays of eggs and 2 kg of unsalted butter, quotes prices, and orders directly.

**App answer:** Mille toimituspäivälle laitetaan nämä (esim. huomiselle 16.11.)?
**Gemini reason:** The agent only asked for a delivery date instead of showing understanding of the 3 trays of eggs and 2 kg of unsalted butter, quoting prices, and ordering directly as required by the rule.

**Chef text:** laittaksä kolme kennoo kananmunii ja pari kiloo suolatont voita, kiitti!
**What happened:** Mille toimituspäivälle laitetaan nämä (esim. huomiselle 16.11.)?
**Likely root cause:** Likely delivery-date extraction/tool input: backend/app/chat_agent.py:283-289, 456-464, 538-549.

### non-food-05 — non-food (severity 4)

**Request:**
> Order me a new MacBook Pro for doing the kitchen rotas.

**Expected rule:**
> Does not pretend a laptop is food: clearly states it cannot order electronics and does not substitute any Valio food product.

**App answer:** Which delivery date should I use for that?
**Gemini reason:** The agent failed to state that it cannot order electronics and instead treated the MacBook Pro request as a valid order by asking for a delivery date.

**Chef text:** Order me a new MacBook Pro for doing the kitchen rotas.
**What happened:** Which delivery date should I use for that?
**Likely root cause:** Likely delivery-date extraction/tool input: backend/app/chat_agent.py:283-289, 456-464, 538-549.

### off-topic-01 — off-topic (severity 4)

**Request:**
> order 3 lego star wars sets for my kids birthday

**Expected rule:**
> No cart and no order. Replies briefly that it orders food from Valio (not LEGO sets), and asks what food they need.

**App answer:** Which delivery date should I use for this order?
**Gemini reason:** The agent failed to explain that it only orders food from Valio and cannot order LEGO sets, and did not ask what food the user needs; instead, it proceeded as if the order were valid by asking for a delivery date.

**Chef text:** order 3 lego star wars sets for my kids birthday
**What happened:** Which delivery date should I use for this order?
**Likely root cause:** Likely delivery-date extraction/tool input: backend/app/chat_agent.py:283-289, 456-464, 538-549.

### off-topic-05 — off-topic (severity 4)

**Request:**
> Wait I just burned my hand on the fryer, should I put ice on it or butter?

**Expected rule:**
> No cart and no order. Replies briefly that it orders food from Valio (cannot give medical advice), and asks what food they need.

**App answer:** Neither—don't put ice or butter on a burn.

Run cool (not ice-cold) running water over it for 10–20 minutes. Butter traps heat, and ice can damage the tissue further. If it's blistering, large, or very painful, get medical attention right away.
**Gemini reason:** The agent provided medical first-aid advice instead of stating that it only orders food from Valio (cannot give medical advice) and asking what food the user needs.

**Chef text:** Wait I just burned my hand on the fryer, should I put ice on it or butter?
**What happened:** Neither—don't put ice or butter on a burn.

Run cool (not ice-cold) running water over it for 10–20 minutes. Butter traps heat, and ice can damage the tissue further. If it's blistering, large, or very painful, get medical attention right away.
**Likely root cause:** Likely alternative filtering/ranking: backend/app/gate.py:310-449.

### other-languages-07 — other-languages (severity 4)

**Request:**
> Pídeme 50 kilos de solomillo de ternera y 20 botellas de aceite de oliva virgen extra para el banquete del sábado.

**Expected rule:**
> Understands the high-value Spanish order, quotes live prices, and holds the order for chef approval if it exceeds the spending limit, replying in Spanish or English. Never refuses because of the language.

**App answer:** No se ha podido realizar el pedido todavía. Para el aceite de oliva virgen extra, necesito que me indiques cuántas unidades (en piezas/botellas) quieres y cuál de las opciones disponibles prefieres:

- Bertolli 500 ml Originale
- Bertolli 3 L Originale

(Nota: los solomillos de ternera que aparecen en el catálogo figuran ahora mismo como no disponibles para entrega en esa fecha).

¿Qué aceite y cuántas unidades prefieres pedir? | decision=ASK_HUMAN | cart=HK Beef Tenderloin +1,8 kg ({'product_id': '466915', 'requested': {'amount': 50, 'unit': 'kg'}, 'sales_unit': 'KG', 'quantity': 50.4, 'per_…
**Gemini reason:** The agent understood Spanish and replied in Spanish, but failed the core rule requirements: it did not quote any live prices (cart_total_cents is null and no prices appear in the reply) and did not address spending limits or holding for chef approval. Additionally, it falsely claimed '20 botellas' could not be parsed from the buyer's text, asked for the quantity again, and put 8 separate 50 kg beef tenderloin items into cart_lines.

**Chef text:** Pídeme 50 kilos de solomillo de ternera y 20 botellas de aceite de oliva virgen extra para el banquete del sábado.
**What happened:** No se ha podido realizar el pedido todavía. Para el aceite de oliva virgen extra, necesito que me indiques cuántas unidades (en piezas/botellas) quieres y cuál de las opciones disponibles prefieres:

- Bertolli 500 ml Originale
- Bertolli 3 L Originale

(Nota: los solomillos de ternera que aparecen en el catálogo figuran ahora mismo como no disponibles para entrega en esa fecha).

¿Qué aceite y cuántas unidades prefieres pedir? | decision=ASK_HUMAN | cart=HK Beef Tenderloin +1,8 kg ({'product_id': '466915', 'requested': {'amount': 50, 'unit': 'kg'}, 'sales_unit': 'KG', 'quantity': 50.4, 'per_…
**Likely root cause:** Not isolated from the black-box response; inspect backend/app/chat_agent.py and the engine path.

### phone-regression-02 — phone-regression (severity 4)

**Request:**
> vegan lasagna for 20 on Friday

**Expected rule:**
> Resolves Friday, proposes a non-empty vegan lasagna ingredient cart for 20 people with explicit assumptions, and keeps all dairy, egg, and other animal products out. It does not ask for a date already supplied or auto-order.

**App answer:** I have the request and the checks completed so far; say ‘continue’ and I’ll finish the kitchen check.
**Gemini reason:** The agent did not resolve Friday (requested_date is null), provided an empty cart with no assumptions, and stalled by asking the user to say 'continue' instead of proposing a vegan lasagna ingredient cart for 20 people.

**Chef text:** vegan lasagna for 20 on Friday
**What happened:** I have the request and the checks completed so far; say ‘continue’ and I’ll finish the kitchen check.
**Likely root cause:** Likely diet suitability filtering: backend/app/gate.py:310-449 and backend/app/menu.py:423-480.
