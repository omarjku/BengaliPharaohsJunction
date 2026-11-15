# Junction 2026 submission: text to paste

Copy each block into the matching field of the Junction platform. Final submission is due **Sun 15 Nov, 10:00**
(Helsinki), and peer review starts at **10:30**.

## Project name
Front Door

## Punchline (one sentence)
The buyer's agent is the visitor, and Valio wants a front door.

## Description: short (≈150 words)
Front Door is the door Valio Aimo could offer to its buyers' own AI agents.

A kebab shop, café or restaurant types a need into one box, in English or Finnish ("1000 L lactose-free milk for
Monday", "20 kg döner kebab meat"), or pastes a menu, and the agent asks for the number of guests if needed. Or says it: push-to-talk voice lets a chef
order hands-free mid-service, before the delivery cut-off. Our Gemini
buyer agent finds the right products, quotes Valio's API live and converts the amounts. It proposes every order, and
the chef approves it. Below the kitchen's confidence bar it asks instead of guessing. Each proposal comes with reasons
and alternatives.

Valio's front door re-checks every order, from any agent, against the buyer's stored mandate, using fresh prices
and stock. It catches the traps in the data: passed cut-offs, unknown stock, short stock and prompt injection. Only
a human can approve. Every decision is signed (Ed25519) and audited.

It is open by design: OpenAPI 3.1, JSON Schemas, an MCP server for any agent, a GS1 and Peppol mapping, and an MIT
licence.

## Description: long (≈300 words)
Gartner expects most B2B buying to run through AI agents by 2028. Valio Aimo already has A.I.mo for its own
customers, but restaurants will bring their own agents, and nothing checks them at the door. **Front Door** is that
door: the interface and operating model Valio could offer buyers' agents.

**The buyer's agent (Gemini).** One box for kebab shops, cafés and restaurants, typed or spoken, in English or Finnish:
an order, or a menu (it asks "for how many guests?" when it needs to). Voice is push-to-talk, transcribed by Gemini in
about a second. Valio delivers in about 24 h on agreed days, so the point is catching the cut-off hands-free during
service.
- Gemini parses it.
- Our agent searches Valio's full catalogue, quotes the live Valio API (price, stock, cut-off) and converts litres
  and kilos into sales units exactly.
- The Gemini Decisions API gives a calibrated confidence that each product and quantity is what the chef meant.
  On 33 labelled cases, our 0.70 threshold ordered no wrong product.
- It never spends on its own: the chef approves every order (our design choice; reliability over speed, because
  it is the kitchen's money). Below the 0.70 bar it asks instead of guessing. For example, it rejects 5-gram sugar
  sachets for baking and picks caster sugar.

**Valio's front door.** It re-checks every order, from any agent, against the buyer's mandate, which is stored at
Valio's side and never sent by the agent. It uses fresh quotes.
- **Hard rules refuse:** excluded allergens, missing claims, the maximum price, passed cut-offs.
- **Sign-off rules hold the order for the chef:** spend limits, the weekly budget, delivery reliability (an 80% on-time floor applies when the buyer sets none).
- **Data traps become questions, not guesses:** "available Monday" after the cut-off, stock 999999 (unknown),
  short stock (it proposes a split or a substitute), prompt injection.
- Only a human approves, even from a phone.
- Every decision is Ed25519-signed and audited for the buyer and for Valio.
- Urgent in Helsinki? It suggests Valio's Cash & Carry or Click & Collect (about 4 h). These are clearly suggestions;
  it never places a pickup order.

**Open and honest.**
- An OpenAPI 3.1 spec and JSON Schemas.
- An MCP server, so Claude, ChatGPT or Gemini CLI can order through the same door.
- GS1 allergens, a Peppol mapping, and a standards map.
- Every assumption is documented: Valio's API is the challenge mock, and cut-offs and delivery days are demo
  assumptions.

Codex built much of the core (47 commits on main say "Built by Codex") and also reviewed it: 112 numbered review findings across the rooms—79 kept/fixed, 12 rejected, 10 deferred,
2 explicitly forwarded, and 6 already fixed (with status overlaps; see `docs/CODEX.md`).

## Best Use of Gemini: the four answers

Rewritten from the code on Sun 15 Nov (`backend/app/*.py`, every Gemini call). The principle is **Gemini proposes, code
decides, a human approves.** The app was *built* with Claude Code and Codex; everything the product *runs on* is
Gemini.

### 1. The problem, and why it matters

Restaurants will send AI agents to buy from wholesalers like Valio Aimo, and today nothing checks those agents at
the seller's side. Kitchens order the way people talk: "1000 L lactose-free milk", a Finnish voice note, a
handwritten list, a chalkboard menu. A wrong guess costs money (an extra zero), safety (an allergen) or service (a
missed cut-off). The hard part isn't reading the words. It's knowing **when the agent may act alone** and when it
must ask the chef.

### 2. How the Gemini API is integrated

| Capability | Model | What it returns | What our code does with it |
|---|---|---|---|
| Reading an order | `gemini-4-hydrogen`, structured output (JSON schema, temperature 0) | items: product, amount, unit, dietary needs, purpose | Every item must be grounded in the chef's own words (product, amount and unit in one clause), or the chef is asked |
| Routing (order, menu or unclear; guest count) | `gemini-4-hydrogen`, structured | intent, covers | Code picks the path. A menu with no guest count → "For how many guests?" |
| Matching catalogue hits | `gemini-decision-1` (Decisions API) | P(yes) "is this hit the item?", one call per hit | Hits are kept or dropped by probability; the search stops at a confident match |
| **Line judge: product and quantity** | `gemini-decision-1` | P(yes) for "is it the product?" (no amounts) and "is the quantity right?" | **The weaker P(yes) decides when to ask:** below the buyer's threshold (0.70, measured) the agent asks instead of guessing; at or above, it proposes the line for the chef to approve. Among confident lines, confidence leads and price only breaks near-ties. The number is stored in the audit |
| Plausibility, steering, date intent, same product in Finnish | `gemini-decision-1` | P(yes) each | **Can only add a question**, never permit anything. Unanswered → the mandate's uncertainty policy (ask) |
| Menu → ingredients | `gemini-4-hydrogen`, structured | dishes, ingredients, per-portion amounts, assumptions | Code scales and merges, quotes Valio and runs the judge. A menu never orders by itself |
| Menu assumption check | `gemini-decision-1` | P(yes) "needed for this dish?", "portion reasonable?" | Low scores are flagged for the chef |
| Spare amounts | `gemini-4-hydrogen`, structured (no thinking) | 0–20 % extra per ingredient, with a reason | Shown as a proposal; code applies limits |
| Rules in plain language → mandate | `gemini-4-hydrogen` via Zoha's compiler, structured | proposed mandate, open questions | A Decisions "is this rule faithful?" check adds open questions. Saving needs the approver key; loosening needs a second confirmation |
| Onboarding text → profile | `gemini-4-hydrogen`, structured | location, diets, spare level, cuisine, unclear | Stored as profile memories: guidance, never rules |
| Photo of a list, menu board or whiteboard | `gemini-4-hydrogen` (image input), structured | kind, text, items, covers, `suspicious` | Places nothing. The text goes through the same `/api/agent/ask`. Planted instructions are only text |
| Push-to-talk | `gemini-3.5-transcribe-live` (Live API) | the chef's words; numbers normalised to digits | Same pipeline as typing |
| **Talk** | `gemini-3.8-live` (Live, native audio, tool calls, barge-in) | speech, plus tool calls `ask_agent` and `search_catalogue` | `ask_agent` runs the full pipeline and the front door. **No approve tool.** The browser never sees the Gemini key |

### 3. What is innovative

- **Calibrated confidence as policy.** When to ask isn't a prompt instruction. It's a number from the Decisions API
  that a buyer sets a threshold on, measured on 33 labelled cases with real Valio products: at 0.70, 0 wrong
  automatic orders. Every decision is stored with its score.
- **Gemini can only add caution.** Five extra Decisions guards can each turn "order" into "ask", never the reverse.
  Money, stock, cut-offs, limits and approval stay in code and at Valio's front door, which re-checks every order
  from any agent.
- **One pipeline for every input.** Typed text, Finnish voice, a live conversation and a phone photo all land on the
  same grounded, judged, audited path. That's why a planted note in a photo changes nothing.
- **Our QA caught Gemini's own trap.** The agent once auto-bought coffee milk (0.72, cheapest). We changed the question
  and the ranking, and added it to the eval. It now scores 0.12.

### 4. Why Gemini, honestly

- **Any capable LLM could do:** reading a request or a menu into JSON, routing order vs menu, onboarding text into a
  profile.
- **What depends on Gemini specifically:**
  - The **Decisions API's calibrated probabilities**: deterministic (6/6 identical scores), about 0.5 s, cheap
    enough to ask per candidate, and measured on our eval. A model's self-reported confidence in generated text
    can't be thresholded like this.
  - The **Live API's native audio with tool calls and barge-in**: Talk orders through our pipeline in about 1.3 s to
    first audio.
  - **One API family for text, image and audio**, each with structured output. Photo, voice and text share one
    validated path, with one key held server-side.

## Challenges
- **Valio Aimo: Trusted Trade Agents** (main challenge)
- **Best Use of Gemini API**
- **Best Use of Codex**
- **CRACI**: CI runs on CRACI (7 CRACI jobs for the live commit `76f5a92`, per the build-evidence endpoint).

## Technologies used
Python 3, FastAPI, Pydantic, httpx, `cryptography` (Ed25519), React 19, TypeScript, Vite, Google Gemini API
(`gemini-4-hydrogen` structured output, Gemini Decisions API, Gemini transcribe-live for voice), RFC 9421 HTTP Message
Signatures (optional agent signing), Model Context Protocol (official Python SDK), OpenAPI
3.1 / JSON Schema, Render, Claude Code, OpenAI Codex CLI, RAEA (video), Playwright (deck PDF).

## Links
- Repository (public, MIT): https://github.com/omarjku/BengaliPharaohsJunction
- Live demo: https://valio-front-door.onrender.com (the free tier needs about a minute to wake up)
- API docs: https://valio-front-door-api.onrender.com/docs
- Demo video: (link added at submission)
- Deck: `docs/deck/FrontDoor-pitch.pdf` (upload the file)

## Team
- Omar Kassem
- Fathia Fairuz Zoha

## Judge access to the live demo (proposal: Omar decides before any key is made)

**Recommended:** a separate seeded buyer, `judge-kitchen`, with its own keys and a small budget. Judges never touch
`lapland-kitchen` (our demo) or the real keys.

**Why this is the safest option:**
- Every key is bound to one buyer. A judge key can only order, approve and read the audit for `judge-kitchen`
  (`auth.py`). Their orders can never show up in our demo kitchen.
- The keys live only in Render's Environment tab, so removing them from there and redeploying kills them.
- Rate limits already cap a key at 30 agent requests per minute.
- Orders are records at our door. The Valio mock has no order endpoint, so nothing real is bought.

**Steps:**
1. **Seed the buyer: done.** `backend/app/mandates.py` seeds `judge-kitchen`: the demo kitchen's rules (peanut-free,
   EUR 1,500 auto-approve, 90 % reliability floor, Finnish preference), its kitchen facts and location, and a
   **EUR 3,000** weekly budget. A judge sees "milk → ordered" once or twice, then the budget hold, which shows a rule
   working rather than a broken demo. It stays inert: without keys, nobody can act as it.
2. **Make two keys** on Omar's laptop: `openssl rand -hex 24`, twice. Never put them in the repo, the board, a
   commit, a URL or a screenshot.
3. **Env changes on Render** (backend service → Environment). Append, comma-separated, to the existing values:
   - `AGENT_KEYS`: `,<judge-agent-key>=judge-kitchen:Judge agent`
   - `APPROVER_KEYS`: `,<judge-approver-key>=judge-kitchen:Judge`

   Then save; Render redeploys. Nothing else changes. `DATA_DIR`, `VALIO_ADMIN_KEYS` and `DEMO_RESET_ENABLED` stay
   as they are.
4. **Share the keys** only in the submission form's private field, or in person at peer review on a printed card.
   Judges paste them into the site's **Keys** tab. The UI keeps them in that browser only.
5. **After judging:** remove both entries from `AGENT_KEYS` and `APPROVER_KEYS` and save. The keys stop working
   after the redeploy.
6. **Reset the sandbox, any time:** `python3 scripts/demo_prep.py https://valio-front-door-api.onrender.com
   --env .env --buyer judge-kitchen --restore-mandate`. It archives **only** `judge-kitchen`'s orders, audit lines,
   idempotency keys and edited rules to `DATA_DIR/archive/<timestamp>-judge-kitchen/` (nothing is deleted). Then it
   warms the backend and prints the judge kitchen's budget. `lapland-kitchen` and the other buyers are untouched,
   so this is safe between demos. It needs the admin key and `DEMO_RESET_ENABLED=1`, both already set on Render.
   (`--all` still resets every buyer at once.)

**What judges can and can't do with these keys:**
- They can order, approve, edit `judge-kitchen`'s rules (`PUT /api/mandate`), and read its audit.
- They can't see or touch `lapland-kitchen`, the Valio key, the Gemini key, or the admin routes.
- A judge loosening their own kitchen's rules is fine: it's their sandbox, and the reset's `restore_mandate`
  undoes it.

**Lighter alternative:** if seeding a buyer is too late, show the demo on our own laptop at the table. There are no
keys to share, but judges can't try it themselves.

## Final checklist before Sun 10:00
- [ ] Video is **public**, **≤ 2:00** (target 1:55), and opens in a private window; `.srt` captions uploaded
- [ ] Deck PDF uploaded (`docs/deck/FrontDoor-pitch.pdf`; re-export with `docs/deck/export.mjs` after the new screenshots land)
- [x] Repository public, MIT licence in `LICENSE`
- [ ] Render warmed up (`/api/health`), and the demo agent and approver keys work on the live site
- [ ] If judges get access: `judge-kitchen` is seeded (done); add its two keys on Render, share them only privately, and plan their removal after judging
- [ ] Links above checked in a private window
- [ ] Challenges ticked (CRACI only if CI really runs there)
- [ ] Draft switched to **FINAL** before **Sun 10:00**
- [ ] **Both** of us at peer review at **10:30**, or we lose main-prize eligibility
