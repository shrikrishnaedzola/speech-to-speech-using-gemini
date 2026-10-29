"""The live Gemini session logic, with a fake Gemini connection (no network, no key).

Checks the things that are hard to see by hand: the tool response goes back with
the same id and the right scheduling, timeouts and retries are logged, response
time is measured, and a dropped connection resumes with the latest handle.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace

from google.genai import types

from app.config import DEFAULT_CALL_SETTINGS
from app.db import SessionLocal
from app.models import Answer, Call, ToolCall, TurnMetric
from app.services.gemini_live import LiveCall

LOUD = (b"\x00\x40" * 640)  # 640 samples at about half volume
AUDIO_OUT = b"\x00\x00" * 2400  # 0.1 s of agent audio at 24 kHz


class FakeSession:
    """Stands in for google.genai's AsyncSession."""

    def __init__(self):
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.tool_responses: list[types.FunctionResponse] = []
        self.client_content: list = []
        self.audio_in = 0

    async def send_client_content(self, turns=None, turn_complete=True):
        self.client_content.append(turns)

    async def send_realtime_input(self, audio=None, audio_stream_end=None):
        self.audio_in += 1

    async def send_tool_response(self, function_responses):
        self.tool_responses.extend(function_responses)

    async def receive(self):
        while True:
            msg = await self.inbox.get()
            if msg is None:
                raise ConnectionError("connection closed")  # what a dropped socket looks like
            yield msg
            if msg.server_content and msg.server_content.turn_complete:
                return

    async def close(self):
        self.inbox.put_nowait(None)

    def push(self, **kwargs):
        self.inbox.put_nowait(types.LiveServerMessage(**kwargs))


class FakeLive:
    def __init__(self, sessions):
        self.sessions = sessions
        self.configs: list[types.LiveConnectConfig] = []

    @asynccontextmanager
    async def connect(self, model, config):
        self.configs.append(config)
        yield self.sessions.pop(0)


def make_call(call_id, form, sessions, **overrides):
    settings = {**DEFAULT_CALL_SETTINGS, **overrides}
    with SessionLocal() as db:
        db.get(Call, call_id).settings = settings
        db.commit()
    live = LiveCall(call_id, settings, form)
    fake = FakeLive(sessions)
    live.client = SimpleNamespace(aio=SimpleNamespace(live=fake))
    return live, fake


async def wait_until(check, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not met in time")


def tool_call(fc_id, name, args):
    return types.LiveServerToolCall(function_calls=[types.FunctionCall(id=fc_id, name=name, args=args)])


def audio_msg(data=AUDIO_OUT):
    return types.LiveServerContent(model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(data=data, mime_type="audio/pcm"))]))


def tool_rows(call_id):
    with SessionLocal() as db:
        return db.query(ToolCall).filter_by(call_id=call_id).order_by(ToolCall.id).all()


def test_invalid_answer_gets_interrupt_with_same_id(call_id, form):
    async def run():
        session = FakeSession()
        live, fake = make_call(call_id, form, [session])
        live.start()
        await wait_until(lambda: session.client_content)  # greeting trigger sent
        session.push(server_content=audio_msg())  # agent is talking...
        session.push(tool_call=tool_call("fc-1", "save_answer", {"field_id": "age", "value": "150", "confidence": "high"}))
        session.push(tool_call=tool_call("fc-2", "save_answer", {"field_id": "age", "value": "35", "confidence": "high"}))
        await wait_until(lambda: len(session.tool_responses) == 2)
        await live.end()
        return session, fake

    session, fake = asyncio.run(run())
    by_id = {r.id: r for r in session.tool_responses}
    assert by_id["fc-1"].response["ok"] is False and by_id["fc-1"].scheduling == types.FunctionResponseScheduling.INTERRUPT
    # Agent audio is still coming (no turn_complete yet), so AUTO picks SILENT.
    assert by_id["fc-2"].response["ok"] is True and by_id["fc-2"].scheduling == types.FunctionResponseScheduling.SILENT
    rows = {r.gemini_call_id: r for r in tool_rows(call_id)}
    assert rows["fc-1"].scheduling == "INTERRUPT" and rows["fc-2"].scheduling == "SILENT"
    assert rows["fc-1"].agent_speaking_at_call is True  # it arrived while agent audio was playing
    # The setup sent to Gemini: async tools, both transcriptions, resumption, no thinking_level.
    config = fake.configs[0]
    assert config.tools[0].function_declarations[0].behavior == types.Behavior.NON_BLOCKING
    assert config.input_audio_transcription is not None and config.output_audio_transcription is not None
    assert config.session_resumption is not None and config.thinking_config is None


def test_silent_agent_gets_when_idle_after_save(call_id, form):
    """Live bug: the agent called save_answer, went quiet, and SILENT left dead air."""
    async def run():
        session = FakeSession()
        live, _ = make_call(call_id, form, [session])
        live.start()
        await wait_until(lambda: session.client_content)
        session.push(tool_call=tool_call("fc-q", "save_answer", {"field_id": "age", "value": "35", "confidence": "high"}))
        await wait_until(lambda: session.tool_responses)
        await live.end()
        return session

    session = asyncio.run(run())
    assert session.tool_responses[0].scheduling == types.FunctionResponseScheduling.WHEN_IDLE


def test_extended_thinking_sends_no_scheduling(call_id, form):
    async def run():
        session = FakeSession()
        live, fake = make_call(call_id, form, [session], model="gemini-3.8-live-extended-thinking", thinking_level="medium")
        live.start()
        session.push(tool_call=tool_call("fc-x", "save_answer", {"field_id": "age", "value": "150", "confidence": "high"}))
        await wait_until(lambda: session.tool_responses)
        await live.end()
        return session, fake

    session, fake = asyncio.run(run())
    assert session.tool_responses[0].scheduling is None
    assert fake.configs[0].thinking_config.thinking_level == types.ThinkingLevel.MEDIUM


def test_tool_timeout_and_retry_are_logged(call_id, form):
    async def run():
        session = FakeSession()
        live, _ = make_call(call_id, form, [session], tool_delay_ms=500, tool_timeout_ms=100, tool_max_retries=1)
        live.start()
        session.push(tool_call=tool_call("fc-slow", "save_answer", {"field_id": "district", "value": "Sample", "confidence": "high"}))
        await wait_until(lambda: session.tool_responses)
        await live.end()
        return session

    session = asyncio.run(run())
    assert session.tool_responses[0].response["ok"] is False
    assert session.tool_responses[0].scheduling == types.FunctionResponseScheduling.INTERRUPT
    row = tool_rows(call_id)[0]
    assert row.timed_out is True and row.retries == 1
    with SessionLocal() as db:  # the slow attempt was cancelled before it could save
        assert db.query(Answer).filter_by(call_id=call_id, field_id="district").count() == 0


def test_response_time_from_caller_stop_to_first_audio(call_id, form):
    async def run():
        session = FakeSession()
        live, _ = make_call(call_id, form, [session])
        live.start()
        await wait_until(lambda: session.client_content)
        session.push(server_content=audio_msg())  # greeting
        session.push(server_content=types.LiveServerContent(turn_complete=True))
        await wait_until(lambda: live.turn_count == 1 and live.turn is None)
        live.playback_end_t = 0  # pretend the greeting finished playing
        live.prev_turn_end_t = time.perf_counter()
        await live.send_audio(LOUD)  # caller speaks...
        await asyncio.sleep(0.3)  # ...then is silent for 300 ms
        session.push(server_content=types.LiveServerContent(input_transcription=types.Transcription(text="Haan ji")))
        session.push(server_content=audio_msg())
        session.push(server_content=types.LiveServerContent(turn_complete=True))
        await wait_until(lambda: live.turn_count == 2 and live.turn is None)
        await live.end()

    asyncio.run(run())
    with SessionLocal() as db:
        turns = db.query(TurnMetric).filter_by(call_id=call_id).order_by(TurnMetric.turn_index).all()
    assert turns[0].total_ms is None  # greeting: nobody spoke before it
    assert turns[1].stop_source == "energy" and 250 <= turns[1].total_ms < 2000
    assert turns[1].user_text == "Haan ji"


def test_dropped_connection_resumes_with_latest_handle(call_id, form):
    async def run():
        first, second = FakeSession(), FakeSession()
        live, fake = make_call(call_id, form, [first, second])
        live.start()
        first.push(tool_call=tool_call("fc-a", "save_answer", {"field_id": "caller_name", "value": "Test User", "confidence": "high"}))
        await wait_until(lambda: first.tool_responses)
        first.push(session_resumption_update=types.LiveServerSessionResumptionUpdate(new_handle="handle-2", resumable=True))
        await asyncio.sleep(0.05)
        first.inbox.put_nowait(None)  # the connection drops
        await wait_until(lambda: len(fake.configs) == 2 and live.session is second)
        await live.end()
        return first, second, fake

    first, second, fake = asyncio.run(run())
    assert fake.configs[1].session_resumption.handle == "handle-2"
    assert len(first.client_content) == 1 and second.client_content == []  # greeted once, not again
    with SessionLocal() as db:
        call = db.get(Call, call_id)
        assert call.reconnects == 1
        saved = db.query(Answer).filter_by(call_id=call_id, field_id="caller_name").one()
        assert saved.value == "Test User"  # nothing lost
