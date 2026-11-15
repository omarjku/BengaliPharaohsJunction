# Front Door: Remotion composition

Motion composition `FrontDoor` for the submission video: 1920x1080, 30 fps, 115 s (3450 frames), 16 beats.
Everything on screen is driven by one data file: `src/timeline.ts` (beats with `id, start, end, caption, overlay, mediaSlot`).

## Render

```
npm install                      # once
npm run studio                   # live preview
node scripts/render.mjs          # full 1080p H.264 -> out/placeholder.mp4 (auto-detects public/vo.wav and public/music.mp3)
node scripts/render.mjs out/final.mp4 --concurrency=4
npx remotion render FrontDoor out/placeholder.mp4   # same thing, silent, defaults from src/config.ts
node scripts/stills.mjs          # the 6 key stills -> out/stills/*.png (bundles once)
node scripts/stills.mjs --all    # plus 10 extra review frames (x*.png)
npx remotion still FrontDoor out/stills/x.png --frame=975   # any single frame
```

Remotion bundles its own ffmpeg/ffprobe (`@remotion/compositor`); no system ffmpeg is needed. The first still or render downloads
Chrome Headless Shell (about 100 MB) into `node_modules/.remotion`. Bundling takes about a minute on this machine.
Google Fonts (Roboto) are fetched at render time through `@remotion/google-fonts`, so the first render needs network access.

Measured here (8 logical cores, `--concurrency=4`): full 1080p render of 3450 frames took 5.5 to 7.5 minutes (12.6 MB MP4, H.264, silent AAC track);
the 6 stills take about 40 s after a one-minute bundle. The very first run can fail with "Timed out ... trying to connect to the browser"
while the Chrome Headless Shell download/scan and the bundling compete for the CPU: just run it again.

## Where to drop footage (all optional; missing files render a labelled "FOOTAGE: <name>" placeholder)

| File | Used in | Notes |
| --- | --- | --- |
| `public/veo/coldopen_a.mp4` | beat 01 (0:00-0:06), full bleed | Night-kitchen cold open. The corner tag "Illustration, AI-generated" is always shown. |
| `public/rec/take.webm` | beats 02-08 (0:06-0:58), phone frame | One continuous live take. Beat N seeks to `startFromSec` (see `TAKE(...)` in `timeline.ts`, 8 s per beat step); adjust those offsets to line up with the real take. |
| `public/vo.wav` | whole video | Played when it exists. Not generated here. |
| `public/music.mp3` | whole video | Optional, played ducked (about 0.12 under voice, 0.4 without), faded in and out. |

Audio flags: `HAS_VO` / `HAS_MUSIC` in `src/config.ts` default to `false`. `scripts/render.mjs` checks `fs.existsSync` for the two files at render time and
passes `hasVo` / `hasMusic` as input props (written to `out/props.json`), which override the defaults. To enable without the script, flip the constants.

## Components (`src/components`)

`VideoSlot`, `Stamp` (spring "land": scale + rotate), `TicketCard` (thermal order ticket), `ConfidenceBar` (0.897 and 0.115 vs dashed "ASK BELOW 0.70"),
`EvidenceCards` (reveal one at a time), `TrapTickets`, `ArchitectureStrip`, `Captions` (burned in, 44 px, white on 70% ink pill, one sentence at a time),
`LiveBadge` (`x4` prop), `EndCard`, `DoorGlyph` (SVG), plus `Icons`. Scenes per beat are in `src/scenes.tsx`.

## Editing the script

Change captions, times or overlay text in `src/timeline.ts`. A module-load check throws unless there are 16 contiguous beats totalling exactly 115 s.
Commented alternates are left in the file: `// VERIFY ON PHONE` (beat 08) and `// ONLY IF CRACI LIVE` (beat 14). No voice and no CRACI claim is made on screen.

## Not done / open items

- No real footage: the Veo cold open, the live take and the voice-over are placeholders until the files are dropped in. The take offsets are guesses.
- The "x4" badge exists but is not shown anywhere; enable it (`<LiveBadge x4 />` in `scenes.tsx`) only if the take is actually sped up.
- Repo URL on the end card is `github.com/omarjku/BengaliPharaohsJunction` (taken from the repo's git remote). Change `REPO_URL` in `src/config.ts` if the submission repo differs.
- The 7 handwriting lines in beat 03 are generic scribbles, not the real order lines.
- The "29 commits" and "33 cases / 14 of 15" figures are copied from the script as given; not re-verified here.
- No end-card caption (the tagline is on screen) and no audio mix beyond the simple duck.
- Nothing in `G:\valio\BengaliPharaohsJunction` was touched or committed; `.env` files were not read.
