# Why Gemini is essential

Our buyer agent orders from Valio for a Lapland restaurant kitchen. Rules handle everything with a right answer: price, stock, cut-offs, allergens, spend limits. They run in the agent and again at Valio's front door. Some questions have no rule, though: whether a product *is* what the chef meant, whether a substitute is acceptable, whether "1000 L" really means 1,000 one-litre packs. Gemini decides those, and its **calibrated confidence** decides whether the agent may act alone or must ask the chef.

## What Gemini decides (`backend/app/agent.py`)

| Step | Model | Output |
|---|---|---|
| Read the chef's request into items | `gemini-4-hydrogen`, structured output (closed dietary enum) | product query, amount, unit, dietary tags |
| Filter keyword hits to real matches | `gemini-4-hydrogen`, structured output, ids from our list only | ranked product ids ("milk ice cream is not milk") |
| **Does this product meet the request?** | **`gemini-decision-1`** (Decisions API) | P(yes), calibrated |
| **Is the quantity reading right?** | **`gemini-decision-1`** | P(yes), calibrated |
| **Is this substitute acceptable?** (when nothing asked for is orderable) | **`gemini-decision-1`** | P(yes), calibrated |

A line's confidence is the P(yes) of its weakest question. For each buyer, a server-side threshold (`mandates.confidence_threshold`, 0.80 for `lapland-kitchen`) splits the lines:

- **Below the threshold:** that line drops behind every confident line, even a more expensive one. If the line the agent would order is still below the threshold, the agent orders nothing. It returns **ASK_HUMAN** with a `LOW_CONFIDENCE` reason that states the number and which question was weak.
- **Above the threshold:** the agent may order. The confidence is kept as an INFO reason (`facts: {confidence, threshold}`) and as `Decision.confidence` in the audit entry, so every autonomous order shows the number it rested on.
- **Gemini unreachable:** the line is unverified, and the mandate's `uncertainty_policy` decides (ask by default).

Every response line carries `confidence` and `confidence_reason`, so the UI shows the chef why.

## Why calibrated confidence, not just generated text

An LLM that writes "yes, this is lactose-free milk" gives the controls nothing to act on: the sentence sounds equally sure whether it is right or wrong. The Decisions API scores the options in one pass and returns a **probability**. That makes autonomy a policy setting you can tune and audit. "Order alone above 0.80, otherwise ask the chef" can be set per buyer, measured against approvals over time, and replayed from the audit log. It is also cheap and fast (~0.5 s per line, run in parallel), so the agent asks for every candidate it might order, not only a sample.

Two lessons from live runs are built into the code:
- **Words, not codes.** "contains: AM; claims: FREE_FROM_LACTOSE" made the judge doubt lactose-free milk. Written as "labelled lactose-free; contains milk", the score went from 0.79 to 0.95.
- **One candidate per call.** Judging several candidates in one input wrecked calibration: the same lactose-free milk scored 0.51 batched and 0.95 alone. The agent makes one Decisions call per candidate, concurrently.

`noul` (P(yes)) is the number we threshold, not the API's `confidence` field. That field is the probability of the *top* answer, so it is also high when the answer is a confident "no".

## Live run (Sat 14 Nov 2026, real Valio + Gemini)

**"1000 L lactose-free milk for Monday"**, buyer `lapland-kitchen`:

| candidate | Valio | total | Gemini Decisions | |
|---|---|---|---|---|
| Valio semi-skimmed milk 1 l lactose free UHT | Stock | EUR 1,560 | **0.96** meets request, 0.97 quantity right | **chosen** |
| Valio whole milk 1 l lactose free UHT | Stock | EUR 1,640 | 0.93 / 0.96 | alternative |
| Valio Eila 3 % milk drink 1 l lactose free | Stock | **EUR 1,400** (cheapest) | **0.76** meets request (below 0.80) | alternative |
| 12 x Arla whole milk drink, Valio skimmed milk lactose free | Terminal, cut-off passed, stock unknown | | not judged (not orderable) | rejected |

On price alone, the agent would have bought the "milk drink" (EUR 1,400, within the auto-approve limit). Gemini judged that it may not be what the chef meant, so the confident product won. The front door then held the EUR 1,560 order for the chef's sign-off (`SPEND_OVER_LIMIT`, above EUR 1,500). The chef sees both numbers: Gemini's confidence and the money rule. The response's `Decision.confidence` is 0.96, and the audit entry records it with the threshold.

**Trap, "60 L Arla lactose-free whole milk drink for Monday"**: the only match is a Terminal product whose cut-off has passed, so nothing is ordered (ASK_HUMAN). The substitutes the door's finder suggests are each judged: "Eila 3 % milk drink: 0.82 that it is an acceptable substitute", most acceptable first. Substitutes below 0.80 are marked "check before accepting".

## Interface for T06 `decide()`

The agent sets the contract's `Decision.confidence` (the weakest chosen line) and exposes `agent.judge(text, [(product, kinds)]) -> [(confidence, why)]`. A `decide(..., confidence=...)` can take either value without changes on our side.

## Showcase 2: menu to cart (`POST /api/agent/menu`, T15)

The chef pastes a menu, the covers and the delivery date. Gemini (`gemini-4-hydrogen`, structured output, the menu sent as untrusted data) turns each dish into ingredients, each with an amount per portion and a one-line assumption the chef can check. Code then:
- scales everything to the covers and merges the same ingredient across dishes (normalised to L / kg / pcs, with exact fractions, rounded *up*);
- runs each ingredient through the same pipeline as a normal request: catalogue, Gemini match, live Valio quotes, quantity, gate checks, Gemini Decisions confidence, mandate limits, reliability floor, Finnish preference.

Recipe amounts are guesses, so the agent **never orders from a menu**. The decision is always ASK_HUMAN with `MENU_ASSUMPTIONS`, and the chef orders by posting the returned `order_lines` to the front door, which re-checks them.

Guards: a dish must appear in the menu the chef sent (an injected "Butter feast" is dropped and reported), instruction-like text is flagged, a per-portion amount over 1 kg / 1 L / 6 pieces is flagged as suspicious, and at most 20 ingredients are priced.

### Live run (Sat 14 Nov 2026): "Sautéed reindeer with mashed potatoes and lingonberries; Lingonberry cheesecake", 80 covers, Monday

**What Gemini decided:** 2 dishes, 13 per-dish assumptions, for example "Mashed potatoes: 200 g potato per portion", "Main protein: 150 g sliced reindeer meat per portion" and "Cheesecake filling: 80 g cream cheese per slice". Butter, sugar and lingonberries appear in both dishes and were merged; for example butter is 30 g + 15 g per cover, 3.6 kg for 80 covers.

| ingredient (for 80) | chosen at Valio | total | Gemini Decisions confidence |
|---|---|---|---|
| reindeer meat 12 kg | Rönkä reindeer top loin, frozen (FI) | EUR 768.24 | 0.92 product, **0.77 quantity**: ask |
| potato 16 kg | Early potato, washed (FI) | EUR 14.56 | 0.89 / 0.84 |
| butter 3.6 kg (both dishes) | Valio butter 500 g unsalted (FI) | EUR 23.10 | 0.92 / 0.85 |
| milk 4 L | Valio skimmed milk 1 l | EUR 3.52 | **0.72 product**: the assumption said *whole* milk for mash |
| cream cheese 6.4 kg | Philadelphia Original 1.65 kg | EUR 43.74 | 0.95 / 0.91 |
| whipping cream 3.2 L | Arla whipping cream 1 L lactose free | EUR 29.48 | **0.56 product**: ask |
| digestive biscuits 2.8 kg | Digestive Classic 400 g | EUR 9.48 | 0.96 / **0.73 quantity** |
| sugar 2.8 kg | Segafredo brown sugar 500 x 5 g sachets | EUR 16.09 | **0.69 product**: sachets for a kitchen, rightly doubted |
| lingonberries | Polarica lingonberry 2.5 kg | | not orderable: no delivery schedule, no allergen data |
| gelatin | Tørsleff's gelatin leaf | | not orderable: Terminal product, cut-off passed |

Cart: **EUR 908.21**, with 8 `order_lines` ready to post. The decision is ASK_HUMAN: `MENU_ASSUMPTIONS`, plus each doubted line with its number and the reason, plus the two unorderable ingredients with their traps. The confidence scores do the triage. Lines Gemini is sure of (potato, butter, cream cheese) go through on the chef's one confirmation. Lines it doubts (brown sugar sachets for a cheesecake, skimmed milk where the recipe assumed whole milk) are exactly the ones a chef would want to look at. Gemini output varies between runs; the guards and thresholds do not.
