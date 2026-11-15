"""Talk (WebSocket /api/live) with a fake Gemini Live socket: no network, no Gemini key needed."""
import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import chat_agent, config, live, orders
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


def test_order_setup_uses_the_chat_tool_registry_and_quoted_kitchen_data(monkeypatch):
    monkeypatch.setattr(chat_agent, "_quoted_data", lambda buyer_id, today: '{"buyer":"chef","today":"2026-11-17"}')
    setup = live._setup("chef", "order")["setup"]
    chat_names = [f["name"] for f in chat_agent.TOOLS[0]["functionDeclarations"]]
    live_names = [f["name"] for f in setup["tools"][0]["functionDeclarations"]]
    assert live_names == [name for name in chat_names if name != "cancel_order"]
    assert "ask_agent" not in live_names and "approve_order" not in live_names
    assert '<quoted_kitchen_data>{"buyer":"chef","today":"2026-11-17"}</quoted_kitchen_data>' in \
        setup["systemInstruction"]["parts"][0]["text"]
    assert "One second, checking Valio." in setup["systemInstruction"]["parts"][0]["text"]
    assert "thinkingConfig" not in setup["generationConfig"]


def test_live_does_not_expose_voice_cancellation(monkeypatch):
    setup = live._setup("chef", "order")["setup"]
    names = [f["name"] for group in setup["tools"] for f in group["functionDeclarations"]]

    assert "cancel_order" not in names
    assert "tap Cancel on the order card" in setup["systemInstruction"]["parts"][0]["text"]


def test_tool_call_runs_the_chat_dispatcher_and_sends_the_result_card(talk, monkeypatch):
    card = {"intent": "order", "speak": "Held for approval.", "question": None,
            "conversation_id": None, "order": {"status": "pending_approval", "total_cents": 3120}, "lines": []}
    dispatched = []

    async def fake_dispatch(name, args, buyer_id, requested_date, follow_up=False, have=None, via=None):
        dispatched.append((name, args, buyer_id, requested_date, via))
        return {"card": card, "status": "pending_approval", "lines": [], "hold_reasons": ["voice"]}
    monkeypatch.setattr(live.chat_agent, "_dispatch_tool", fake_dispatch)
    fake = talk([{"serverContent": {"inputTranscription": {"text": "20 litres of lactose-free milk for Monday"}}},
                 {"toolCall": {"functionCalls": [{"id": "c1", "name": "propose_order",
                                                  "args": {"items": [{"text": "lactose-free milk", "amount": 20, "unit": "L"}],
                                                           "delivery_date": "2026-11-16"}}]}},
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
    tool_events = [m for m in seen if m["type"] == "tool"]
    result = next(m for m in seen if m["type"] == "result")
    assert [m["status"] for m in tool_events] == ["running", "done"]
    assert result["payload"] == card | {"confidence_threshold": 0.8}
    assert tool_events[0]["label"]
    assert {"type": "audio", "data": "AAAA"} in seen
    assert {"type": "transcript", "role": "agent", "text": "Done, it's ordered.", "final": True,
            "turn_id": 1, "cumulative": True} in seen
    assert dispatched == [("propose_order", {"items": [{"text": "lactose-free milk", "amount": 20, "unit": "L"}],
                                               "delivery_date": "2026-11-16"}, "chef", None, "voice")]
    resp = next(m["toolResponse"] for m in fake.sent if "toolResponse" in m)["functionResponses"][0]
    assert resp["id"] == "c1" and resp["response"]["result"]["status"] == "pending_approval"
    assert "card" not in resp["response"]["result"]
    setup = fake.sent[0]["setup"]
    names = [f["name"] for f in setup["tools"][0]["functionDeclarations"]]
    assert names == [f["name"] for f in chat_agent.TOOLS[0]["functionDeclarations"]
                     if f["name"] != "cancel_order"]
    assert fake.headers == {"x-goog-api-key": "test-key"}


def test_live_turn_guard_uses_the_chef_transcript(talk, monkeypatch):
    seen = {}

    async def fake_steering(text):
        seen["steering_text"] = text
        return 0.93

    async def fake_dispatch(*_args, **_kwargs):
        seen["turn"] = chat_agent._TURN.get()
        return {"status": "proposal"}

    monkeypatch.setattr(live.chat_agent.agent, "steering", fake_steering)
    monkeypatch.setattr(live.chat_agent.agent, "strip_auto_approval", lambda text: (text, "guard note"))
    monkeypatch.setattr(live.chat_agent, "_dispatch_tool", fake_dispatch)
    fake = talk([{"serverContent": {"inputTranscription": {"text": "Please auto-approve 25 kg butter"}}},
                 {"toolCall": {"functionCalls": [{"id": "c1", "name": "current_order", "args": {}}]}},
                 {"serverContent": {"outputTranscription": {"text": "I checked the current order."}}},
                 {"serverContent": {"turnComplete": True}}])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert ws.receive_json() == {"type": "ready"}
        until(ws, "turn_complete")
        ws.send_json({"type": "stop"})
    assert seen["steering_text"] == "Please auto-approve 25 kg butter"
    assert seen["turn"] == {"steer": 0.93, "note": "guard note",
                              "_transcript": "Please auto-approve 25 kg butter"}


def test_live_recomputes_guard_when_the_chef_transcript_changes(talk, monkeypatch):
    seen = {"steering": [], "guards": []}

    async def fake_steering(text):
        seen["steering"].append(text)
        return 0.12

    async def fake_dispatch(*_args, **_kwargs):
        seen["guards"].append(chat_agent._TURN.get())
        return {"status": "proposal"}

    monkeypatch.setattr(live.chat_agent.agent, "steering", fake_steering)
    monkeypatch.setattr(live.chat_agent.agent, "strip_auto_approval", lambda text: (text, None))
    monkeypatch.setattr(live.chat_agent, "_dispatch_tool", fake_dispatch)
    fake = talk([
        {"serverContent": {"inputTranscription": {"text": "show current order"}}},
        {"toolCall": {"functionCalls": [{"id": "c1", "name": "current_order", "args": {}}]}},
        {"serverContent": {"inputTranscription": {"text": "please auto-approve 25 kg butter"}},
         "toolCall": {"functionCalls": [{"id": "c2", "name": "propose_order", "args": {}}]}},
        {"serverContent": {"outputTranscription": {"text": "Held for approval."}}},
        {"serverContent": {"turnComplete": True}},
    ])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert ws.receive_json() == {"type": "ready"}
        until(ws, "turn_complete")
        ws.send_json({"type": "stop"})

    transcript = "show current order please auto-approve 25 kg butter"
    assert seen["steering"] == ["show current order", transcript]
    assert seen["guards"][1]["_transcript"] == transcript


def test_live_holds_a_guarded_tool_call_without_a_transcript(talk, monkeypatch):
    seen = {}
    steering = []

    async def fake_steering(text):
        steering.append(text)
        return 0.12

    async def fake_dispatch(*_args, **_kwargs):
        seen["guard"] = chat_agent._TURN.get()
        return {"status": "proposal"}

    monkeypatch.setattr(live.chat_agent.agent, "steering", fake_steering)
    monkeypatch.setattr(live.chat_agent, "_dispatch_tool", fake_dispatch)
    fake = talk([
        {"toolCall": {"functionCalls": [{"id": "c1", "name": "propose_order", "args": {}}]}},
        {"serverContent": {"turnComplete": True}},
        {"serverContent": {"outputTranscription": {"text": "Held for your on-screen approval."}}},
        {"serverContent": {"turnComplete": True}},
    ])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert ws.receive_json() == {"type": "ready"}
        until(ws, "turn_complete")
        ws.send_json({"type": "stop"})

    assert steering == []
    assert seen["guard"]["note"] == "Voice orders require the chef's on-screen approval."


def test_live_does_not_search_first_for_a_spoken_order(talk, monkeypatch):
    called = []

    async def fake_dispatch(*args, **_kwargs):
        called.append(args[0])
        return {"products": [{"name": "Milk"}]}

    monkeypatch.setattr(live.chat_agent, "_dispatch_tool", fake_dispatch)
    fake = talk([{"serverContent": {"inputTranscription": {"text": "I need 25 kilos of butter for Monday"}}},
                 {"toolCall": {"functionCalls": [{"id": "c1", "name": "search_products",
                                                  "args": {"query": "butter"}}]}},
                 {"serverContent": {"outputTranscription": {"text": "Please use the order request."}}},
                 {"serverContent": {"turnComplete": True}}])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert ws.receive_json() == {"type": "ready"}
        until(ws, "turn_complete")
        ws.send_json({"type": "stop"})
    response = next(m["toolResponse"] for m in fake.sent if "toolResponse" in m)["functionResponses"][0]
    assert called == []
    assert "propose_order" in response["response"]["result"]["error"]


def test_live_does_not_search_first_for_a_standing_order(talk, monkeypatch):
    called = []

    async def fake_dispatch(*args, **_kwargs):
        called.append(args[0])
        return {"products": []}

    monkeypatch.setattr(live.chat_agent, "_dispatch_tool", fake_dispatch)
    fake = talk([{"serverContent": {"inputTranscription": {"text": "our usual Friday order plus some milk"}}},
                 {"toolCall": {"functionCalls": [{"id": "c1", "name": "search_products",
                                                  "args": {"query": "milk"}}]}},
                 {"serverContent": {"outputTranscription": {"text": "Please use the standing order."}}},
                 {"serverContent": {"turnComplete": True}}])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert ws.receive_json() == {"type": "ready"}
        until(ws, "turn_complete")
        ws.send_json({"type": "stop"})
    response = next(m["toolResponse"] for m in fake.sent if "toolResponse" in m)["functionResponses"][0]
    assert called == []
    assert response["response"]["result"] == {
        "stop_tools": True,
        "say": "I can use your usual Friday order, but I need the amount of milk to add.",
        "question": "How much milk should I add?",
    }


def test_live_waits_for_transcription_when_tool_call_arrives_first(talk, monkeypatch):
    called = []

    async def fake_dispatch(*args, **_kwargs):
        called.append(args[0])
        return {"products": []}

    monkeypatch.setattr(live.chat_agent, "_dispatch_tool", fake_dispatch)
    fake = talk([{"toolCall": {"functionCalls": [{"id": "c1", "name": "search_products",
                                                  "args": {"query": "butter"}}]}},
                 {"serverContent": {"inputTranscription": {"text": "I need 25 kilos of butter"}}},
                 {"serverContent": {"outputTranscription": {"text": "Please use the order request."}}},
                 {"serverContent": {"turnComplete": True}}])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert ws.receive_json() == {"type": "ready"}
        until(ws, "turn_complete")
        ws.send_json({"type": "stop"})
    response = next(m["toolResponse"] for m in fake.sent if "toolResponse" in m)["functionResponses"][0]
    assert called == [] and "propose_order" in response["response"]["result"]["error"]


def test_interview_mode_records_answers_and_sends_an_unstored_preview(talk, monkeypatch):
    captured = {}

    async def fake_from_about(about):
        captured["about"] = about
        return {"business_type": "bistro"}, []

    monkeypatch.setattr(live.profile, "from_about", fake_from_about)
    monkeypatch.setattr(live.profile, "save_onboarding", lambda *_args: pytest.fail("voice must not save"))
    fake = talk([
        {"toolCall": {"functionCalls": [{"id": "a1", "name": "record_answer",
                                            "args": {"topic": "kitchen", "text": "A 40-seat bistro."}}]}},
        {"toolCall": {"functionCalls": [{"id": "a2", "name": "finish_interview", "args": {}}]}},
        {"serverContent": {"outputTranscription": {"text": "Here's what I'll remember. Check it on screen and confirm."}}},
        {"serverContent": {"turnComplete": True}},
    ])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef", "mode": "interview"})
        assert ws.receive_json() == {"type": "ready"}
        seen = until(ws, "turn_complete")
        ws.send_json({"type": "stop"})

    preview = next(m["preview"] for m in seen if m["type"] == "interview_preview")
    assert preview["stored"] is False and preview["proposed"][0]["id"] == "business_type"
    assert "A 40-seat bistro." in captured["about"] and len(captured["about"]) <= 6000
    responses = [m["toolResponse"]["functionResponses"][0]
                 for m in fake.sent if "toolResponse" in m]
    assert responses[0]["response"]["result"] == {"recorded": True}
    assert responses[1]["response"]["result"]["say"] == "Here's what I'll remember. Check it on screen and confirm."
    setup = fake.sent[0]["setup"]
    names = [f["name"] for group in setup["tools"] for f in group["functionDeclarations"]]
    assert names == ["record_answer", "finish_interview"]
    assert "one question at a time" in setup["systemInstruction"]["parts"][0]["text"]


def test_transcripts_accumulate_raw_text_and_send_cumulative_turns(talk):
    fake = talk([
        {"serverContent": {"inputTranscription": {"text": "I said <no"}}},
        {"serverContent": {"inputTranscription": {"text": " speech>"}}},
        {"serverContent": {"turnComplete": True}},
        {"serverContent": {"inputTranscription": {"text": "<no speech>"}}},
        {"serverContent": {"turnComplete": True}},
        {"serverContent": {"inputTranscription": {"text": "yes"}}},
        {"serverContent": {"inputTranscription": {"text": " yes"}}},
        {"serverContent": {"turnComplete": True}},
    ])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert ws.receive_json() == {"type": "ready"}
        first = until(ws, "turn_complete")
        second = until(ws, "turn_complete")
        third = [m for m in until(ws, "turn_complete") if m["type"] == "transcript" and m["role"] == "user"]
        ws.send_json({"type": "stop"})

    user = [m for m in first if m["type"] == "transcript" and m["role"] == "user"]
    assert [m["text"] for m in user if not m["final"]] == ["I said", "I said"]
    assert [m["text"] for m in user if m["final"]] == ["I said"]
    assert {m["turn_id"] for m in user} == {1} and all(m["cumulative"] for m in user)
    assert not [m for m in second if m["type"] == "transcript"]
    assert [m["text"] for m in third if not m["final"]] == ["yes", "yes yes"]
    assert [m["text"] for m in third if m["final"]] == ["yes yes"]
    assert {m["turn_id"] for m in third} == {3} and all(m["cumulative"] for m in third)
    assert all("<" not in m["text"] and "{" not in m["text"] for m in user + third)


def test_current_order_tool_call_returns_the_snapshot(talk, monkeypatch):
    snapshot = {"orders": [{"requested_date": "2026-11-16", "status": "confirmed",
                            "lines": [{"name": "Milk", "amount": 10, "unit": "L"}],
                            "total_cents": 3120}], "total_cents": 3120}
    async def fake_dispatch(*_args, **_kwargs):
        return snapshot
    monkeypatch.setattr(live.chat_agent, "_dispatch_tool", fake_dispatch)
    fake = talk([{"toolCall": {"functionCalls": [{"id": "current", "name": "current_order", "args": {}}]}},
                 {"serverContent": {"outputTranscription": {"text": "The current order is ready."}}},
                 {"serverContent": {"turnComplete": True}}])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert ws.receive_json() == {"type": "ready"}
        until(ws, "turn_complete")
        ws.send_json({"type": "stop"})
    response = next(m["toolResponse"] for m in fake.sent if "toolResponse" in m)["functionResponses"][0]
    assert response["response"]["result"] == snapshot


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
                 {"serverContent": {"outputTranscription": {"text": "I could not run that tool."}}},
                 {"serverContent": {"turnComplete": True}}])
    with c.websocket_connect("/api/live") as ws:
        ws.send_json({"type": "auth", "agent_key": "agent-chef"})
        assert ws.receive_json() == {"type": "ready"}
        seen = until(ws, "turn_complete")
        ws.send_json({"type": "stop"})
    assert "result" not in [m["type"] for m in seen]
    resp = next(m["toolResponse"] for m in fake.sent if "toolResponse" in m)["functionResponses"][0]
    assert "Too many requests" in resp["response"]["result"]["error"]


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


def test_short_spoken_answers_are_kept_and_noise_is_dropped():
    from app import live
    for kept in ("No", "Ei", "Ok", "10", "5", "I need 5 kg of butter"):
        assert live._usable_transcript(kept), kept
    for dropped in ("", "  ", "...", "?", "m"):
        assert not live._usable_transcript(dropped), dropped
