# Front Door submission video

`frontdoor.tsx` is the 1920×1080, 30 fps Junction 2026 submission cut. The current cut is 1:55 (3450 frames), with a dedicated caption band from y=900 to the bottom edge. Every information-bearing region is authored to end by y=880.

## Timing

| Section | Timeline |
| --- | ---: |
| Cold open / notification | 0:00–0:07 |
| Front Door transition | 0:07–0:10.5 |
| Explainer | 0:10.5–0:18.5 |
| Live demo, one continuous take | 0:18.5–1:20.5 |
| Gemini / Codex / CRACI cards | 1:20.5–1:46 |
| Closer and end card | 1:46–1:55 |

The live slot length is the single `DEMO_DURATION_SECONDS` value in `timeline.ts` (default 62 seconds). All phone keyframes and callouts are relative to that slot. The placeholder is normal-speed and carries no speed badges. The final take should be a portrait iPhone Mirroring recording that shows the Finnish list, Gemini read, Valio price/stock/delivery checks, the voice change, the real hold reason, the approver tap, and the signed result in one uninterrupted take.

## Drop in the real take

1. Replace `media/demo.mp4` with the final portrait recording, keeping the filename.
2. Keep `DEMO_DURATION_SECONDS` at 62 unless the recording length changes. If it changes, update that one value; section starts and the composition duration derive from it.
3. Retune only the relative `demo.keyframes` and `demo.callouts` times in `timeline.ts` to the real actions. Keep `LIVE · one take · real time` and do not splice result footage into the slot.
4. Verify the actual exception reason, price, score, stock, dates, and signed build from the take before recording voiceover.

## Captions and voiceover

`captions.srt` is the uploadable caption file. `words.json` is the matching burn-in data. Both keep `Omar` / `Zoha` speaker tags, max two-line wording, and timings for the 1:55 cut. Captions occupy only y≥900; cards, callouts, the phone, numbers, labels, URLs, and the lockup stay above y=880.

Put the recorded mix at `media/voiceover.wav` and set `voiceover.enabled` to `true` in `timeline.ts`. The composition remains renderable without voiceover while that flag is `false`. The master mix target is -14 LUFS with a -1.5 dBTP ceiling. Door creak, whoosh, notification chime, and stamp hits are local media under `media/`.

## Checks and renders

From this folder:

```sh
raea check --quick frontdoor.tsx
node check-caption-band.mjs
raea render frontdoor.tsx -o out/frontdoor-draft-v6.mp4 --quality draft --manifest out/frontdoor-draft-v6.json
raea check out/frontdoor-draft-v6.mp4 --manifest out/frontdoor-draft-v6.json --shape 16:9 -o out/frontdoor-draft-v6-check.json
ffmpeg -y -i out/frontdoor-draft-v6.mp4 -vf "fps=1/4,scale=384:-2,tile=5x6:padding=6:margin=6" -frames:v 1 -q:v 3 out/sheet-v6.jpg
```

`check-caption-band.mjs` asserts the authored layout constants and renders one full-resolution still per second to `out/v6-stills/` (the requested 2-second sweep is therefore covered). Inspect those stills at 1920×1080 for readable text and a clear caption band. The contact sheet is one frame per four seconds.

The generic Raea checker reports safe-area P1s for the captions because its default 120 px bottom UI zone conflicts with this cut's explicit caption band beginning at y=900. The owner rule is enforced by `check-caption-band.mjs`: all information regions end at or above y=880, while captions are the only content in y≥900. The final draft measures -14.8 LUFS / -1.5 dBTP, with no clipped text, dead sound stops, or flashing violations.

The final deliverable should use a new output filename beside this draft, for example `out/frontdoor-final.mp4`.
