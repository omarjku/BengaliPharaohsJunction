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
| Type a request, press Ask (or Cmd/Ctrl+Enter, or a "Try:" example) | Button "Asking…" | App `submit` → `ask(text)` | `POST /api/agent/ask/stream` (SSE: `phase` events, then `result` or `error`); falls back to `POST /api/agent/ask` only if the stream never opened (404/405) |
| Progress | One calm line, each step at least 400 ms ("Reading your request…", "Searching Valio's catalogue…", …), read out politely | App `phaseLine` (`usePhaseLine`) in `.working[role=status]` | the SSE `phase` events |
| Stream drops mid-way | "The connection dropped… Check History before asking again" (never retried, so no double order) | `api.askAgentStream` throws `DROPPED` | none |
| Delivery day | "Delivery Mon 16 Nov · or the day you write", a native date picker | App `date` / `dateSet` | sent as `requested_date` only when picked |
| Result: ordered / your call / not ordered | Status, a headline, what and how much, total, the Gemini line ("Matched by Gemini · 84%"), "Sent to Valio's front door: confirmed · See it in History" | `RunResult` | (from the ask response) |
| Result: menu | "A cart for 80 guests, €…", the cart per ingredient, "Order this cart · €…" | `MenuResult` | (from the ask response) |
| Phone, after a result | The box folds into one row ("… · Mon 16 Nov · Edit"); action bar at the thumb once the reasons are seen | App `collapsed`, `.decide.floating` | none |

## 3. Answering the agent's question (follow-ups)

| Step | What the user sees | Component · handler | API |
|---|---|---|---|
| A question that can be answered here (`conversation_id`) | The question, an answer box (with the mic inside it) and Send; Enter sends | `Question` → `onAnswer` → App `ask(words, convo)` | `POST /api/agent/ask/stream` with `{"text": "", "follow_up": {"to": conversation_id, "answer": "…"}}` |
| While the answer is sent | The question **stays**, with "Sending…", inputs disabled, the progress line; then the new result replaces it | App `ask` keeps `result` when `to` is set | as above |
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

## 7. Voice, Talk and photo

| Step | What the user sees | Component · handler | API |
|---|---|---|---|
| Mic (first time) | A short note: "Hold to order by voice…" + Start talking / Not now; then the browser's mic prompt | `MicButton` → `useVoice.start` (intro), `acceptIntro` | none |
| Mic: phone | Tap to start ("Listening… tap the mic to send."), tap again to send | `MicButton` (`pointerType === 'touch'`) | `POST /api/voice/transcribe` (body: the recording, X-Agent-Key) |
| Mic: desktop | Hold to talk and let go to send, or tap to toggle; Enter/Space toggles | `MicButton` `down` / `up` / `key` | as above |
| The words | Appear in the box, then go as if typed | App `useVoice(… onText)` → `ask(words)` | ask |
| Read-back | The backend's `speak` sentence spoken in the request's language (unlocked by the first tap on iOS); "Read aloud. Mute" | `useReadBack.speak`, `unlockSpeech` | none |
| A spoken question | It's spoken, then the mic opens by itself: "Listening for your answer… tap the mic to send. Cancel" | App effect → `voice.start(true, true)` | follow_up |
| Voice failures | "The microphone is blocked. You can type instead…", "I didn't hear any words…", "Couldn't start the microphone…" | `VoiceStatus` | — |
| One voice button (for the order box) | `<VoiceButton voice={voice} talk={{ available: caps.talk, open: talk.open }} disabled={…} />`: opens Talk when /api/health says talk: true, else it is the push-to-talk mic | `VoiceButton` (`Voice.tsx`) | as Talk / as the mic |
| Talk | "Talk" opens a full-screen conversation: a circle (listening / checking / speaking), captions, "Checking Valio prices…", the result card (approve on screen), **End** | App `openTalk` → `Talk` | WebSocket `/api/live` (auth message first; PCM16 audio both ways) |
| Photo (inside the box) | `<PhotoButton variant="icon" …/>`: a round 44 px camera button like the mic; what was read floats under the box with a close button | `PhotoButton` | as Photo |
| Photo | "Photo" (camera or library) → "Reading your photo…" with a thumbnail → what was read and what couldn't be → the text goes into the box and is asked | `PhotoButton` → `onRead` → App `ask(text)` | `POST /api/vision/read` (multipart `image`, X-Agent-Key) |

## How to check it

- Mock mode needs no backend: `npm run dev`, then open `http://localhost:5173/?mock=1`. It covers most rows (milk 1000 L = approval, butter = ordered,
  "1000 kg butter" = split, "döner" = best guess, a menu, "ASAP" = urgent options, Rules, History, Valio view, Talk).
- Real backend: `frontend/scripts/` has dev-only scripts: `qa.mjs` (axe + phone widths), `keyboard.mjs`,
  `capture.mjs` (screenshots), `followup.mjs` (questions and answers), `voice-e2e.mjs` (voice in headed Chrome).
