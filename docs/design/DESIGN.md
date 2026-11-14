# DESIGN.md: Front Door

Design system for "Front Door", the approval console where a restaurant chef supervises an AI purchasing agent ordering from the wholesaler Valio Aimo.

## Overview
- **Personality:** calm, exact, trustworthy. An operations console for a working kitchen, not a chatbot and not a marketing page.
- **Feel:** Nordic and quiet. Lots of white space, thin borders, one blue accent. Colour is reserved for meaning: green, amber and red only ever signal an order's status.
- **Density:** comfortable. The chef reads it at a glance between tasks, so the decision is always the largest thing on screen.
- **Platform:** desktop web first (1280px wide content area, max 1120px), fully usable at 375px on a phone.

## Colors
| Token | Hex | Use |
|---|---|---|
| `text` | `#1C1F23` | Body text and headings |
| `muted` | `#5D6670` | Secondary text, labels, timestamps |
| `background` | `#F4F5F7` | Page background |
| `surface` | `#FFFFFF` | Cards, tables, modals |
| `border` | `#D9DDE2` | 1px card and table borders, dividers |
| `accent` | `#0B5CAD` | Primary buttons, links, focus rings, the chosen row's left edge |
| `accent-soft` | `#E7F0FA` | Chosen-row background, selected states |
| `good` / `good-bg` | `#1E7A3C` / `#E8F5EC` | "Ordered", confidence at or above the threshold |
| `warn` / `warn-bg` | `#8A5A00` / `#FFF4DC` | "Needs your OK", low confidence, unknown stock |
| `bad` / `bad-bg` | `#B3261E` / `#FDECEA` | "Refused", passed cut-off, allergen conflict |

Rules:
- Status colours always appear as a pair: dark text on its pale background, plus an icon or word. Never colour alone.
- No gradients, no dark mode, no brand colours other than the accent.

## Typography
- **Font:** Inter (fallback: system-ui, sans-serif). Numbers use tabular figures so prices and quantities line up.
- **Scale:** 28/34 semibold for the decision headline; 20/28 semibold for card titles; 16/24 regular for body; 14/20 for labels, table cells and pills; 12/16 medium, uppercase with 0.04em tracking, for small section labels.
- **Money and quantities:** semibold, right-aligned in tables, always with the unit ("€1,560.00", "1,000 × 1 L").
- Sentence case everywhere. No all-caps buttons.

## Shape, spacing and elevation
- **Radius:** 8px on cards, inputs and buttons; 999px on pills and status chips.
- **Spacing:** 4px base grid. 24px card padding on desktop, 16px on phone. 16px gaps between cards.
- **Elevation:** flat. Cards have a 1px `border` and no shadow. Only the keys modal has a soft shadow (0 8px 24px rgba(28,31,35,0.12)).

## Components
- **Status chip:** large pill with an icon and a word: "Ordered" (good), "Needs your OK" (warn), "Refused" (bad). It is the first thing in the decision card.
- **Decision card:** the hero. Status chip, one plain sentence on why, a short list of reasons each with an icon and a suggested fix, then the actions. A 4px left edge in the status colour.
- **Buttons:** primary is solid `accent` with white text; secondary is white with a `border`; the destructive "Reject" is white with `bad` text and border. Height 40px, 16px horizontal padding. One primary button per card.
- **Confidence pill:** "Gemini 0.96" in a small pill. `good` pair at or above 0.80, `warn` pair below. A one-line reason sits beside or under it.
- **Product row / card:** product name and brand on the left; quantity and line total on the right; under the name, an availability line ("In stock, order by Sun 17:00", "Cut-off passed", "Stock unknown") and small fact tags ("on time 97%", "origin FI", "1.2 kg CO₂/kg"). The chosen row has an `accent-soft` background, an `accent` left edge and a "Chosen" tag. Rejected rows are muted, with the reason in one line.
- **Substitute cards:** three cards in a row labelled "Best", "Better", "Good" (stacked on phone), each with a "Why it's safe" line, price and reliability.
- **Split-order proposal:** a bordered card with a compact table of lines, the total, and one primary button, "Use this order".
- **Audit timeline:** a vertical line with dots; each entry shows the time, the actor ("Buyer agent", "Valio front door", "Chef Aino"), a small status chip and a summary; reasons expand on click.
- **Inputs:** 40px high, 1px `border`, 8px radius, visible label above (never placeholder-only), 2px `accent` focus ring.
- **Fact tags:** small grey pills (`background` fill, `muted` text). Not interactive.

## Do
- Put the decision and its reason above everything else after a run.
- Say things plainly: "Above your €1,500 auto-approve limit".
- Show unknowns honestly ("Stock unknown"), never as zero or as "available".
- Keep every status readable without colour: icon plus word.

## Don't
- No chat bubbles, avatars, typing indicators or assistant personas.
- No hero images, illustrations, gradients or decorative icons.
- No marketing copy, exclamation marks or emoji in the interface.
- Don't hide the reasons behind a click: the top reasons are always visible.
