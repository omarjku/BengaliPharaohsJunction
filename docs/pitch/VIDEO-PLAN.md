# Front Door: Junction 2026 video plan

## Target and truth rules

- Runtime target: **1:58**. Hard maximum: **2:00**. The upload is a public YouTube video. Sources: [`docs/briefing.md`](../briefing.md) §1 and [`CLAUDE.md`](../../CLAUDE.md) “Hard facts”.
- The middle is one continuous live-demo recording. It starts with the Finnish handwritten list and ends with the signed result. It is the proof, not a mock UI montage. Source: current video decision and [`docs/pitch/video-script.md`](video-script.md) “One-take rules”.
- Use `video/media/coldopen-b.mp4` for the first eight seconds. Keep the on-screen label **Illustration, AI-generated**. Source: [`video/media/coldopen-b.NOTE.md`](../../video/media/coldopen-b.NOTE.md).
- The old English list in `video-script.md` is superseded by the Finnish list in [`demo-take-checklist.md`](demo-take-checklist.md). Keep the story, but shoot the real list in Finnish.
- Show only values returned by the app or the prepared evidence. The mock has no real orders or payments. Source: [`docs/pitch/wow-and-dont-show.md`](wow-and-dont-show.md), [`docs/CRACI.md`](../CRACI.md), and [`docs/GEMINI.md`](../GEMINI.md).
- Burn in captions and upload the matching `.srt`. Caption both Omar and Zoha. Source: current video decision and [`docs/pitch/video-script.md`](video-script.md) “One-take rules”.
- Build the template and graphics in Raea. Follow its word-cued footage rule, frame-pure motion rule, and `raea check` checks. Sources: [`~/.claude/skills/raea/SKILL.md`](file:///Users/omar/.claude/skills/raea/SKILL.md) §3–4, [`~/.claude/skills/raea/footage.md`](file:///Users/omar/.claude/skills/raea/footage.md), and [`~/.claude/skills/raea/graphics.md`](file:///Users/omar/.claude/skills/raea/graphics.md).

## Requirements checklist

| Done | Requirement | Source / acceptance check |
|---|---|---|
| [ ] | Cold open is the eight-second `coldopen-b.mp4`; label it **Illustration, AI-generated**. | [`video/media/coldopen-b.NOTE.md`](../../video/media/coldopen-b.NOTE.md) |
| [ ] | A door-opening transition introduces **Front Door** and the line **Agents knock. The door checks. The chef decides.** | Current video decision; [`docs/pitch/video-script.md`](video-script.md) |
| [ ] | The live slot is one real iPhone Mirroring screen recording. It shows photo → Finnish read → Valio quote and stock → Talk change → approval → signed result. | Current video decision; [`docs/pitch/live-pitch.md`](live-pitch.md) |
| [ ] | The Finnish list contains six or seven item lines and one visible hold or exception. | [`demo-take-checklist.md`](demo-take-checklist.md); `backend/app/vision.py` and `backend/app/chat_agent.py` |
| [ ] | The screen says `LIVE · one take`. No pasted card, reordered result, or second order is inserted. | [`docs/pitch/video-script.md`](video-script.md) “One-take rules” |
| [ ] | Any retimed wait has a visible `×2` or `×4` badge. Do not retime speech, a tap, a decision, or a result. | Current video decision; Raea footage guidance |
| [ ] | Gemini is named once with the real photo path and the real Decisions score or threshold. The line says why Gemini is essential. | [`docs/GEMINI.md`](../GEMINI.md); [`docs/SUBMISSION-PLAN.md`](../SUBMISSION-PLAN.md) “Best Use of Gemini API” |
| [ ] | Codex is named once with the concrete history fact: **29 commits marked “Built by Codex” on main**. Verify the history before export. | [`docs/CODEX.md`](../CODEX.md); [`docs/SUBMISSION-PLAN.md`](../SUBMISSION-PLAN.md) “Best Use of Codex” |
| [ ] | CRACI is named once. Say **CI runs on CRACI**. Show the live build hash and SBOM only if the endpoint returns `status: ok` and a non-empty `sbom_sha256`. | [`docs/CRACI.md`](../CRACI.md); [`docs/SUBMISSION-PLAN.md`](../SUBMISSION-PLAN.md) “Best Use of CRACI” |
| [ ] | Captions are readable, burned in, and delivered as a matching `.srt`. | Current video decision; Raea footage guidance |
| [ ] | Export is no longer than 1:58 in the master cut; open the public YouTube link in a private window before submission. | [`docs/briefing.md`](../briefing.md) §1; [`docs/SUBMISSION-PLAN.md`](../SUBMISSION-PLAN.md) |

## Timed beat sheet

The voiceover is about 220 words. That leaves room for a calm delivery near 2.3 words per second and short pauses around the live actions. The captions column is the caption text. Dynamic text in square brackets must be replaced with the value visible in the take.

| Time | Section | On screen | Voiceover (who says it) | Caption | Transition |
|---|---|---|---|---|---|
| 0:00–0:08 | TEMPLATE · cold open | `coldopen-b.mp4`: dark Lapland kitchen, phone on steel counter, 06:00. Label: `Illustration, AI-generated`. | **Zoha:** “It’s 06:00. Five hundred guests arrive today. The cut-off is closing. One wrong guess can stop service.” | Same sentence, split into short two-line captions. | Hold the phone close-up, then match-cut to a real phone. |
| 0:08–0:14 | TEMPLATE · door | A simple door opens. Title: `Front Door`. Tagline: `Agents knock. The door checks. The chef decides.` | **Omar:** “Agents knock. The door checks the list, the facts, and the permission. The chef decides.” | Same sentence. | Door sound and a clean match cut into the mirrored phone. |
| 0:14–0:20 | LIVE SLOT · photo | iPhone Mirroring. Finnish list in view. Small label: `LIVE · one take`. Omar photographs it. | **Zoha:** “This is one live take. I photograph a Finnish kitchen list on the phone.” | Same sentence. | Phone-screen match cut. |
| 0:20–0:31 | LIVE SLOT · read | Photo read result with seven items, Finnish units, and any unreadable or ignored-instruction state. Small label: `GEMINI · photo read`. | **Omar:** “Gemini reads seven lines, including Finnish units, then turns the photo into a checked request.” | Same sentence. | Short wipe from photo to structured items. |
| 0:31–0:42 | LIVE SLOT · checks | Real progress states. Show a product, price, stock, delivery date, pack size, and the actual decision score if the UI exposes it. Add `×2` or `×4` only over a sped-up wait. | **Zoha:** “The door checks Valio’s catalogue, price, stock, delivery date, and pack size.” | Same sentence. | Progress dissolve; keep the live label fixed. |
| 0:42–0:52 | LIVE SLOT · Talk change | Tap **Talk**. Show the transcript and the changed potato quantity on the pending card. | **Omar:** “I say, ‘Change the potatoes to 30 kilograms.’ Talk changes the pending cart.” | Same sentence. | Let the spoken line bridge into the transcript. |
| 0:52–1:02 | LIVE SLOT · hold | Show the actual hold reason. If the live card shows the known spend case, show `€1,560 > €1,500`, `Needs your OK`, and the milk line. If it shows stock, cut-off, or another reason, use that exact reason instead. | **Zoha:** “The live card shows the real exception. The cart needs the chef.” | Same sentence, plus the actual reason as a screen label. | Push the hold card forward; no invented substitute. |
| 1:02–1:09 | LIVE SLOT · approval | Show that Talk cannot approve. Tap **Approve** with the approver view/key. | **Omar:** “Talk cannot approve. I tap Approve with the approver key.” | Same sentence. | Hard cut on the tap. |
| 1:09–1:12 | LIVE SLOT · signed result | Green `Ordered` card, signed statement, audit entry. | **Zoha:** “Now it is signed, ordered, and audited.” | Same sentence. | Stamp/check animation into the proof cards. |
| 1:12–1:26 | TEMPLATE · Gemini proof | Template card beside the real score: `Gemini Decisions · 0.70 buyer threshold`. Caption: `A score can ask. It cannot grant permission.` | **Zoha:** “Gemini matters because its Decisions score measures uncertainty. Above the buyer’s 0.70 threshold, code may act; below it, the chef is asked.” | Same sentence. | Score line grows from the live score, then locks. |
| 1:26–1:37 | TEMPLATE · Codex proof | `CODEX · 29 “Built by Codex” commits on main`. Show the real history result and one chat-agent or approval screen. | **Omar:** “Codex built the engine, the Gemini agent, and these safety paths. The main history shows 29 commits marked ‘Built by Codex.’” | Same sentence. | Commit count wipes into a code-to-screen cut. |
| 1:37–1:47 | TEMPLATE · CRACI proof | `CRACI · CI runs on CRACI`. If verified, also show `status: ok` and the real `sbom_sha256`; otherwise omit the live-evidence panel. | **Zoha:** “CRACI runs our CI and records the build evidence. We show the live hash only when this build says status ok.” | Same sentence. | Evidence chain draws from CI to the signed order. |
| 1:47–1:58 | TEMPLATE · closer | Close-up of the phone and chef’s hand. End card: `Agents knock. The door checks. The chef decides.` Repo URL and `Valio challenge mock · no real orders or payments`. | **Omar:** “The order is confirmed.” **Zoha:** “Agents knock. The door checks. The chef decides.” | Both lines, then the tagline. | Hold the final card for readability; fade to black. |

## Template versus live-demo slot

| Part | Build now | Drop in later |
|---|---|---|
| Cold open | Use the supplied eight-second clip and label. | Nothing. |
| Door transition | Build the door-open motion, title, tagline, and sound bridge. | Nothing. |
| Live screen frame | Build the `LIVE · one take` frame, lower-third style, `×2/×4` badge, and safe caption area. | The real iPhone Mirroring recording from 0:14–1:12. |
| Explanation cards | Build Gemini, Codex, CRACI, J1–J5 callouts, and the end card. Keep dynamic values as placeholders until verified. | Insert the real Decisions score, actual exception reason, git history capture, and CRACI endpoint capture. |
| Captions | Prepare the caption timing from this beat sheet and the `.srt` structure. | Re-time captions to the final voice recording. Do not hide live actions under captions. |
| Final QA | Check Raea text, safe areas, transitions, public-link copy, and total duration. | Check the final live values and open the finished YouTube link privately. |

### Honest speed-up rule

The live slot has a **58-second target**. Warm the app before recording. If Gemini, the catalogue quote, or the voice response waits, speed only the waiting frames to `×2` or `×4` and keep the badge visible. Do not speed the spoken Talk change, the approval tap, the status change, or the signed result. Do not splice a result from another order into the one-take slot. If the real flow cannot fit 58 seconds after honest retiming, shorten template cards; do not fake the live flow.

## What each judge must see

| Track / criterion | One concrete fact to show | Where it appears |
|---|---|---|
| Valio J1 · end to end | The same request goes from Finnish photo to Valio quote, held card, approver tap, signed `Ordered`, and audit entry. | Live slot, 0:14–1:12. |
| Valio J2 · buyer need | Seven handwritten lines become a checked cart without the chef retyping every item. | Photo read and item card. |
| Valio J3 · autonomy and controls | Talk cannot approve; the card says `Needs your OK` and only the approver tap changes it to `Ordered`. | Hold and approval beats. |
| Valio J4 · exceptions | The card displays one real reason from the mock—spend limit, partial stock, unknown stock, cut-off, or diet/allergen hold—and does not invent a substitute. | Live hold card; use the actual reason from the take. |
| Valio J5 · openness and production path | The signed result is tied to the documented OpenAPI 3.1/MCP front door and an audit trail. | End of live slot and proof card. |
| Best Use of Gemini API | Gemini reads the Finnish photo and its Decisions `p_yes` score is used against the buyer’s `0.70` threshold; code still owns money, stock, dates, mandates, and approval. | Live read, score card, voiceover at 1:12–1:26. |
| Best Use of Codex | The shipped history contains 29 commits marked `Built by Codex` on main. | Codex proof card at 1:26–1:37. |
| Best Use of CRACI | CI runs on the `craci` runner. The live build’s SBOM hash is shown only when `/.well-known/front-door-build.json` says `status: ok`. | CRACI proof card at 1:37–1:47. |

