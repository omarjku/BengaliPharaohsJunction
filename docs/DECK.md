# Pitch deck (T23): 10 slides

Each slide body stays at 25 words or fewer; speaker notes are separate. The screenshots are in
`docs/design/screens/` (1280 px desktop, 390 px phone). Those were captured in the UI's mock mode, so their product
names and amounts are illustrative: label them "UI" and don't quote their numbers. Numbers on slides come from the
live runs in `docs/m1-e2e.md`, `docs/GEMINI.md` and `docs/CODEX.md`.

---

### 1. Title
**Front Door: trusted trade agents for Valio Aimo**
*The buyer's agent is the visitor, and Valio wants a front door.*
Junction 2026 · Omar Kassem · Fathia Fairuz Zoha

> **Notes:** One breath. Name, pitch line, team. Open the live demo on the next tab.

### 2. The problem
- 90% of B2B buying via AI agents by 2028¹
- Valio Aimo: webshop, VALO, A.I.mo²; no public API³
- Buyers will bring their own agents. Who checks them?

> **Sources:**
> 1. Gartner, via [Digital Commerce 360, Nov 2025](https://www.digitalcommerce360.com/2025/11/28/gartner-ai-agents-15-trillion-in-b2b-purchases-by-2028/)
> 2. [valioaimo.fi, innovative tools](https://www.valioaimo.fi/en/company/why-choose-valio-aimo-as-a-partner/innovative-tools-for-everyday-work/)
> 3. Our research, `docs/research/valio-context.md`
>
> Peers are cautious too: US Foods' AI tools "do not place orders autonomously" ([Distribution Strategy, Feb 2026](https://distributionstrategy.com/2026/02/how-agentic-commerce-is-starting-to-reach-wholesale-distribution/)).
>
> **Notes:** Frame it as the next step for A.I.mo, never "fully autonomous".

### 3. What we built
**Chef's words → Gemini buyer agent → Valio front door → Valio.**
The door re-checks every order, from any agent, against the buyer's mandate. Unsure means ask.

> **Notes:** Show the architecture diagram from the README. Two halves: our agent is one client; the door is the
> product.

### 4. Demo
Screens: `3-needs-ok-1280.png` (held for the chef), `4-approved-390.png` (approved on a phone),
`9-menu-cart-1280.png` (menu → cart).
**1000 L milk → €1,400, ordered alone. 1500 L → held → chef approves. Menu for 80 → cart.**

> **Notes:** Live, measured Sun 15 Nov:
> - 1000 L: Gemini 0.90 on the cheapest milk, €1,400, AUTO confirmed.
> - 1500 L: €2,100, LINE_OVER_CAP + SPEND_OVER_LIMIT, held. The agent key gets 401 on approve; the approver key
>   confirms.
> - Menu: always ASK_HUMAN (MENU_ASSUMPTIONS).

### 5. Trust and controls (J3)
- **Hard rules refuse:** allergens, claims, max price, cut-off
- **Sign-off rules hold:** limits, weekly budget, reliability
- Only humans approve
- Every decision signed and audited

> **Notes:** The mandate is stored at Valio's side; an agent can't send its own (422). Ed25519-signed decisions,
> verifiable at `/.well-known/front-door-keys.json`. Audit for the buyer and, read-only, for Valio staff. Approval
> re-checks fresh quotes; a changed price keeps the order pending. Screen: `7-history-1280.png`.

### 6. Exceptions (J4)
- Cut-off passed, "available Monday" anyway
- 999999 = unknown, not unlimited
- Short stock → split
- Substitutes: allergen-safe, same category
- Injection → nothing ordered

> **Notes:**
> - The traps come from Valio's mock data: Terminal cut-offs four days ahead, about 15% of products undeliverable.
> - Each one asks, with reasons and alternatives (D6: never silently guess).
> - Screen: `6-short-stock-split-1280.png`.

### 7. Open by design (J5)
- OpenAPI 3.1 and JSON Schemas
- MCP server: any agent plugs in
- Signed statements (Ed25519)
- GS1 allergens; Peppol mapped; AP2 / RFC 9421 next

> **Notes:**
> - Point to `docs/STANDARDS.md` for the standards table (implemented / mapped / next).
> - The MCP server was tested end to end with the live Valio mock.
> - Everything is MIT-licensed and the repo is public.

### 8. Gemini decides when to ask
| threshold | handled alone | wrong autos |
|---|---|---|
| 0.7 | 11 | 0 |
| **0.8** | **11** | **0** |
| 0.9 | 8 | 0 |

Sugar sachets for baking: **0.44**. Caster sugar: **0.94**.

> **Notes:**
> - Gemini Decisions API: calibrated P(yes) on 30 hand-labelled cases with real Valio products.
> - The highest-scoring trap reached 0.52.
> - The evaluation changed the agent: it now asks "is it the product?" and "is the quantity right?" separately.
> - If Gemini is down, the agent asks the chef: it loses autonomy, not safety.

### 9. Codex as our adversary
**9 reviews · 62 findings · 43 fixed, each with a test.**
It caught prompt-injection bypasses, unvalidated confidence and stale approvals.

> **Notes:**
> - From `docs/CODEX.md`: 11 rejected with reasons. Codex and Claude independently agreed on 3 of 4 bugs in PR #8.
> - Lesson learned: always run `codex exec … < /dev/null`.

### 10. Real vs mocked, and next
- **Real:** live Valio mock API, the full catalogue, Gemini, signing, MCP.
- **Assumed:** cut-offs, delivery days, no Valio order endpoint.
- **Next:** Postgres, per-agent identity, signed mandates.

> **Notes:**
> - The Valio API is the challenge's mock; "placing" an order creates the door's own record.
> - On Render, state is lost on redeploy unless `DATA_DIR` sits on a persistent disk.
> - Next steps, in order, are in `docs/NEXT-STEPS.md`.
> - Close: "Any agent can visit. Only the right orders get in."
