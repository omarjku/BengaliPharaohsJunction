# Front Door: design rationale (for critique)

**Who it's for.** A chef between services, often on a phone, often with wet hands. The screen has one job: answer "Do I need to do anything?" as fast as possible.

These are the decisions worth arguing with. To change one, start with the tokens at the top of `frontend/src/index.css` (colour, type scale, spacing, radius, easing). All the chef-facing wording is in `frontend/src/copy.ts`.

## 1. The answer is a sentence, and it's the only big thing
After a run, the page shows a status word ("Needs your OK"), then the decision as one sentence in large type ("€60 over your €1,500 limit."), then the amount and one action. Nothing else on the page is large or coloured, so the eye has nowhere else to go.
*Trade-off:* the reasons behind the sentence sit one tap away. When the backend gives several reasons, only the first becomes the headline.

## 2. Type and space carry the hierarchy, not boxes
There are no cards, no shadows, no pills and no badges. Sections are separated by whitespace and a few hairlines. Hierarchy comes from four text sizes (40 / 22 / 17 / 15 px) and three ink tones. The layout is one left-aligned column, 640px wide, on desktop too, because a decision reads better as a short page than as a dashboard.
*Trade-off:* desktop looks sparse. That's deliberate: the chef shouldn't have to scan.

## 3. The system font, on purpose
On the chef's iPhone it renders as SF, which feels native, loads instantly and has proper tabular figures for prices. On Windows it renders as Segoe.
*Open question for Zoha:* a characterful face (e.g. a humanist grotesk) might give more identity. It would only matter in the answer sentence.

## 4. Progressive disclosure for everything that isn't the decision
"Why this lactose-free milk", "Other options (2)", "Also worth knowing" and "What the agent understood" are native `<details>` elements. They work with the keyboard and screen readers, and they animate their height where the browser supports it. The facts (on-time rate, origin, CO₂) are written as sentences inside "Why this…", not as tags.

## 5. Gemini confidence in one voice
Everywhere it says "Matched by Gemini · 95%", or "Gemini's best guess · 72%, please check" in amber, followed by Gemini's own reason. "Why this…" says once what the number means: below 80%, the agent asks you first. Percentages are floored the same way the backend floors them, so 79.9% never reads as 80%.

## 6. Thumb-zone actions on a phone
When an order needs approval, a bar fixed to the bottom of the screen holds "Approve €1,560.00" (full width, 48px tall) and "Reject". It respects the iOS safe area. On desktop the same buttons sit inline under the answer. The amount sits on the button, so you can't approve without seeing it.

## 7. Calm motion only where something changes
- The answer fades and rises 6px over 220ms ease-out.
- The phone action bar slides up from the bottom.
- Buttons scale to 0.97 when pressed.
- The disclosure chevrons rotate.

Nothing moves on its own except the thin progress line while the agent works. Under `prefers-reduced-motion`, only opacity and colour transitions remain.

## 8. Human copy, and real data only
- Statuses are words: "Ordered", "Needs your OK", "Not ordered", "Rejected".
- Errors say what happened and what to do ("Can't reach the ordering service…").
- History reads as an activity feed ("Chef Aino approved the order"), grouped Today, Yesterday, then by date.
- Keys are a one-time first-run step with one sentence per key and Show/Hide toggles; after that they live behind a small "Keys" link.
- No invented numbers anywhere. The buyer name comes from the history, because the API has no "who am I" call. Mandate limits appear only where a reason names them.

## After critique #1 (`CRITIQUE-1.md`)
- **Status words are honest.** Red "Not ordered" only when nothing can be done. Amber "Your call" whenever an action is waiting: approval, a short-stock split, a low-confidence guess. Neutral "Ready to order" for a menu cart, where no rule fired. Green "Ordered".
- **No dead ends.** A low-confidence result offers "Order it · €250", "Not this one" (back to the field, cursor at the end) and "Order this instead" on each option that can be ordered. A short-stock result leads with "Valio has 640. Top up with 360 organic?" and one "Order both · €5,246".
- **One primary per screen.** After a result, "Ask the agent" becomes a quiet "Ask again". On a phone the composer folds into a 48px summary row ("1200 L lactose-free milk… · Mon 16 Nov · Edit").
- **The outcome is the headline.** After approval: "Ordered for Mon 16 Nov.", then "Chef Aino approved · 05:26" and "Arrives Monday, in 2 days." The Approve button briefly turns into a green "Ordered ✓".
- **Read before approving.** On a phone, the bottom action bar appears only after the reasons above it have been on screen. In the menu, "Order this cart" comes after the cart, not above "check them".
- **An opening screen that answers "do I need to do anything?"** "Morning, Chef Aino. Nothing waiting for you." The waiting count is checked against each order's real status, not guessed from the history. Below that: the question at 40px, "Try:" examples, and the last three requests.
- **History reads per request.** One row per request, titled with the chef's words and its final outcome, with the steps (agent, Valio, chef) inside and no UUIDs.
- **Identity.** Warm paper `#FBFAF7` with white fields. A small door glyph, the product's name drawn, not decoration. Tabular figures in headline money. Disabled buttons are grey, not pale blue. Reject is grey, 16px from Approve; red is for results only.
- **Names and copy.** Catalogue names are tidied (no ®, "1 L", no "Suomesta", no SHOUTING). "excl. VAT", "640 packs", "Stock not confirmed", "Also works". Thresholds read "below the 80% it needs to order on its own".
- **Phone header.** The brand gets its own line and the five destinations sit on the next, so nothing wraps.

## One box for everyone
A kebab shop ordering döner meat shouldn't be asked "for how many guests". So there's one field. Its grey placeholder cycles slowly through three real examples: a milk order, döner meat for the rotisserie, and a menu for 80 guests. It stays still under reduced motion, and it's never real text. The same examples are the "Try:" links.
- **The date.** It comes from the words ("Friday") when the backend finds one. The small "Delivery Mon 16 Nov" control shows the date that will be or was used, and only overrides it if the chef picks one.
- **What happens next depends on what was asked.** An order shows the usual answer. A menu shows "A cart for 80 guests, €…". A menu without a guest count asks one thing: "For how many guests?", with the number field right there. The answer goes into the box and the agent reads it again. An unclear request asks for more in plain words.
- **Navigation is Order · History · Rules · Keys.** There's no separate Menu tab.

## Known gaps
- Product names come straight from Valio's catalogue ("Valio Eila® 3 % milk drink 1 l lactose free"). Cleaning them up would need a naming pass in the data.
- History can't tell "Valio held for your OK" apart from "Valio refused" when the front door's outcome was an ask, because the audit entry doesn't store the order status. The opening screen's waiting count avoids this by checking each order's real status.
- The rule compiler never produces an on-time delivery rule from plain language. Saving rules drops it, though only after the "Looser" confirm.
- The `<details>` height animation needs Chrome 131 or later. Safari opens the sections instantly.
