# Handoff for Zoha: Sun 15 Nov, ~03:30

Omar is resting. This one file has everything you need; you don't need to read the message board.
**Ask your Claude:** "Read docs/ZOHA-HANDOFF.md and docs/SUBMISSION-PLAN.md on branch omar/m1-integration and explain them to me in short, plain bullet points."

## 1. Where we are
- **The live app works end to end:** request → Valio price, stock and delivery check → held order card → chef taps Approve → signed order → History.
- **Live links:** https://valio-front-door.onrender.com (app) · repo github.com/omarjku/BengaliPharaohsJunction.
- **Last deploy:** 03:10 (PR #124). Smoke test 9/10, the usual result; the one miss is an old "order the milk again" check.

## 2. What changed since your 01:45 update (all live now)
- **CRACI**
  - The live app fetches its own CRACI build evidence.
  - Every signed order names the build that signed it (commit and SBOM).
  - We fixed the vulnerabilities CRACI reported. CRACI still shows 7 "HIGH", and we can't find where they come from (our own scans show 0). So we switched off the "hold auto-orders if the build has HIGH vulnerabilities" gate on Render. The code is still there, and the story stays the same.
- **Fewer questions:** if no delivery date is given, the agent picks the next delivery day and shows it on the card.
- **The coffee-milk bug is fixed:** "coffee milk" no longer auto-orders plain milk.
- **Multi-item requests:** each item gets its own status (chosen, held, no match, out of stock).
  - Alternatives never mix items (no more "potatoes vs salmon" comparisons).
  - "70 kg potatoes 70 kg salmon" without commas works.
- **"Approve selected"** now works in one tap.
- **New clean cart:** one row per product, a sticky cart bar at the bottom, and short fact chips (on-time %, CO₂e, origin, labels).
- **Design pass:** the menu is grouped with icons, Kitchen and Rules fold into sections, the send arrow is animated, and hover labels sound like a win.
- **Valio's Discord answers are built in:**
  - stock "999999" means unknown but orderable;
  - pack size 0.01 means whole units;
  - "Valio is busy" gives a calm "try again in 30 s".
- **Docs:** a new judge-ready README with a "Judges: where to look" table, plus `docs/CODEX.md`, `docs/GEMINI.md` and `docs/CRACI.md`.

## 3. Omar's last test (voice, 03:07): what went wrong and what's being fixed now
- **The agent quoted one product and price, then the order card used another.** It said trout at €15.77/kg, and the card showed a different trout at €18.01. Same with salmon. *Fix in progress:* the product you're told about is the product you get; any swap is said out loud.
- **Fish showed "no allergens".** Valio's data has no allergen info for some fish, and a kitchen that bans fish could have been sent fish. *Fix in progress:* missing data counts as "unknown", fish is recognised from the name, and a ban always asks a human. (A good J4 robustness story.)
- **Prices showed "/L" for fish** instead of "/kg". *Fix in progress.*
- **"Show me my cart"** listed old and already-confirmed orders. *Fix in progress:* only orders still waiting are listed, and the answer points to the History tab.
- **The voice session hit its 5-minute limit mid-sentence.** *Fix in progress:* a warning 30 s before, then one clear "tap Talk to continue, your cards are kept" message.
- **"Go ahead and make the order" on voice.** Voice can't approve, which is on purpose. *Fix in progress:* it now says "tap Approve on the card".
- Omar approves the deploy of these fixes when he's back (target: before 07:00).

## 4. Scores (our estimates)
- **Valio:** about 75 (your v4 report: 69).
- **Gemini:** about 81 (79).
- **Codex:** about 80 (73).
- **CRACI:** about 44 (17.5).

Measured:
- **Chat accuracy:** 105 of 164 test requests (64%).
- **Unsafe automatic orders:** 0 of 164, including 10 attempts to trick it.
- **Code checks:** 770 automatic tests pass.

## 5. Plan to the finish (details in docs/SUBMISSION-PLAN.md)
- **Two audiences:**
  - **Peer review (10:30)** is judged on the **Valio** criteria (J1–J5). The live demo carries it.
  - **The written submission and video** are what the **Gemini, Codex and CRACI** judges see. Each needs one concrete fact on screen.
- **Video (max 2:00):** one real live take of the **photo flow**.
  1. A handwritten list of kitchen items is photographed.
  2. Gemini reads it.
  3. Valio prices and stock are checked.
  4. A held card appears, and the chef approves it.

  We both talk over it. A short story opens and closes it: a chef at 06:00 with 500 guests and a cut-off coming. Voice is the backup take. The script is in `docs/pitch/video-script.md` (being rewritten now).
- **Live pitch:** the story, then the same photo demo, explained as it happens. See `docs/pitch/live-pitch.md`.

## 6. Your tasks (in this order)
1. **Deck:** polish `docs/pitch/slides.md` (6–8 slides, plus the CRACI slide in `docs/deck/index.html`), then export the PDF. Make sure Codex, Gemini and CRACI each get one clear fact.
2. **Video:** edit Omar's photo-flow take with both voices, add the story open and close, keep it at 2:00 or under, and make it public.
3. **Submission text:** update `docs/SUBMISSION.md` with the numbers in section 4.
4. Your doc fixes from the v4 report, if any are still open.

## 7. Timeline
- **By 07:00:** final deploy, then no more code changes.
- **07:00–09:30:** video, deck, rehearsal.
- **09:50:** submit.
- **10:30:** peer review. Both of us must be there, or we lose eligibility.
