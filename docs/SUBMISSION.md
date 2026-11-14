# Junction 2026 submission: text to paste

Copy each block into the matching field of the Junction platform. Final submission is due **Sun 15 Nov, 10:00**
(Helsinki), and peer review starts at **10:30**.

## Project name
Front Door

## Punchline (one sentence)
The buyer's agent is the visitor, and Valio wants a front door.

## Description: short (≈150 words)
Front Door is the door Valio Aimo could offer to its buyers' own AI agents.

A chef types a need ("1000 L lactose-free milk for Monday") or pastes a menu for 80 guests. Our Gemini
buyer agent finds the right products, quotes Valio's API live and converts the amounts. It orders on its own only
when it is sure and within the buyer's rules. Everything else goes to the chef, with reasons and alternatives.

Valio's front door re-checks every order, from any agent, against the buyer's stored mandate, using fresh prices
and stock. It catches the traps in the data: passed cut-offs, unknown stock, short stock and prompt injection. Only
a human can approve. Every decision is signed (Ed25519) and audited.

It is open by design: OpenAPI 3.1, JSON Schemas, an MCP server for any agent, a GS1 and Peppol mapping, and an MIT
licence.

## Description: long (≈300 words)
Gartner expects most B2B buying to run through AI agents by 2028. Valio Aimo already has A.I.mo for its own
customers, but restaurants will bring their own agents, and nothing checks them at the door. **Front Door** is that
door: the interface and operating model Valio could offer buyers' agents.

**The buyer's agent (Gemini).** A chef types a need or pastes a menu with the number of covers.
- Gemini parses it.
- Our agent searches Valio's full catalogue, quotes the live Valio API (price, stock, cut-off) and converts litres
  and kilos into sales units exactly.
- The Gemini Decisions API gives a calibrated confidence that each product and quantity is what the chef meant.
  On 30 labelled cases, our 0.80 threshold ordered no wrong product.
- It acts alone only when it is confident and within the buyer's limits. For example, it rejects 5-gram sugar
  sachets for baking and picks caster sugar.

**Valio's front door.** It re-checks every order, from any agent, against the buyer's mandate, which is stored at
Valio's side and never sent by the agent. It uses fresh quotes.
- **Hard rules refuse:** excluded allergens, missing claims, the maximum price, passed cut-offs.
- **Sign-off rules hold the order for the chef:** spend limits, the weekly budget, delivery reliability.
- **Data traps become questions, not guesses:** "available Monday" after the cut-off, stock 999999 (unknown),
  short stock (it proposes a split or a substitute), prompt injection.
- Only a human approves, even from a phone.
- Every decision is Ed25519-signed and audited for the buyer and for Valio.

**Open and honest.**
- An OpenAPI 3.1 spec and JSON Schemas.
- An MCP server, so Claude, ChatGPT or Gemini CLI can order through the same door.
- GS1 allergens, a Peppol mapping, and a standards map.
- Every assumption is documented: Valio's API is the challenge mock, and cut-offs and delivery days are demo
  assumptions.

Codex was our adversary: 62 findings, 43 fixed, each with a test.

**Optional lines, only if they ship before submission** (add them to both descriptions):
- One input box: "One box for kebab shops, cafés and restaurants: type an order or paste a menu, and the agent
  asks for the number of guests when it needs it."
- Voice: "Push-to-talk via Gemini Live, so a chef mid-service can order hands-free and the agent catches the order
  cut-off. Valio delivers in about 24 hours on agreed days, so the cut-off is what matters."
- If voice ships, add "Gemini Live API" to Technologies used.

## Challenges
- **Valio Aimo: Trusted Trade Agents** (main challenge)
- **Best Use of Gemini API**
- **Best Use of Codex**
- **CRACI**: only if CI is running on CRACI by submission time. Leave it unticked otherwise.

## Technologies used
Python 3, FastAPI, Pydantic, httpx, `cryptography` (Ed25519), React 19, TypeScript, Vite, Google Gemini API
(`gemini-4-hydrogen` structured output, Gemini Decisions API), Model Context Protocol (official Python SDK), OpenAPI
3.1 / JSON Schema, Render, Claude Code, OpenAI Codex CLI, RAEA (video), Playwright (deck PDF).

## Links
- Repository (public, MIT): https://github.com/omarjku/BengaliPharaohsJunction
- Live demo: https://valio-front-door.onrender.com (the free tier needs about a minute to wake up)
- API docs: https://valio-front-door-api.onrender.com/docs
- Video: *paste the public YouTube link*
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
1. **Seed the buyer** (a code change in `backend/app/mandates.py`, which belongs to Room 3 / Omar). Next to the
   `smoke-kitchen` copy, add a judge kitchen with the same rules but smaller limits:

   ```python
   _MANDATES["judge-kitchen"] = _MANDATES["lapland-kitchen"].model_copy(update={
       "id": "judge-kitchen-2026-11", "buyer_id": "judge-kitchen", "weekly_budget_cents": 300000})
   ```

   With EUR 3,000 a week, a judge sees "1000 L milk → ordered" once or twice, then the budget hold. That shows a
   rule working, not a broken demo.
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
6. **Clean-up:** `POST /api/admin/demo/reset` (admin key, `DEMO_RESET_ENABLED=1`) archives orders, the audit trail
   and idempotency keys to `DATA_DIR/archive/<timestamp>/` and starts empty. Note that it resets **all** buyers at
   once, `lapland-kitchen` too, so run it after peer review, not between demos. Pass `restore_mandate: true` if a
   judge changed the judge kitchen's rules.

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
- [ ] If judges get access: `judge-kitchen` seeded, its keys added on Render, shared only privately, and the removal planned for after judging
- [ ] Links above checked in a private window
- [ ] Challenges ticked (CRACI only if CI really runs there)
- [ ] Draft switched to **FINAL** before **Sun 10:00**
- [ ] **Both** of us at peer review at **10:30**, or we lose main-prize eligibility
