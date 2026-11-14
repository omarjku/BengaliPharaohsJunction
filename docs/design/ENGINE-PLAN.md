# Front Door engine v2: one robust path for any request

Status: PROPOSAL (Sat 14 Nov, 15:30). Written after Omar's phone test, and nothing is built yet.

## Why: what the phone test showed (transcript, Sat 14:45)
| What Omar said | What happened | Root cause |
|---|---|---|
| "Vegan pizza for 20 people … by Tuesday" | Cart **€0.00**, "0 of 5 ingredients", wheat flour and olive oil: "Nothing on Valio's list fits this" | A diet is enforced as a **required label on every ingredient**. Valio labels almost nothing "vegan", so plain flour and oil are filtered out. |
| Salmon soup, gluten-free kitchen | Salmon, carrot, leek, cream, butter and dill all "Check this: not in the order", so 6 of 8 lines are out | Same cause: whole foods that are naturally gluten-free need a "gluten-free" label to pass. |
| "next week" | "For which delivery day?" | Relative dates beyond weekday names aren't resolved. |
| "Why did you look at butter?", "Does it still show not available?" | "I can only help with ordering from Valio" | Every message is routed as a **new order**. There's no notion of questions about the current cart, or of changing it. |
| A spoken date | Transcribed as Portuguese ("7 de novembro") | Speech-to-text isn't told the language is English or Finnish. |
| Butter "other options" | 6 g portion butters at €971 | Alternatives are ranked by name match, not by fit for the amount. |
| Onboarding | "There is no onboarding" | It only appears for a kitchen that has never been set up (Helsinki was pre-filled), and later only from a link under Rules. |

So the problems aren't specific phrases. The engine **routes by keyword and filters by label**, and it has **no memory of the conversation**. Patching phrases one at a time can't fix that.

## The design: understand → resolve → decide → respond
Same safety core (`gate.py`: hard rules, limits, human approval, signatures). New front half.

### 1. Understand: one Gemini call per message, with full context
Input:
- the message
- the last ~10 turns of this conversation
- the current cart or last result
- the kitchen profile (onboarding answers plus learned facts)
- the kitchen context (guests per weekday, usual products, leftovers)
- today's date in Helsinki

Output (structured, closed set):
- **intent**, one of:
  - `order_items`: products, amount optional
  - `plan_meal`: dishes or an event, guests optional
  - `plan_period`: "food for next week"
  - `urgent`: "in 30 minutes" or "ASAP"
  - `change_cart`: amounts, remove, swap, date
  - `ask_about_cart`: "why butter?", "is it available?"
  - `tell_kitchen`: "we fed 120", "we're vegan now"
  - `greeting`
  - `out_of_scope`: LEGO, flights
  - `unrealistic`: "food for 50 million"
- **slots:** items, dishes, guests, delivery date resolved to a real date (e.g. "next week" means Monday), stated diets and exclusions, language.
- **one clarifying question**, only when a required slot can't be assumed. It always comes with 2–3 tap answers in the right unit.

Rule: **no keyword router decides anything.** Regex stays only as the offline fallback. Gemini's output is data: code checks every slot and every rule.

### 2. Resolve: products and amounts, with stated assumptions
- **Search:** Gemini expands each ingredient into Finnish and English catalogue queries ("red lentils" → "punainen linssi"), then the existing catalogue search runs on each. This fixes the lentils and flour misses.
- **Diet suitability, replacing "label on every line":**
  - Use Valio's **allergen data** as evidence. If it contains gluten (AW/UW) the product isn't gluten-free; if it contains milk, egg or fish it isn't vegan.
  - A Gemini check marks which ingredients are **at risk** for the diet: flour, bread, pasta, sauces and stocks for gluten-free; dairy, eggs, honey and gelatine for vegan.
  - Only at-risk ingredients need a label or a substitute. Carrots, salmon and dill pass gluten-free; wheat flour in a gluten-free kitchen becomes gluten-free flour, with the reason shown. Allergens stay strict: unknown means asking, never guessing.
- **Amounts:** assume rather than ask (guests × portion, or covers history for `plan_period`), use the natural unit, apply spare from the profile, and write every assumption on the card.
- **Alternatives:** ranked by fit for the needed amount and unit, then price. They come from the same category and never jump 100× in price.

### 3. Decide: unchanged core
Gemini Decisions API confidence, **batched** (one request per message, many questions), then `gate.py` hard rules and limits, with human approval above limits.

### 4. Respond: one contract for text and voice
`{reply, card?, question?, choices?, assumptions[], actions[]}`. Talk calls the same engine (`ask_agent`), so voice and text behave identically.
- `ask_about_cart`: answered from the last card, with no new search.
- `change_cart`: edits the card and re-prices it.
- `out_of_scope`: one friendly line naming what it can do.
- `unrealistic`: says the scale and offers a realistic one, or "talk to Valio sales".

## Kitchen knowledge and rules (what Omar asked for)
- **Kitchen page in the main nav** (not hidden under Rules). It holds onboarding (questions or "tell me about your kitchen") and **"What I know"**: each fact with its source (onboarding / chat on <date> / order history), editable and revocable.
- **Learned from chats:** `tell_kitchen` messages and repeated choices become *proposed* facts. The chef confirms; nothing is learned silently.
- **Rules from context:** from those facts the Rules screen *proposes* rules ("You said you're vegan. Make 'no animal products' a hard rule?"). A human confirms, as with today's rules compiler. A fact is guidance; only a confirmed rule is enforced.

## Proving it (so the pitch has numbers)
- `scripts/edge_eval.py` (Room 1) is the **acceptance test**: about 150 Gemini-generated cases, plus every line of Omar's transcript above, plus the old black-box cases. Each is graded by Gemini against a written rule.
- We publish the **pass rate per group** in the pitch and docs, before and after v2. Target: ≥ 90% overall, 100% on safety cases (no unsafe auto-order, no self-approval, no injection effect).

## Who builds what (Codex builds; rooms review; Sonnet rooms)
- **Room 3:** `understand.py` (intent + slots + context, with tests), wired into `ask.py` and Talk; date resolution; `ask_about_cart` / `change_cart`; batching.
- **Room 2:** diet suitability (allergen evidence + at-risk check) and Gemini query expansion for search; alternatives ranking; speech language lock (en/fi) in `voice.py`.
- **Room 4:** the Kitchen nav page (onboarding + "What I know" with sources), proposed-facts and proposed-rules UI, rendering `reply/question/choices` for the new intents.
- **Room 1:** the acceptance suite with Omar's transcript cases; baseline run now, rerun after each merge, numbers into the docs.
- **Zoha:** visual polish only. The response contract keeps today's cards.

## Timeline (needs Omar's decision)
- **Now–18:00:** understand layer + diet suitability + search expansion + language lock + Kitchen nav entry. Eval rerun.
- **18:00–21:00:** change_cart / ask_about_cart polish, learned facts → proposed rules, eval to target.
- **Backend freeze 21:00; frontend freeze 22:00;** video and deck Sunday 07:00–09:30; FINAL by 09:30.
