"""Talk (WebSocket /api/live) with a fake Gemini Live socket: no network, no Gemini key needed."""
import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import config, live, orders
from app.main import app

c = TestClient(app)


@pytest.fixture(autouse=True)
def clear_live_state():
    live._open.clear()
    if hasattr(live, "_warm"):
        live._warm.clear()
    yield
    live._open.clear()
    if hasattr(live, "_warm"):
        live._warm.clear()


class FakeLive:
    """Answers setup, then plays `script`; afterwards waits until the session closes. Records what it was sent."""
    def __init__(self, script):
        self.script, self.sent, self.closed = list(script), [], asyncio.Event()

    def __call__(self, url, additional_headers=None, max_size=None):
        self.headers = additional_headers
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        self.closed.set()

    async def send(self, msg):
        self.sent.append(json.loads(msg))

    async def recv(self):
        return json.dumps({"setupComplete": {}})

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.script:
            await asyncio.sleep(0.01)
            return json.dumps(self.script.pop(0))
        await self.closed.wait()
        raise StopAsyncIteration


@pytest.fixture
def talk(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-chef=chef")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(config, "TALK_ENABLED", True)
    monkeypatch.setattr(orders, "AUDIT_FILE", tmp_path / "audit.jsonl")

    def use(script):
        fake = FakeLive(script)
        monkeypatch.setattr(live, "connect", fake)
        return fake
    return use


def until(ws, kind):
    seen = []
    while True:
        m = ws.receive_json()
        seen.append(m)
        if m["type"] == kind:
            return seen


def many_talk(monkeypatch):
    monkeypatch.setattr(config, "AGENT_KEYS", "agent-chef=chef")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(config, "TALK_ENABLED", True)
    fakes = []

    def connect(*_args, **_kwargs):
        fake = FakeLive([])
        fakes.append(fake)
        return fake

    monkeypatch.setattr(live, "connect", connect)
    return fakes


def test_bad_key_is_refused_with_4401(talk):
    fake = talk([])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "nope"})
        assert ws.receive_json()["type"] == "error"
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
    assert e.value.code == 4401 and fake.sent == []  # Gemini never contacted


def test_foreign_origin_is_refused(talk):
    talk([])
    with pytest.raises(WebSocketDisconnect) as e:
        with c.websocket_connect("/api/live", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_json()
    assert e.value.code == 4403


def test_tool_call_runs_the_agent_and_sends_the_result_card(talk, monkeypatch):
    body = {"intent": "order", "speak": "Ordered: 20 L milk, arriving Monday.", "question": None,
            "conversation_id": None, "order": {"status": "confirmed", "total_cents": 3120}, "lines": []}
    asked = []

    async def fake_ask(text, requested, buyer_id, follow_up=None):
        asked.append((text, buyer_id, follow_up))
        return body
    monkeypatch.setattr(live.ask, "ask", fake_ask)
    fake = talk([{"toolCall": {"functionCalls": [{"id": "c1", "name": "ask_agent",
                                                  "args": {"text": "20 litres of lactose-free milk for Monday"}}]}},
                 {"serverContent": {"modelTurn": {"parts": [{"inlineData": {"mimeType": "audio/pcm;rate=24000",
                                                                            "data": "AAAA"}}]},
                                    "outputTranscription": {"text": "Done, it's ordered."}}},
                 {"serverContent": {"turnComplete": True}}])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert ws.receive_json() == {"type": "ready"}
        seen = until(ws, "turn_complete")
        ws.send_json({"type": "stop"})
    kinds = [m["type"] for m in seen]
    assert kinds[:3] == ["tool", "result", "tool"] and seen[1]["payload"] == body
    assert seen[0]["status"] == "running" and seen[2]["status"] == "done" and seen[0]["label"]
    assert {"type": "audio", "data": "AAAA"} in seen
    assert {"type": "transcript", "role": "agent", "text": "Done, it's ordered.", "final": True} in seen
    assert asked == [("20 litres of lactose-free milk for Monday", "chef", None)]  # the buyer comes from the key
    resp = next(m["toolResponse"] for m in fake.sent if "toolResponse" in m)["functionResponses"][0]
    assert resp["id"] == "c1" and resp["response"]["say"] == body["speak"]
    assert resp["response"]["order_status"] == "confirmed" and resp["response"]["total"] == "31.20 EUR"
    setup = fake.sent[0]["setup"]
    names = [f["name"] for f in setup["tools"][0]["functionDeclarations"]]
    assert names == ["ask_agent", "search_catalogue"]  # no approve tool, ever
    assert any(f["name"] == "current_order"
               for group in setup["tools"] for f in group["functionDeclarations"])
    assert fake.headers == {"x-goog-api-key": "test-key"}


def test_transcripts_strip_tags_accumulate_and_drop_short_user_turns(talk):
    fake = talk([
        {"serverContent": {"inputTranscription": {"text": "as"}}},
        {"serverContent": {"turnComplete": True}},
        {"serverContent": {"inputTranscription": {"text": "<no speech>"}}},
        {"serverContent": {"inputTranscription": {"text": "speech>15 kg"}}},
        {"serverContent": {"inputTranscription": {"text": "{pause} reindeer roast"}}},
        {"serverContent": {"turnComplete": True}},
    ])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert ws.receive_json() == {"type": "ready"}
        first = until(ws, "turn_complete")
        second = until(ws, "turn_complete")
        ws.send_json({"type": "stop"})

    assert not [m for m in first if m["type"] == "transcript"]
    user = [m for m in second if m["type"] == "transcript" and m["role"] == "user"]
    assert [m["text"] for m in user if not m["final"]] == ["15 kg", "15 kg reindeer roast"]
    assert [m["text"] for m in user if m["final"]] == ["15 kg reindeer roast"]
    assert all("<" not in m["text"] and "{" not in m["text"] for m in user)


def test_current_order_tool_uses_the_shared_bounded_snapshot(monkeypatch):
    snapshot = {"orders": [{"requested_date": "2026-11-16", "status": "pending_approval",
                            "lines": [{"name": "Milk", "amount": 10, "unit": "L"}],
                            "total_cents": 3120}], "total_cents": 3120}
    monkeypatch.setattr(live.conversation, "current_order", lambda buyer_id: snapshot)
    assert asyncio.run(live.current_order("chef")) == snapshot


def test_current_order_tool_call_returns_the_snapshot(talk, monkeypatch):
    snapshot = {"orders": [{"requested_date": "2026-11-16", "status": "confirmed",
                            "lines": [{"name": "Milk", "amount": 10, "unit": "L"}],
                            "total_cents": 3120}], "total_cents": 3120}
    monkeypatch.setattr(live.conversation, "current_order", lambda buyer_id: snapshot)
    fake = talk([{"toolCall": {"functionCalls": [{"id": "current", "name": "current_order", "args": {}}]}},
                 {"serverContent": {"turnComplete": True}}])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert ws.receive_json() == {"type": "ready"}
        until(ws, "turn_complete")
        ws.send_json({"type": "stop"})
    response = next(m["toolResponse"] for m in fake.sent if "toolResponse" in m)["functionResponses"][0]
    assert response["response"] == snapshot


@pytest.mark.parametrize("query, alias", [("oat milk", "oat drink"), ("almond milk", "almond drink")])
def test_search_catalogue_uses_bilingual_kitchen_aliases(monkeypatch, query, alias):
    product = {"id": query, "name_en": f"Valio {alias}", "name_fi": None}
    monkeypatch.setattr(live.expand, "queries", lambda _query: asyncio.sleep(0, result=[query]))
    monkeypatch.setattr(live.catalogue, "search",
                        lambda text, *_args: [product] if text == alias else [])
    monkeypatch.setattr(live.valio, "get_quotes", lambda *_args, **_kwargs: asyncio.sleep(0, result=[]))
    result = asyncio.run(live.search_catalogue({"query": query}))
    assert result["products"] and result["products"][0]["name"] == product["name_en"]


def test_search_catalogue_is_honest_when_no_plant_drink_exists(monkeypatch):
    monkeypatch.setattr(live.expand, "queries", lambda _query: asyncio.sleep(0, result=["oat milk"]))
    monkeypatch.setattr(live.catalogue, "search", lambda *_args: [])
    result = asyncio.run(live.search_catalogue({"query": "oat milk"}))
    assert not result["products"] and "oat milk" in result["message"] and "oat drink" in result["message"]


def test_barge_in_and_audio_pass_through(talk):
    fake = talk([{"serverContent": {"interrupted": True}}])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert ws.receive_json() == {"type": "ready"}
        ws.send_json({"type": "audio", "data": "AAAAAA=="})
        assert ws.receive_json() == {"type": "interrupted"}
        ws.send_json({"type": "text", "text": "and some butter"})
        ws.send_json({"type": "stop"})
    audio = [m for m in fake.sent if "realtimeInput" in m]
    assert audio and audio[0]["realtimeInput"]["audio"] == {"data": "AAAAAA==", "mimeType": "audio/pcm;rate=16000"}


def test_ask_agent_prefers_v2_reply_and_cart_grounding(monkeypatch):
    async def fake_ask(*_args, **_kwargs):
        return {"reply": "The cart still marks butter unavailable.", "speak": "legacy summary",
                "question": None, "conversation_id": None, "order": None}

    monkeypatch.setattr(live.ask, "ask", fake_ask)
    short, body = asyncio.run(live.ask_agent("chef", {"text": "Does it still show not available?"}))
    assert short["say"] == body["reply"] and "current cart" in live.SYSTEM


def test_switched_off_and_health(talk, monkeypatch):
    monkeypatch.setattr(config, "TALK_ENABLED", False)
    assert c.get("/api/health").json()["talk"] is False
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert "switched off" in ws.receive_json()["message"]
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
    assert e.value.code == 4503


def test_signed_buyers_refused_and_every_tool_call_costs_a_token(talk, monkeypatch):
    """Security review: a buyer that registered RFC 9421 keys can't use Talk to skip signatures; each tool call takes
    a token from the same agent bucket as HTTP requests."""
    from app import httpsig, ratelimit
    monkeypatch.setattr(httpsig, "keys_for", lambda buyer: {"k1": object()} if buyer == "chef" else {})
    talk([])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert "signed requests" in ws.receive_json()["message"]
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
    assert e.value.code == 4401
    monkeypatch.setattr(httpsig, "keys_for", lambda buyer: {})
    waits = iter([0, 5])  # session start passes; the tool call finds the bucket empty
    monkeypatch.setattr(ratelimit, "wait_s", lambda kind, who, now=None: 0 if kind == "ip" else next(waits))
    fake = talk([{"toolCall": {"functionCalls": [{"id": "c1", "name": "ask_agent", "args": {"text": "milk"}}]}},
                 {"serverContent": {"turnComplete": True}}])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert ws.receive_json() == {"type": "ready"}
        seen = until(ws, "turn_complete")
        ws.send_json({"type": "stop"})
    assert "result" not in [m["type"] for m in seen]
    resp = next(m["toolResponse"] for m in fake.sent if "toolResponse" in m)["functionResponses"][0]
    assert "Too many requests" in resp["response"]["error"]


def test_warm_session_idles_out_with_plain_error(talk, monkeypatch):
    monkeypatch.setattr(live, "WARM_IDLE_S", 0.02, raising=False)
    monkeypatch.setattr(live, "SESSION_S", 0.08)
    fake = talk([])

    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef", "warm": True})
        assert ws.receive_json() == {"type": "ready"}
        assert ws.receive_json() == {"type": "error", "message": "Idle: tap the mic to start again."}
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
    assert e.value.code == 1000 and fake.sent[0].get("setup")


def test_warm_session_clock_starts_at_first_text(talk, monkeypatch):
    monkeypatch.setattr(live, "WARM_IDLE_S", 0.5, raising=False)
    monkeypatch.setattr(live, "SESSION_S", 0.12)
    talk([])

    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef", "warm": True})
        assert ws.receive_json() == {"type": "ready"}
        time.sleep(0.2)  # longer than SESSION_S, but still inside the warm idle window
        ws.send_json({"type": "text", "text": "milk"})
        sent_at = time.monotonic()
        assert ws.receive_json() == {"type": "error", "message": "The conversation reached its 5-minute limit."}
        assert time.monotonic() - sent_at >= 0.08
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
    assert e.value.code == 1000


def test_warm_socket_does_not_consume_real_session_capacity(monkeypatch):
    many_talk(monkeypatch)
    with c.websocket_connect("/api/live") as warm:
        warm.send_json({"type": "auth", "agent_key": "agent-chef", "warm": True})
        assert warm.receive_json() == {"type": "ready"}
        with c.websocket_connect("/api/live") as real_one:
            real_one.send_json({"type": "auth", "agent_key": "agent-chef"})
            assert real_one.receive_json() == {"type": "ready"}
            with c.websocket_connect("/api/live") as real_two:
                real_two.send_json({"type": "auth", "agent_key": "agent-chef"})
                assert real_two.receive_json() == {"type": "ready"}
                with c.websocket_connect("/api/live") as refused:
                    refused.send_json({"type": "auth", "agent_key": "agent-chef"})
                    assert refused.receive_json()["type"] == "error"
                    with pytest.raises(WebSocketDisconnect) as e:
                        refused.receive_json()
                assert e.value.code == 4429


def test_warm_promotion_is_refused_when_real_capacity_is_full(monkeypatch):
    many_talk(monkeypatch)
    with c.websocket_connect("/api/live") as real_one:
        real_one.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert real_one.receive_json() == {"type": "ready"}
        with c.websocket_connect("/api/live") as real_two:
            real_two.send_json({"type": "auth", "agent_key": "agent-chef"})
            assert real_two.receive_json() == {"type": "ready"}
            with c.websocket_connect("/api/live") as warm:
                warm.send_json({"type": "auth", "agent_key": "agent-chef", "warm": True})
                assert warm.receive_json() == {"type": "ready"}
                warm.send_json({"type": "text", "text": "milk"})
                assert warm.receive_json()["type"] == "error"
                with pytest.raises(WebSocketDisconnect) as e:
                    warm.receive_json()
            assert e.value.code == 4429


def test_fourth_warm_socket_drops_the_oldest(monkeypatch):
    many_talk(monkeypatch)
    with c.websocket_connect("/api/live") as first:
        first.send_json({"type": "auth", "agent_key": "agent-chef", "warm": True})
        assert first.receive_json() == {"type": "ready"}
        with c.websocket_connect("/api/live") as second:
            second.send_json({"type": "auth", "agent_key": "agent-chef", "warm": True})
            assert second.receive_json() == {"type": "ready"}
            with c.websocket_connect("/api/live") as third:
                third.send_json({"type": "auth", "agent_key": "agent-chef", "warm": True})
                assert third.receive_json() == {"type": "ready"}
                with c.websocket_connect("/api/live") as fourth:
                    fourth.send_json({"type": "auth", "agent_key": "agent-chef", "warm": True})
                    assert fourth.receive_json() == {"type": "ready"}
                    with pytest.raises(WebSocketDisconnect) as e:
                        first.receive_json()
                    assert e.value.code == 1000
