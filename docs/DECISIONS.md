# ✅ Decisions: from our meeting at Noli Otaniemi (Sat 14 Nov, ~01:00)

Source: our ~19-min recording, transcribed locally. **Quotes are ours.** Where we didn't decide, it says **OPEN**; nothing here is filled in by Claude. Speaker labels in the transcript are anonymous (Speaker 1 / 2).

| # | Decision | What we decided | Status |
|---|---|---|---|
| D0 | Draft submission | Not discussed in the meeting | ❓ Was it submitted before 23:55? |
| D1 | Hero customer | **Lapland restaurant + chef planning a menu**, combined. Reasons: delivery reliability is vital in Lapland; "Finland-focused", like Agronomy was Bangladesh-focused. Reliability and Finnish origin both covered; price "later". Allergens "could still be an option" (dish allergens on the menu). | ✅ Decided |
| D2 | Where guardrails live | "Autonomy of the human, control of the human." **"We need more info to make a really good decision."** | 🟡 **OPEN** (explainer below) |
| D3 | Signature features | **Gemini Decisions API calibrated confidence + menu-to-cart.** Others: "look at them later / add later". | ✅ Decided |
| D4 | Input channels | **Text + voice (voice-to-voice, like Google showed).** Use cases: owner at the office computer says "this is my new menu", or talking while walking around the kitchen. **Photo later.** | ✅ Decided |
| D5 | Customer history | **Onboarding questions + past orders + remembering what was said.** Rule: **don't over-generalise.** "I don't want wheat flour in this recipe" applies to *today's order*, not forever. | ✅ Decided |
| D6 | API traps | **Lenient: bring it up to the human, never silently reject.** Explain why, offer alternatives. "Maybe we understood the traps wrong", so ask Valio. | ✅ Decided (+ booth question) |
| D7 | Open standard | "Not sure yet… maybe explain the standard a bit more." J5 = "tell them how we built it and how we'd make it production-ready". | 🟡 **OPEN** (explainer below) |
| D8 | Tech stack | **Python + TypeScript, web app frontend.** Frontend must **not look like the copy-paste demo everyone has**; we have design notes. Hosting and storage not discussed. | ✅ Partly (hosting/storage **OPEN**) |
| D9 | Extra tech prizes | **Gemini** (both agree: "it's like a football field, open to play"). **CRACI** (already talked to their team: "told her to expect me"). **Codex**: use the credits, e.g. code review via Claude, "cherry on top at the end". | ✅ Decided |
| D10 | Gemma offline | Discussed; noted the app needs Wi-Fi for prices, stock and cut-offs anyway. No decision. | 🟡 **OPEN** (later) |
| D11 | Work split | **Not final.** Zoha wants more backend this time. Break tasks so **either person can take them**; both Claudes use the board to avoid overlap. | ✅ Approach decided; owners **OPEN** |
| D12 | Demo + video | Not discussed. Agreed: **when pitching, explicitly name the criterion we meet** ("this is the end-to-end flow, J1"), and **be ready for peer-review questions** and answer confidently. | 🟡 **OPEN** (format) |
| ⏱ | Timeline | **Main tasks done by "tomorrow afternoon/evening"**, then polish + stand-out; **"by tomorrow midnight, finalise everything."** | ❓ Recorded after midnight: "tomorrow" = **Saturday**? |

## Explainers for the two big OPEN ones

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
