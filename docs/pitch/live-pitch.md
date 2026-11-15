# Front Door: three-minute peer-review pitch

**Roles:** Zoha tells the story and narrates. Omar drives the phone and laptop. Both stay for questions.

**Props:** the same handwritten list from [`video-script.md`](video-script.md), Phone A with the agent key, Phone B with the approver key, and a laptop showing the signed order. Do not use voice for the main demo.

## Before the table

- Warm the live app and open the health check.
- Run the photo flow once, then reset the demo kitchen before the judges arrive.
- Start the video at its photo-flow frame. It is the fallback if the live flow cannot load.
- Keep the list, the held card, and the approval screen ready. If a step takes more than 10 seconds, switch to the fallback without apologising for the technology.

## Script and screen directions

| Time | Speaker and words | What to show or do | Criteria covered |
|---|---|---|---|
| 0:00–0:20 | **Zoha:** “It is 06:00. A chef has 500 guests, a delivery cut-off is closing, and a handwritten list to place. The chef needs speed, but cannot afford an extra zero or an unsafe product.” | Hold up the list. Point to `500 GUESTS`, the delivery date, and the seven items. | J2 user need |
| 0:20–0:35 | **Omar:** “The buyer’s agent is the visitor. Front Door is Valio’s check at the door: it reads the request, checks the facts, and lets the chef decide.” | Show the simple architecture slide: agent → front door → ordered, held, or not ordered. | J3 controls; J5 openness |
| 0:35–0:48 | **Zoha:** “We will do one real photo flow. The photo is not a prepared answer: it is this list, read now.” | Give the list a quick overhead shot. Omar opens Phone A’s photo flow. | J1 end-to-end |
| 0:48–1:08 | **Omar:** “The photo becomes seven items. The agent checks Valio prices, stock, delivery, and pack sizes. Notice the exception line: the system explains the stock or cut-off problem instead of guessing.” | Point to the read result, progress lines, live quote, delivery date, and the exception reason or alternative. | J1 working demo; J4 exceptions |
| 1:08–1:28 | **Zoha:** “The milk line is €1,560, above the kitchen’s €1,500 limit, so the whole cart is held. The agent has no approval power.” | Point to the held card, the reason panel, the limit, and `Needs your OK`. Show Phone A’s agent session. | J3 autonomy and controls |
| 1:28–1:43 | **Omar:** “Now the chef approves on screen.” | Hand Phone B to the judge if they want to tap; otherwise Omar taps. Point to `Approve`, then `Ordered`. | J1; J3 human control |
| 1:43–1:55 | **Zoha:** “The result is signed and audited. The same order can be checked by Valio.” | On the laptop, open the audit entry and signature verification. Point to the signed statement and build line. | J3; J5 production path |
| 1:55–2:15 | **Omar:** “The exception is the point. Partial stock, unknown stock, a passed cut-off, or an allergen does not become a silent substitute. The door gives a reason and asks the chef.” | Point to the exception line and alternative panel. If the live take shows a different real reason, use that exact reason. | J4 robustness |
| 2:15–2:35 | **Zoha:** “Gemini handles the photo and the uncertainty score. The deterministic door still owns money, stock, dates, mandates, and approval. Any agent can use the same door through OpenAPI or MCP.” | Show the Gemini score on the result, then the architecture slide’s OpenAPI/MCP labels. Explain that OpenAPI is a shared web interface and MCP is a tool connection for agents. | J2; J3; J5 |
| 2:35–2:48 | **Omar:** “Codex built the engine and the agent you just watched, with 29 ‘Built by Codex’ commits on main. CRACI runs the build checks and records the build evidence.” | Point to `docs/CODEX.md`, then the CRACI evidence/build line. Do not claim live CRACI status unless the endpoint is verified. | Codex prize; CRACI prize |
| 2:48–3:00 | **Zoha:** “Agents knock. The door checks. The chef decides.” **Omar:** “And the order is confirmed.” | Return to the green `Ordered` card and signed result. | Close; all criteria |

## Where to point for J1–J5

- **J1 — working end to end:** point to the photo read, progress states, live quote, held card, approval tap, and final audit entry.
- **J2 — solves the user need:** point to the 06:00 story, the handwritten list, the delivery date, and the fact that the chef gets a checked cart without typing every item.
- **J3 — autonomy and controls:** point to `Needs your OK`, the €1,500 limit, the agent session without approval power, and the approver’s tap.
- **J4 — robustness:** point to the exception reason and alternative. Say plainly that unknown or unsafe data becomes a question, not a guess.
- **J5 — openness and production path:** point to the signed statement, build evidence, OpenAPI/MCP labels, and the repo files [`docs/CRACI.md`](../CRACI.md), [`docs/GEMINI.md`](../GEMINI.md), and [`docs/CODEX.md`](../CODEX.md).

## Wi-Fi fallback

If the live page has not advanced after 10 seconds, Omar says: “The live path is slow, so we are switching to the recorded real take of the same photo flow.” Start the public video at the photo capture and narrate the same sequence over it: read → checks → exception → held → chef approval → signed result.

If the video cannot load, show the local screenshots in this order: photo read, result with exception, held card, approval tap, signed order. The spoken claims stay the same, but every number must come from the screenshots. Do not switch to voice unless the photo backup is also unavailable; voice is a backup take, not the peer-review demo.
