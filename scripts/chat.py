#!/usr/bin/env python3
"""Talk to the engine from the terminal: no frontend, no server, real Gemini.

    python3 scripts/chat.py                       # interactive, buyer helsinki-bistro
    python3 scripts/chat.py --buyer lapland-kitchen
    python3 scripts/chat.py --script convo.txt    # replay a conversation, one chef line per line

Runs the FastAPI app in-process (TestClient) with a fresh DATA_DIR, so every run starts clean. While the agent has an
open question, what you type answers it (sent as a follow-up); otherwise it's a new message. Each turn prints what
Gemini understood, the reply, the question and choices, the cart, the status, the time it took, and any Gemini failure.

Commands: /new (fresh conversation)  /approve (approve the last held order)  /reject  /orders  /debug (raw JSON on/off)
          /buyer <id>  /quit.   Answer a choice by number ("2") or by text.
"""
import argparse
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="chat-"))
os.environ.setdefault("SANDBOX_ENABLED", "1")
for pkg in ("contracts", "compiler", "profile", "backend"):
    sys.path.insert(0, str(ROOT / pkg))

GEMINI_FAILURES: list[str] = []


class _Catch(logging.Handler):
    def emit(self, record):
        msg = record.getMessage()
        if "Gemini" in msg and ("fail" in msg.lower() or "fallback" in msg.lower()):
            GEMINI_FAILURES.append(msg)


def keys(buyer: str) -> tuple[str, str]:
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"')

    def find(var):
        for part in env.get(var, "").split(","):
            key, _, who = part.partition("=")
            if who.split(":")[0].strip() == buyer:
                return key.strip()
        return ""
    return find("AGENT_KEYS"), find("APPROVER_KEYS")


def money(cents) -> str:
    return "—" if cents is None else f"€{cents / 100:,.2f}"


def lines_of(body: dict) -> list[dict]:
    cards = body.get("cards") or [body]
    out = []
    for card in cards:
        order = card.get("order") or {}
        if order.get("lines"):
            for ln in order["lines"]:
                out.append({"name": ln.get("name") or ln.get("product_id"), "qty": ln.get("quantity"),
                            "unit": ln.get("unit"), "total": ln.get("line_total_cents"), "status": order.get("status")})
            continue
        for ln in card.get("lines") or []:
            if ln.get("chosen"):
                p = ln.get("product") or {}
                q = ln.get("quantity") or {}
                out.append({"name": p.get("name_en") or p.get("name_fi") or p.get("id"), "qty": q.get("quantity"),
                            "unit": q.get("unit") or (ln.get("quote") or {}).get("sales_unit"),
                            "total": ln.get("line_total_cents"), "status": "proposal"})
    return out


def show(body: dict, ms: float, debug: bool) -> None:
    und = body.get("understood") or {}
    acts = und.get("actions") if isinstance(und, dict) else None
    if acts:
        brief = "; ".join(f"{a.get('intent')}{' ' + json.dumps(a.get('slots', {}).get('items'), ensure_ascii=False) if a.get('slots', {}).get('items') else ''}"
                          for a in acts)
        print(f"  \033[2mgemini understood ({und.get('source', '?')}): {brief}\033[0m")
    if und.get("interpretation") if isinstance(und, dict) else None:
        print(f"  \033[2minterpretation: {und['interpretation']}\033[0m")
    reply = body.get("reply") or body.get("speak") or ""
    print(f"\033[1magent:\033[0m {reply}")
    q = body.get("question")
    if q and q not in reply:
        print(f"  question: {q}")
    choices = body.get("choices") or []
    for i, c in enumerate(choices, 1):
        label = c.get("label") if isinstance(c, dict) else c
        print(f"    {i}) {label}")
    lines = lines_of(body)
    for ln in lines:
        print(f"  cart: {ln['qty']} {ln['unit'] or ''} × {ln['name']}  {money(ln['total'])}  [{ln['status']}]")
    order = body.get("order") or {}
    if order:
        print(f"  order {str(order.get('order_id'))[:8]}: {order.get('status')}  total {money(order.get('total_cents'))}")
    d = body.get("decision") or {}
    if d.get("reasons"):
        print(f"  reasons: {', '.join(r.get('code', '?') for r in d['reasons'][:5])}")
    print(f"  \033[2m{ms:.0f} ms{'  ⚠ GEMINI FAILED: ' + GEMINI_FAILURES[-1] if GEMINI_FAILURES else ''}\033[0m")
    GEMINI_FAILURES.clear()
    if debug:
        print(json.dumps(body, ensure_ascii=False, indent=1, default=str)[:6000])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--buyer", default="helsinki-bistro")
    ap.add_argument("--script", help="replay: one chef line per line ('#' comments, '/command' allowed)")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()

    logging.getLogger().addHandler(_Catch())
    from fastapi.testclient import TestClient
    from app import catalogue, main as appmain

    print(f"loading catalogue… (DATA_DIR={os.environ['DATA_DIR']})", flush=True)
    catalogue.load()
    client = TestClient(appmain.app)
    buyer, debug = a.buyer, a.debug
    agent, approver = keys(buyer)
    if not agent:
        sys.exit(f"no agent key for {buyer} in .env")
    convo, pending, last_order = None, False, None
    lines_in = (Path(a.script).read_text().splitlines() if a.script else None)

    def next_line():
        if lines_in is None:
            try:
                return input("\n\033[1mchef:\033[0m ")
            except EOFError:
                return "/quit"
        while lines_in:
            ln = lines_in.pop(0)
            if ln.strip() and not ln.lstrip().startswith("#"):
                print(f"\n\033[1mchef:\033[0m {ln}")
                return ln
        return "/quit"

    print(f"buyer {buyer}. Type like a chef. /new /approve /reject /orders /debug /buyer <id> /quit")
    while True:
        text = next_line().strip()
        if not text:
            continue
        if text == "/quit":
            break
        if text == "/new":
            convo, pending = None, False
            print("  (new conversation)")
            continue
        if text == "/debug":
            debug = not debug
            print(f"  debug {'on' if debug else 'off'}")
            continue
        if text.startswith("/buyer "):
            buyer = text.split(None, 1)[1]
            agent, approver = keys(buyer)
            convo, pending = None, False
            print(f"  buyer {buyer} ({'keys ok' if agent else 'NO KEYS'})")
            continue
        if text == "/orders":
            r = client.get("/api/orders", headers={"X-Agent-Key": agent})
            for o in (r.json() if r.status_code == 200 else [])[-8:]:
                print(f"  {str(o.get('order_id'))[:8]} {o.get('status')} {o.get('requested_date')} {money(o.get('total_cents'))}")
            if r.status_code != 200:
                print(f"  HTTP {r.status_code}")
            continue
        if text in ("/approve", "/reject"):
            if not last_order:
                print("  no held order in this conversation")
                continue
            r = client.post(f"/api/orders/{last_order}/{text[1:]}", headers={"X-Approver-Key": approver})
            b = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            print(f"  HTTP {r.status_code}: {b.get('status') or b.get('detail')}")
            continue
        body = {"follow_up": {"to": convo, "answer": text}} if (pending and convo) else {"text": text}
        t0 = time.perf_counter()
        r = client.post("/api/agent/ask", json=body, headers={"X-Agent-Key": agent})
        ms = (time.perf_counter() - t0) * 1000
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}: {r.text[:400]}")
            if r.status_code == 404 and pending:  # the question expired: send it as a new message next time
                pending = False
            continue
        out = r.json()
        show(out, ms, debug)
        convo = out.get("conversation_id") or convo
        pending = bool(out.get("question") or out.get("choices"))
        oid = (out.get("order") or {}).get("order_id")
        if oid:
            last_order = oid


if __name__ == "__main__":
    main()
