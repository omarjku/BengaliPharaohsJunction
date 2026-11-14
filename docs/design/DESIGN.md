# DESIGN.md: Front Door

Design system for "Front Door", the approval console where a restaurant chef supervises an AI purchasing agent ordering from the wholesaler Valio Aimo.

## Overview
- **Personality:** calm, exact, trustworthy. An operations console for a working kitchen, not a chatbot and not a marketing page.
- **Feel:** Nordic and quiet. Lots of white space, few borders, one blue accent. Colour is reserved for meaning: green, amber and red only ever signal an order's status.
- **Density:** comfortable. The chef reads it at a glance between tasks, so the decision is always the largest thing on screen.
- **Platform:** phone first (390px, thumb-zone actions, safe areas), the same single 640px column on desktop. Rationale: `docs/design/RATIONALE.md`.

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
- No gradients, no dark mode, no brand colours other than the accent. The accent appears only on the one primary action, links and focus.

## Typography
- **Font:** the platform UI face (`-apple-system`, Segoe UI, system-ui): SF on the chef's iPhone. Native, instant, tabular figures for money.
- **Scale:** answer sentence 40/46 semibold (28px on a phone); titles 22/29 semibold; body 17/26; secondary 15/22; tiny 13/18. No uppercase labels.
- **Money and quantities:** tabular figures, always with the unit in words ("1,000 × unit", "€1,560.00 before VAT").
- Sentence case everywhere.

## Shape, spacing and elevation
- **Layout:** one left-aligned column, 640px max, centred. Whitespace separates sections; hairlines (`#E7E9EC`) only where rows need dividing.
- **Spacing:** 4px base scale (4, 8, 12, 16, 24, 32, 48, 72).
- **Radius:** 12px on fields and buttons. No cards, no shadows (only the Keys dialog has one).
- **Touch:** every target is at least 48px tall.

## Components
- **Answer:** status word with a small dot in the status colour, then the decision as one sentence, the amount and one primary action. It's the only large element on the page.
- **Buttons:** primary is solid accent with white text; "Reject" is plain text in `bad`. Pressed state scales to 0.97. One primary per screen.
- **Phone action bar:** when approval is needed, Approve (with the amount) and Reject sit fixed at the bottom, respecting the safe area.
- **Disclosure:** native `<details>` rows ("Why this …", "Other options (n)"), a hairline between them, a rotating chevron.
- **Confidence:** a plain sentence plus the number ("Sure this is what you meant · 0.95"); when unsure, Gemini's own reason in `warn`.
- **Substitutes / split order:** plain rows, name on the left, price on the right; the split has a total and one "Use this order".
- **History:** an activity feed grouped by day: time, a status dot, one line of who did what, details on tap.
- **Inputs:** labelled above, 48px tall, 1px `#8D949C` outline (3:1), 2px accent focus ring.

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
