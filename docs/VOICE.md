# Voice: push-to-talk ordering with Gemini Live (spike + design)

Status: **transcription built** (`POST /api/voice/transcribe`, below). The read-back stays with the browser's speechSynthesis for now; Live audio-out is measured (~0.5 s to first audio) but not wired.

## Built: `POST /api/voice/transcribe`

- **Request:** `X-Agent-Key`; the body is the raw recording (Content-Type `audio/webm`, `audio/ogg`, `audio/mp4`, `audio/mpeg`, `audio/aac`, `audio/wav` or `audio/flac`); at most **1 MB / 30 s**; rate-limited per key like agent runs.
- **Response:** `200 {"text": "…", "seconds": 3.0, "model": "gemini-3.5-transcribe-live"}`. The UI shows the text and sends it to `POST /api/agent/ask`; nothing is ordered here.
- **Errors:** 4xx/503 with a plain `detail` sentence the UI can show: 415 wrong type, 413 too big, 422 unreadable / too short / over 30 s / no words heard, 503 voice unavailable ("type the order instead"), 401 no key.
- **How it works:** PyAV (pip wheels bundle ffmpeg; no system package on Render) decodes any browser format to 16 kHz mono PCM16, because the Live API accepts only `audio/pcm` (WebM and Ogg are refused with 1007). The clip is streamed as one push-to-talk turn (manual activityStart / activityEnd). The transcribe model ends with `generationComplete` / `ACTIVITY_END`, never `turnComplete`, and the backend finishes on whichever comes first. `GEMINI_LISTEN_MODEL` switches models (default `gemini-3.5-transcribe-live`, the one that keeps Finnish numbers).
- **Live latency (real clips through the endpoint code):** 3 s English as WebM/Opus, Ogg/Opus and WAV: **1.26–1.34 s** total (decode ~10 ms, the rest is the Live round trip including setup), each "1,000 L of lactose-free milk for Monday."; Finnish WebM: 1.37 s, "Sata litraa laktoositonta maitoa maanantaiksi."; `say` "Twenty kilos of butter for Monday": 1.15 s, "20 kilos of butter for Monday.". Test: `RUN_LIVE_VOICE=1 .venv/bin/python -m pytest -q tests/test_voice.py -k live -s`.
 The chef holds a button and speaks. The words go into the same `POST /api/agent/ask` flow as typed text, and the agent reads back the decision in one short sentence.

## What the spike measured (Sat 14 Nov 2026, our key, from the backend)

`backend/scripts/voice_spike.py` opens a Live websocket from the backend. The key is sent in the `x-goog-api-key` header, so it is never in a URL or in the browser. The script streams 16 kHz PCM in 100 ms chunks, the way a browser would, and marks the push-to-talk turn with manual `activityStart` / `activityEnd`. With automatic voice-activity detection, a turn that simply ended never produced a transcript.

| step | model | result | latency |
|---|---|---|---|
| open session | either | `setupComplete` | 0.3–0.5 s (can be hidden: open on button-down) |
| transcript, English ("One thousand litres of lactose-free milk for Monday") | `gemini-3.8-live`, input transcription | "1,000 L of lactose-free milk for Monday." (already in the agent's notation) | **0.88–0.91 s** after button-up (3 runs) |
| transcript, Finnish ("Sata litraa laktoositonta maitoa maanantaiksi") | `gemini-3.8-live` | "**Saat** litraa…": the number was lost | 0.93 s |
| transcript, Finnish | **`gemini-3.5-transcribe-live`** (TEXT modality) | "**Sata** litraa laktoositonta maitoa maanantaiksi." correct | **0.93–0.98 s** |
| read-back ("1,000 litres lactose-free milk, 1,400 euros, ordered for Monday.") | `gemini-3.8-live`, audio out | spoken exactly (output transcription matches) | **0.40–0.53 s** to first audio |

The audio was synthetic (macOS `say`), so real kitchen speech and noise still need a check, but the plumbing and latencies are verified. A lost number fails safe: the agent finds no amount and asks "How much?".

## Design

```
browser                         backend (FastAPI)                                Gemini
───────                         ─────────────────                                ──────
hold button ──ws /api/voice──▶  auth (first message, agent key; never in URL)
  {"type":"start"}              open Live: gemini-3.5-transcribe-live,  ──────▶  setup (0.3-0.5 s, overlaps speech)
  PCM16 16 kHz frames ────────▶ activityStart + audio chunks          ──────▶
release button
  {"type":"stop"}  ───────────▶ activityEnd                            ──────▶  transcript (~0.9 s)
                  ◀── {"type":"transcript","text":…}   (shown at once, so the chef sees what was heard)
                                ask.ask(transcript)   (same guards: steering, grounding, confidence, limits)
                  ◀── {"type":"result", …/ask body…}   (rendered by the existing cards)
                                readback(decision): a fixed template, never model wording
                                open Live: gemini-3.8-live, AUDIO       ──────▶  first audio (~0.5 s)
                  ◀── PCM 24 kHz audio frames + {"type":"said","text":…}
```

- **Two models, each for what it measured best:** the transcription model listens (it kept the Finnish number), and `gemini-3.8-live` speaks.
- **The read-back is a template filled from the Decision, not free model text.** Examples: "1,000 litres lactose-free milk, €1,400, ordered for Monday." / "Needs your OK: €60 over your limit." / "Not ordered: Valio can't confirm the stock. Check the screen." The voice model only says the sentence. The backend compares the output transcription with it and sends the text either way, so the screen is the record.
- **Voice never approves.** A spoken "yes, approve it" is just more text through `/ask`. Approval stays a click behind the approver key, and the steering classifier and the phrase list apply to the transcript as to typed text.
- **Key and auth:** browsers can't set headers on a websocket, so the first message carries the agent key (or a short-lived token from `POST /api/voice/token`). It never goes in the URL. The Gemini key stays on the server.
- **Limits:** at most 30 s of audio per press, one Live session per connection, closed after the read-back, and the existing rate limits on `/ask`.
- **Dependencies:** none new. `websockets` is already installed through `uvicorn[standard]` (list it explicitly when building).

## Latency budget for one spoken order

transcript ~0.9 s + `/ask` (today 8–12 s, mostly Valio quotes and the Gemini parse/rank/judge calls) + first read-back audio ~0.5 s. **Voice adds about 1.5 s on top of typing.** The chef sees the transcript at once, and the cards when `/ask` returns.

## Build steps (when the team says go)
1. `GET /api/voice` websocket (auth, the 30 s cap, the relay to the transcription model, then `ask.ask`, then `readback()`, then speaking): about 150 lines, with tests faking the Live socket.
2. `readback(decision, body)`: a pure function with templates for confirmed / pending approval / refused / asked, and tests.
3. Frontend (Room 4): a hold-to-talk button, an AudioWorklet for 16 kHz PCM16, playback of 24 kHz PCM, and showing the transcript and the "said" text.

## Urgent pickup (built in `/api/agent/ask`, used by voice too)

When the chef signals urgency ("ASAP", "now", "today", "in 30 minutes", "heti", "tänään"), or orders for today, or Valio's earliest delivery is later than the day needed, the `/ask` response adds `urgent_options`. These are **suggestions, each marked `assumption`; the agent never places them**:
- **Helsinki buyers** (location beside the mandate; demo buyer `helsinki-bistro`):
  - `walk_in`: Valio Aimo Cash & Carry Helsinki, Vanha Talvitie 2 (Sörnäinen, Tukkutori), today's opening hours with "open now" / "closed now" (Mon–Fri 7–18, Sat 8–17, Sun 9–16), and "Store stock is not confirmed via the API: call 010 381 7645 before you go".
  - `click_and_collect`: "ready from about 4 hours after it is confirmed", Helsinki only, placed on Valio's own site.
  - plus the next delivery.
- **Everyone else** (e.g. `lapland-kitchen`): only the honest `next_delivery`, i.e. the earliest delivery day and its cut-off from the live quotes.

"ASAP" or "now" with no date means today. Facts are only what valioaimo.fi publishes; store stock and pickup are not in the mock API, and every suggestion says so. Voice read-back example: "Valio can deliver Monday. For today: Cash & Carry Helsinki is open until 17:00, call first."

Live (Sat 05:47), "20 kg unsalted butter ASAP":
- `helsinki-bistro`: held for the chef (Valio delivers Monday, not today), with walk-in (closed now, opens 08:00), Click & Collect (around 09:47) and Monday's delivery;
- `lapland-kitchen`: only "The earliest Valio delivery for these products is 2026-11-16 if ordered before 2026-11-15 17:00".
