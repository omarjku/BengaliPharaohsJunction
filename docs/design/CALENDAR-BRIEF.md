# Feature brief: the delivery calendar

Status: **BRIEF, waiting for Zoha's design input. Nothing is built yet.** Sat 14 Nov 2026, about 19:30, from Omar via the control room.

## What Omar asked for
A calendar showing **every delivery that's coming in, every planned one and the recurring ones**.
- **Minimised on the first page, where the chat sits.** It's always visible but small, and never pushes the conversation away.
- **Tap it and it opens with a smooth animation** into the full calendar. Tap a day to see what arrives that day.
- It must work and look perfect the first time, be impressive, and need little iteration. Omar: "use as many agents and tokens as needed".

## What a day can show (all from real data in our backend, labelled honestly)
| Kind | Source today | Shown as |
|---|---|---|
| **Confirmed delivery** | confirmed front-door orders (`orders.py`), with their requested delivery date, lines, totals and signed statement | solid: "Arriving Fri 20 Nov · 4 lines · €184" |
| **Waiting for your OK** | `pending_approval` orders (over a limit, or an assumed amount or product, reason `ASSUMPTION_CONFIRM`) | an amber dot with an Approve button in the day view |
| **Recurring (planned)** | standing orders from onboarding (engine branch: memory `standing_order:<weekday>` with lines), e.g. "Usual Friday order" | dotted or outlined: "Usual Friday order · not placed yet", with one tap to place it, skip it this week or edit it |
| **Order cut-off** | Valio's `closingTime` for the next delivery days (`valio.py` quotes) | a small countdown on today and tomorrow: "Order by 14:00 for Monday" |
| **Urgent pickup** (Helsinki) | the urgent flow (Cash & Carry / Click & Collect suggestions; it never places a pickup) | only if the chef accepted one; otherwise not shown |
| **Kitchen context** (optional) | `kitchen_context()`: expected guests per weekday (SIMULATED demo history, always labelled) | a faint "~128 guests" on busy days, with a "simulated" tag |

Honesty rules:
- The Valio mock has **no shipment tracking**, so "Arriving" means the requested delivery date of a confirmed order. Never say "out for delivery" or "on the truck".
- Simulated numbers are always tagged.
- Nothing is placed from the calendar without the same front door and approval rules as the chat.

## The interactions (Omar's intent; open to Zoha's design)
- **Minimised:** a slim strip above or beside the conversation, showing the next 7 days with a dot per day (colour = kind) and today's cut-off countdown. On a phone, one row under the header.
- **Open:** tap the strip; it smoothly expands (shared-element / FLIP-style) into a week or month view; tap outside or swipe down to close. Respect `prefers-reduced-motion`.
- **Day view:** the deliveries for that day as compact cards (status, lines, total, and the actions approve / open in chat / skip recurring). "Open in chat" puts that order's card into the conversation.
- Works at 390 px and on a laptop, in FI and EN, keyboard and screen reader accessible, with 48 px targets.

## Proposed build (after Zoha's input)
- **Backend:** `GET /api/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD` (agent key; the buyer comes from the key) → `{days: [{date, cutoff?, entries: [{kind: confirmed|pending|recurring|pickup, order_id?, title, lines, total_cents, status, actions[]}], guests_expected?, simulated?}]}`. Plus `POST /api/calendar/recurring/<weekday>/skip?date=` and `…/place?date=`; the latter places through the normal front door, so assumptions and limits still apply.
- **Frontend:** `Calendar.tsx`, `CalendarStrip.tsx`, `DayView.tsx` with their own CSS and Zoha's tokens, mounted by one hook in the conversation screen.
- **Three agents:** Codex builds the backend, Codex builds the UI, and an independent reviewer and tester checks both against this brief and Zoha's design. Backend battle test (pytest plus a scripted calendar scenario) before merge; Omar and Zoha test on phones.

## Zoha: what we need from your side
Reply on the message board (or add a section below and push it) with:
- the look: the strip, the open state and the day cards
- the animation feel
- what you'd add or cut
- anything from your judging report that this should help with
