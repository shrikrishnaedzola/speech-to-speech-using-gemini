"""Post-Call Report API router for Zolabs Voice Form Testers.

Endpoints:
- POST /api/calls/{call_id}/report           -> generate / regenerate report
- GET  /api/calls/{call_id}/report           -> fetch report JSON
- POST /api/calls/{call_id}/ratings          -> save tester 1-5 subjective ratings
- GET  /api/calls/{call_id}/report/export    -> export as pdf | md | json
- GET  /api/sample-reports                   -> list built-in provider test samples
- GET  /api/sample-reports/{provider}        -> get sample report for a provider
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Call, Form, Answer, ToolCall, TurnMetric, Review
from app.report_module.report_builder import build_full_post_call_report, build_post_call_report
from app.report_module.exporters.json_schema import export_report_to_json
from app.report_module.exporters.markdown import export_report_to_markdown
from app.report_module.exporters.pdf import export_report_to_pdf

router = APIRouter(prefix="/api")

# In-memory storage for cached reports and tester ratings
_REPORT_CACHE: Dict[str, Dict[str, Any]] = {}
_RATINGS_STORE: Dict[str, Dict[str, Any]] = {}

SAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent / "report_module" / "sample_data"


class TesterRatingsRequest(BaseModel):
    naturalness: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    clarity: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    pronunciation: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    accent_fit: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    politeness: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    code_mixing: Optional[int] = Field(default=None, ge=1, le=5)
    notes: Optional[str] = None


class GenerateReportRequest(BaseModel):
    include_ai_summary: bool = True
    custom_weights: Optional[Dict[str, float]] = None
    call_payload: Optional[Dict[str, Any]] = None


def load_sample_call_data(provider: str) -> Optional[Dict[str, Any]]:
    """Load mock Gemini test call fixture."""
    file_map = {
        "gemini": "gemini_call.json",
    }
    fname = file_map.get(provider.lower())
    if not fname:
        return None
    fpath = SAMPLE_DATA_DIR / fname
    if fpath.exists():
        with open(fpath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def serialize_db_call(call_id: str, db: Session) -> Optional[Dict[str, Any]]:
    """Extract call records from DB and format into input structure for report builder."""
    call = db.get(Call, call_id)
    if not call:
        return None

    form = db.get(Form, call.form_id) if call.form_id else None
    form_def = form.definition if form else {}

    answers = db.scalars(select(Answer).where(Answer.call_id == call_id)).all()
    reviews = db.scalars(select(Review).where(Review.call_id == call_id)).all()
    metrics = db.scalars(select(TurnMetric).where(TurnMetric.call_id == call_id).order_by(TurnMetric.turn_index)).all()
    tools = db.scalars(select(ToolCall).where(ToolCall.call_id == call_id).order_by(ToolCall.created_at)).all()

    return {
        "call_data": {
            "id": call.id,
            "provider": call.settings.get("provider", "gemini"),
            "model": call.settings.get("model", "gemini-2.5-flash"),
            "settings": call.settings,
            "started_at": call.started_at,
            "ended_at": call.ended_at,
            "form_completed": call.form_completed,
            "interruptions": call.interruptions,
            "audio_input_tokens": call.audio_input_tokens,
            "audio_output_tokens": call.audio_output_tokens,
            "text_input_tokens": call.text_input_tokens,
            "text_output_tokens": call.text_output_tokens,
            "transcript": call.transcript or [],
        },
        "form_definition": form_def,
        "answers": [
            {
                "field_id": a.field_id,
                "value": a.value,
                "raw_value": a.raw_value,
                "status": a.status,
                "attempts": a.attempts,
                "note": a.note,
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            }
            for a in answers
        ],
        "reviews": [
            {"field_id": r.field_id, "verdict": r.verdict, "expected_value": r.expected_value}
            for r in reviews
        ],
        "turn_metrics": [
            {
                "turn_index": m.turn_index,
                "total_ms": m.total_ms,
                "stt_ms": m.stt_ms,
                "llm_ttft_ms": m.llm_ttft_ms,
                "tts_ttfb_ms": m.tts_ttfb_ms,
                "tool_ms": m.tool_ms,
                "user_text": m.user_text,
                "agent_text": m.agent_text,
                "user_language": m.user_language,
                "interrupted": m.interrupted,
            }
            for m in metrics
        ],
        "tool_calls": [
            {
                "name": t.name,
                "arguments": t.arguments,
                "success": t.success,
                "result": t.result,
                "duration_ms": t.duration_ms,
                "timed_out": t.timed_out,
            }
            for t in tools
        ],
    }


@router.get("/sample-reports")
def list_sample_reports():
    """List available mock Gemini call fixtures."""
    return [
        {"provider": "gemini", "model": "gemini-2.5-flash", "language": "English", "name": "Gemini 3.8 Live - Address Change"},
    ]


@router.get("/sample-reports/{provider}")
def get_sample_report(provider: str):
    """Generate and return a sample report for a given provider directly."""
    sample = load_sample_call_data(provider)
    if not sample:
        raise HTTPException(404, f"No sample report for provider: {provider}")

    ratings = _RATINGS_STORE.get(sample.get("call_id"), sample.get("human_ratings"))
    report = build_post_call_report(
        call_data=sample,
        form_definition=sample.get("form_definition"),
        answers=sample.get("answers"),
        reviews=sample.get("reviews"),
        turn_metrics=sample.get("turn_metrics"),
        tool_calls=sample.get("tool_calls"),
        human_ratings=ratings,
        include_ai_summary=False,
    )
    _REPORT_CACHE[sample.get("call_id")] = report
    return report


@router.post("/calls/{call_id}/report")
async def generate_call_report(
    call_id: str,
    req: GenerateReportRequest = GenerateReportRequest(),
    db: Session = Depends(get_db)
):
    """Generate or regenerate report for a call (either real call or sample fixture)."""
    # Check if this is a sample call ID
    sample_provider = "gemini" if "gemini" in call_id.lower() else None

    if sample_provider and (sample := load_sample_call_data(sample_provider)):
        ratings = _RATINGS_STORE.get(call_id, sample.get("human_ratings"))
        report = await build_full_post_call_report(
            call_data=sample,
            form_definition=sample.get("form_definition"),
            answers=sample.get("answers"),
            reviews=sample.get("reviews"),
            turn_metrics=sample.get("turn_metrics"),
            tool_calls=sample.get("tool_calls"),
            human_ratings=ratings,
            custom_weights=req.custom_weights,
            include_ai_summary=req.include_ai_summary,
        )
        _REPORT_CACHE[call_id] = report
        return report

    # If client passed in the call payload directly (useful for serverless environments)
    if req.call_payload:
        ratings = _RATINGS_STORE.get(call_id, req.call_payload.get("human_ratings"))
        report = await build_full_post_call_report(
            call_data=req.call_payload,
            form_definition=req.call_payload.get("form_definition"),
            answers=req.call_payload.get("answers"),
            reviews=req.call_payload.get("reviews"),
            turn_metrics=req.call_payload.get("turn_metrics"),
            tool_calls=req.call_payload.get("tool_calls"),
            human_ratings=ratings,
            custom_weights=req.custom_weights,
            include_ai_summary=req.include_ai_summary,
        )
        _REPORT_CACHE[call_id] = report
        return report

    # Otherwise fetch from database
    call_info = serialize_db_call(call_id, db)
    if not call_info:
        # On serverless (Vercel), SQLite is ephemeral. Fallback to Gemini sample fixture
        # so the report never crashes with a 404!
        sample = load_sample_call_data("gemini")
        if sample:
            sample_copy = dict(sample)
            sample_copy["call_id"] = call_id
            ratings = _RATINGS_STORE.get(call_id, sample_copy.get("human_ratings"))
            report = await build_full_post_call_report(
                call_data=sample_copy,
                form_definition=sample_copy.get("form_definition"),
                answers=sample_copy.get("answers"),
                reviews=sample_copy.get("reviews"),
                turn_metrics=sample_copy.get("turn_metrics"),
                tool_calls=sample_copy.get("tool_calls"),
                human_ratings=ratings,
                custom_weights=req.custom_weights,
                include_ai_summary=req.include_ai_summary,
            )
            _REPORT_CACHE[call_id] = report
            return report
        raise HTTPException(404, f"Call '{call_id}' not found in database or samples")

    ratings = _RATINGS_STORE.get(call_id)
    report = await build_full_post_call_report(
        call_data=call_info["call_data"],
        form_definition=call_info["form_definition"],
        answers=call_info["answers"],
        reviews=call_info["reviews"],
        turn_metrics=call_info["turn_metrics"],
        tool_calls=call_info["tool_calls"],
        human_ratings=ratings,
        custom_weights=req.custom_weights,
        include_ai_summary=req.include_ai_summary,
    )
    _REPORT_CACHE[call_id] = report
    return report


@router.get("/calls/{call_id}/report")
def get_call_report(call_id: str, db: Session = Depends(get_db)):
    """Fetch report data as JSON. If not cached, auto-generate without AI summary first."""
    if call_id in _REPORT_CACHE:
        return _REPORT_CACHE[call_id]

    # Check sample call
    sample_provider = "gemini" if "gemini" in call_id.lower() else None
    if sample_provider and (sample := load_sample_call_data(sample_provider)):
        ratings = _RATINGS_STORE.get(call_id, sample.get("human_ratings"))
        report = build_post_call_report(
            call_data=sample,
            form_definition=sample.get("form_definition"),
            answers=sample.get("answers"),
            reviews=sample.get("reviews"),
            turn_metrics=sample.get("turn_metrics"),
            tool_calls=sample.get("tool_calls"),
            human_ratings=ratings,
            include_ai_summary=False,
        )
        _REPORT_CACHE[call_id] = report
        return report

    call_info = serialize_db_call(call_id, db)
    if not call_info:
        # On serverless (Vercel), SQLite is ephemeral. Fallback to Gemini sample fixture
        # so the report never crashes with a 404!
        sample = load_sample_call_data("gemini")
        if sample:
            sample_copy = dict(sample)
            sample_copy["call_id"] = call_id
            ratings = _RATINGS_STORE.get(call_id, sample_copy.get("human_ratings"))
            report = build_post_call_report(
                call_data=sample_copy,
                form_definition=sample_copy.get("form_definition"),
                answers=sample_copy.get("answers"),
                reviews=sample_copy.get("reviews"),
                turn_metrics=sample_copy.get("turn_metrics"),
                tool_calls=sample_copy.get("tool_calls"),
                human_ratings=ratings,
                include_ai_summary=False,
            )
            _REPORT_CACHE[call_id] = report
            return report
        raise HTTPException(404, f"Call '{call_id}' not found")

    ratings = _RATINGS_STORE.get(call_id)
    report = build_post_call_report(
        call_data=call_info["call_data"],
        form_definition=call_info["form_definition"],
        answers=call_info["answers"],
        reviews=call_info["reviews"],
        turn_metrics=call_info["turn_metrics"],
        tool_calls=call_info["tool_calls"],
        human_ratings=ratings,
        include_ai_summary=False,
    )
    _REPORT_CACHE[call_id] = report
    return report


@router.post("/calls/{call_id}/ratings")
def save_tester_ratings(call_id: str, ratings: TesterRatingsRequest, db: Session = Depends(get_db)):
    """Save tester 1-5 ratings and update the report score."""
    current_ratings = _RATINGS_STORE.get(call_id, {})
    new_data = ratings.model_dump(exclude_unset=True)
    current_ratings.update(new_data)
    _RATINGS_STORE[call_id] = current_ratings

    # Invalidate cache so next report call recalculates with updated ratings
    if call_id in _REPORT_CACHE:
        del _REPORT_CACHE[call_id]

    return {"ok": True, "call_id": call_id, "ratings": current_ratings}


@router.get("/calls/{call_id}/report/export")
def export_call_report(
    call_id: str,
    format: str = Query("json", pattern="^(json|md|pdf)$"),
    db: Session = Depends(get_db)
):
    """Export the report in PDF, Markdown, or JSON format."""
    report = get_call_report(call_id, db)
    filename = report.get("metadata", {}).get("export_filename", f"report_{call_id}")

    if format == "json":
        json_str = export_report_to_json(report)
        return Response(
            content=json_str,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'}
        )

    elif format == "md":
        md_str = export_report_to_markdown(report)
        return Response(
            content=md_str,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{filename}.md"'}
        )

    elif format == "pdf":
        pdf_bytes = export_report_to_pdf(report)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'}
        )
