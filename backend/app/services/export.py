"""Export a test report as JSON or CSV.

CSV = one row per form field, so calls from the Gemini, Sarvam and OpenAI testers
can be pasted into one spreadsheet. COMMON_COLUMNS is copied unchanged from the
Sarvam tester and comes first; the Gemini-only columns (GEMINI_EXTRA_COLUMNS)
come last, so they are easy to drop or map. A second CSV (section=turns) has one
row per turn, again with the Sarvam columns first.

How the shared columns are filled for a speech-to-speech model:
    pipeline   = "gemini_live"
    llm_model  = the Gemini model id
    stt_model, tts_model = "native-audio" (Gemini hears and speaks itself)
    tts_voice  = the Gemini voice
    est_cost_inr = USD estimate x the usd_to_inr setting

NOTE: the OpenAI tester's export was not available when this was built (the
Sarvam tester has the same note). If its column names differ, change
COMMON_COLUMNS below (one place) in all testers.
"""

import csv
import io
import json

COMMON_COLUMNS = [
    "call_id", "pipeline", "mode", "form_id", "form_name", "started_at", "duration_s",
    "stt_model", "llm_model", "tts_model", "tts_voice", "language", "audio_quality",
    "field_id", "field_label", "required", "visible", "status", "saved_value", "confidence",
    "attempts", "review_verdict", "expected_value",
    "accuracy", "completion", "turns", "interruptions", "avg_response_ms", "max_response_ms",
    "tool_calls", "tool_calls_failed", "json_parse_failures", "est_cost_inr",
]
GEMINI_EXTRA_COLUMNS = [
    "reconnects", "tool_timeouts", "tool_retries", "avg_tool_ms", "tool_calls_while_speaking",
    "audio_input_tokens", "audio_output_tokens", "est_cost_usd",
    "vad_silence_ms", "save_ok_scheduling", "tool_behavior", "thinking_level",
]
CSV_COLUMNS = COMMON_COLUMNS + GEMINI_EXTRA_COLUMNS

SARVAM_TURN_COLUMNS = [
    "call_id", "turn_index", "stt_ms", "llm_ttft_ms", "tts_ttfb_ms", "total_ms",
    "turn_wait_ms", "tool_ms", "interrupted", "user_language", "user_text", "agent_text",
]
TURN_COLUMNS = SARVAM_TURN_COLUMNS + ["stop_source"]

NATIVE_AUDIO = "native-audio"


def _cell(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else value


def report_rows(report: dict) -> list[dict]:
    call, settings, m = report["call"], report["settings"], report["metrics"]
    thinking = settings.get("model") == "gemini-3.8-live-extended-thinking"
    shared = {
        "call_id": call["call_id"],
        "pipeline": call["pipeline"],
        "mode": call["mode"],
        "form_id": call["form_id"],
        "form_name": call["form_name"],
        "started_at": call["started_at"],
        "duration_s": call["duration_s"],
        "stt_model": NATIVE_AUDIO,
        "llm_model": settings.get("model"),
        "tts_model": NATIVE_AUDIO,
        "tts_voice": settings.get("voice"),
        "language": settings.get("language"),
        "audio_quality": settings.get("audio_quality"),
        "accuracy": m["accuracy"],
        "completion": m["completion"],
        "turns": m["turns"],
        "interruptions": m["interruptions"],
        "avg_response_ms": m["avg_response_ms"],
        "max_response_ms": m["max_response_ms"],
        "tool_calls": m["tool_calls"],
        "tool_calls_failed": m["tool_calls_failed"],
        "json_parse_failures": m["json_parse_failures"],
        "est_cost_inr": m["cost"]["total"],
        "reconnects": m["reconnects"],
        "tool_timeouts": m["tool_timeouts"],
        "tool_retries": m["tool_retries"],
        "avg_tool_ms": m["avg_tool_ms"],
        "tool_calls_while_speaking": m["tool_calls_while_speaking"],
        "audio_input_tokens": m["audio_input_tokens"],
        "audio_output_tokens": m["audio_output_tokens"],
        "est_cost_usd": m["cost"]["total_usd"],
        "vad_silence_ms": settings.get("vad_silence_ms"),
        "save_ok_scheduling": settings.get("save_ok_scheduling") if not thinking else "not supported",
        "tool_behavior": settings.get("tool_behavior") if not thinking else "NON_BLOCKING",
        "thinking_level": settings.get("thinking_level") if thinking else None,
    }
    rows = []
    for f in report["form"]["fields"]:
        review = f["review"] or {}
        rows.append(
            {
                **shared,
                "field_id": f["id"],
                "field_label": f["label"],
                "required": f["required"],
                "visible": f["visible"],
                "status": f["status"] if f["visible"] else "not_applicable",
                "saved_value": f["value"],
                "confidence": f["confidence"],
                "attempts": f["attempts"],
                "review_verdict": review.get("verdict"),
                "expected_value": review.get("expected_value"),
            }
        )
    return rows


def to_csv(report: dict, section: str = "fields") -> str:
    out = io.StringIO()
    if section == "turns":
        writer = csv.DictWriter(out, fieldnames=TURN_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for t in report["turns"]:
            writer.writerow({k: _cell(v) for k, v in {"call_id": report["call"]["call_id"], **t}.items()})
    else:
        writer = csv.DictWriter(out, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in report_rows(report):
            writer.writerow({k: _cell(row.get(k)) for k in CSV_COLUMNS})
    return out.getvalue()


def to_json(report: dict) -> str:
    """The full report, plus the same field rows as the CSV for easy comparison."""
    return json.dumps({**report, "rows": report_rows(report)}, ensure_ascii=False, indent=2, default=str)
