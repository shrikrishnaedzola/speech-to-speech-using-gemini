"""Build the full call report: answers, transcript, turn metrics, tool calls, scores and cost.

Used by GET /api/calls/{id} and by the JSON/CSV export.
"""

from datetime import datetime, timezone
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Call, ToolCall, TurnMetric
from app.services.tools import FILLED, NEEDS_CONFIRMATION, form_state


def _avg(values):
    values = [v for v in values if v is not None]
    return round(mean(values), 1) if values else None


def _max(values):
    values = [v for v in values if v is not None]
    return round(max(values), 1) if values else None


def iso_utc(dt: datetime | None) -> str | None:
    """ISO time with a UTC marker (SQLite drops the timezone when storing)."""
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def call_duration_s(call: Call) -> float:
    start = call.started_at if call.started_at.tzinfo else call.started_at.replace(tzinfo=timezone.utc)
    end = call.ended_at or datetime.now(timezone.utc)
    end = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
    return round((end - start).total_seconds(), 1)


def estimate_cost(settings: dict, call: Call) -> dict:
    """Estimated cost from the token counts in Gemini's usage_metadata.

    Rates are USD per 1M tokens (editable in the UI). `total` is in INR, so the
    shared est_cost_inr column means the same thing as in the Sarvam tester.
    """
    per_m = 1_000_000
    audio_in = call.audio_input_tokens / per_m * settings["rate_audio_input_per_1m"]
    text_in = call.text_input_tokens / per_m * settings["rate_text_input_per_1m"]
    audio_out = call.audio_output_tokens / per_m * settings["rate_audio_output_per_1m"]
    text_out = call.text_output_tokens / per_m * settings["rate_text_output_per_1m"]
    total_usd = audio_in + text_in + audio_out + text_out
    return {
        "currency": "INR",
        "usd_to_inr": settings["usd_to_inr"],
        "input_usd": round(audio_in + text_in, 5),
        "output_usd": round(audio_out + text_out, 5),
        "total_usd": round(total_usd, 5),
        "total": round(total_usd * settings["usd_to_inr"], 4),
    }


def scores(fields: list[dict]) -> dict:
    """Accuracy = correct / reviewed filled fields. Completion = filled required / visible required."""
    filled = [f for f in fields if f["visible"] and f["status"] in (FILLED, NEEDS_CONFIRMATION)]
    reviewed = [f for f in filled if f["review"]]
    correct = [f for f in reviewed if f["review"]["verdict"] == "correct"]
    required = [f for f in fields if f["visible"] and f["required"]]
    required_filled = [f for f in required if f["status"] == FILLED]
    return {
        "filled_fields": len(filled),
        "reviewed_fields": len(reviewed),
        "correct_fields": len(correct),
        # Accuracy uses reviewed fields only, so unreviewed answers don't count as wrong.
        "accuracy": round(len(correct) / len(reviewed), 3) if reviewed else None,
        "required_total": len(required),
        "required_filled": len(required_filled),
        "completion": round(len(required_filled) / len(required), 3) if required else None,
    }


def turn_dict(t: TurnMetric) -> dict:
    return {
        "turn_index": t.turn_index,
        "stt_ms": t.stt_ms,
        "llm_ttft_ms": t.llm_ttft_ms,
        "tts_ttfb_ms": t.tts_ttfb_ms,
        "total_ms": t.total_ms,
        "turn_wait_ms": t.turn_wait_ms,
        "tool_ms": t.tool_ms,
        "stop_source": t.stop_source,
        "user_text": t.user_text,
        "agent_text": t.agent_text,
        "user_language": t.user_language,
        "interrupted": t.interrupted,
    }


def tool_dict(t: ToolCall) -> dict:
    return {
        "id": t.id,
        "gemini_call_id": t.gemini_call_id,
        "name": t.name,
        "arguments": t.arguments,
        "success": t.success,
        "result": t.result,
        "scheduling": t.scheduling,
        "duration_ms": t.duration_ms,
        "timed_out": t.timed_out,
        "retries": t.retries,
        "cancelled": t.cancelled,
        "agent_speaking_at_call": t.agent_speaking_at_call,
        "audio_chunks_during_tool": t.audio_chunks_during_tool,
        "created_at": iso_utc(t.created_at),
    }


def build_report(db: Session, call_id: str) -> dict | None:
    call = db.get(Call, call_id)
    if call is None:
        return None
    state = form_state(db, call_id)
    turns = db.scalars(select(TurnMetric).where(TurnMetric.call_id == call_id).order_by(TurnMetric.turn_index)).all()
    tools = db.scalars(select(ToolCall).where(ToolCall.call_id == call_id).order_by(ToolCall.id)).all()
    duration = call_duration_s(call)
    # Response-time stats use caller turns only (the greeting has no caller speech before it).
    caller_turns = [t for t in turns if t.stop_source is not None]
    return {
        "call": {
            "call_id": call.id,
            "pipeline": "gemini_live",
            "mode": call.mode,
            "status": call.status,
            "form_id": state["form_id"],
            "form_name": state["form_name"],
            "started_at": iso_utc(call.started_at),
            "ended_at": iso_utc(call.ended_at),
            "duration_s": duration,
            "form_completed": call.form_completed,
        },
        "settings": call.settings,
        "form": state,
        "transcript": call.transcript or [],
        "turns": [turn_dict(t) for t in turns],
        "tool_calls": [tool_dict(t) for t in tools],
        "metrics": {
            "turns": len(caller_turns),
            "interruptions": call.interruptions,
            "reconnects": call.reconnects,
            "duration_s": duration,
            "avg_response_ms": _avg([t.total_ms for t in caller_turns]),
            "max_response_ms": _max([t.total_ms for t in caller_turns]),
            "tool_calls": len(tools),
            "tool_calls_failed": sum(1 for t in tools if not t.success),
            "tool_timeouts": sum(1 for t in tools if t.timed_out),
            "tool_retries": sum(t.retries for t in tools),
            "tool_cancellations": sum(1 for t in tools if t.cancelled),
            "avg_tool_ms": _avg([t.duration_ms for t in tools]),
            "max_tool_ms": _max([t.duration_ms for t in tools]),
            # Async behaviour: the agent was talking when the tool call came in, or kept talking while it ran.
            "tool_calls_while_speaking": sum(
                1 for t in tools if t.agent_speaking_at_call or (t.audio_chunks_during_tool or 0) > 0
            ),
            "json_parse_failures": call.json_parse_failures,
            "audio_input_tokens": call.audio_input_tokens,
            "text_input_tokens": call.text_input_tokens,
            "audio_output_tokens": call.audio_output_tokens,
            "text_output_tokens": call.text_output_tokens,
            **scores(state["fields"]),
            "cost": estimate_cost(call.settings, call),
        },
        "errors": call.errors or [],
    }
