"""Real Gemini Live voice check with isolated local state.

By default this starts the backend on :8795 with a temporary DATA_DIR, runs the requested
three-turn smoke conversation plus the Helsinki standing-order case, and prints transcripts,
tool events, card statuses, and timings. Pass --no-start to use an already-running server.
"""
import argparse
import asyncio
import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.request
import wave
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
PYTHON = Path("/Users/omar/Code/BengaliPharaohsJunction/backend/.venv/bin/python")
PORT = 8795


def agent_key(buyer: str) -> str:
    env = dict(line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines()
               if "=" in line and not line.startswith("#"))
    for part in env["AGENT_KEYS"].strip().strip('"').split(","):
        key, _, who = part.partition("=")
        if who.split(":")[0].strip() == buyer:
            return key.strip()
    raise SystemExit(f"no agent key for {buyer} in .env")


def clip(text: str) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        aiff, wav = Path(d) / "talk.aiff", Path(d) / "talk.wav"
        subprocess.run(["say", "-o", str(aiff), text], check=True)
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(wav)], check=True)
        with wave.open(str(wav)) as stream:
            return stream.readframes(stream.getnframes())


def _health(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


async def start_backend(port: int) -> tuple[subprocess.Popen, tempfile.TemporaryDirectory]:
    data = tempfile.TemporaryDirectory(prefix="talk-check-")
    env = os.environ.copy()
    env.update({
        "DATA_DIR": data.name,
        "SANDBOX_ENABLED": "1",
        "PYTHONPATH": os.pathsep.join((str(ROOT / "contracts"), str(ROOT / "compiler"), str(ROOT / "profile"))),
    })
    process = subprocess.Popen([str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                "--port", str(port)], cwd=BACKEND, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    health = f"http://127.0.0.1:{port}/api/health"
    for _ in range(60):
        if await asyncio.to_thread(_health, health):
            return process, data
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            data.cleanup()
            raise RuntimeError(f"local backend exited with {process.returncode}: {output[-1000:]}")
        await asyncio.sleep(0.25)
    process.terminate()
    data.cleanup()
    raise RuntimeError(f"local backend did not become healthy at {health}")


async def run_turn(ws, buyer: str, number: int, text: str) -> None:
    pcm = clip(text)
    chunk = 3200  # 100 ms at 16 kHz mono PCM16
    started = time.monotonic()
    speech_end = None
    first_audio = None
    result_at = None
    tool_done = None
    spoken_result = None
    tools = []
    transcripts = []
    card_statuses = []
    tool_called = False
    tool_done_seen = False
    post_tool_output = False

    async def speak() -> None:
        nonlocal speech_end
        for at in range(0, len(pcm), chunk):
            await ws.send(json.dumps({"type": "audio", "data": base64.b64encode(pcm[at:at + chunk]).decode()}))
            await asyncio.sleep(0.1)
        speech_end = time.monotonic()
        for _ in range(30):
            await ws.send(json.dumps({"type": "audio", "data": base64.b64encode(b"\0" * chunk).decode()}))
            await asyncio.sleep(0.1)

    print(f"\nTURN {number} [{buyer}] chef: {text!r}")
    sender = asyncio.create_task(speak())
    try:
        while time.monotonic() - started < 60:
            message = json.loads(await asyncio.wait_for(ws.recv(), 30))
            now = time.monotonic()
            kind = message.get("type")
            if kind == "audio":
                if first_audio is None and speech_end is not None:
                    first_audio = now
                if tool_done_seen and speech_end is not None:
                    post_tool_output = True
                if spoken_result is None and (result_at or tool_done) and speech_end is not None:
                    spoken_result = now
            elif kind == "transcript":
                if message.get("final"):
                    transcripts.append((message.get("role"), message.get("text")))
                    print(f"  transcript {message.get('role')}: {message.get('text')}")
                if message.get("role") == "agent" and tool_done_seen:
                    post_tool_output = True
            elif kind == "tool":
                tool_called = True
                tools.append((message.get("name"), message.get("status")))
                print(f"  tool {message.get('status')}: {message.get('name')} — {message.get('label')}")
                if message.get("status") == "done":
                    tool_done = now
                    tool_done_seen = True
            elif kind == "result":
                result_at = now
                payload = message.get("payload") or {}
                order = payload.get("order") or {}
                status = order.get("status") or payload.get("status") or "no-card"
                card_statuses.append(status)
                print(f"  card status: {status}")
            elif kind == "error":
                print(f"  error: {message.get('message')}")
                break
            elif kind == "turn_complete":
                if not tool_called or post_tool_output:
                    break
    finally:
        sender.cancel()
        await asyncio.gather(sender, return_exceptions=True)

    def latency(at):
        return None if at is None or speech_end is None else at - speech_end

    def shown(value):
        return "n/a" if value is None else f"{value:.2f}s"

    print(f"  timing: filler/first audio={shown(latency(first_audio))}, "
          f"card/tool result={shown(latency(result_at or tool_done))}, "
          f"spoken result={shown(latency(spoken_result))}")
    if first_audio is not None and latency(first_audio) > 2:
        print("  TARGET FAIL: first agent audio is over 2s")
    if (result_at or tool_done) is not None and latency(result_at or tool_done) > 8:
        print("  TARGET FAIL: tool/card result is over 8s")


async def run_case(url: str, buyer: str, turns: list[str]) -> None:
    async with websockets.connect(url, max_size=2**22) as ws:
        await ws.send(json.dumps({"type": "auth", "agent_key": agent_key(buyer)}))
        ready = json.loads(await ws.recv())
        print(f"ready [{buyer}]: {ready}")
        for number, text in enumerate(turns, 1):
            await run_turn(ws, buyer, number, text)
        await ws.send(json.dumps({"type": "stop"}))


async def main(url: str, buyer: str, text: str | None, start_local: bool) -> None:
    process = data = None
    if start_local:
        process, data = await start_backend(PORT)
        url = f"ws://127.0.0.1:{PORT}/api/live"
        print(f"local backend: {url} DATA_DIR={data.name}")
    try:
        if text:
            await run_case(url, buyer, [text])
        else:
            await run_case(url, "smoke-kitchen", [
                "I need twenty five kilos of butter for Monday",
                "yes the unsalted one",
                "how much butter is in my order?",
            ])
            await run_case(url, "helsinki-bistro", ["our usual Friday order plus some milk"])
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if data is not None:
            data.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=f"ws://127.0.0.1:{PORT}/api/live")
    parser.add_argument("--buyer", default="smoke-kitchen")
    parser.add_argument("--text", help="Run one spoken turn instead of the acceptance scenarios.")
    parser.add_argument("--no-start", action="store_true", help="Use --url without starting a local backend.")
    args = parser.parse_args()
    asyncio.run(main(args.url, args.buyer, args.text, not args.no_start))
