# Front Door: final demo video script

**Target:** 1:57. **Hard cap:** 2:00. **Format:** public video, one real photo-flow take, Omar and Zoha speaking over the recording.

The story starts at 06:00: a chef has 500 guests, a delivery cut-off is approaching, and the kitchen cannot afford a wrong order. It ends with the chef in control and the order confirmed.

## The handwritten list

Write this on one sheet. Keep the bilingual wording clear and large:

```text
ORDER FOR MONDAY · 500 GUESTS
1000 l lactose-free milk
25 kg potatoes
20 kg rice
15 kg unsalted butter
30 kg mozzarella
10 kg wheat flour
60 l Arla lactose-free whole milk drink
```

The last line is the exception test. Before recording, confirm that the live result shows a real stock or delivery exception, such as partial stock, unknown stock, or a passed cut-off, with a reason and an alternative. If the live catalogue gives a different reason, narrate the reason on screen; never invent one. The 1,000-litre milk line should also make the order exceed the kitchen’s €1,500 auto-approval limit, so the held card is visible.

## Timed script

| Time | Speaker and words | What is on screen |
|---|---|---|
| 0:00–0:08 | **Zoha:** “It’s 06:00. Five hundred guests arrive today, and the delivery cut-off is closing. One wrong guess could stop service.” | Close shot of the chef’s hand, the list, and a clock reading 06:00. Keep the list readable. |
| 0:08–0:16 | **Omar:** “So the chef takes one photo. Front Door reads it, checks Valio, and puts the decision back in the chef’s hands.” | Phone opens the photo flow. Small title: `Front Door · Valio Aimo · Junction 2026`. |
| 0:16–0:28 | **Zoha:** “This is one live take. Gemini reads the handwriting, finds the seven items, and keeps the kitchen exception visible instead of guessing.” | Phone camera → photo captured → read result. On-screen once: `GEMINI · photo read + Decisions score`. Show the exception line and its status. |
| 0:28–0:40 | **Omar:** “The agent now checks the catalogue, live prices, stock, delivery date, and pack sizes. The score you see is a check on what the chef meant.” | Progress states, then at least one real Decisions score, live quote, units, stock, and requested delivery date. Speed up waits only with a small `×4` badge. |
| 0:40–0:52 | **Zoha:** “The milk line is €1,560, above the kitchen’s €1,500 limit. The door holds the cart for the chef.” | Held order card. Make the milk line, total, `Needs your OK`, and `€1,500 limit` readable. Show the exception reason and alternative panel too. |
| 0:52–1:04 | **Omar:** “The short or uncertain line is not silently replaced. The card explains the problem and shows the safe next choice.” | Scroll to the exception line. Show the actual stock or cut-off reason, the alternative, and the held status. Do not show a made-up substitute. |
| 1:04–1:12 | **Zoha:** “The agent cannot approve. The chef can.” | Second phone or approver view. Finger taps **Approve**. The card changes to `Ordered`. |
| 1:12–1:20 | **Omar:** “Now the order is confirmed, signed, and recorded for the kitchen and Valio.” | Green `Ordered` card, audit entry, then signature verification. Show the build line if the live app provides it. |
| 1:20–1:32 | **Zoha:** “This is why Gemini matters here: it does not just write a reply. Its Decisions score sets when the agent may act alone; code still controls money, stock, dates, and approval.” | A simple 0.70 threshold graphic beside the real score from the take. Caption: `Confidence can ask; it cannot grant permission.` |
| 1:32–1:42 | **Omar:** “Codex built the core we just used: the engine, the Gemini agent, and the safety paths. The main branch records 29 commits marked ‘Built by Codex’.” | On-screen once: `CODEX · 29 “Built by Codex” commits on main`. Show the real `git log` result, then the chat-agent and approval screens. |
| 1:42–1:50 | **Zoha:** “CRACI runs the build checks and ties the order to its build evidence: the SBOM, vulnerabilities, and network trace.” | On-screen once: `CRACI · this build’s SBOM + network trace`. Show the live `/.well-known/front-door-build.json` only if it has `status: ok` and a non-empty `sbom_sha256`; otherwise show the CI-on-CRACI fact and remove the live-evidence claim. |
| 1:50–1:57 | **Omar:** “The order is confirmed.” **Zoha:** “At 06:00, the chef is still in control.” | Return to the chef’s phone: green `Ordered`, the signed order, and the chef’s hand. End card: `Agents knock. The door checks. The chef decides.` Repo URL and `Valio challenge mock · no real orders or payments`. |

## One-take rules

- The real take runs from the photo capture through the held card, approval tap, and signed result. Keep it continuous and label it `LIVE · one take`.
- Do not paste in a result, change an amount, or splice a different order into the take. Speed up only waiting screens, with `×4` visible.
- Keep the two phones and the final signature in the same chronological order. Omar drives the screens; Omar and Zoha record the voiceover to picture afterward.
- Voice ordering is a backup take only. It is not part of the main cut.
- Burn in captions and upload the matching `.srt`. Keep every spoken line in the 1:57 timing.

## Evidence to verify before export

- The photo read shows the seven list items and the exception reason.
- The held card shows the real milk price or real cart total, the €1,500 limit, and `Needs your OK`.
- The chef’s approval tap changes the card to `Ordered`; the agent key is not used to approve.
- The signed result and audit entry are visible.
- The Gemini, Codex, and CRACI labels each appear once, with the concrete fact stated above.
- The video is public, opens in a private window, and is no longer than 2:00.
