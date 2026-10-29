"""Unit and integration tests for the Post-Call Report module.

Tests cover:
- WER & CER calculation (English, Hindi, Tamil)
- Caller correction detection
- Number mishearing detection
- Latency statistics and ratings
- Accuracy & error recovery
- Cost calculation for Gemini (token-based pricing)
- Overall scoring (0-100) and verdict classification
- PII masking (Phone numbers, Aadhaar numbers)
- Full report generation across all 4 provider mock fixtures
- JSON, Markdown, and PDF export integrity
"""

import json
from pathlib import Path
import pytest

from app.report_module.security import scan_and_mask_text, sanitize_report_data
from app.report_module.mishearing import (
    calculate_wer,
    calculate_cer,
    is_caller_correction,
    detect_number_confusion,
    analyze_mishearings,
)
from app.report_module.latency import analyze_latency, classify_latency_rating
from app.report_module.accuracy import analyze_accuracy
from app.report_module.cost import calculate_call_cost
from app.report_module.scoring import (
    compute_component_scores,
    compute_overall_score,
    generate_key_strengths_and_problems,
)
from app.report_module.report_builder import build_post_call_report
from app.report_module.exporters.json_schema import validate_report_schema, export_report_to_json
from app.report_module.exporters.markdown import export_report_to_markdown
from app.report_module.exporters.pdf import export_report_to_pdf

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "app" / "report_module" / "sample_data"


# ==============================================================================
# 1. WER / CER Calculation Tests (English, Hindi, Tamil)
# ==============================================================================
def test_wer_cer_english():
    ref = "my name is rahul sharma"
    hyp_identical = "My Name Is Rahul Sharma"
    hyp_err = "my name is rohit sharma"

    assert calculate_wer(ref, hyp_identical) == 0.0
    assert calculate_cer(ref, hyp_identical) == 0.0

    # 1 word out of 5 changed -> WER = 0.2
    assert calculate_wer(ref, hyp_err) == 0.2
    # Few characters changed
    assert 0.0 < calculate_cer(ref, hyp_err) < 0.25


def test_wer_cer_hindi():
    ref = "मेरा नाम सुरेश कुमार है"
    hyp_identical = "मेरा नाम सुरेश कुमार है"
    hyp_err = "मेरा नाम रमेश कुमार है"

    assert calculate_wer(ref, hyp_identical) == 0.0
    assert calculate_cer(ref, hyp_identical) == 0.0

    # 1 substitution out of 5 words
    assert calculate_wer(ref, hyp_err) == 0.2
    assert calculate_cer(ref, hyp_err) > 0.0


def test_wer_cer_tamil():
    ref = "என் பெயர் முருகன்"
    hyp_identical = "என் பெயர் முருகன்"
    hyp_err = "என் பெயர் கண்ணன்"

    assert calculate_wer(ref, hyp_identical) == 0.0
    assert calculate_cer(ref, hyp_identical) == 0.0

    # 1 substitution out of 3 words -> ~0.33
    assert 0.30 <= calculate_wer(ref, hyp_err) <= 0.35
    assert calculate_cer(ref, hyp_err) > 0.0


# ==============================================================================
# 2. Caller Correction Detection Tests
# ==============================================================================
def test_caller_correction_detection():
    # English corrections
    assert is_caller_correction("No, I said flat 15, not 50.") is True
    assert is_caller_correction("Actually, that's wrong, I told you Bangalore.") is True
    assert is_caller_correction("Nope, I meant next week.") is True

    # Hindi corrections
    assert is_caller_correction("नहीं, मैंने कहा था पांच एकड़।") is True
    assert is_caller_correction("nahi maine kaha rohtak") is True

    # Tamil corrections
    assert is_caller_correction("இல்லை, நான் சொன்னது 600028.") is True
    assert is_caller_correction("illa naan sonnadhu washing machine") is True

    # Regular conversational turns (should NOT trigger)
    assert is_caller_correction("Yes, that is correct.") is False
    assert is_caller_correction("My name is Suresh.") is False
    assert is_caller_correction("Sure, go ahead.") is False


# ==============================================================================
# 3. Number Mishearing Checks
# ==============================================================================
def test_detect_number_confusion():
    # Spoken 'fifteen', recorded 50
    note = detect_number_confusion("I live at flat fifteen", "50")
    assert note is not None
    assert "fifteen" in note and "50" in note

    # Spoken 'fourteen', recorded 40
    note_14 = detect_number_confusion("fourteen days", "40")
    assert note_14 is not None

    # Normal matching number
    assert detect_number_confusion("twenty five", "25") is None


# ==============================================================================
# 4. Latency Statistics and Rating Tests
# ==============================================================================
def test_latency_calculation():
    metrics = [
        {"turn_index": 1, "total_ms": 700.0, "user_text": "hi", "agent_text": "hello"},
        {"turn_index": 2, "total_ms": 900.0, "user_text": "q1", "agent_text": "a1"},
        {"turn_index": 3, "total_ms": 1100.0, "user_text": "q2", "agent_text": "a2"},
        {"turn_index": 4, "total_ms": 1300.0, "user_text": "q3", "agent_text": "a3"},
    ]
    res = analyze_latency(metrics)
    assert res["average_ms"] == 1000.0
    assert res["median_ms"] == 1000.0
    assert res["max_ms"] == 1300.0
    assert res["rating"] in ("Good", "OK")
    assert len(res["slowest_turns"]) == 3
    assert res["slowest_turns"][0]["latency_ms"] == 1300.0

    assert classify_latency_rating(850.0) == "Good"
    assert classify_latency_rating(1200.0) == "OK"
    assert classify_latency_rating(1750.0) == "Poor"


# ==============================================================================
# 5. Accuracy & Error Recovery Tests
# ==============================================================================
def test_accuracy_calculation():
    form_def = {
        "fields": [
            {"id": "name", "required": True, "label": "Name"},
            {"id": "age", "required": True, "label": "Age"},
            {"id": "city", "required": False, "label": "City"},
        ]
    }

    answers = [
        {"field_id": "name", "value": "Alice", "attempts": 1},
        {"field_id": "age", "value": 25, "attempts": 2}, # retried once
    ]
    reviews = [
        {"field_id": "name", "verdict": "correct", "expected_value": "Alice"},
        {"field_id": "age", "verdict": "correct", "expected_value": "25"},
    ]
    tool_calls = [
        {"name": "check_age", "success": True},
        {"name": "save_record", "success": True},
    ]

    res = analyze_accuracy(form_def, answers, reviews, tool_calls)
    assert res["field_accuracy_percent"] == 100.0
    assert res["completion_percent"] == 100.0  # both required fields (name, age) filled
    assert res["tool_call_stats"]["success_rate_percent"] == 100.0
    assert res["error_recovery"]["retry_attempts"] == 1
    assert res["error_recovery"]["successfully_resolved"] == 1


# ==============================================================================
# 6. Cost Calculation per Provider Tests
# ==============================================================================
def test_cost_calculation_providers():
    # Gemini — token-based pricing
    gemini_cost = calculate_call_cost(
        provider="gemini",
        duration_seconds=120.0,
        audio_in_tokens=10000,
        audio_out_tokens=20000,
        text_in_tokens=2000,
        text_out_tokens=500,
    )
    assert gemini_cost["total_cost_usd"] > 0.0
    assert gemini_cost["total_cost_inr"] > 0.0
    assert gemini_cost["projection_1000_calls"]["usd"] == round(gemini_cost["total_cost_usd"] * 1000.0, 2)
    assert len(gemini_cost["breakdown"]) == 4


# ==============================================================================
# 7. Scoring and Verdict Tests
# ==============================================================================
def test_overall_scoring():
    subscores = {
        "accuracy": 95.0,
        "latency": 90.0,
        "mishearings": 85.0,
        "voice_quality": 88.0,
        "language_support": 100.0,
        "cost": 90.0,
    }
    score, verdict = compute_overall_score(subscores)
    assert 85.0 <= score <= 95.0
    assert verdict == "Good"

    # Poor score test
    poor_sub = {k: 40.0 for k in subscores}
    poor_score, poor_verdict = compute_overall_score(poor_sub)
    assert poor_score <= 50.0
    assert poor_verdict == "Poor"


# ==============================================================================
# 8. PII Masking Security Tests
# ==============================================================================
def test_pii_masking():
    # 10-digit Indian phone number
    sample_phone = "User phone is 9876543210 please verify"
    masked, warns = scan_and_mask_text(sample_phone)
    assert "98XXXXXX10" in masked
    assert "9876543210" not in masked
    assert len(warns) == 1

    # 12-digit Aadhaar number
    sample_aadhaar = "Aadhaar ID 1234 5678 9012 provided"
    masked_a, warns_a = scan_and_mask_text(sample_aadhaar)
    assert "XXXX-XXXX-9012" in masked_a
    assert "1234 5678" not in masked_a
    assert len(warns_a) == 1


# ==============================================================================
# 9. Gemini Fixture — Report Generation & Schema
# ==============================================================================
@pytest.mark.parametrize("fixture_name", [
    "gemini_call.json",
])
def test_sample_fixtures_generate_valid_reports(fixture_name):
    fpath = SAMPLE_DIR / fixture_name
    assert fpath.exists(), f"Sample fixture missing: {fixture_name}"

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    report = build_post_call_report(
        call_data=data,
        form_definition=data.get("form_definition"),
        answers=data.get("answers"),
        reviews=data.get("reviews"),
        turn_metrics=data.get("turn_metrics"),
        tool_calls=data.get("tool_calls"),
        human_ratings=data.get("human_ratings"),
    )

    # 1. Validate Schema
    is_valid, errors = validate_report_schema(report)
    assert is_valid, f"Schema validation failed for {fixture_name}: {errors}"

    # 2. Check all 10 sections exist
    assert "call_info" in report
    assert "scoring" in report
    assert "transcript" in report
    assert "mishearings" in report
    assert "voice_quality" in report
    assert "latency" in report
    assert "language" in report
    assert "accuracy" in report
    assert "cost" in report
    assert "issues_and_recommendations" in report
    assert "ai_summary" in report

    # 3. Check Security Banner
    assert report["metadata"]["banner_notice"] == "TEST MODE - dummy data only"
    assert "AI-assisted test report" in report["metadata"]["footer_notice"]

    # 4. JSON Export
    json_out = export_report_to_json(report)
    assert isinstance(json_out, str) and len(json_out) > 500

    # 5. Markdown Export
    md_out = export_report_to_markdown(report)
    assert "# Post-Call Report" in md_out
    assert "TEST MODE - dummy data only" in md_out

    # 6. PDF Export
    pdf_bytes = export_report_to_pdf(report)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
