# Front Door: five-minute peer-review run of show

The live peer review is five minutes. Zoha tells the story and narrates. Omar drives the phone and laptop. The public video is a short proof cut; the audience then sees a fresh live run and one robustness check.

## Before the five minutes

- Open the public video and cue it at the start. Keep a local copy and the local screenshots in the same order.
- Warm `https://valio-front-door.onrender.com`. Use the seeded `lapland-kitchen` buyer, its agent key, and its approver key.
- Reset only `lapland-kitchen`. Confirm the €1,500 limit, the list, the Talk button, and the approval view.
- Keep the Finnish list from [`demo-take-checklist.md`](demo-take-checklist.md) on the table. Keep the signed result and audit view one tap away.
- Decide the live exception from the fresh result. Show the exception the mock actually returns. Do not force a partial-stock, cut-off, or allergen claim that the current quote does not return.

## Timed run

| Time | Duration | Who says or does what | What the audience must see |
|---|---:|---|---|
| 0:00–0:10 | 10 s | **Zoha:** “It is 06:00. Five hundred guests, a closing delivery cut-off, and a handwritten order. The chef needs speed without losing control.” | Zoha holds up the Finnish list. |
| 0:10–1:22 | 72 s | **Zoha:** “This short cut is the same real photo flow we will run now.” Play the video from **0:00–1:12**: cold open, door, live photo, read, quote, Talk change, hold, approver tap, signed result. | The public video proves the complete path and the tagline. |
| 1:22–1:40 | 18 s | **Omar:** “Now we reset one seeded buyer and do the photo again. The photo is data; Gemini reads it, and the door still owns the checks.” **Zoha** points to the `LIVE · one take` screen label. | Omar opens the app and shows the clean buyer state. |
| 1:40–2:10 | 30 s | **Omar** photographs the list and sends the read request. **Zoha:** “The phone reads Finnish lines and turns them into a cart request. Watch the selected product, unit, date, price, and stock.” | Photo result, seven item lines, progress, and live quote. |
| 2:10–2:30 | 20 s | **Zoha:** “This is the real hold: [say the visible reason]. The card explains it instead of guessing.” **Omar** points to `Needs your OK`, the limit or exception, and any returned alternative. | One real spend, stock, cut-off, unknown-stock, or diet/allergen exception. |
| 2:30–2:55 | 25 s | **Omar** taps Talk and says: “Change the potatoes to 30 kilograms.” **Zoha:** “The pending cart changes, but it is still held.” | User transcript, changed quantity, pending status. |
| 2:55–3:10 | 15 s | **Omar** says: “Approve this order.” **Zoha:** “The voice agent cannot approve. Approval stays on the screen.” | The refusal or instruction to tap the on-screen approval. No order state change. |
| 3:10–3:35 | 25 s | **Omar** taps **Approve** with the approver view/key. **Zoha:** “The chef signs off. The same order is now ordered and audited.” | `Ordered`, signature verification, audit entry. |
| 3:35–4:15 | 40 s | **Zoha:** “We also test the door against an exception, not just the happy path.” **Omar** shows one fresh live exception. Use the order’s actual partial stock/cut-off/unknown-stock reason. If preflight confirms an allergen or diet rule, show that hold instead. | The reason, the affected line, and the safe question/alternative. No invented substitute. |
| 4:15–4:40 | 25 s | **Omar:** “Gemini supplies the photo and uncertainty score; deterministic code owns money, stock, dates, mandates, and approval. Codex built this path. CRACI runs the CI evidence.” **Zoha** points to the score threshold, `29 Built by Codex` commits, and `CI on CRACI`. | One proof card per tech track. Show a live CRACI hash only if the endpoint is `status: ok`. |
| 4:40–5:00 | 20 s | **Zoha:** “Agents knock. The door checks. The chef decides.” **Omar:** “The order is confirmed, signed, and recorded.” Both pause for the first question. | Final signed order, repo/video link, and `Valio challenge mock · no real orders or payments`. |

Total: **5:00**. The video cut is **1:12**. The fresh live run and the exception are the remaining proof.

## Which exceptions to show live

Show two controls live, plus one data exception:

1. **Approval control, always:** say “Approve this order” in Talk. The code has no voice approval tool. The agent must keep the card pending and direct the chef to the screen.
2. **The current photo’s real hold, always:** show the spend-limit hold if the `1000 l` line returns the known `€1,560 > €1,500` result. Otherwise show the actual partial-stock, unknown-stock, cut-off, or other returned reason.
3. **One additional data exception, only if preflight confirms it:** prefer an allergen/diet hold when the seeded kitchen rule and catalogue data make it real. If not, use a second partial-stock or cut-off case that the mock currently returns. Keep a screenshot of the alternative ready, but label it as a recorded/prepared case if it is not run live.

Do not run four full carts in five minutes. The audience needs to see the guardrail work, not a long queue of similar requests.

## Fallbacks

### Network or Gemini fails before the live result

Omar says: **“The live path is not returning, so we are switching to the recorded real take of this same photo flow.”** Start the public video at 0:14, the photo capture, and play through the signed result. Zoha narrates the visible read, quote, hold, approval, and audit. Do not apologise or claim the live path succeeded.

### The public video cannot load

Omar opens the local stills in this order: Finnish photo, Gemini read, live quote, hold with exception, Talk change, approval tap, signed order. Zoha says: **“These are the frames from the same continuous take; the numbers are the values shown in those frames.”** Use no number that is absent from a still.

### Talk fails but the photo flow works

Omar says: **“The order path is live; the voice path is unavailable on this connection. The recorded take shows the same pending-cart change and the on-screen approval boundary.”** Continue with the photo result, show the prepared Talk frame, and prove approval with the approver key. Do not pretend a typed change was spoken.

### The exception is not returned

Do not manufacture one. Show the actual hold reason from the card, or use the prepared, clearly labelled exception frame. The line is: **“The door reports the condition Valio returned; it does not invent a substitute.”**

## Roles and handoff

- **Zoha:** list/story, all spoken explanation, the visible exception reason, Gemini/Codex/CRACI proof cards, and the final tagline.
- **Omar:** app reset, photo capture, send, Talk transcript, approval tap, signed order, audit view, and all fallback switching.
- **Both:** stay for questions. If asked about a real order, say that this is the Valio challenge mock and no real purchase or payment is made.

