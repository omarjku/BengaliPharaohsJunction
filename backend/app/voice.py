"""Push-to-talk: the browser's recording → Gemini Live → the chef's words (which the UI then sends to /api/agent/ask).

The browser never sees a Gemini key: it uploads the clip (audio/webm, audio/ogg, audio/mp4, audio/wav...) to our
backend. PyAV (wheels bundle ffmpeg) decodes it to 16 kHz mono PCM16, which is all the Live API accepts, and the
backend streams it as one push-to-talk turn (manual activityStart / activityEnd: with automatic voice detection a
finished clip produced no transcript in the spike). Model: gemini-3.5-transcribe-live by default (it kept Finnish
numbers that gemini-3.8-live misheard: "Sata" → "Saat"); GEMINI_LISTEN_MODEL overrides it. See docs/VOICE.md.
"""
import asyncio
import base64
import math
from array import array
import io
import json
import logging

import av
import websockets
from fastapi import HTTPException

from . import config, conversation

LIVE_URL = ("wss://generativelanguage.googleapis.com/ws/"
            "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent")
MAX_BYTES = 1_000_000
MAX_SECONDS = 30
RATE = 16_000
CHUNK = RATE * 2 // 10  # 100 ms of PCM16 mono
LIVE_BUDGET_S = 8  # the whole Live round trip (a 3 s clip takes ~1.3 s); past it, a plain 503
SPEECH_RMS = 300  # loudest 100 ms window below this (of 32767) = no speech: silence/room noise is ~0-100
TIMEOUT_S = 15
# Declared type → the ONE demuxer allowed to read it (never auto-probed: a crafted file must not be able to pick a
# playlist/HLS/concat demuxer that opens URLs), and no network protocol is allowed at all.
DEMUXERS = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/mpeg": "mp3", "audio/aac": "aac",
            "audio/wav": "wav", "audio/x-wav": "wav", "audio/wave": "wav", "audio/flac": "flac"}
TYPES = tuple(DEMUXERS)
SANE_RATES, MAX_CHANNELS = (8_000, 96_000), 2
log = logging.getLogger(__name__)
connect = websockets.connect  # tests replace this with a fake Live socket


def to_pcm16(data: bytes, kind: str = "audio/webm") -> tuple[bytes, float]:
    """A browser recording of the declared type → (16 kHz mono PCM16, seconds). ValueError if it can't be read, isn't
    that type, or is longer than MAX_SECONDS (checked per frame BEFORE decoding work is spent on it)."""
    fmt = DEMUXERS[kind]
    cap = MAX_SECONDS * RATE * 2
    try:
        with av.open(io.BytesIO(data), format=fmt, options={"protocol_whitelist": "", "safe": "1"}) as box:
            if box.format.name != fmt:
                raise ValueError(f"not a {kind} recording")
            stream = next(s for s in box.streams if s.type == "audio")
            rate, channels = stream.codec_context.sample_rate or 0, stream.codec_context.channels or 0
            if not SANE_RATES[0] <= rate <= SANE_RATES[1] or not 1 <= channels <= MAX_CHANNELS:
                raise ValueError("unsupported sample rate or channel count")
            if stream.duration and stream.time_base and float(stream.duration * stream.time_base) > MAX_SECONDS + 1:
                raise ValueError(f"longer than {MAX_SECONDS} s")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)
            out = bytearray()
            for frame in box.decode(stream):
                projected = len(out) + int(frame.samples * RATE / (frame.sample_rate or rate)) * 2
                if projected > cap:
                    raise ValueError(f"longer than {MAX_SECONDS} s")
                for f in resampler.resample(frame):
                    out += bytes(f.planes[0])[: f.samples * 2]
            for f in resampler.resample(None):  # flush
                out += bytes(f.planes[0])[: f.samples * 2]
            if len(out) > cap:
                raise ValueError(f"longer than {MAX_SECONDS} s")
    except (av.error.FFmpegError, StopIteration, OSError) as e:  # first: PyAV errors are ValueErrors too, and their
        raise ValueError("not a readable audio recording") from e  # messages (errno, decoder detail) stay server-side
    except ValueError:
        raise
    return bytes(out), len(out) / (RATE * 2)


def has_speech(pcm: bytes) -> bool:
    """Any 100 ms window loud enough to be a voice (RMS over PCM16). Cheap: no model call for a silent clip."""
    samples = array("h", pcm[: len(pcm) // 2 * 2])
    step = RATE // 10
    return any(math.sqrt(sum(x * x for x in samples[i:i + step]) / max(1, len(samples[i:i + step]))) >= SPEECH_RMS
               for i in range(0, len(samples), step))


async def live_transcribe(pcm: bytes) -> str:
    """One push-to-talk turn on Gemini Live; returns the input transcription."""
    model = config.GEMINI_LISTEN_MODEL
    setup = {"setup": {"model": f"models/{model}",
                       "generationConfig": {"responseModalities": ["TEXT" if "transcribe" in model else "AUDIO"]},
                       "inputAudioTranscription": {},
                       "realtimeInputConfig": {"automaticActivityDetection": {"disabled": True}},
                       "systemInstruction": {"parts": [{"text": "Only listen. Reply with the single word OK."}]}}}
    async with connect(LIVE_URL, additional_headers={"x-goog-api-key": config.GEMINI_API_KEY}, max_size=2**20) as ws:  # bounded frames
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
            if len(text) > 4000:  # a 30 s clip is a few hundred characters (Codex #12)
                raise RuntimeError("transcript too long")
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
        pcm, seconds = await asyncio.to_thread(to_pcm16, data, kind)
    except ValueError as e:
        log.info("voice decode refused (%s)", e)  # the decoder's own wording stays in the log
        raise HTTPException(422, detail="I couldn't read that recording. Try again, or type the order.") from None
    if not has_speech(pcm):  # silence costs nothing and answers at once (a silent clip took 16.6 s to fail)
        raise HTTPException(422, detail="I didn't hear any words. Try again, closer to the microphone.")
    if seconds < 0.3:
        raise HTTPException(422, detail="The recording is too short. Hold the button while you speak.")
    try:
        text = await asyncio.wait_for(live_transcribe(pcm), LIVE_BUDGET_S)
    except Exception as e:  # noqa: BLE001 - upstream details stay in the log, never the key
        log.warning("Live transcription failed (%s)", type(e).__name__)
        raise HTTPException(503, detail="Voice is unavailable right now; type the order instead.") from None
    if not text:
        raise HTTPException(422, detail="No words were heard. Try again, closer to the microphone.")
    # "Sata litraa" → "100 litraa": the chef sees digits, and raw_text keeps exactly what was heard
    return {"text": conversation.spoken_to_digits(text), "raw_text": text, "seconds": round(seconds, 1),
            "model": config.GEMINI_LISTEN_MODEL}
