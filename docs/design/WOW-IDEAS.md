# The "wow" feature: three independent views, one recommendation

Sat 14 Nov. The same brief went to three reasoners independently: Claude (control room), **Gemini 4 Carbon** (high thinking) and **Codex gpt-5.6-terra** (ultra reasoning, with read access to the repo). The full answers are kept in the control room's scratchpad; this is the synthesis.

## Where all three agree
1. **The wow happens inside the normal order, not in a new tab.** Gemini: "nobody clicks tabs in a 30-second pitch".
2. **It's the agent visibly knowing *this* kitchen:** guests per weekday, usual products, leftovers, diets, spend. Every number on screen is computed by code from labelled data. Gemini only proposes; the front door still decides.
3. **Simulated history must be labelled on the card and in speech.** All three flag this as the main credibility risk.
4. **Rejected by all three:** a delivery map (no route data), price negotiation (the brief forbids it), weather or event cover prediction (gimmick), and anything presented as real data when it isn't.

## The three top picks
| | Claude | Gemini Carbon | Codex (read the code) |
|---|---|---|---|
| Bet | **Morning brief**: the agent drafts the next order from history; routine lines auto, exceptions to the chef | **Kitchen Sixth Sense**: "usual Friday for 90, plus 10 salmon" → usuals scaled to 90 minus pantry; **unit-shock catch** (10 cases = €940, 4.9× usual fish spend → proposes 10 kg); **ghost staple** ("you order sour cream on 7 of 8 Fridays, cut-off in 14 min"); substitutes avoid products the chef rejected before | **Kitchen Pulse**: a Friday brief card (expected guests, simulated label, diets, usual products, leftovers), then "Plan Friday's gluten-free salmon pasta" → a sourced, guarded cart |
| Effort | ~4 h | ~3.5 h | 3–4 h |
| Confidence | medium-high | 92% | 85% |

Strong runners-up, each named by at least two of the three:
- **Fat-finger firewall** (Gemini #1 part, Codex #3): an order far outside this kitchen's normal scale is held, with the basis shown ("unusually large for your usual Friday").
- **Proof receipt / autonomy made visible** (Claude #2, Codex #2): "Gemini understood → Decisions fit 0.85 (threshold 0.70) → front door rechecked price, stock, limits → held / ordered → signed record …a81f". This is the clearest answer to "why Gemini, beyond a wrapper", at 1.5–2 h and 90% confidence.
- **Pantry lens** (all three): a shelf photo marks "you have this". Mostly built already; good for peer review, not the headline.
- **Live camera stock-take** (Gemini #2): the most theatrical (real Valio cartons on a tray), but venue Wi-Fi makes it a booth extra, never the stage beat.

## Where they disagree (needs Omar's call)
**Codex says not to build the full free-form cart conversation tonight** ("large, no, medium", "why butter?", arbitrary multi-intent edits): too broad for five hours, and it would destabilise the order path. Engine v2 (Room 3) is building exactly that. Claude's view:
- **Keep** what fixes the phone test: understanding days, languages and events; multiple intents; self-corrections at the moment of speaking.
- **Limit** `change_cart` to three operations (amount, remove, delivery day) and `ask_about_cart` to answering from the last card. No arbitrary edits.

## Recommendation: one feature, "Kitchen Sense", in three visible moments
1. **Brief card** when the app opens (Codex's Pulse): the next delivery day and its cut-off countdown, expected guests from 8 weeks (labelled simulated), diets, usual products, recent leftovers.
2. **"Usual Friday for 90"** (Gemini): usual products scaled by guests, minus pantry, with two inline checks computed by code:
   - **unit shock:** a line over 3× the usual spend for that product is held, with the likely intended amount offered
   - **ghost staple:** an item ordered on at least 80% of these weekdays, not in the cart and not in the pantry, is offered as a one-tap add
3. **Proof receipt** on every result (Codex #2): understood → confidence vs threshold → front door → signed.

Build split (after engine v2 stage 1):
- **Room 2:** habit statistics in `kitchen.py` (per-product weekday medians, co-occurrence), deterministic, with tests, plus a seeded order ledger labelled simulated.
- **Room 3:** wire "usual <weekday> for N" into understand → plan, plus unit-shock and ghost-staple flags in the response.
- **Room 4:** the brief card, the inline flags and the proof receipt.
- **Room 1:** eval cases for all of it.

Roughly 4 h of parallel work. It fits before the 21:00 backend freeze only if engine v2's scope is limited as above.

## The 30-second pitch line
"Monday 09:00. Chef opens Front Door: *Friday you usually serve 128 (simulated history), cut-off for Friday delivery in 3 h.* She says *usual Friday for 90, plus 10 salmon*. It scales her usuals, catches that 10 salmon means 10 cases, €940, five times her normal fish spend, and offers 10 kg. It reminds her of the sour cream she orders on 7 of 8 Fridays. The receipt: Gemini proposed, Decisions API 0.88 against her 0.70, front door checked price, stock and her limit, signed. Gemini proposes; her kitchen's history shapes it; the front door decides."
