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

## Final checklist before Sun 10:00
- [ ] Video is **public**, **≤ 2:00** (target 1:55), and opens in a private window; `.srt` captions uploaded
- [ ] Deck PDF uploaded (`docs/deck/FrontDoor-pitch.pdf`; re-export with `docs/deck/export.mjs` after the new screenshots land)
- [x] Repository public, MIT licence in `LICENSE`
- [ ] Render warmed up (`/api/health`), and the demo agent and approver keys work on the live site
- [ ] Links above checked in a private window
- [ ] Challenges ticked (CRACI only if CI really runs there)
- [ ] Draft switched to **FINAL** before **Sun 10:00**
- [ ] **Both** of us at peer review at **10:30**, or we lose main-prize eligibility
