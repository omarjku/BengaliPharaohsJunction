# Codex run: Talk pre-warm (room4-warmup)

- Model/effort: gpt-reserve, max. Brief: new liveWarm.ts (warm slot, buffered replay, 45 s expiry, visibility/focus lifecycle), switch useLive.ts to takeLive; no App/api/CSS edits.
- Result: liveWarm.ts + the useLive.ts swap, tsc + eslint clean. Kept as is, plus one change by hand: re-warm on pointerdown/keydown after the 45 s expiry; the App hook line was added by hand.
