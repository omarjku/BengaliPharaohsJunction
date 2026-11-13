# Proposal (for discussion, not decided): Valio Aimo × Google Gemini

**Entries:** Valio Aimo *Trusted Trade Agents* (main, €4,000) + *Best Use of Gemini API* (tech, €4,000 + $1,000 GCP credits each). Cheap add-on: CRACI (CI runner line).

**One line:** a buyer writes their purchasing rules in plain language; their agent shops Valio Aimo and **knows exactly when it may buy on its own and when a human must sign off**, with every step in a readable audit trail.

## How it works
```
Buyer rules (plain text)          Request: "1,000 L lactose-free milk by Monday"
        │                                        │
  [1] Gemini compiles ──► Mandate JSON ◄──────────┤
      hard rules · when-unsure policy ·          │
      guidance · open questions                  ▼
                                    [2] Catalogue search (static data: allergens,
                                        claims, lot size, carbon, reliability)
                                                 ▼
                                    [3] Valio API: availability + price
                                        (cut-off, partial stock, Terminal = unknown)
                                                 ▼
                                    [4] Gemini Decisions API: calibrated checks
                                        "meets lactose-free?" "safe substitute?" "rank good/better/best"
                                                 ▼
                                    [5] Guardrails: hard rules + confidence threshold
                                        → AUTO-ORDER · ASK HUMAN · DECLINE (with reason)
                                                 ▼
                                    [6] Order + audit trail (human-readable)
```
The design ideas come from our earlier projects: Zoha's *Agent on a Leash* mandate design, and the "answer only when confident, otherwise hand off" pattern from Agronomy. **All code is new, written here.**

## Where each Google tool earns its place
| Tool | Job | Why it's not a bolt-on |
|---|---|---|
| **Gemini 4 (Hydrogen)** | Turns the buyer's rules and requests into structured JSON; plans tool calls | The whole interface is natural language → verifiable structure |
| **Gemini Decisions API** | Yes/no, choice and rubric scores **with calibrated confidence** | Confidence is the guardrail: below threshold → human. It's also cheap and fast (slide: 150–250 ms, $0.10/1M input tokens, up to 1,000 questions per call) |
| **Stitch** (shown in the keynote) | Generates the approval-screen UI fast | Frees hours for the agent logic |
| Gemini API skill for Claude Code | `npx skills add google-gemini/gemini-skills --skill gemini-api-dev` | Our coding agents write correct Gemini code |
| Gemma (optional, separate €1,000 prize) | A small local model for the allergen check, if time allows | Only if it's real, not a checkbox |

## How it scores (Valio's weights)
- **Demo 30%:** one live run: request → search → API → decision → order, or "ask human" on the phone screen.
- **User need 20%:** the mandate captures what the buyer *meant*; open questions are asked, not guessed.
- **Autonomy & controls 20%:** three outcomes with reasons; thresholds the buyer sets; full audit log.
- **Exceptions 15%:** the three traps we already found (passed cut-off, 51-unit partial stock, Terminal "999999" = unknown), plus allergen-safe substitution.
- **Openness 15%:** the mandate and decision formats published as JSON Schema / OpenAPI, so any agent can use them.

## To verify before committing
1. **Decisions API access:** is it live in AI Studio for us? Ask at the DeepMind booth (floor 3, booth 3) and grab the event credits.
2. Valio mentors (floor 3, booth 1): is a confidence-threshold guardrail what they mean by "autonomy and controls"? Do they want x402-style payments, or is it out of scope?
3. Decide team split tonight: one person on mandate + guardrails + Gemini, one on catalogue/API + demo UI.
