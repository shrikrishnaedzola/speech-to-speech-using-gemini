"""Report builder orchestrator for Zolabs Voice Form Testers.

Collects inputs from call tables (or serialized dicts), runs all metrics
computations, enforces security/PII masking, and formats the unified report payload.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.report_module.security import sanitize_report_data
from app.report_module.mishearing import analyze_mishearings
from app.report_module.latency import analyze_latency
from app.report_module.accuracy import analyze_accuracy
from app.report_module.cost import calculate_call_cost
from app.report_module.language import analyze_language_support
from app.report_module.voice_quality import analyze_voice_quality
from app.report_module.scoring import (
    compute_component_scores,
    compute_overall_score,
    generate_key_strengths_and_problems,
)
from app.report_module.issues import generate_issues_and_recommendations
from app.report_module.summary_llm import generate_ai_summary


def format_duration(seconds: float) -> str:
    """Format duration in seconds into 'M:SS' or 'H:MM:SS'."""
    secs = int(max(0, seconds))
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def build_post_call_report(
    call_data: Dict[str, Any],
    form_definition: Optional[Dict[str, Any]] = None,
    answers: Optional[List[Dict[str, Any]]] = None,
    reviews: Optional[List[Dict[str, Any]]] = None,
    turn_metrics: Optional[List[Dict[str, Any]]] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    human_ratings: Optional[Dict[str, Any]] = None,
    expected_script: Optional[List[Dict[str, Any]]] = None,
    custom_weights: Optional[Dict[str, float]] = None,
    include_ai_summary: bool = False
) -> Dict[str, Any]:
    """Synchronous core builder that computes all 10 report sections.
    
    Can accept either dict data from APIs or serialized database records.
    """
    settings = call_data.get("settings", {}) or {}
    provider = call_data.get("provider") or settings.get("provider") or "gemini"
    model = call_data.get("model") or settings.get("model") or "gemini-2.5-flash"
    voice = settings.get("voice", "Default")
    language = settings.get("language", "English")
    audio_mode = settings.get("audio_mode", "Normal (16 kHz)")

    started_at = call_data.get("started_at")
    ended_at = call_data.get("ended_at")

    # Duration calculation
    duration_seconds = 0.0
    if isinstance(started_at, datetime) and isinstance(ended_at, datetime):
        duration_seconds = (ended_at - started_at).total_seconds()
    elif isinstance(started_at, str) and isinstance(ended_at, str):
        try:
            t0 = datetime.fromisoformat(started_at)
            t1 = datetime.fromisoformat(ended_at)
            duration_seconds = (t1 - t0).total_seconds()
        except Exception:
            duration_seconds = call_data.get("duration_seconds", 60.0)
    else:
        duration_seconds = call_data.get("duration_seconds", 60.0)

    duration_formatted = format_duration(duration_seconds)
    created_date = (started_at if isinstance(started_at, str) else str(started_at or datetime.now(timezone.utc)))[:10]

    transcript = call_data.get("transcript", []) or []
    answers_list = answers or []
    reviews_list = reviews or []
    turn_metrics_list = turn_metrics or []
    tool_calls_list = tool_calls or []
    form_completed = call_data.get("form_completed", False)
    interruptions = call_data.get("interruptions", 0)

    # 1. Compute Individual Sections
    # Mishearings (Section 3)
    mishearings_result = analyze_mishearings(
        transcript=transcript,
        answers=answers_list,
        reviews=reviews_list,
        expected_script=expected_script
    )

    # Latency (Section 5)
    latency_result = analyze_latency(
        turn_metrics=turn_metrics_list,
        tool_calls=tool_calls_list
    )

    # Accuracy (Section 7)
    accuracy_result = analyze_accuracy(
        form_definition=form_definition or {},
        answers=answers_list,
        reviews=reviews_list,
        tool_calls=tool_calls_list,
        transcript=transcript
    )

    # Cost (Section 8)
    cost_result = calculate_call_cost(
        provider=provider,
        duration_seconds=duration_seconds,
        audio_in_tokens=call_data.get("audio_input_tokens", 0),
        audio_out_tokens=call_data.get("audio_output_tokens", 0),
        text_in_tokens=call_data.get("text_input_tokens", 0),
        text_out_tokens=call_data.get("text_output_tokens", 0),
        form_completed=form_completed
    )

    # Language (Section 6)
    code_mixed_rating = human_ratings.get("code_mixing") if human_ratings else None
    language_result = analyze_language_support(
        selected_language=language,
        transcript=transcript,
        mishearings=mishearings_result.get("items", []),
        code_mixing_rating=code_mixed_rating
    )

    # Voice Quality (Section 4)
    voice_quality_result = analyze_voice_quality(
        transcript=transcript,
        turn_metrics=turn_metrics_list,
        interruptions_count=interruptions,
        human_ratings=human_ratings
    )

    # 2. Overall Score & Verdict (Section 1)
    subscores = compute_component_scores(
        accuracy_data=accuracy_result,
        latency_data=latency_result,
        mishearing_data=mishearings_result,
        voice_quality_data=voice_quality_result,
        language_data=language_result,
        cost_data=cost_result
    )

    overall_score, verdict = compute_overall_score(subscores, custom_weights)
    strengths, problems = generate_key_strengths_and_problems(
        subscores=subscores,
        accuracy_data=accuracy_result,
        latency_data=latency_result,
        mishearing_data=mishearings_result,
        voice_quality_data=voice_quality_result,
        language_data=language_result,
        cost_data=cost_result
    )

    # 3. Issues and Recommendations (Section 9)
    issues_result = generate_issues_and_recommendations(
        accuracy_data=accuracy_result,
        latency_data=latency_result,
        mishearing_data=mishearings_result,
        voice_quality_data=voice_quality_result,
        language_data=language_result
    )

    # Call Summary (Section 1)
    call_id = call_data.get("id") or call_data.get("call_id") or "test-call"
    call_summary = {
        "call_id": call_id,
        "provider": provider,
        "model": model,
        "voice": voice,
        "language": language,
        "audio_mode": audio_mode,
        "duration_seconds": round(duration_seconds, 1),
        "duration_formatted": duration_formatted,
        "started_at": str(started_at),
        "ended_at": str(ended_at),
        "created_date": created_date,
        "form_completed": form_completed,
    }

    scoring_summary = {
        "overall_score": overall_score,
        "verdict": verdict,
        "subscores": subscores,
        "strengths": strengths,
        "problems": problems,
    }

    # Assembled Report Data
    raw_report = {
        "metadata": {
            "version": "1.0.0",
            "test_mode": True,
            "banner_notice": "TEST MODE - dummy data only",
            "footer_notice": "AI-assisted test report - must be reviewed by a team member before sharing outside EdZola.",
            "export_filename": f"report_{provider}_{model}_{language}_{created_date}_{call_id}".replace(" ", "_"),
        },
        "call_info": call_summary,
        "scoring": scoring_summary,
        "transcript": transcript,
        "mishearings": mishearings_result,
        "voice_quality": voice_quality_result,
        "latency": latency_result,
        "language": language_result,
        "accuracy": accuracy_result,
        "cost": cost_result,
        "issues_and_recommendations": issues_result,
        "ai_summary": {
            "disclaimer": "AI-generated summary - review before sharing.",
            "text": None,
            "generated_by": None,
        },
    }

    # 4. Enforce PII masking and security scan
    sanitized_report, pii_warnings = sanitize_report_data(raw_report)
    sanitized_report["metadata"]["security_warnings"] = pii_warnings

    return sanitized_report


async def build_full_post_call_report(
    call_data: Dict[str, Any],
    form_definition: Optional[Dict[str, Any]] = None,
    answers: Optional[List[Dict[str, Any]]] = None,
    reviews: Optional[List[Dict[str, Any]]] = None,
    turn_metrics: Optional[List[Dict[str, Any]]] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    human_ratings: Optional[Dict[str, Any]] = None,
    expected_script: Optional[List[Dict[str, Any]]] = None,
    custom_weights: Optional[Dict[str, float]] = None,
    include_ai_summary: bool = True
) -> Dict[str, Any]:
    """Async wrapper that also runs AI summary generation."""
    report = build_post_call_report(
        call_data=call_data,
        form_definition=form_definition,
        answers=answers,
        reviews=reviews,
        turn_metrics=turn_metrics,
        tool_calls=tool_calls,
        human_ratings=human_ratings,
        expected_script=expected_script,
        custom_weights=custom_weights,
    )

    if include_ai_summary:
        ai_summary_res = await generate_ai_summary(report)
        report["ai_summary"] = ai_summary_res

    return report
