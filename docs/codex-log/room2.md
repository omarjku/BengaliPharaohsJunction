# Codex log: Room 2 (front door & security)

| # | When (EET) | Model / effort | Ask | Result | Kept / rejected |
|---|---|---|---|---|---|
| 1 | Sat 14 Nov 03:5x | gpt-reserve / max, workspace-write | Draft: `/api/orders` uses the stored mandate (drop body field, MANDATE_MISSING refusal, approve on the current mandate, tests) | Never ran: `timeout` isn't on macOS (exit 127) | Rerun |
| 2 | Sat 14 Nov 03:58 | gpt-reserve / max, workspace-write | Same prompt | Hung on "Reading additional input from stdin" (background shell kept stdin open); killed after ~5 min with no edits | Rejected; under the 30-min time-box Claude wrote the change by hand. Lesson: run `codex exec ... </dev/null` |
| 3 | Sat 14 Nov 04:2x | gpt-5.6-terra / ultra, read-only | Adversarial review of the front door on room2-mandates (gate, orders, auth, mandates, order routes) | Running in the background ("Codex never blocks") | Findings fixed in a follow-up commit |
| 4 | Sat 14 Nov 04:4x | gpt-5.6-terra / ultra, read-only | Adversarial review of M2 (split + substitutes) on room2-m2 | Running in the background | Findings fixed in a follow-up commit |
