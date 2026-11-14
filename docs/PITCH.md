# Pitch: 3 minutes, plus the hard questions (T21)

**Structure** (from judges' advice for short hackathon pitches):
- the pain in the first 20 seconds;
- the live demo for about half the time;
- name each judging criterion as it is shown, so the judges can tick it off;
- the tech in 30 seconds, then next steps.

Don't narrate what went wrong during the build; save that for Q&A. One person speaks and one drives the demo.
Rehearse it timed, twice. Keep the recorded video open in a tab as a fallback.

**Before going on stage:**
- Warm up Render: open https://valio-front-door-api.onrender.com/api/health about 2 minutes ahead, because the free
  tier sleeps.
- Have the agent key and the approver key loaded in the UI.

## Script (about 3:00)

**0:00 Hook (20 s).**
"It's Friday night in a Lapland restaurant. The chef needs a thousand litres of lactose-free milk by Monday. More and
more buyers send an AI agent to do that. To Valio, that agent is a visitor nobody has checked. *The buyer's agent is
the visitor, and Valio wants a front door.* We built that door."

**0:20 What it is (20 s).**
"Two halves:
- a buyer's agent, built on Gemini, that turns the chef's words into an order;
- Valio's front door, which re-checks every order from *any* agent against the buyer's rules, the buyer's mandate,
  with fresh prices and stock.

Anything the data can't settle goes to a human, with the reason and alternatives. We never silently guess."

**0:40 Demo 1: the happy path, end to end (50 s). J1, J2.**
1. Type "1000 L lactose-free milk for Monday".
2. "Gemini read the request, and Gemini's Decisions API judged each candidate. The cheapest is a milk *drink*, at
   0.76 confidence. The agent picks real milk at 0.96, not the cheapest guess." (**J2**: exactly what the buyer asked
   for.)
3. "Every quote is live from Valio's API: price, stock, cut-off. Here are the facts: on time 100%, 1.1 kg CO2 per
   kg, Finnish."
4. "€1,560 is over the chef's €1,500 limit, so the door holds it." Switch to the approver key and approve.
   "The agent key can't approve; only the human can." (**J1**: request → lookup → order → approval, for real.)

**1:30 Demo 2: a trap (30 s). J4.**
1. Run a Terminal product, for example "60 L Arla lactose-free whole milk drink for Monday".
2. "Valio's API says *available Monday*, but the cut-off passed on Thursday, and stock 999999 means *unknown*, not
   unlimited. The agent doesn't order. It explains both and offers up to three substitutes that are orderable for Monday,
   allergen-safe and in the same category."
3. If time allows, show a split: "51 in stock, 1,000 asked: here's the same order covered by a second product,
   proposed to the chef."
4. Once menu-to-cart has landed, swap this for "here's my new menu" → a cart that always asks, because recipe
   amounts are assumptions.

**2:00 Controls and audit (20 s). J3.**
"What the agent decides alone comes from the buyer's mandate: the €1,500 limit, the per-line cap, the weekly
budget, no peanuts, at least 90% on-time delivery. Hard rules refuse, sign-off rules ask. Every decision, including
the options we rejected and why, goes to an append-only audit log." Open the audit view.

**2:20 Open and real (20 s). J5.**
"There's no proprietary format:
- an OpenAPI 3.1 spec and JSON Schemas for every message;
- GS1 allergen codes;
- a Peppol order mapping;
- an MCP server, so Claude, ChatGPT or Gemini CLI can plug into the same door.

Every assumption and data trap is written down, and the path to production is concrete: Postgres, signed requests
under RFC 9421, AP2-style signed mandates."

**2:40 Gemini and Codex (15 s).**
"Gemini isn't decoration here.
- It reads the chef. Its Decisions confidence decides when the agent may act alone, and below 0.8 it asks the chef.
- If Gemini is down, the agent falls back and asks the chef instead of ordering.
- Codex was our adversary: 8 reviews, 58 findings, 39 fixed, each with a test."

**2:55 Close (5 s).** "Any agent can visit. Only the right orders get in."

## The 10 hardest questions

1. **"Your API keys sit in the browser. Isn't that insecure?"**
   - The keys in the UI are demo keys for one demo buyer. They live in the browser's localStorage, which is readable
     by any script on that page (noted as a `ponytail:` comment in `frontend/src/api.ts`). They can only order or
     approve within that buyer's mandate.
   - Valio's API key and the Gemini key never reach the browser; only the backend holds them.
   - In production each agent gets its own identity: OAuth client credentials, or signed requests under RFC 9421.
     Approvers sign in as people.

2. **"What if Gemini is down?"**
   - Parsing falls back to a simple parser and keyword search, and the answer says so.
   - The Decisions check becomes "unverified", which under the default policy means asking the chef.
   - Money, stock, cut-offs and mandate rules never depend on Gemini. They are deterministic code, so a Gemini outage
     costs autonomy, not safety.

3. **"Why not just a chatbot?"**
   - A chatbot is one more agent. Valio's problem is *every* agent: theirs, ours, a buyer's homegrown one.
   - The front door is the part that makes any of them safe: the buyer's rules are checked at Valio's side, with
     fresh data and an audit trail.
   - The chef's UI is just one client.

4. **"The mock API is limited. How much is real?"**
   - All prices, stock and cut-offs are live calls to Valio's mock API, and the catalogue is Valio's full file of
     17,546 products.
   - The mock has no order endpoint, so "placing" an order means the door's own order record.
   - We found and handled its traps: the requested date is ignored, Terminal stock is 999999 (= unknown), cut-offs
     have often passed already, and about 15% of products are undeliverable. All of it is in `docs/ASSUMPTIONS.md`.

5. **"What stops a hijacked agent from overspending?"**
   - The door, not the agent. The buyer's mandate is stored at Valio's side; an agent can't send its own (that's a
     422).
   - Every order is re-checked with fresh quotes against the limits, the weekly budget and the hard rules.
   - The chef's text is fenced as untrusted, and parsed items must be grounded in the chef's own words.

6. **"How does this scale?"**
   - Today it runs one worker: the order lock and the JSON files live in one process, and the README says so.
   - Next: Postgres with row locks and idempotency keys, a shared quote cache, and an outbound rate limiter towards
     Valio. The ranking and the gate are stateless and scale out as they are.
   - Valio calls are batched up to 1,000 products. We never sweep the catalogue.

7. **"Why should a judge trust the 0.8 threshold?"**
   - It is per buyer and visible in the audit.
   - We measured it live: lactose-free milk scores 0.96, and the milk drink 0.76.
   - It is still a guess until it is calibrated against real orders. That is item 9 in `docs/NEXT-STEPS.md`.

8. **"What happens if a price changes between the quote and the approval?"** Approval re-runs the gate with fresh
   quotes. A changed price keeps the order pending, with the old and new price. A passed cut-off refuses it. A human
   never signs off on terms they didn't see.

9. **"What's the path to production?"** In order:
   1. Postgres, with a tamper-evident audit.
   2. Per-agent identity, using RFC 9421 or mTLS.
   3. Buyers editing their own versioned mandates.
   4. Multi-worker locking.
   5. Signed quotes.
   6. Valio's real order endpoint.
   7. Peppol order export.

   Every item has its reason in `docs/NEXT-STEPS.md`.

10. **"What's actually new here?"** Most teams put the guardrails inside their own agent. We put them at the
    *seller's* door, so they hold for agents we didn't write. They come with an open contract, an MCP server, and a
    rule that uncertainty always reaches a human with alternatives, never a silent guess or a silent refusal.

**Backups:**
- "Why Render?": one push deploys both halves.
- "Why the per-line cap?": a fat-finger guard ("10000 L").
- "Carbon?": shown on every line, and it can rank once a buyer asks for it.
