# Google Stitch prompt (UI draft for the demo)

Paste the block below into Google Stitch (stitch.withgoogle.com) as a web app, then export the HTML/Tailwind. Room 4 ports the look into our React UI; the data wiring stays ours.

---

Design a web app called **"Front Door"**: an approval console where a restaurant chef supervises an AI purchasing agent that orders food from the wholesaler Valio Aimo. This is NOT a chatbot. It's a calm, trustworthy operations console, Nordic and clean: lots of white space, one deep blue accent, a green / amber / red status palette, and a readable sans-serif. Desktop first, but it must work on a phone at 375px.

**Screen 1: Agent console (main screen)**
- Top bar: "Front Door" wordmark; the buyer, "Lapland Kitchen · Chef Aino"; a small "keys" icon button.
- Request card: a large text field, "What do you need?", with a placeholder like "1000 L lactose-free milk for Monday"; a delivery date picker; and a primary button, "Ask the agent".
- Decision card (the hero of the page). A big status chip that is one of: "Ordered" (green), "Needs your OK" (amber) or "Refused" (red). Below it, one sentence on why, e.g. "€1,560 is above your €1,500 auto-approve limit". Then a list of reasons, each with an icon and a suggested fix, and two buttons, "Approve" and "Reject", shown only when the status is "Needs your OK". Also show "Gemini confidence 0.96" as a small badge.
- Candidate products: a table or a stack of cards. Each row shows:
  - product name, brand, quantity ("1,000 × 1 L") and line total in €
  - Valio availability, for example "In stock, order by Sun 17:00", "Cut-off passed", or "Stock unknown"
  - a Gemini confidence pill (green if ≥ 0.8, amber below), with a one-line reason
  - small facts: "on time 97%", "origin FI 🇫🇮", "1.2 kg CO₂/kg"

  The chosen row is highlighted with a "Chosen" tag and a short "why this one". Rejected rows are greyed out, with the reason.
- Substitutes panel (shown when an item can't be ordered): three cards labelled Best / Better / Good, each with "why it's safe" (allergens, claims), price and reliability.
- Split-order proposal (shown when stock is short): "Only 51 L available, so split across 2 products". A mini table of the lines, the total, and a button, "Use this order".

**Screen 2: Audit log**
A vertical timeline of every decision for this buyer, newest first. Each entry shows the time, the actor ("Buyer agent", "Valio front door", "Chef Aino"), the outcome chip, the summary, and expandable reasons. A filter for outcome.

**Screen 3: Keys panel (a modal)**
Two password-style fields, "Agent key" and "Approver key", each with a short explanation: "The agent key lets the AI place orders. The approver key is yours: only you can approve." A Save button.

Tone of the copy: plain, short and confident. No marketing fluff, and no chat bubbles.
