# Front Door video template

This is the reusable 16:9 Junction 2026 submission template for Front Door: 1920×1080, 30 fps, 1:57 (3510 frames).
The composition is [`frontdoor.tsx`](frontdoor.tsx); all replaceable timing and demo presentation data live in
[`timeline.ts`](timeline.ts).

The local brand kit mirrors `frontend/src/index.css`: warm paper, ink, Valio teal, lime action colour, and the system
UI face. Source footage from `video/media/` is linked into this folder under `media/` so the raea project stays inside
`video/raea/` without copying or modifying the original media. No raea workspace or nested git repository was created.

## Drop in the real live demo

1. Replace [`media/demo.mp4`](media/demo.mp4) with the real continuous landscape recording. Keep the filename so the
   composition needs no source edit.
2. In [`timeline.ts`](timeline.ts), update `sections.demo.duration` and the following section `start` values if the
   take is not 66 seconds. Update `demo.crop` to the normalized phone-window crop (`x`, `y`, `width`, `height`, each
   from 0 to 1), `demo.callouts` for the exact relative seconds, and `demo.speedRanges` for each intended ×4 range.
   The placeholder is normal-speed; the ×4 badge is already driven by those configured ranges.
3. Keep the `LIVE · one take` badge only for the continuous take. Do not splice result footage into the live take.

## Replace captions and voiceover

- [`captions.srt`](captions.srt) is the human-editable placeholder subtitle script, with `Omar` / `Zoha` speaker
  labels and timings adapted from `docs/pitch/video-script.md`.
- [`words.json`](words.json) is the normalized cue data used by the headless composition. After recording, replace
  both files with matching timings; keep times in seconds from the start of the final 1:57 cut.
- Put the recorded voiceover at `media/voiceover.wav`, then set `voiceover.enabled` to `true` in `timeline.ts`. The
  render works without it while the toggle is `false`.

## Verify and render

Run these commands from `video/raea/`:

```sh
# Fast composition lint
raea check --quick frontdoor.tsx

# Key stills for visual inspection
raea render frontdoor.tsx --at 0,120,239,240,270,330,540,749,750,1020,1350,1800,2340,2729,2730,2910,3090,3269,3270,3390,3509 -o out/frames/

# Draft render
raea render frontdoor.tsx -o out/frontdoor-draft.mp4 --quality draft --manifest out/frontdoor-draft.json
raea check out/frontdoor-draft.mp4 --manifest out/frontdoor-draft.json --shape 16:9 -o out/frontdoor-draft.check.json

# Master render
raea render frontdoor.tsx -o out/frontdoor-master.mp4 --quality master --manifest out/frontdoor-master.json
raea check out/frontdoor-master.mp4 --manifest out/frontdoor-master.json --shape 16:9 -o out/frontdoor-master.check.json

# Share copy
ffmpeg -i out/frontdoor-master.mp4 -c:v libx264 -preset slow -crf 23 -maxrate 2600k -bufsize 5200k -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart out/frontdoor-master-share.mp4
```

`out/` is ignored by the local `.gitignore`; no render output is intended for git. The current placeholder demo is
made from the existing hook/menu/held/rules/sugar/history/approve/urgent-voice/voice-fi clips and is not the final live
take.

