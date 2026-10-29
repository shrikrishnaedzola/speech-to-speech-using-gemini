"""Request bodies for the API (pydantic)."""

from typing import Any, Literal

from pydantic import BaseModel, Field

Sensitivity = Literal["default", "high", "low"]


class CallSettings(BaseModel):
    """Everything the tester can choose in Column 1 and the Settings panel."""

    model: Literal["gemini-3.8-live", "gemini-3.8-live-extended-thinking"] = "gemini-3.8-live"
    voice: str = "Kore"
    language: str = "auto"
    audio_quality: Literal["normal", "phone"] = "normal"
    vad_start_sensitivity: Sensitivity = "default"
    vad_end_sensitivity: Sensitivity = "default"
    vad_prefix_padding_ms: int = Field(20, ge=0, le=2000)
    vad_silence_ms: int = Field(500, ge=100, le=3000)
    tool_behavior: Literal["NON_BLOCKING", "BLOCKING"] = "NON_BLOCKING"
    save_ok_scheduling: Literal["AUTO", "SILENT", "WHEN_IDLE"] = "AUTO"
    tool_timeout_ms: int = Field(3000, ge=100, le=30000)
    tool_max_retries: int = Field(1, ge=0, le=5)
    tool_delay_ms: int = Field(0, ge=0, le=20000)
    thinking_level: Literal["low", "medium", "high"] = "low"
    rate_audio_input_per_1m: float = 3.00
    rate_text_input_per_1m: float = 0.75
    rate_audio_output_per_1m: float = 12.00
    rate_text_output_per_1m: float = 4.50
    usd_to_inr: float = 88.0
    usage_counting: Literal["sum", "last"] = "sum"


class SessionRequest(BaseModel):
    form_id: str
    settings: CallSettings = CallSettings()


class SimulateRequest(BaseModel):
    form_id: str
    settings: CallSettings = CallSettings()
    speed: float = Field(1.0, gt=0, le=20)  # 2.0 = twice as fast


class ToolRequest(BaseModel):
    call_id: str
    arguments: Any = None  # dict or JSON string, exactly as a model would send it


class ReviewItem(BaseModel):
    field_id: str
    verdict: Literal["correct", "wrong"] | None = None  # None removes the mark
    expected_value: str | None = None


class ReviewRequest(BaseModel):
    reviews: list[ReviewItem]
