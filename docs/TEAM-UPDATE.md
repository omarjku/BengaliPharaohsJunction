# Team update for Zoha: Sun 15 Nov, 01:45

What happened between about 20:00 and 01:45, in plain words. Omar and his agents did this; the measured numbers come from real tests.

## What's live on the app now
- **Gemini is the brain for both typing and voice.** It's the same brain with the same tools, so text and voice behave the same.
- **Voice is safer.**
  - Every spoken order waits for the chef's tap on screen.
  - Voice can't cancel orders; it says "tap Cancel on the order card".
  - Short answers like "No", "Ei" or "10" are now understood.
- **Your "80%" finding is fixed.** The screen shows each kitchen's real confidence level (70% for the demo kitchens).
- **Echo is fixed.** The microphone ignores the agent's own voice while it's speaking.
- **Allergens are read properly.** We weren't reading Valio's "free from" information.
  - Fewer pointless "no allergen data" questions: e.g. caster sugar is now known to be peanut-free.
  - Products with an unknown allergen can no longer slip past a ban: e.g. an ice cream got past a peanut ban.
- **The big milk bug is fixed.** 1,000 L of milk sold in cases of 5 no longer becomes 5,000 L.
- **Prices are locked.** An automatic order uses exactly the prices the agent showed. If Valio's price changed, a human decides.
- **Late-night dates are fixed.** Dates now follow Finnish time. Just after midnight, "yesterday" was treated as a valid delivery day.
- **More information on order lines:** sustainability labels (Blue Swan, Organic, MSC, Fairtrade…) and returnable-packaging deposit notes.
- **QR test kitchens have more room:** up to 40 per hour from one Wi-Fi network, so a whole judging table can try it.
- **CRACI is live.** The app shows real evidence from CRACI about how it was built: 340 software parts, the 19 internet addresses the build talked to, and 7 high-risk vulnerabilities that CRACI found.

## Measured (honest numbers)
- **Chat accuracy:** 97 of 164 test requests handled right, **59%** (was 33% with the old engine).
- **Safety:** **0 unsafe automatic orders out of 164**, including 10 attempts to trick it into approving.
- **Voice speed:** first spoken words in about 1 second, the held order card in about 6 seconds.
- **Full scenario tests:** 14 of 22 pass (they still use the old engine path).
- **Code checks:** 736 automatic tests pass.

## Scores (estimates; an independent re-score of all four is running now)
- Valio about 75 (your v4: 69)
- Gemini about 81 (79; your Gemini polish may lift it more)
- Codex about 80 (73)
- CRACI about 44 (17.5). An independent check scored 33 before the live evidence worked.

## Coming in the next deploy (built and being checked)
- **The 7 vulnerabilities CRACI found are fixed.** That's our CRACI story: "CRACI found them in our build, and we fixed them the same night." The live page will then show 0.
- **Fewer questions.** If the chef gives no delivery date, the agent picks the next delivery day, shows it and asks for one tap. That was the most common reason for lost J2 points.
- **Each signed order names the build that signed it** (CRACI provenance).
- **A new, cleaner README and a CRACI slide.** The GitHub page now shows the live app link and topics.

## What's left: Zoha (your strengths)
1. **The presentation.** Polish the deck from `docs/pitch/slides.md`: 7 slides, plus 1 CRACI slide (Codex is drafting it in `docs/deck/index.html`). Then export the PDF.
2. **The demo video.** The script is `docs/pitch/video-script.md`: one real 40-second photo demo in the middle, with our own voices explaining over it. Zoha speaks about half.
3. **The submission text** (`docs/SUBMISSION.md`) needs the new numbers: 59% accuracy, 0 unsafe of 164, voice on one brain, CRACI live evidence and fixes, Codex built the core.
4. **Your doc fixes** (the stale numbers from your report) are still open.

## What's left: Omar
- Test voice and the photo flow on the phone (live now).
- Record the demo take for the video.
- Approve the next deploy.

## Timeline
- **By 07:00:** final deploy, then no more changes.
- **07:00–09:30:** video, deck, rehearsal.
- **09:50:** submit.
- **10:30:** peer review (both of us there).
