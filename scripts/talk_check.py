"""Real end-to-end check of Talk (/api/live): a spoken WAV in, transcripts + tool events + audio out.

    python3 scripts/talk_check.py [ws://localhost:8000/api/live] [--buyer smoke-kitchen] [--text "..."]

Makes the clip with macOS `say` (16 kHz mono PCM16 via afconvert), reads the agent key for --buyer from .env
(never printed), streams the clip in real-time 100 ms chunks followed by silence (so Gemini's voice detection ends
the turn), and prints every event until the agent's spoken answer after a tool result is complete.
"""
import argparse
import asyncio
import base64
import json
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parent.parent


def agent_key(buyer: str) -> str:
    env = dict(line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines() if "=" in line and not line.startswith("#"))
    for part in env["AGENT_KEYS"].strip().strip('"').split(","):
        key, _, who = part.partition("=")
        if who.split(":")[0].strip() == buyer:
            return key.strip()
    raise SystemExit(f"no agent key for {buyer} in .env")


def clip(text: str) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        aiff, wav = Path(d) / "t.aiff", Path(d) / "t.wav"
        subprocess.run(["say", "-o", str(aiff), text], check=True)
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(wav)], check=True)
        with wave.open(str(wav)) as w:
            return w.readframes(w.getnframes())


async def main(url: str, buyer: str, text: str) -> None:
    pcm = clip(text)
    chunk = 3200  # 100 ms
    async with websockets.connect(url, max_size=2**22) as ws:
        t0 = time.monotonic()
        await ws.send(json.dumps({"type": "auth", "agent_key": agent_key(buyer)}))
        print(f"{time.monotonic() - t0:5.2f}s", json.loads(await ws.recv()))
        speech_end = None

        async def speak():
            nonlocal speech_end
            for i in range(0, len(pcm), chunk):
                await ws.send(json.dumps({"type": "audio", "data": base64.b64encode(pcm[i:i + chunk]).decode()}))
                await asyncio.sleep(0.1)
            speech_end = time.monotonic()
            for _ in range(30):  # 3 s of silence: the end of the chef's turn
                await ws.send(json.dumps({"type": "audio", "data": base64.b64encode(b"\0" * chunk).decode()}))
                await asyncio.sleep(0.1)
        sender = asyncio.create_task(speak())
        first_audio, audio_chunks, had_result, t_start, answered = None, 0, False, time.monotonic(), False
        while time.monotonic() - t_start < 60:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), 30))
            except asyncio.TimeoutError:
                print("timeout waiting for events"); break
            t = time.monotonic() - t0
            if m["type"] == "audio":
                audio_chunks += 1
                if had_result and not answered:
                    answered = True  # the spoken answer AFTER the tool result
                    print(f"{t:5.2f}s agent starts the answer, {time.monotonic() - t_result:.2f}s after the result")
                if first_audio is None and speech_end:
                    first_audio = time.monotonic() - speech_end
                    print(f"{t:5.2f}s first agent audio, {first_audio:.2f}s after the chef stopped speaking")
                continue
            if m["type"] == "result":
                had_result, answered, t_result = True, False, time.monotonic()
                p = m["payload"]
                print(f"{t:5.2f}s result: intent={p.get('intent')} order={(p.get('order') or {}).get('status')} "
                      f"question={p.get('question')!r} speak={p.get('speak')!r}")
                continue
            if m["type"] == "transcript" and not m["final"]:
                continue
            print(f"{t:5.2f}s", m)
            if m["type"] == "turn_complete" and answered:
                break
            if m["type"] == "error":
                break
        sender.cancel()
        await ws.send(json.dumps({"type": "stop"}))
        print(f"audio chunks received: {audio_chunks}; tool result: {had_result}")


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("url", nargs="?", default="ws://localhost:8000/api/live")
    a.add_argument("--buyer", default="smoke-kitchen")
    a.add_argument("--text", default="I need 20 litres of lactose-free milk for Monday.")
    args = a.parse_args()
    asyncio.run(main(args.url, args.buyer, args.text))
