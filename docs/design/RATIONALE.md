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

## 5. Gemini confidence as plain language, the number second
"Sure this is what you meant · 0.95". When Gemini is unsure, its own reason replaces the generic sentence ("A fat-free UHT drink; 'milk drink' could also mean the regular Eila drink · 0.72"), shown in the warning colour. The number is floored the same way the backend floors it, so 0.799 never reads as 0.80.

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

## Known gaps
- Product names come straight from Valio's catalogue ("Valio Eila® 3 % milk drink 1 l lactose free"). Cleaning them up would need a naming pass in the data.
- History can't tell "Valio held for your OK" apart from "Valio refused" when the front door's outcome was an ask, because the audit entry doesn't store the order status.
- The `<details>` height animation needs Chrome 131 or later. Safari opens the sections instantly.
