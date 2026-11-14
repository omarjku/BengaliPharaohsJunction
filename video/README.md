# Submission video (T22)

Made with RAEA (0.1.1-rc2) from real recordings of the app. Shot list: `docs/VIDEO.md`. Script: `vo-script.md`.

| File | What |
|---|---|
| `record.mjs` | Playwright records each beat of the demo against a local stack (headed Chromium; one `.webm` per beat in `out/rec/`) |
| `cut.sh` | Trims and speeds each recording to its slot → `media/<shot>.mp4` |
| `front-door.tsx` | The RAEA composition: 1920×1080, 30 fps, 1:55 |
| `vo-script.md` | The voiceover, timed to the cuts (to be recorded; no synthetic voice here) |
| `out/front-door-draft-v3-share.mp4` | Draft with captions only, for review (share copy; the full render stays local). `raea check` is clean |

Rebuild:

```bash
# 1. a local stack with its own DATA_DIR (see the header of record.mjs), then:
KEYS=keys.json FI_WAV=voice-fi.wav ASAP_WAV=voice-cream-asap.wav FIVE_WAV=voice-five.wav node video/record.mjs   # from a folder with playwright installed
video/cut.sh
raea render video/front-door.tsx -o video/out/front-door-draft-v4.mp4 --manifest video/out/render.json --quality high
raea check video/out/front-door-draft-v4.mp4 --manifest video/out/render.json
```

Known limits:
- The two voice shots (spoken Finnish, and the Helsinki follow-up) use `say` clips as the microphone. The app's
  push-to-talk and `/api/voice/transcribe` run for real.
- The menu clip runs at about 4× to fit 11 s.
- There's no music bed yet.
