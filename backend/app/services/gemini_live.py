"""One live call: browser audio <-> this backend <-> Gemini Live API.

    Browser mic (16 kHz PCM) --WS /ws/call--> LiveCall.send_audio() --> Gemini
    Browser speaker <--WS-- LiveCall._on_audio() <-- Gemini (24 kHz PCM)
    Gemini tool_call --> LiveCall._handle_tool() --> services/tools.py --> FunctionResponse

The backend holds the API key, runs every tool call itself and keeps all the
timings on one clock (time.perf_counter()).

Gemini docs used here (all on ai.google.dev):
- Connect / send / receive:  /gemini-api/docs/live-guide
- Async tools, scheduling:   /gemini-api/docs/live-tools
- Resumption, GoAway, context window compression: /gemini-api/docs/live-session
- Extended thinking (thinking_level, interaction_status): /gemini-api/docs/models/gemini-3.8-live-extended-thinking

Notes on the SDK (google-genai):
- session.receive() stops after each complete turn, so we call it in a loop.
- When the connection closes, receive() raises an APIError: we reconnect with
  the latest session resumption handle. Answers live in SQLite, so nothing
  saved is lost even if the session itself cannot be resumed.
"""

import asyncio
import json
import time

from fastapi import WebSocket
from google import genai
from google.genai import types
from loguru import logger

from app.config import GEMINI_API_KEY, INPUT_MIME_TYPE, INPUT_SAMPLE_RATE, MODEL_INFO, OUTPUT_SAMPLE_RATE
from app.db import SessionLocal
from app.models import Call, ToolCall, TurnMetric, utcnow
from app.services import prompt
from app.services.audio import VOICE_RMS_THRESHOLD, PhoneLine, rms
from app.services.events import bus
from app.services.scheduling import choose_scheduling, effective_behavior
from app.services.tool_schema import gemini_tools
from app.services.tools import _answers, form_state, log_tool_call, next_question, run_tool

MAX_RECONNECT_ATTEMPTS = 5
BROWSER_GRACE_S = 30  # keep the call alive this long if the browser's WebSocket drops
STATUS_TICK_S = 0.2

_SENSITIVITY = {
    "start": {"high": types.StartSensitivity.START_SENSITIVITY_HIGH, "low": types.StartSensitivity.START_SENSITIVITY_LOW},
    "end": {"high": types.EndSensitivity.END_SENSITIVITY_HIGH, "low": types.EndSensitivity.END_SENSITIVITY_LOW},
}


def build_live_config(settings: dict, form: dict, resume_handle: str | None) -> types.LiveConnectConfig:
    """The session setup sent to Gemini when connecting.

    Args:
        settings: Call settings (model, voice, language, VAD, tool options).
        form: The form definition (fields go into the system instruction and tool enums).
        resume_handle: Latest session resumption handle, or None for a new session.
    """
    model = MODEL_INFO[settings["model"]]
    vad = types.AutomaticActivityDetection(
        disabled=False,
        start_of_speech_sensitivity=_SENSITIVITY["start"].get(settings["vad_start_sensitivity"]),
        end_of_speech_sensitivity=_SENSITIVITY["end"].get(settings["vad_end_sensitivity"]),
        prefix_padding_ms=settings["vad_prefix_padding_ms"],
        silence_duration_ms=settings["vad_silence_ms"],
    )
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=prompt.build_system_prompt(form, settings["language"]),
        tools=gemini_tools([f["id"] for f in form["fields"]], effective_behavior(settings)),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=settings["voice"]))
        ),
        # Text of both sides, for the transcript column.
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(automatic_activity_detection=vad),
        # The server sends new handles; we reconnect with the latest one after a drop.
        session_resumption=types.SessionResumptionConfig(handle=resume_handle),
        # Without compression, audio sessions end after ~15 minutes.
        context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
    )
    # gemini-3.8-live rejects thinking_level, so it is only sent to extended-thinking.
    if model["supports_thinking_level"]:
        config.thinking_config = types.ThinkingConfig(thinking_level=types.ThinkingLevel(settings["thinking_level"].upper()))
    return config


class AgentTurn:
    """One agent reply, from its first audio chunk to turn_complete / interrupted."""

    def __init__(self, index: int, caller_spoke: bool, user_text: str):
        self.index = index
        self.caller_spoke = caller_spoke  # False for the greeting and for replies to a tool result
        self.first_audio_t: float | None = None
        self.response_ms: float | None = None
        self.stop_source: str | None = None
        self.user_text = user_text or None
        self.user_language: str | None = None
        self.agent_text: list[str] = []
        self.tool_ms = 0.0
        self.interrupted = False

    def metrics(self) -> dict:
        return {
            "turn_index": self.index,
            "total_ms": self.response_ms,
            "tool_ms": round(self.tool_ms, 1) if self.tool_ms else None,
            "stop_source": self.stop_source,
            "interrupted": self.interrupted,
            "user_text": self.user_text,
            "user_language": self.user_language,
            "agent_text": "".join(self.agent_text).strip() or None,
        }


class LiveCall:
    def __init__(self, call_id: str, settings: dict, form: dict):
        self.call_id = call_id
        self.settings = settings
        self.form = form
        self.model_info = MODEL_INFO[settings["model"]]
        self.client = None  # created on first connect (tests put a fake client here)

        self.browser: WebSocket | None = None
        self.session = None  # the current Gemini AsyncSession
        self.session_gen = 0  # +1 per connection; tool responses go only to the session that asked
        self.resume_handle: str | None = None
        self.needs_resume_context = False
        self.closed = False
        self.muted = False
        self.drop_requested = False
        self._tasks: set[asyncio.Task] = set()
        self._main_task: asyncio.Task | None = None
        self._grace_task: asyncio.Task | None = None

        phone = settings["audio_quality"] == "phone"
        self.phone_in = PhoneLine(INPUT_SAMPLE_RATE) if phone else None
        self.phone_out = PhoneLine(OUTPUT_SAMPLE_RATE) if phone else None

        # --- timing state (all time.perf_counter() seconds) ---
        self.last_voice_t: float | None = None  # last mic chunk loud enough to be speech
        self.server_eos_t: float | None = None  # Gemini's end-of-speech signal, if it sends one
        self.playback_end_t = 0.0  # when the browser will finish playing the audio sent so far
        self.prev_turn_end_t = 0.0
        self.turn: AgentTurn | None = None
        self.turn_count = 0  # turn 0 = greeting
        self.caller_text: list[str] = []  # caller transcription since the last agent turn started
        self.caller_language: str | None = None
        self.after_interruption = False  # drop late agent transcript pieces of an interrupted reply
        self.greeted = False
        self.audio_chunks = 0
        self.pending_tool_ms = 0.0  # tool time before the next agent turn starts
        self.tools_running = 0
        self.thinking = False  # extended-thinking: interaction_status IN_PROGRESS
        self.status = None
        self.cancelled_ids: set[str] = set()
        self.usage_conn = {"audio_in": 0, "text_in": 0, "audio_out": 0, "text_out": 0}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self._main_task = asyncio.create_task(self._run())
        self._spawn(self._status_ticker())

    def _spawn(self, coro):
        task = asyncio.create_task(coro)
        self._tasks.add(task)  # keep a reference so the task isn't garbage-collected
        task.add_done_callback(self._tasks.discard)
        return task

    async def attach(self, ws: WebSocket):
        """A browser WebSocket connected (first time, or again after a drop)."""
        if self._grace_task:
            self._grace_task.cancel()
            self._grace_task = None
        self.browser = ws

    def detach(self, ws: WebSocket):
        """The browser WebSocket closed. End the call unless it comes back soon."""
        if self.browser is ws:
            self.browser = None
        if not self.closed:
            self._grace_task = self._spawn(self._end_after_grace())

    async def _end_after_grace(self):
        await asyncio.sleep(BROWSER_GRACE_S)
        if self.browser is None and not self.closed:
            self._error("Browser disconnected and did not come back. Call ended.")
            await self.end()

    async def end(self):
        """Stop the call: close Gemini, save the last turn, mark the call ended."""
        if self.closed:
            return
        self.closed = True
        self._finish_turn()
        if self.session is not None:
            try:
                await self.session.close()
            except Exception:
                pass
        current = asyncio.current_task()
        for task in [self._main_task, *self._tasks]:
            if task is not None and task is not current:
                task.cancel()
        self._update_call(lambda c: (setattr(c, "status", "ended"), setattr(c, "ended_at", utcnow())))
        self._set_status("ended")
        bus.publish(self.call_id, "call_ended", {})
        await self._send_browser({"type": "ended"})
        _calls.pop(self.call_id, None)

    async def _run(self):
        """Connect, and reconnect after drops, until the call ends."""
        failures = 0
        while not self.closed:
            self._set_status("reconnecting" if self.greeted else "connecting")
            try:
                await self._connect_once()
                failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as e:
                failures += 1
                if self.closed:
                    break
                message = _safe_error(e)
                logger.warning(f"[{self.call_id}] Gemini connection error: {message}")
                self._error(f"Gemini connection error: {message}")
                if self.resume_handle and failures >= 2:
                    # The handle may have expired: start a fresh session and replay the saved answers.
                    self.resume_handle = None
                    self.needs_resume_context = True
                if failures >= MAX_RECONNECT_ATTEMPTS:
                    self._error("Could not connect to Gemini. Call ended.", fatal=True)
                    await self.end()
                    break
                await asyncio.sleep(min(2 ** failures * 0.25, 4))
            if self.closed:
                break
            self._on_disconnected()
            if self.greeted:
                n = self._update_call(lambda c: setattr(c, "reconnects", c.reconnects + 1)).reconnects
                bus.publish(self.call_id, "counters", {"reconnects": n})

    async def _connect_once(self):
        if self.client is None:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
        config = build_live_config(self.settings, self.form, self.resume_handle)
        resumed = self.resume_handle is not None
        self._log("connecting", model=self.settings["model"], resume=resumed)
        async with self.client.aio.live.connect(model=self.settings["model"], config=config) as session:
            try:
                self.session = session
                self.session_gen += 1
                self.usage_conn = {k: 0 for k in self.usage_conn}
                self._log("connected", resumed=resumed)
                self._set_status("listening")
                if not self.greeted:
                    await session.send_client_content(
                        turns=types.Content(role="user", parts=[types.Part(text=prompt.GREETING_TRIGGER)]),
                        turn_complete=True,
                    )
                    self.greeted = True
                elif not resumed or self.needs_resume_context:
                    # A brand-new session knows nothing about the call: tell it what is already saved.
                    with SessionLocal() as db:
                        text = prompt.resume_message(
                            form_state(db, self.call_id), next_question(self.form, _answers(db, self.call_id))
                        )
                    await session.send_client_content(
                        turns=types.Content(role="user", parts=[types.Part(text=text)]), turn_complete=True
                    )
                    self.needs_resume_context = False
                await self._receive_loop(session)
            finally:
                self.session = None

    async def _receive_loop(self, session):
        try:
            while not self.closed:
                async for msg in session.receive():
                    await self._on_message(msg)
                    if self.drop_requested:
                        break
                if self.drop_requested:
                    break
        except Exception:
            # Closing the connection ourselves (test drop / GoAway) also lands here; that is not an error.
            if not (self.drop_requested or self.closed):
                raise
        if self.drop_requested:
            self.drop_requested = False
            self._log("reconnecting_now")  # leaving `async with` closes the connection

    def _on_disconnected(self):
        """The Gemini connection is gone: any audio still being generated is lost."""
        if self.turn:
            self.turn.interrupted = True
            self._finish_turn()
        self.playback_end_t = time.perf_counter()
        self.thinking = False

    # ------------------------------------------------------------------
    # Browser -> Gemini
    # ------------------------------------------------------------------

    async def send_audio(self, pcm: bytes):
        """One mic chunk from the browser (16 kHz, 16-bit PCM)."""
        if self.closed or self.muted:
            return
        now = time.perf_counter()
        if rms(pcm) >= VOICE_RMS_THRESHOLD:
            self.last_voice_t = now
        if self.phone_in:
            pcm = self.phone_in.process(pcm)
        session = self.session
        if session is None:
            return  # reconnecting: this bit of audio is dropped
        try:
            await session.send_realtime_input(audio=types.Blob(data=pcm, mime_type=INPUT_MIME_TYPE))
        except Exception:
            pass  # the receive loop notices the closed connection and reconnects

    async def set_muted(self, muted: bool):
        self.muted = muted
        if muted and self.session is not None:
            # Tell Gemini the audio stream paused, so its VAD doesn't wait for more.
            try:
                await self.session.send_realtime_input(audio_stream_end=True)
            except Exception:
                pass
        bus.publish(self.call_id, "gemini", {"event": "muted" if muted else "unmuted"})

    async def request_drop(self):
        """Test button: close the Gemini connection to check that resumption works."""
        self.drop_requested = True
        bus.publish(self.call_id, "gemini", {"event": "test_drop", "handle_available": self.resume_handle is not None})
        if self.session is not None:
            try:
                await self.session.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Gemini -> us
    # ------------------------------------------------------------------

    async def _on_message(self, msg: types.LiveServerMessage):
        sc = msg.server_content
        if sc is not None:
            if sc.model_turn and sc.model_turn.parts:
                for part in sc.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        await self._on_audio(part.inline_data.data)
            if sc.input_transcription and sc.input_transcription.text:
                self._on_caller_text(sc.input_transcription)
            if sc.output_transcription and sc.output_transcription.text:
                self._on_agent_text(sc.output_transcription.text)
            if sc.interrupted:
                await self._on_interrupted()
            if sc.interaction_status is not None:
                # Extended thinking: turn_complete no longer means "idle"; IN_PROGRESS = still working.
                self.thinking = sc.interaction_status == types.InteractionStatus.IN_PROGRESS
            if sc.turn_complete:
                self._log("turn_complete", reason=str(sc.turn_complete_reason) if sc.turn_complete_reason else None)
                self._finish_turn()
            elif sc.generation_complete:
                self._log("generation_complete")

        if msg.tool_call and msg.tool_call.function_calls:
            for fc in msg.tool_call.function_calls:
                # Run each tool in its own task, so audio keeps flowing while it runs.
                self._spawn(self._handle_tool(fc, self.session_gen))

        if msg.tool_call_cancellation and msg.tool_call_cancellation.ids:
            self._on_tool_cancellation(list(msg.tool_call_cancellation.ids))

        if msg.session_resumption_update:
            update = msg.session_resumption_update
            if update.resumable and update.new_handle:
                self.resume_handle = update.new_handle
            self._log("session_resumption_update", resumable=update.resumable)  # the handle itself is not logged

        if msg.go_away:
            self._log("go_away", time_left=str(msg.go_away.time_left))
            # The server will close this connection soon: reconnect now with the latest handle.
            self.drop_requested = True

        if msg.voice_activity and msg.voice_activity.voice_activity_type == types.VoiceActivityType.ACTIVITY_END:
            self.server_eos_t = time.perf_counter()
        if msg.voice_activity_detection_signal and \
                msg.voice_activity_detection_signal.vad_signal_type == types.VadSignalType.VAD_SIGNAL_TYPE_EOS:
            self.server_eos_t = time.perf_counter()

        if msg.usage_metadata:
            self._on_usage(msg.usage_metadata)

    async def _on_audio(self, pcm: bytes):
        now = time.perf_counter()
        self.audio_chunks += 1
        if self.turn is None:
            self._start_turn()
        if self.turn.first_audio_t is None:
            self._measure_response(now)
        if self.phone_out:
            pcm = self.phone_out.process(pcm)
        # 2 bytes per sample at 24 kHz. The browser plays chunks back to back.
        self.playback_end_t = max(self.playback_end_t, now) + len(pcm) / 2 / OUTPUT_SAMPLE_RATE
        if self.browser is not None:
            try:
                await self.browser.send_bytes(pcm)
            except Exception:
                pass

    def _start_turn(self):
        """A new agent reply begins: close the caller's bubble and open a turn."""
        caller_spoke = self.turn_count > 0 and (
            bool(self.caller_text) or (self.last_voice_t is not None and self.last_voice_t > self.prev_turn_end_t)
        )
        user_text = "".join(self.caller_text).strip()
        if user_text:
            self._add_transcript({"role": "caller", "text": user_text, "language": self.caller_language})
        self.turn = AgentTurn(self.turn_count, caller_spoke, user_text)
        self.turn.user_language = self.caller_language
        self.turn.tool_ms = self.pending_tool_ms
        self.pending_tool_ms = 0.0
        self.turn_count += 1
        self.caller_text = []
        self.after_interruption = False

    def _measure_response(self, now: float):
        """First agent audio of the turn: response time = now - when the caller stopped speaking.

        "Stopped speaking" = the last mic chunk loud enough to be speech (our own
        check, so it includes Gemini's VAD silence window, like a real caller hears it).
        If the mic level never crossed the threshold, Gemini's end-of-speech signal is used.
        """
        t = self.turn
        t.first_audio_t = now
        if t.caller_spoke:
            if self.last_voice_t is not None and self.last_voice_t > self.prev_turn_end_t:
                t.response_ms, t.stop_source = round((now - self.last_voice_t) * 1000, 1), "energy"
            elif self.server_eos_t is not None:
                t.response_ms, t.stop_source = round((now - self.server_eos_t) * 1000, 1), "server_vad"
        self.server_eos_t = None
        bus.publish(self.call_id, "turn_metrics", t.metrics())  # provisional, so the bar shows at once

    def _finish_turn(self):
        """turn_complete / interrupted / call end: save the turn and the agent's bubble."""
        t = self.turn
        if t is None:
            return
        self.turn = None
        self.prev_turn_end_t = max(time.perf_counter(), self.playback_end_t)
        data = t.metrics()
        if data["agent_text"]:
            self._add_transcript({"role": "agent", "text": data["agent_text"], "interrupted": t.interrupted})
        with SessionLocal() as db:
            db.add(TurnMetric(call_id=self.call_id, **data))
            db.commit()
        bus.publish(self.call_id, "turn_metrics", data)

    def _on_caller_text(self, tr: types.Transcription):
        self.caller_text.append(tr.text)
        if tr.language_code:
            self.caller_language = tr.language_code
        bus.publish(self.call_id, "transcript_partial", {"role": "caller", "text": "".join(self.caller_text)})

    def _on_agent_text(self, text: str):
        if self.turn is None:
            if self.after_interruption:
                self._log("late_agent_text_dropped", text=text)  # belongs to the reply that was cut off
                return
            self._start_turn()  # text can arrive just before the first audio
        self.turn.agent_text.append(text)
        bus.publish(self.call_id, "transcript_partial", {"role": "agent", "text": "".join(self.turn.agent_text)})

    async def _on_interrupted(self):
        """The caller spoke over the agent (barge-in): Gemini stopped generating."""
        self.playback_end_t = time.perf_counter()
        await self._send_browser({"type": "clear_audio"})  # stop playing what is already buffered
        if self.turn is not None and not self.turn.interrupted:
            self.turn.interrupted = True
            n = self._update_call(lambda c: setattr(c, "interruptions", c.interruptions + 1)).interruptions
            bus.publish(self.call_id, "counters", {"interruptions": n})
            self._finish_turn()
            self.after_interruption = True

    def _on_usage(self, usage: types.UsageMetadata):
        """Add token counts per modality (audio vs text) for the cost estimate."""
        counts = {"audio_in": 0, "text_in": 0, "audio_out": 0, "text_out": 0}
        for detail in usage.prompt_tokens_details or []:
            key = "audio_in" if detail.modality == types.MediaModality.AUDIO else "text_in"
            counts[key] += detail.token_count or 0
        for detail in usage.response_tokens_details or []:
            key = "audio_out" if detail.modality == types.MediaModality.AUDIO else "text_out"
            counts[key] += detail.token_count or 0
        counts["text_out"] += usage.thoughts_token_count or 0  # thinking is billed as output text

        if self.settings["usage_counting"] == "last":
            # Usage is a running total for this connection: add only what is new.
            delta = {k: max(0, counts[k] - self.usage_conn[k]) for k in counts}
            self.usage_conn = {k: max(counts[k], self.usage_conn[k]) for k in counts}
        else:
            delta = counts

        def add(c: Call):
            c.audio_input_tokens += delta["audio_in"]
            c.text_input_tokens += delta["text_in"]
            c.audio_output_tokens += delta["audio_out"]
            c.text_output_tokens += delta["text_out"]

        call = self._update_call(add)
        bus.publish(self.call_id, "usage", {
            "audio_input_tokens": call.audio_input_tokens, "text_input_tokens": call.text_input_tokens,
            "audio_output_tokens": call.audio_output_tokens, "text_output_tokens": call.text_output_tokens,
            "raw": usage.model_dump(exclude_none=True, mode="json"),
        })

    # ------------------------------------------------------------------
    # Tool calls
    # ------------------------------------------------------------------

    async def _handle_tool(self, fc: types.FunctionCall, gen: int):
        """Run one tool call and send the FunctionResponse with the same id."""
        t0 = time.perf_counter()
        speaking_at_call = t0 < self.playback_end_t
        chunks_at_call = self.audio_chunks
        self.tools_running += 1
        self._refresh_status()
        self._log("tool_call_received", id=fc.id, name=fc.name)
        try:
            result, arguments, parse_error, timed_out, retries = await self._execute(fc.name, fc.args)
            # Decide now, when the result is ready: is the agent still talking, or waiting for us?
            agent_busy = self.turn is not None or time.perf_counter() < self.playback_end_t
            scheduling = choose_scheduling(self.settings, fc.name, result, agent_busy)
            cancelled = fc.id in self.cancelled_ids
            sent = False
            if cancelled:
                self._log("tool_response_skipped", id=fc.id, reason="cancelled by Gemini")
            elif gen != self.session_gen or self.session is None:
                # The connection that asked is gone; a resumed session does not expect this id.
                self._log("tool_response_skipped", id=fc.id, reason="connection changed")
            else:
                response = types.FunctionResponse(
                    id=fc.id, name=fc.name, response=result,
                    scheduling=types.FunctionResponseScheduling(scheduling) if scheduling else None,
                )
                try:
                    await self.session.send_tool_response(function_responses=[response])
                    sent = True
                except Exception as e:
                    self._error(f"Could not send tool response for {fc.name}: {_safe_error(e)}")
            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            with SessionLocal() as db:
                log_tool_call(
                    db, self.call_id, fc.name, arguments, result, duration_ms,
                    gemini_call_id=fc.id, scheduling=scheduling if sent else None, timed_out=timed_out,
                    retries=retries, cancelled=cancelled, agent_speaking_at_call=speaking_at_call,
                    audio_chunks_during_tool=self.audio_chunks - chunks_at_call, parse_error=parse_error,
                )
            if self.turn is not None:
                self.turn.tool_ms += duration_ms
            else:
                self.pending_tool_ms += duration_ms
        finally:
            self.tools_running -= 1
            self._refresh_status()

    async def _execute(self, name: str, args) -> tuple[dict, object, str | None, bool, int]:
        """Run the tool with a timeout and retries.

        Returns:
            (result, arguments, parse_error, timed_out, retries)
        """
        timeout = self.settings["tool_timeout_ms"] / 1000
        delay = self.settings["tool_delay_ms"] / 1000
        max_retries = self.settings["tool_max_retries"]
        args = dict(args) if args is not None else {}

        async def attempt():
            if delay:
                await asyncio.sleep(delay)  # test setting: pretend the backend is slow
            return await asyncio.to_thread(self._run_tool_sync, name, args)

        retries, timed_out, last_error = 0, False, ""
        while True:
            try:
                result, arguments, parse_error = await asyncio.wait_for(attempt(), timeout)
                return result, arguments, parse_error, timed_out, retries
            except asyncio.TimeoutError:
                timed_out, last_error = True, f"timed out after {self.settings['tool_timeout_ms']} ms"
            except Exception as e:
                last_error = _safe_error(e)
                logger.exception(f"[{self.call_id}] tool {name} failed")
            self._log("tool_attempt_failed", name=name, error=last_error, retry=retries < max_retries)
            if retries >= max_retries:
                break
            retries += 1
        result = {"ok": False, "error": f"The answer could not be saved ({last_error}). Ask the question again."}
        return result, args, None, timed_out, retries

    def _run_tool_sync(self, name: str, args: dict):
        with SessionLocal() as db:
            return run_tool(db, self.call_id, name, args)

    def _on_tool_cancellation(self, ids: list[str]):
        """Gemini cancelled tool calls (usually a barge-in). Saved answers stay saved."""
        self.cancelled_ids.update(ids)
        with SessionLocal() as db:
            for row in db.query(ToolCall).filter(ToolCall.call_id == self.call_id, ToolCall.gemini_call_id.in_(ids)):
                row.cancelled = True
            db.commit()
        bus.publish(self.call_id, "tool_cancelled", {"ids": ids})

    # ------------------------------------------------------------------
    # Status and helpers
    # ------------------------------------------------------------------

    def _refresh_status(self):
        if self.closed or (self.status in ("connecting", "reconnecting") and self.session is None):
            return
        if self.tools_running:
            status = "tool_running"
        elif time.perf_counter() < self.playback_end_t:
            status = "speaking"
        elif self.thinking:
            status = "thinking"
        else:
            status = "listening"
        self._set_status(status)

    async def _status_ticker(self):
        """'Agent speaking' ends when the browser finishes playing, not when Gemini stops sending."""
        while not self.closed:
            await asyncio.sleep(STATUS_TICK_S)
            if self.session is not None:
                self._refresh_status()

    def _set_status(self, status: str):
        if status == self.status:
            return
        self.status = status
        self._update_call(lambda c: setattr(c, "status", status))
        bus.publish(self.call_id, "status", {"status": status})

    def _update_call(self, fn) -> Call:
        with SessionLocal() as db:
            call = db.get(Call, self.call_id)
            fn(call)
            db.commit()
            return call

    def _add_transcript(self, entry: dict):
        event = bus.publish(self.call_id, "transcript", entry)
        entry = {**entry, "ts": event["ts"]}
        self._update_call(lambda c: setattr(c, "transcript", [*(c.transcript or []), entry]))

    def _log(self, event: str, **data):
        """Raw event log entry (shown in the collapsible log in Column 3)."""
        bus.publish(self.call_id, "gemini", {"event": event, **data})

    def _error(self, message: str, fatal: bool = False):
        bus.publish(self.call_id, "error", {"message": message, "fatal": fatal})
        self._update_call(lambda c: setattr(c, "errors", [*(c.errors or []), message]))

    async def _send_browser(self, message: dict):
        if self.browser is not None:
            try:
                await self.browser.send_text(json.dumps(message))
            except Exception:
                pass


def _safe_error(e: Exception) -> str:
    """Error text without anything that looks like the API key."""
    text = f"{type(e).__name__}: {e}"
    if GEMINI_API_KEY:
        text = text.replace(GEMINI_API_KEY, "***")
    return text[:500]


# call_id -> running LiveCall
_calls: dict[str, LiveCall] = {}


def get_live_call(call_id: str) -> LiveCall | None:
    return _calls.get(call_id)


def start_live_call(call_id: str, settings: dict, form: dict) -> LiveCall:
    live = LiveCall(call_id, settings, form)
    _calls[call_id] = live
    live.start()
    return live


async def end_live_call(call_id: str) -> bool:
    live = _calls.get(call_id)
    if live is None:
        return False
    await live.end()
    return True


async def end_all():
    for live in list(_calls.values()):
        await live.end()
