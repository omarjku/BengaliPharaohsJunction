"""Push-to-talk transcription: POST /api/voice/transcribe with a fake Gemini Live socket (no network)."""
import io
import json
import math
import struct
import wave

import pytest
from fastapi.testclient import TestClient

from app import config, voice
from app.main import app

c = TestClient(app, raise_server_exceptions=False)


def wav(seconds=1.0, rate=48_000) -> bytes:
    """A real WAV (a 440 Hz tone), as a browser fallback recording would be."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate)))
                               for i in range(int(seconds * rate))))
    return buf.getvalue()


class FakeLive:
    """Records what the backend sends; answers like gemini-3.5-transcribe-live (no turnComplete)."""
    def __init__(self, text="20 kg butter for Monday.", fail=False):
        self.sent, self.text, self.fail, self.headers = [], text, fail, None
        self.replies = [{"setupComplete": {}},
                        {"serverContent": {"interimInputTranscription": {"text": "20 kg"}}},
                        {"serverContent": {"inputTranscription": {"text": text}}},
                        {"serverContent": {"generationComplete": True}}]

    def __call__(self, url, additional_headers=None, max_size=None):
        self.headers = additional_headers
        if self.fail:
            raise OSError("network down")
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def send(self, msg):
        self.sent.append(json.loads(msg))

    async def recv(self):
        return json.dumps(self.replies.pop(0))


@pytest.fixture
def live(monkeypatch):
    fake = FakeLive()
    monkeypatch.setattr(voice, "connect", fake)
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-chef=chef")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    return fake


def post(body, ctype="audio/wav", key="agent-chef"):
    return c.post("/api/voice/transcribe", content=body,
                  headers={"Content-Type": ctype} | ({"X-Agent-Key": key} if key else {}))


def test_recording_becomes_the_chefs_words(live):
    r = post(wav(1.0))
    assert r.status_code == 200 and r.json() == {"text": "20 kg butter for Monday.", "seconds": 1.0,
                                                 "model": config.GEMINI_LISTEN_MODEL}
    setup, start, *audio, end = live.sent
    assert setup["setup"]["model"] == f"models/{config.GEMINI_LISTEN_MODEL}"
    assert setup["setup"]["realtimeInputConfig"]["automaticActivityDetection"]["disabled"] is True  # push-to-talk
    assert "activityStart" in start["realtimeInput"] and "activityEnd" in end["realtimeInput"]
    assert all(a["realtimeInput"]["audio"]["mimeType"] == "audio/pcm;rate=16000" for a in audio)
    assert len(audio) == 10  # 1 s at 16 kHz in 100 ms chunks (resampled from 48 kHz)
    assert live.headers == {"x-goog-api-key": "test-key"}  # the key goes to Google in a header, never to the browser


@pytest.mark.parametrize("body, ctype, status", [
    (wav(1.0), "text/plain", 415),
    (b"", "audio/webm", 422),
    (b"definitely not audio", "audio/webm", 422),
    (wav(0.1), "audio/wav", 422),      # too short
    (wav(31.0, rate=8000), "audio/wav", 422),  # over 30 s
])
def test_bad_recordings_get_a_plain_reason(live, body, ctype, status):
    r = post(body, ctype)
    assert r.status_code == status and isinstance(r.json()["detail"], str)


def test_decoder_errors_never_reach_the_client(live):
    # Live probe found "[Errno 1094995529] Invalid data found when processing input" in the 422 (PyAV errors are
    # ValueErrors, so they slipped through the pass-through for our own messages).
    for junk in (b"\x00not audio at all" * 10, b"\x00" * 200_000, b"RIFF\x00\x00\x00\x00WAVEjunk"):
        r = post(junk, "audio/webm")
        assert r.status_code == 422 and "Errno" not in r.text and "Invalid data" not in r.text
        assert "not a readable audio recording" in r.json()["detail"]


def test_size_cap_and_auth(live):
    assert post(b"x" * (voice.MAX_BYTES + 1), "audio/webm").status_code == 413  # refused before it is read
    assert post(wav(1.0), key=None).status_code == 401
    assert post(wav(1.0), key="nope").status_code == 401


def test_live_down_or_silence_is_a_clear_error(live, monkeypatch):
    monkeypatch.setattr(voice, "connect", FakeLive(fail=True))
    r = post(wav(1.0))
    assert r.status_code == 503 and "type the order" in r.json()["detail"]
    monkeypatch.setattr(voice, "connect", FakeLive(text=""))
    assert post(wav(1.0)).status_code == 422


def test_other_routes_keep_the_small_body_cap(live):
    r = c.post("/api/agent/ask", content=b"x" * 70_000, headers={"Content-Type": "application/json",
                                                                  "X-Agent-Key": "agent-chef"})
    assert r.status_code == 413


@pytest.mark.skipif(not __import__("os").environ.get("RUN_LIVE_VOICE") or not __import__("shutil").which("say"),
                    reason="live: RUN_LIVE_VOICE=1 on macOS (uses `say`, afconvert and the real Gemini key)")
def test_live_recording_with_say(tmp_path):
    """RUN_LIVE_VOICE=1 .venv/bin/python -m pytest -q tests/test_voice.py -k live -s : a real spoken clip, real Live."""
    import asyncio
    import subprocess
    import time
    aiff, wav_ = tmp_path / "t.aiff", tmp_path / "t.wav"
    subprocess.run(["say", "-o", str(aiff), "Twenty kilos of butter for Monday"], check=True)
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(wav_)], check=True)
    t = time.monotonic()
    out = asyncio.run(voice.transcribe(wav_.read_bytes(), "audio/wav"))
    print(f"\nlive: {out['seconds']} s of audio → {out['text']!r} in {time.monotonic() - t:.2f} s")
    assert "butter" in out["text"].lower() and "20" in out["text"]


def test_decoder_is_pinned_to_the_declared_type(live):
    """Security review: no format auto-probing (a WAV sent as audio/webm is refused, not sniffed and decoded)."""
    assert post(wav(1.0), "audio/webm").status_code == 422
    with pytest.raises(ValueError):
        voice.to_pcm16(b"#EXTM3U\n#EXT-X-TARGETDURATION:1\nhttp://169.254.169.254/latest\n", "audio/mpeg")
