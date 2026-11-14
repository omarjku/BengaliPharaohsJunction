"""Spike: Gemini Live from the backend (the key goes in a header, never to the browser). See docs/VOICE.md.

Usage:  cd backend && .venv/bin/python scripts/voice_spike.py speech.wav [models/gemini-3.5-transcribe-live]
Measures the push-to-talk transcript latency (manual activityStart/activityEnd) and the read-back time to first
audio. The transcribe model is text-only: its "speak" phase fails by design (read-back uses gemini-3.8-live)."""
import asyncio, base64, json, sys, time, wave
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
import websockets
from app import config

URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
MODEL = sys.argv[2] if len(sys.argv) > 2 else "models/gemini-3.8-live"

async def session(setup_extra, send, label):
    t0 = time.monotonic()
    async with websockets.connect(URL, additional_headers={"x-goog-api-key": config.GEMINI_API_KEY}, max_size=None) as ws:
        await ws.send(json.dumps({"setup": {"model": MODEL, **setup_extra}}))
        msg = json.loads(await ws.recv()); t_setup = time.monotonic() - t0
        assert "setupComplete" in msg, msg
        t_sent = await send(ws)
        transcript, out_text, first_audio, audio_bytes, t_tr = "", "", None, 0, None
        while True:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), 20))
            except asyncio.TimeoutError:
                break
            sc = m.get("serverContent", {})
            if "inputTranscription" in sc:
                transcript += sc["inputTranscription"].get("text", ""); t_tr = time.monotonic() - t_sent
            if "outputTranscription" in sc:
                out_text += sc["outputTranscription"].get("text", "")
            for part in sc.get("modelTurn", {}).get("parts", []):
                if "inlineData" in part:
                    if first_audio is None: first_audio = time.monotonic() - t_sent
                    audio_bytes += len(base64.b64decode(part["inlineData"]["data"]))
            if sc.get("turnComplete"):
                break
        print(f"[{label}] setup {t_setup:.2f}s | transcript {t_tr and f'{t_tr:.2f}s'}: {transcript.strip()!r} | "
              f"first audio {first_audio and f'{first_audio:.2f}s'} ({audio_bytes} bytes) | said: {out_text.strip()!r}")

async def main():
    with wave.open(sys.argv[1]) as w:
        pcm = w.readframes(w.getnframes()); rate = w.getframerate()
    async def send_audio(ws):
        await ws.send(json.dumps({"realtimeInput": {"activityStart": {}}}))  # button down
        for i in range(0, len(pcm), 3200):  # 100 ms chunks, as a browser would stream them
            await ws.send(json.dumps({"realtimeInput": {"audio": {"data": base64.b64encode(pcm[i:i+3200]).decode(),
                                                                "mimeType": f"audio/pcm;rate={rate}"}}}))
        t = time.monotonic()
        await ws.send(json.dumps({"realtimeInput": {"activityEnd": {}}}))  # button up
        return t
    # 1) push-to-talk: transcript of the chef's speech (the model is told to stay silent: we only want the words)
    listen_modality = ["TEXT"] if "transcribe" in MODEL else ["AUDIO"]
    await session({"generationConfig": {"responseModalities": listen_modality}, "inputAudioTranscription": {},
                   "realtimeInputConfig": {"automaticActivityDetection": {"disabled": True}},
                   "systemInstruction": {"parts": [{"text": "Only listen. Reply with the single word OK."}]}},
                  send_audio, "listen")
    # 2) read-back: speak one sentence the backend wrote
    async def send_text(ws):
        t = time.monotonic()
        await ws.send(json.dumps({"clientContent": {"turns": [{"role": "user", "parts": [{"text":
            "Read this aloud exactly, nothing else: 1,000 litres lactose-free milk, 1,400 euros, ordered for Monday."}]}],
            "turnComplete": True}}))
        return t
    await session({"generationConfig": {"responseModalities": ["AUDIO"]}, "outputAudioTranscription": {}},
                  send_text, "speak")

asyncio.run(main())
