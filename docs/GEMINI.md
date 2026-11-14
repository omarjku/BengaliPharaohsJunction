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
