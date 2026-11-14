# ✅ Decisions: from our meeting at Noli Otaniemi (Sat 14 Nov, ~01:00)

Source: our ~19-min recording, transcribed locally. **Quotes are ours.** Where we didn't decide, it says **OPEN**; nothing here is filled in by Claude. Speaker labels in the transcript are anonymous (Speaker 1 / 2).

| # | Decision | What we decided | Status |
|---|---|---|---|
| D0 | Draft submission | Not discussed in the meeting | ❓ Was it submitted before 23:55? |
| D1 | Hero customer | **Lapland restaurant + chef planning a menu**, combined. Reasons: delivery reliability is vital in Lapland; "Finland-focused", like Agronomy was Bangladesh-focused. Reliability and Finnish origin both covered; price "later". Allergens "could still be an option" (dish allergens on the menu). | ✅ Decided |
| D2 | Where guardrails live | **Both.** Our agent checks the rules, and **our order endpoint is Valio's front door**: it re-checks every order (cut-off, quantity, mandate) and returns a structured refusal with reasons + alternatives instead of breaking the flow. Rogue orders get blocked at the door. | ✅ Decided (Sat ~02:00) |
| D3 | Signature features | **Gemini Decisions API calibrated confidence + menu-to-cart.** Others: "look at them later / add later". | ✅ Decided |
| D4 | Input channels | **Text + voice (voice-to-voice, like Google showed).** Use cases: owner at the office computer says "this is my new menu", or talking while walking around the kitchen. **Photo later.** | ✅ Decided |
| D5 | Customer history | **Onboarding questions + past orders + remembering what was said.** Rule: **don't over-generalise.** "I don't want wheat flour in this recipe" applies to *today's order*, not forever. | ✅ Decided |
| D6 | API traps | **Lenient: bring it up to the human, never silently reject.** Explain why, offer alternatives. "Maybe we understood the traps wrong", so ask Valio. | ✅ Decided (+ booth question) |
| D7 | Open standard | **REST API + OpenAPI spec** (agent-agnostic: Gemini, voice, Claude or anything can use it) **+ README** documenting everything: assumptions, next steps, path to production. | ✅ Decided |
| D8 | Tech stack | **Python + TypeScript, web app.** Distinct frontend (not copy-paste). **Hosting: Render** for backend + frontend, auto-deploys every push to `main` whoever pushes (not Vercel; not laptop-only). Free tier sleeps after 15 min idle, so warm it before demos or upgrade for the weekend (our call). **Storage: JSON files first, Aiven Postgres later** (maybe; extra tech prize). | ✅ Decided |
| D9 | Extra tech prizes | **Gemini** (both agree: "it's like a football field, open to play"). **CRACI** (already talked to their team: "told her to expect me"). **Codex**: use the credits, e.g. code review via Claude, "cherry on top at the end". | ✅ Decided |
| D10 | Gemma offline | Doesn't make sense without internet. **Later / focus on main stuff first.** | ⏸ Parked |
| D11 | Work split | **Keep it dynamic**: no fixed owners, claim tasks on the board. UI: both want to be involved. | ✅ Decided |
| D12 | Demo + video | **Live demo at peer review** + **submission video made with RAEA.** Story: Lapland chef speaks a new menu → cart with reasons → trap explained ("can't arrive Monday, here are 2 alternatives") → asks the human → audit log → rogue order blocked at Valio's door. | ✅ Decided |
| D13 | Reliability floor | **Reliability floor holds for the chef (ASK_HUMAN), never refuses.** Reason: Lapland kitchens may knowingly accept a less reliable supplier; D6, bring it to the human. A product with no reliability record is held the same way. (Omar, Sun 15 Nov, after the Codex review.) | ✅ Decided |
| ⏱ | Timeline | **Sat midday: end-to-end example working AND deployed.** Sat evening: features on top. If ahead: start pitch, deck, video. | ✅ Decided |

## Explainers for D2 and D7 (both now decided, kept for reference)

**D2 · Where the guardrails live.** Two places can say "no":
- **In our buyer agent:** it checks the mandate before ordering. Simple, and what most teams will do.
- **At Valio's front door:** Valio re-checks every incoming order against the buyer's mandate. Even a buggy or hijacked agent can't overspend.
- **Both** is what the pitch line describes ("the buyer's agent is the visitor, Valio has a front door").

J3 asks "what the agent can decide alone, what needs human sign-off, how it's logged". All three options can score; "both" is the most distinctive and the most work.

**D7 · The open standard.** J5 rewards "open, documented standards rather than a proprietary format". In practice it means **publishing the shapes of our messages** so anyone could build a compatible agent:
- `PurchaseRequest`: what the buyer asks
- `Mandate`: the buyer's rules
- `Quote`: Valio's answer, with freshness and known/unknown quantity
- `Decision`: auto / ask human / decline, plus reasons and confidence
- `AuditEntry`

The options are **how** to expose them: a **REST API with an OpenAPI spec** (universal), an **MCP server** (agent-native; many teams will do this), or both. Plus a README with our assumptions and next steps. This is mostly documentation of things we build anyway.

## Booth questions (when we go)
- **Valio:**
  - Terminal cut-off already passed but says "available Monday": trap or quirk?
  - Requested date ignored: intended?
  - Is ordering ours to define?
  - Is our "bring it up to the human" policy what they want?
- **DeepMind:**
  - Is the Decisions API live for us?
  - How do we get the credits?
  - Any Live API limits?
