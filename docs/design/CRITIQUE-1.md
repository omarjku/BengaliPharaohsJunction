# Design critique #1: fresh eyes (Sat 14 Nov, ~12:40)

From an independent senior-designer review of the 21 screenshots, RATIONALE.md and `frontend/src`. Verdict: the restraint is real (one column, one sentence, no cards), but it still reads as a well-behaved default, and several states break trust. Room 4 is working through the fixes below; Zoha's review follows.

## Top fixes, ranked by first impression
1. **Low-confidence dead end:** it says "pick an alternative" with no button. Add "Order <alternative> · €X" and "Not this one" (focuses and prefills the field); on phone, both go in the bottom bar.
2. **Two primary buttons:** "Ask the agent" and "Approve" are both solid blue. Once there's a result, make "Ask" plain. Below 600px, collapse the composer into a 48px summary row ("1000 L lactose-free milk · Mon 16 Nov · Edit").
3. **Status colours lie:** a short-stock rescue shows red "Not ordered"; a menu cart shows amber with no rule fired. Red only for final failures; amber "Your call" when an action is needed; neutral "Ready to order".
4. **After approval** the headline is the outcome ("Ordered for Mon 16 Nov."), with "Chef Aino approved · 04:52" underneath at 15px.
5. **Desktop empty state:** replace the dev note with "Try: 1000 L milk · 200 L milk drink · 1000 butter" links; on an empty screen, a 40px question, 96px top padding, and the last 3 history items.
6. **Split proposal duplicates itself:** headline "Valio has 640. Top up with 360 organic?"; rows "640 packs · €3,104.00"; "Order both · €5,246" in the thumb bar.
7. **History:** one row per request, titled with its final outcome, with sub-events inside; the time once per group; no UUIDs.
8. **Reject** in neutral grey, 16px from Approve (red is for results only).
9. **Tidy catalogue names** client-side (strip ®, "1 l" → "1 L", drop "Suomesta").
10. **Identity:** warm paper `#FBFAF7`, a small door glyph next to the wordmark, tabular figures in headline money; the keys "Show" button inside the field; a disabled Save in grey, not pale blue.

## Copy
"before VAT" → "excl. VAT" (once per screen) · "Sure this is what you meant · 0.95" → "Exact match · 95%" · "Not sure this is what you asked for" → "Best guess, please check" · "(0.72 vs your 0.80 threshold)" → "Below the 80% it needs to order on its own" · "€60 over your €1,500 limit." → "€60 over the €1,500 order limit." · "Works if needed" → "Also works" · "Stock unknown" → "Stock not confirmed" · "640 × unit" → "640 packs" · "Valio has these instead" → "Other butters Valio has" · the history intro → "What was ordered, held or refused." · the mock note → "Demo data. Try:" · keys → "Paste the two keys from your Valio Aimo account. You only do this once." · menu → "Portions are estimates. Check them before you order."

## Flow
- Nothing answers "Do I need to do anything?" when the app opens.
- On phone, the reasons sit below a bottom bar that invites approving before reading. The menu has "Order this cart" above "check them below".
- Gemini confidence speaks in three voices. Pick one form ("Matched by Gemini · 95%") and say once what the number means.
- The header subtitle flickers on load.

## Delight
1. Approve morphs into "Ordered ✓" inside the same button (200ms), and the status dot fills green.
2. An empty-state greeting: "Morning, Aino. Nothing waiting for you."
3. Relative delivery ("Arrives Monday, in 2 days"); Cmd/Ctrl+Enter submits.
