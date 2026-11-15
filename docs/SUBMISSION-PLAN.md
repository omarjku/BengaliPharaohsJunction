# Junction 2026 submission plan

**Deadline:** Sunday 15 November, 10:00 Helsinki. **Peer review:** 10:30, with Omar and Zoha both present.

## Two audiences, two proofs

| Audience | What they judge | What we show |
|---|---|---|
| Valio peer review | **J1** working end-to-end demo (30%); **J2** user need (20%); **J3** autonomy and controls (20%); **J4** exceptions (15%); **J5** openness and path to production (15%) | A short chef story, then the same live phone photo: handwritten list → Gemini read → Valio price/stock/delivery checks → held order → chef approval → signed order. Point to each J criterion on screen. |
| Written submission and public video | Best Use of Gemini API, Best Use of Codex, and Best Use of CRACI | The public video, the polished deck PDF, and the exact repo evidence below. Name each technology once on screen with one concrete fact. |

The video is the evidence the tech-prize judges will see. It must be public and no longer than 2:00. The peer-review demo is live; voice ordering is only a backup take.

## Priority checklist

1. **By 07:00 — Omar: final deploy and approval.** Warm the live app, run the photo flow, confirm the held card and approval tap, and check the signed result. Verify the CRACI build endpoint before claiming live SBOM evidence. Freeze code after this check.
2. **By 07:00 — Zoha: submission text.** Update the numbers and status in `docs/SUBMISSION.md`; do not carry forward stale figures or “next deploy” claims.
3. **07:00–08:15 — Omar: record the demo take.** Record one continuous photo flow with the handwritten list. Keep the actual waits and displayed values truthful; speed up waits only in the edit.
4. **07:00–09:30 — Zoha: video and deck.** Edit the public video to ≤2:00, add captions, polish the deck, and export the final PDF.
5. **08:45–09:20 — Both: rehearse.** Run the three-minute story and photo demo twice. Practice the Wi-Fi fallback and the five J-point callouts.
6. **09:20–09:40 — Both: final check.** Open the public video in a private window, check the PDF, verify the repo links, and confirm the live demo keys.
7. **09:50 — Both: submit.** Zoha submits; Omar reads back the final links and verifies that the selected challenges match the evidence. CRACI is selected only if CI and the live build evidence are real at submission time.
8. **10:30 — Both: peer review.** Zoha tells the story and narrates; Omar drives the photo flow. Both stay for questions.

## What to write for each tech prize

### Best Use of Gemini API

- **Problem:** Explain the kitchen problem and why a wrong guess costs money, safety, or a delivery slot. Point to [`docs/SUBMISSION.md`](SUBMISSION.md) and the user need in [`README.md`](../README.md).
- **Integration:** Describe photo reading, structured output, tool calls, and the Decisions confidence gate. Point to [`docs/GEMINI.md`](GEMINI.md) and the end-to-end trace in [`docs/m1-e2e.md`](m1-e2e.md).
- **Why Gemini is essential:** Say that Gemini adds the photo and language layer plus calibrated Decisions scores; code still controls money, stock, dates, mandates, and approval. Point to [`docs/GEMINI.md`](GEMINI.md) and [`docs/GEMINI-evidence.md`](GEMINI-evidence.md).

### Best Use of Codex

- **Core features:** Codex built the engine, Gemini function-calling agent, voice-on-one-brain path, CRACI evidence, and safety fixes. Point to [`docs/CODEX.md`](CODEX.md), especially its run table and file-to-commit map.
- **Shipped proof:** Show the repository history with `git log -i --grep="Built by Codex" origin/main`; use the matching commit and pull-request evidence recorded in [`docs/CODEX.md`](CODEX.md).
- **Working method:** Explain the loop: narrow brief, parallel worktree, real-Gemini test, regression fix, review, and test gate. Point to the “How the collaboration worked” section in [`docs/CODEX.md`](CODEX.md).

### Best Use of CRACI

- **Technical depth:** Point to [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), where the provenance job runs on `craci`, and to [`docs/CRACI.md`](CRACI.md).
- **Creative use:** Show the deployed `/.well-known/front-door-build.json` evidence: the build commit, SBOM hash, vulnerability counts, and network destinations. Claim `status: ok` only after Omar verifies it after the final deploy.
- **Signed provenance:** Explain that the signed order names the build that signed it, including the commit and SBOM hash. Point to the “Signed provenance” section in [`docs/CRACI.md`](CRACI.md) and the order’s `signed_statement.build` fields.

## Five-line summary

07:00: Omar approves the final deploy and freezes code; Zoha updates the submission numbers.
07:00–09:30: Omar records the one-take photo demo; Zoha edits the public video and exports the deck PDF.
Both rehearse the three-minute story, J1–J5 callouts, and Wi-Fi fallback before 09:40.
09:50: submit the checked links and select CRACI only if its live evidence is verified.
10:30: Omar and Zoha attend peer review and show the chef approving the held order.
