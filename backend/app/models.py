"""Database tables: forms, calls, answers, tool_calls, turn_metrics, reviews.

Same tables as the Sarvam tester, plus Gemini Live fields: tool call ids,
scheduling, timeouts, retries, reconnects and per-modality token usage.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Form(Base):
    __tablename__ = "forms"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    definition: Mapped[dict] = mapped_column(JSON)  # the full form JSON (fields, rules)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    form_id: Mapped[str] = mapped_column(ForeignKey("forms.id"))
    mode: Mapped[str] = mapped_column(String, default="live")  # "live" or "simulate"
    status: Mapped[str] = mapped_column(String, default="connecting")
    settings: Mapped[dict] = mapped_column(JSON)  # model, voice, language, VAD, tools, cost rates
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    form_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    interruptions: Mapped[int] = mapped_column(Integer, default=0)
    reconnects: Mapped[int] = mapped_column(Integer, default=0)
    # Kept for the shared export columns. Gemini sends tool arguments as parsed
    # JSON, so this only counts arguments that fail the schema check.
    json_parse_failures: Mapped[int] = mapped_column(Integer, default=0)
    # Token usage from Gemini's usage_metadata, split by modality (for the cost estimate).
    audio_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    text_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    audio_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    text_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    transcript: Mapped[list] = mapped_column(JSON, default=list)  # chat bubbles
    errors: Mapped[list] = mapped_column(JSON, default=list)


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("call_id", "field_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), index=True)
    field_id: Mapped[str] = mapped_column(String)
    value: Mapped[object] = mapped_column(JSON, nullable=True)  # normalized value
    raw_value: Mapped[object] = mapped_column(JSON, nullable=True)  # what the model sent
    status: Mapped[str] = mapped_column(String, default="pending")  # filled / needs_confirmation / skipped
    confidence: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)  # clarification / skip reason
    attempts: Mapped[int] = mapped_column(Integer, default=0)  # save attempts incl. rejected ones
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), index=True)
    gemini_call_id: Mapped[str | None] = mapped_column(String, nullable=True)  # FunctionCall.id, echoed back
    name: Mapped[str] = mapped_column(String)
    arguments: Mapped[object] = mapped_column(JSON, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean)
    result: Mapped[dict] = mapped_column(JSON)
    scheduling: Mapped[str | None] = mapped_column(String, nullable=True)  # SILENT / WHEN_IDLE / INTERRUPT / None
    duration_ms: Mapped[float] = mapped_column(Float)  # tool call received -> our response sent
    timed_out: Mapped[bool] = mapped_column(Boolean, default=False)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)  # Gemini sent tool_call_cancellation
    # Async behaviour: was the agent speaking when the call arrived, and did its
    # audio keep coming while our tool ran?
    agent_speaking_at_call: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    audio_chunks_during_tool: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TurnMetric(Base):
    __tablename__ = "turn_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), index=True)
    turn_index: Mapped[int] = mapped_column(Integer)
    # Speech-to-speech has no separate STT/LLM/TTS steps. These four stay None and
    # exist only so the turns CSV has the same columns as the Sarvam tester.
    stt_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_ttft_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    tts_ttfb_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    turn_wait_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Caller stops speaking -> first agent audio chunk (measured in the backend).
    total_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    tool_ms: Mapped[float | None] = mapped_column(Float, nullable=True)  # time inside our tools this turn
    # Where "caller stopped" came from: "server_vad" (Gemini activity end) or "energy" (our RMS check).
    stop_source: Mapped[str | None] = mapped_column(String, nullable=True)
    user_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_language: Mapped[str | None] = mapped_column(String, nullable=True)
    interrupted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("call_id", "field_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), index=True)
    field_id: Mapped[str] = mapped_column(String)
    verdict: Mapped[str] = mapped_column(String)  # "correct" or "wrong"
    expected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
