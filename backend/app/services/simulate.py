"""Simulate mode: replay a saved dummy call without a microphone or Gemini.

Reads app/simulate/sample_call.json and plays it step by step:
- "agent"/"caller" steps become transcript bubbles,
- "tool" steps run the REAL tool code (validation, follow-ups, completion) and
  the real scheduling choice for the selected model,
- agent "response_ms" values become turn metrics (made-up numbers, for the UI only),
- "interruption" counts a barge-in, "reconnect" shows a dropped connection.
The UI receives exactly the same events as in a live call, at no cost.
"""

import asyncio
import json
import uuid

from loguru import logger

from app.config import SIMULATE_DIR
from app.db import SessionLocal
from app.models import Call, TurnMetric, utcnow
from app.services.events import bus
from app.services.tools import handle_tool_call

SCRIPT_PATH = SIMULATE_DIR / "sample_call.json"


def _update_call(call_id: str, fn):
    with SessionLocal() as db:
        call = db.get(Call, call_id)
        fn(call)
        db.commit()
        return call


def _add_transcript(call_id: str, entry: dict):
    event = bus.publish(call_id, "transcript", entry)
    _update_call(call_id, lambda c: setattr(c, "transcript", [*(c.transcript or []), {**entry, "ts": event["ts"]}]))


async def _run(call_id: str, speed: float):
    steps = json.loads(SCRIPT_PATH.read_text(encoding="utf-8"))["steps"]

    async def pause(ms: float):
        await asyncio.sleep(ms / 1000 / speed)

    def set_status(status: str):
        _update_call(call_id, lambda c: setattr(c, "status", status))
        bus.publish(call_id, "status", {"status": status})

    set_status("connecting")
    await pause(600)
    set_status("listening")
    turn_index, last_caller = 0, None

    for step in steps:
        kind = step["type"]
        if kind == "caller":
            await pause(900)
            last_caller = step
            set_status("listening")
            _add_transcript(call_id, {"role": "caller", "text": step["text"], "language": step.get("language")})
        elif kind == "tool":
            set_status("tool_running")
            await pause(150)
            with SessionLocal() as db:
                handle_tool_call(
                    db, call_id, step["name"], step.get("raw_args", step.get("args")),
                    gemini_call_id=f"sim-{uuid.uuid4().hex[:8]}",
                    agent_speaking_at_call=bool(step.get("agent_speaking")),
                    audio_chunks_during_tool=3 if step.get("agent_speaking") else 0,
                )
        elif kind == "interruption":
            call = _update_call(call_id, lambda c: setattr(c, "interruptions", c.interruptions + 1))
            bus.publish(call_id, "counters", {"interruptions": call.interruptions})
            set_status("listening")
        elif kind == "reconnect":
            set_status("reconnecting")
            bus.publish(call_id, "gemini", {"event": "simulated_drop"})
            await pause(step.get("ms", 900))
            call = _update_call(call_id, lambda c: setattr(c, "reconnects", c.reconnects + 1))
            bus.publish(call_id, "counters", {"reconnects": call.reconnects})
            bus.publish(call_id, "gemini", {"event": "connected", "resumed": True})
            set_status("listening")
        elif kind == "agent":
            response_ms = step.get("response_ms")
            await pause(response_ms or 400)
            caller_turn = response_ms is not None
            metrics = {
                "turn_index": turn_index,
                "total_ms": response_ms,
                "tool_ms": step.get("tool_ms"),
                "stop_source": "energy" if caller_turn else None,
                "interrupted": bool(step.get("interrupted")),
                "user_text": last_caller["text"] if last_caller and caller_turn else None,
                "user_language": last_caller.get("language") if last_caller and caller_turn else None,
                "agent_text": step["text"],
            }
            with SessionLocal() as db:
                db.add(TurnMetric(call_id=call_id, **metrics))
                db.commit()
            bus.publish(call_id, "turn_metrics", metrics)
            turn_index += 1
            set_status("speaking")
            _add_transcript(call_id, {"role": "agent", "text": step["text"], "interrupted": bool(step.get("interrupted"))})
            # Rough speaking time: ~60 ms per character.
            await pause(min(4000, 60 * len(step["text"])) if not step.get("interrupted") else 800)
            set_status("listening")

    # Dummy usage so the cost panel shows something (about 32 tokens per second of audio).
    def usage(c: Call):
        c.audio_input_tokens, c.text_input_tokens = 5_800, 1_400
        c.audio_output_tokens, c.text_output_tokens = 3_900, 600

    call = _update_call(call_id, usage)
    bus.publish(call_id, "usage", {"audio_input_tokens": call.audio_input_tokens,
                                   "text_input_tokens": call.text_input_tokens,
                                   "audio_output_tokens": call.audio_output_tokens,
                                   "text_output_tokens": call.text_output_tokens})
    _update_call(call_id, lambda c: (setattr(c, "status", "ended"), setattr(c, "ended_at", utcnow())))
    bus.publish(call_id, "status", {"status": "ended"})
    bus.publish(call_id, "call_ended", {})


_tasks: set[asyncio.Task] = set()


def start_simulation(call_id: str, speed: float = 1.0):
    async def runner():
        try:
            await _run(call_id, speed)
        except Exception as e:
            logger.exception("Simulation failed")
            bus.publish(call_id, "error", {"message": f"Simulation error: {e}", "fatal": True})

    task = asyncio.create_task(runner())
    _tasks.add(task)  # keep a reference so the task isn't garbage-collected
    task.add_done_callback(_tasks.discard)
