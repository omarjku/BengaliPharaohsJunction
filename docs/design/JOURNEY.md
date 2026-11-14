# Customer journey: acceptance checklist

Every step a chef (or Valio's staff) can take, what they see, which code does it and which API it calls. A redesign
must keep every row working: same action, same call, same feedback. Restyle freely; don't drop a row.

Files are in `frontend/src/`. "App" is the `Screen` component in `App.tsx`.

## Rules that apply to every row

- **No dead ends.** Every question has a way to answer it; every option the agent shows that Valio can deliver has a
  button. A step that can't continue says why, in plain words, and what to do next.
- **Every button shows it's working** ("Ordering…", "Sending…", "Asking…") and is disabled while its request runs.
- **Every failure is visible** in plain words, with the backend's own `detail` where it gives one (`errorText`,
  `.problem[role=alert]`). Nothing fails silently.
- **Accessibility:** visible focus, controls at least 44 px, screen-reader announcements (the `aria-live` region in App
  and `role=status` on the progress line), reduced motion respected, Finnish and English (`copy.ts` / `copy.fi.ts`).
- **Keys** are only in `localStorage` (`valio-aimo-keys`, `valio-aimo-admin-key`) and the request headers, never in
  URLs or on screen.

## 1. Keys and getting in

| Step | What the user sees | Component · handler | API |
|---|---|---|---|
| First visit, no keys | "Before your first order" with Agent key and Approver key fields (Show/Hide) | App `needsSetup` → `KeysForm` → `setKeys` | none (stored locally) |
| Change keys | "Keys" in the nav opens a sheet | App `keysDialog` → `KeysForm` | none |
| Order button pressed with no agent key | "Enter your keys first (Keys, at the top)." | `RunResult.run_`, `Menu.orderCart` | none |
| Approve with no approver key | Approve disabled + "Add your approver key under Keys to approve." | `RunResult` `canDecide` | none |
| Wrong key | "Enter a valid agent key in Keys. …" / "Approver key needed …" | `api.failureFrom` (401/403) | any |
| Backend down | "Can't reach the backend…" banner | App `useBackendDown` | `GET /api/health` |
| Language | FI / EN in the nav; remembered | `App.switchLang` → `CopyContext` | none |

## 2. Asking

| Step | What the user sees | Component · handler | API |
|---|---|---|---|
| Type a request in the bar, Enter or the send arrow (a "Try:" chip fills the field) | Your message as a bubble on the right, then the progress line in the thread | `Composer` → App `send` → `ask(text)` | `POST /api/agent/ask/stream` (SSE: `phase` events, then `result` or `error`); falls back to `POST /api/agent/ask` only if the stream never opened (404/405) |
| Progress | One calm line, each step at least 400 ms ("Reading your request…", "Searching Valio's catalogue…", …), read out politely | App `phaseLine` (`usePhaseLine`) in `.working[role=status]` | the SSE `phase` events |
| Stream drops mid-way | "The connection dropped… Check History before asking again" (never retried, so no double order) | `api.askAgentStream` throws `DROPPED` | none |
| Delivery day | Said in the words ("for Monday"), or the agent asks "For which delivery day?" with day chips (the date picker is gone) | App `ask` | `requested_date` only for re-asks from a card (same day) |
| Result: ordered / your call / not ordered | Status, a headline, what and how much, total, the Gemini line ("Matched by Gemini · 84%"), "Sent to Valio's front door: confirmed · See it in History" | `RunResult` | (from the ask response) |
| Result: menu | "A cart for 80 guests, €…", the cart per ingredient, "Order this cart · €…" | `MenuResult` | (from the ask response) |
| More than one result | The newest card is full and actionable; earlier ones fold to "Your call: … Open" (tap to reopen, state kept); the agent's `speak` sentence sits above each card | App `renderRes`, `Conversation.css` | none |

## 3. Answering the agent's question (follow-ups)

| Step | What the user sees | Component · handler | API |
|---|---|---|---|
| A question that can be answered here (`conversation_id`) | The agent's message with its one-tap answers; anything else is typed (or dictated) in the bar, whose placeholder says "Type your answer" | `Question` chips → `onAnswer`; the bar → App `send` → `ask(words, convo)` | `POST /api/agent/ask/stream` with `{"text": "", "follow_up": {"to": conversation_id, "answer": "…"}}` |
| While the answer is sent | Your answer as a bubble, the progress line, then the new card or question below | App `ask` | as above |
| "For which delivery day?" | Six one-tap day chips (Mon 16 Nov, …) plus the box | `Question` `nextDays` → `onAnswer('16.11.')` | follow_up |
| "Which one did you mean: 1) A; 2) B; 3) C?" | "Which one did you mean?" with the products as one-tap chips | `Question` `options` → `onAnswer('2')` | follow_up |
| "For how many guests?" | A number box + "Plan the cart" | `GuestsQuestion` → App `answerGuests` | follow_up (or the number appended, if no conversation) |
| "You ordered this 1 minute ago. Order again?" | **Order again** / No, leave it | `Question` `again` → App `orderAgain` / `leaveIt` | follow_up "Order again" (or the text + " again") |
| The question expired (404) | "That question expired. Please ask again." + **Ask again** (re-sends the original words) | App `expired` | `POST /api/agent/ask/stream` with the original text |
| A question that can't be answered inline (off-topic, a date in the past, two different dates) | The question + **Edit your request** (cursor back in the box) | `Question` → App `retry` | none |

## 4. Choosing and ordering

| Step | What the user sees | Component · handler | API |
|---|---|---|---|
| Agent's best guess, not sure | "Order it · €…" / "Not this one" | `RunResult` `guess` → `place([lineOrder])`; `onRetry` | `POST /api/orders` (X-Agent-Key) `{requested_date, lines:[{product_id, quantity}]}`, quantity in that product's sales units |
| Other options (lines the agent didn't choose) | "Other options (n)": each orderable one has **Choose this** ("Ordering…" on that button) | `OtherOption` → `place([lineOrder(l)], id)` | `POST /api/orders`; the front door's verdict replaces the main card |
| When "Choose this" is offered | Until something is ordered or waiting for the chef's OK (also after a refusal, a rejection or a declined run) | `RunResult` `canChoose` | none |
| Substitutes (Valio refused a line) | "Other choices Valio has", each with **Choose this** (same unit: the refused line's amount) or **Ask for this instead** (other pack size) | `Substitutes` → `pickSub` → `place(...)` or `onAskFor(text)` | `POST /api/orders`, or a new `ask` for that product (same delivery day) |
| Split order (stock short) | "Valio has 640. Top up with 360 …?" with the two rows + **Order both · €…** | `RunResult` `split` → `place(split.order_lines)` | `POST /api/orders` with `alternative_order.order_lines` verbatim |
| Menu cart: swap a product | Under an ingredient, "Other options (n)": **Choose this** swaps it into the cart; total and order follow; choosing the agent's pick again undoes it | `MenuResult` `choose(i, l)` | none until the cart is ordered |
| Menu cart: doubted lines | "Check this: not in the order yet." + **Add to the order** / Undo | `MenuResult` `toggleAdd` (lines with `check: true`) | none until ordered |
| Order the menu cart | "Order this cart · €…" | `MenuResult.orderCart` | `POST /api/orders` with `order_lines` plus the chef's swaps and additions |
| Need it sooner (urgent) | "Need it sooner?": walk-in (address, hours, **tel:** link "010 381 7645"), Click & Collect, next delivery. Suggestions only, never an order | `UrgentOptions` | none |

## 5. Deciding (the chef's OK)

| Step | What the user sees | Component · handler | API |
|---|---|---|---|
| Decision card | A header strip (status + delivery day), the headline, "Decided by your order limit." (from `primary_reason`), the items table (product, amount, unit price, total; stacked on a phone), the Gemini line, why / other options / what the agent understood below | `RunResult` (+ `RunResult.css`) | (from the ask response) |
| Held for your OK, one option | "Your call", the reason ("€60 over the €1,500 order limit."), **Approve · €…** / Change quantity / **Decline** (thumb bar on a phone) | `RunResult.decide('approve' / 'reject')` | `POST /api/orders/{id}/approve` or `/reject` (X-Approver-Key, no body) |
| Held for your OK (or a best guess), two or more deliverable options | "Pick one": option cards with real tags only (**Best match** = the agent's pick, **Cheaper** = lower total, **Local** = origin FI), then **Approve selected · €…** / Change quantity / Decline | `RunResult.approveSelected`: the held order → approve; another option → reject the held order, then order the chosen one | `POST /api/orders/{id}/approve`, or `/reject` + `POST /api/orders` |
| Compare options | On any result with 2+ deliverable options, **Compare options (n)** opens up to 4 side by side (swipe on a phone): unit price, total, arrives, order by, stock, on time, origin, CO₂ per kg, match, labels, allergens; best value per row marked; missing = "not reported". **Approve this** (the held order) / **Choose this** | `Compare` (`Compare.tsx`, `Compare.css`) → `RunResult.chooseFromCompare` (same path as Approve selected; after a refusal or rejection: `place`) | `POST /api/orders/{id}/approve`, `/reject` + `POST /api/orders`, or `POST /api/orders` |
| Change quantity | "New amount" + Ask again: the same product, the new amount, the same delivery day | `RunResult.changeQuantity` → App `onAskFor` | `POST /api/agent/ask/stream` |
| After the decision | "Ordered ✓" briefly, then "Ordered for Mon 16 Nov.", "Chef Aino approved · 14:05" | `RunResult` `signOff` | `GET /api/orders/{id}` (signed_off_by) |
| The order changed (409) or was already decided | The backend's message in the card; nothing changes silently | `RunResult.run_` catch | as above |
| Waiting count on the empty screen | "Good afternoon, Aino. 2 orders are waiting for your OK in History." | App `waiting` | `GET /api/orders/{id}` per held order |

## 6. What the agent knows

| Step | What the user sees | Component · handler | API |
|---|---|---|---|
| Profile's dietary default (`PROFILE_DEFAULT`, INFO) | "Gluten-free, because your profile says: Our kitchen is gluten-free." + **Not gluten-free this time** | `RunResult` `profileNote` → `onPlain` → App `ask(text + " (regular, not gluten-free)", runDate)` | `POST /api/agent/ask/stream` |
| Usual products (`line.usual`) | "You usually order this" on the chosen product, menu cart rows and option rows | `RunResult`, `OtherOption`, `MenuResult` | none |
| What I know about your kitchen | Rules screen, closed until tapped: dietary needs (with why), usual products, count from past orders. Read-only | `Rules` → `KitchenProfile` | `GET /api/profile` (X-Agent-Key) |
| Rules in plain words | Current rules, edit the text, **Check the changes** (nothing saved yet), **Save rules**; loosening needs a second yes; someone else saved first (412) shows their rules | `Rules` `check` / `save` | `POST /api/mandate/compile`, `PUT /api/mandate` with `If-Match` (412 on conflict) |
| History | Requests grouped by day, outcome per request, steps inside | `AuditLog` (`history.ts` `groupHistory`) | `GET /api/audit` (X-Approver-Key) |
| Valio view (Valio staff only) | "Valio view" link asks for the admin key; feed per kitchen, security events in red, filters, **Check the signature** → "Signed by the front door ✓" | `ValioView` | `GET /api/admin/audit` (X-Valio-Admin-Key), `POST /api/verify` |

## 7. The conversation screen: text, voice + text, voice only

One thread for all three modes (`Conversation.tsx`, `Composer.tsx`, `Orb.tsx`, `useLive.ts`, `useTalk.ts`). Decisions
are never chat bubbles: every result is the decision card in the thread.

| Step | What the user sees | Component · handler | API |
|---|---|---|---|
| Text only | The thread (your messages right in a bubble, the agent's lines left), the bar at the bottom: **+** (photo), the field, the **mic** (dictation), the round **voice** button | `Conversation`, `Composer` | ask, as above |
| Dictation (mic) | Tap to start, tap again (or let go of a hold on a desktop): the words land in the field to edit and send. "Listening… tap the mic to send." above the bar | `MicButton` → `useVoice` → `setText` | `POST /api/voice/transcribe` |
| Photo (+) | Camera or library → "Reading your photo…" with a thumbnail → what was read → the text is sent as your message | `PhotoButton variant="icon"` → App `send` | `POST /api/vision/read` (multipart `image`) |
| Start voice | The voice button: dictation stops, the big orb appears (thread hidden) | App `startVoice` → `voice.cancel()`, `useTalk.open` (inside the tap: AudioContext + mic, iOS) | WebSocket `/api/live` (auth message first) |
| Voice only | The big orb in the middle: listening (follows your voice), thinking (with the tool line, e.g. "Checking Valio prices…"), speaking; the bar: +, the field, **mute**, **X** | `Orb size="big"`, `useLive` | audio both ways (PCM16) |
| Voice + text | Tap the orb (or "Show the conversation"): the thread with live words (a dot marks the reply being formed), a small orb above the bar; tap it (or "Voice only") to go back; the last layout is remembered | `Orb size="small"`, App `toggleLayout` (`valio-aimo-voice-layout`) | as above |
| Typing while voice is on | Your words go over the socket | App `send` → `useLive.sendText` | `{"type":"text"}` |
| Mute | The mic stops sending; the session stays ("Microphone off.") | `useLive.setMuted` | no audio chunks |
| A result by voice | The decision card in the thread (Approve / Choose / Decline on the card: the voice agent can't approve) | `useLive.onResult` → App `push` | `{"type":"result"}` |
| End voice (X) | Back to text only; the thread is kept | `useTalk.end` (stops the mic, closes the audio) | `{"type":"stop"}` |
| Voice failures | "The microphone is blocked…", "The conversation ended. Tap Talk to start again.", the server's error, as an error in the thread; the orb turns red | `useLive.onError` | — |

## How to check it

- Mock mode needs no backend: `npm run dev`, then open `http://localhost:5173/?mock=1`. It covers most rows (milk 1000 L = approval, butter = ordered,
  "1000 kg butter" = split, "döner" = best guess, a menu, "ASAP" = urgent options, Rules, History, Valio view, Talk).
- Real backend: `frontend/scripts/` has dev-only scripts: `qa.mjs` (axe + phone widths), `keyboard.mjs`,
  `capture.mjs` (screenshots), `followup.mjs` (questions and answers), `voice-e2e.mjs` (voice in headed Chrome).
