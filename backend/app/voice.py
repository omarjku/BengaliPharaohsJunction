"""Push-to-talk: the browser's recording → Gemini Live → the chef's words (which the UI then sends to /api/agent/ask).

The browser never sees a Gemini key: it uploads the clip (audio/webm, audio/ogg, audio/mp4, audio/wav...) to our
backend. PyAV (wheels bundle ffmpeg) decodes it to 16 kHz mono PCM16, which is all the Live API accepts, and the
backend streams it as one push-to-talk turn (manual activityStart / activityEnd: with automatic voice detection a
finished clip produced no transcript in the spike). Model: gemini-3.5-transcribe-live by default (it kept Finnish
numbers that gemini-3.8-live misheard: "Sata" → "Saat"); GEMINI_LISTEN_MODEL overrides it. See docs/VOICE.md.
"""
import asyncio
import base64
import io
import json
import logging

import av
import websockets
from fastapi import HTTPException

from . import config

LIVE_URL = ("wss://generativelanguage.googleapis.com/ws/"
            "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent")
MAX_BYTES = 1_000_000
MAX_SECONDS = 30
RATE = 16_000
CHUNK = RATE * 2 // 10  # 100 ms of PCM16 mono
TIMEOUT_S = 15
TYPES = ("audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/aac", "audio/wav", "audio/x-wav",
         "audio/wave", "audio/flac")
log = logging.getLogger(__name__)
connect = websockets.connect  # tests replace this with a fake Live socket


def to_pcm16(data: bytes) -> tuple[bytes, float]:
    """Any browser recording → (16 kHz mono PCM16, seconds). ValueError if it can't be read or is too long."""
    try:
        with av.open(io.BytesIO(data)) as box:
            stream = next(s for s in box.streams if s.type == "audio")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)
            out = bytearray()
            for frame in box.decode(stream):
                for f in resampler.resample(frame):
                    out += bytes(f.planes[0])[: f.samples * 2]
                if len(out) > MAX_SECONDS * RATE * 2:
                    raise ValueError(f"longer than {MAX_SECONDS} s")
            for f in resampler.resample(None):  # flush
                out += bytes(f.planes[0])[: f.samples * 2]
    except ValueError:
        raise
    except (av.error.FFmpegError, StopIteration, OSError) as e:
        raise ValueError("not a readable audio recording") from e
    return bytes(out), len(out) / (RATE * 2)


async def live_transcribe(pcm: bytes) -> str:
    """One push-to-talk turn on Gemini Live; returns the input transcription."""
    model = config.GEMINI_LISTEN_MODEL
    setup = {"setup": {"model": f"models/{model}",
                       "generationConfig": {"responseModalities": ["TEXT" if "transcribe" in model else "AUDIO"]},
                       "inputAudioTranscription": {},
                       "realtimeInputConfig": {"automaticActivityDetection": {"disabled": True}},
                       "systemInstruction": {"parts": [{"text": "Only listen. Reply with the single word OK."}]}}}
    async with connect(LIVE_URL, additional_headers={"x-goog-api-key": config.GEMINI_API_KEY}, max_size=None) as ws:
        await ws.send(json.dumps(setup))
        if "setupComplete" not in json.loads(await asyncio.wait_for(ws.recv(), TIMEOUT_S)):
            raise RuntimeError("Live setup failed")
        await ws.send(json.dumps({"realtimeInput": {"activityStart": {}}}))  # button down
        for i in range(0, len(pcm), CHUNK):
            await ws.send(json.dumps({"realtimeInput": {"audio": {
                "data": base64.b64encode(pcm[i:i + CHUNK]).decode(), "mimeType": f"audio/pcm;rate={RATE}"}}}))
        await ws.send(json.dumps({"realtimeInput": {"activityEnd": {}}}))  # button up
        text = ""
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), TIMEOUT_S))
            content = msg.get("serverContent", {})
            text += content.get("inputTranscription", {}).get("text", "")  # final text (interim* ones are ignored)
            # The transcribe model ends with generationComplete / ACTIVITY_END and never sends turnComplete
            # (measured); gemini-3.8-live ends its reply with turnComplete.
            ended = msg.get("voiceActivity", {}).get("type") == "ACTIVITY_END"
            if content.get("turnComplete") or content.get("generationComplete") or (ended and text):
                return " ".join(text.split())


async def transcribe(data: bytes, content_type: str) -> dict:
    """→ {text, seconds, model}. 4xx with a plain reason for anything the chef can fix by recording again."""
    kind = (content_type or "").split(";")[0].strip().lower()
    if kind not in TYPES:
        raise HTTPException(415, detail=f"Send the recording as one of: {', '.join(TYPES)}")
    if not data:
        raise HTTPException(422, detail="The recording is empty.")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, detail=f"Recordings may be at most {MAX_BYTES // 1000} KB ({MAX_SECONDS} s).")
    if not config.GEMINI_API_KEY:
        raise HTTPException(503, detail="Voice isn't configured on this server; type the order instead.")
    try:
        pcm, seconds = await asyncio.to_thread(to_pcm16, data)
    except ValueError as e:
        raise HTTPException(422, detail=f"Couldn't read the recording ({e}). Try again, or type it.") from None
    if seconds < 0.3:
        raise HTTPException(422, detail="The recording is too short. Hold the button while you speak.")
    try:
        text = await live_transcribe(pcm)
    except Exception as e:  # noqa: BLE001 - upstream details stay in the log, never the key
        log.warning("Live transcription failed (%s)", type(e).__name__)
        raise HTTPException(503, detail="Voice is unavailable right now; type the order instead.") from None
    if not text:
        raise HTTPException(422, detail="No words were heard. Try again, closer to the microphone.")
    return {"text": text, "seconds": round(seconds, 1), "model": config.GEMINI_LISTEN_MODEL}
