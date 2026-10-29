"""AI-written summary generator for Voice Form Tester reports.

Uses an LLM (e.g., Gemini / Google GenAI via .env) to draft a plain-English,
concise synthesis of the call based STRICTLY on calculated metrics and transcript.

Security and Integrity Constraints:
- Explicit disclaimer label: "AI-generated summary - review before sharing."
- Strict grounding prompt: Never invent numbers or metrics. Only reference
  values explicitly provided in the computed report payload.
- Graceful offline fallback if GEMINI_API_KEY is not configured or network fails.
"""

import os
from typing import Dict, Any, Optional
from loguru import logger


SUMMARY_DISCLAIMER = "AI-generated summary - review before sharing."


def generate_fallback_summary(metrics: Dict[str, Any]) -> str:
    """Deterministic, grounded rule-based summary when LLM is unavailable."""
    call_info = metrics.get("call_info", {})
    provider = call_info.get("provider", "Voice AI")
    score = metrics.get("scoring", {}).get("overall_score", 0)
    verdict = metrics.get("scoring", {}).get("verdict", "Evaluated")
    duration = call_info.get("duration_formatted", "N/A")
    lang = call_info.get("language", "English")

    acc = metrics.get("accuracy", {}).get("field_accuracy_percent", 0)
    lat = int(metrics.get("latency", {}).get("average_ms", 0))
    mis = metrics.get("mishearings", {}).get("total_mishearings", 0)
    fixed_mis = metrics.get("mishearings", {}).get("fixed_count", 0)
    cost = metrics.get("cost", {}).get("total_cost_usd", 0)
    cost_inr = metrics.get("cost", {}).get("total_cost_inr", 0)

    summary_paragraphs = [
        f"This test call with {provider} lasted {duration} in {lang}, achieving an overall score of {score}/100 ({verdict}).",
        f"The agent demonstrated a form data accuracy of {acc}% and an average reply latency of {lat} ms. "
        f"A total of {mis} mishearing(s) or understanding corrections were logged during the session, of which {fixed_mis} were resolved.",
        f"Total session cost was ${cost:.4f} (approx. ₹{cost_inr:.2f}).",
    ]
    return " ".join(summary_paragraphs)


async def generate_ai_summary(report_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an AI-written summary using Google Gemini if available, or fall back cleanly."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    # Extract clean metrics summary to pass to the model
    call_info = report_payload.get("call_info", {})
    scoring = report_payload.get("scoring", {})
    accuracy = report_payload.get("accuracy", {})
    latency = report_payload.get("latency", {})
    mishearing = report_payload.get("mishearings", {})
    voice = report_payload.get("voice_quality", {})
    cost = report_payload.get("cost", {})
    strengths = scoring.get("strengths", [])
    problems = scoring.get("problems", [])

    prompt_context = f"""
TEST REPORT METRICS (STRICT GROUND TRUTH - DO NOT INVENT ANY NUMBERS):
Provider: {call_info.get('provider')}
Model: {call_info.get('model')}
Language: {call_info.get('language')}
Duration: {call_info.get('duration_formatted')}
Overall Score: {scoring.get('overall_score')}/100 (Verdict: {scoring.get('verdict')})
Field Accuracy: {accuracy.get('field_accuracy_percent')}%
Completion Rate: {accuracy.get('completion_percent')}%
Average Latency: {int(latency.get('average_ms', 0))} ms (Rating: {latency.get('rating')})
Mishearings: {mishearing.get('total_mishearings')} total ({mishearing.get('fixed_count')} fixed)
Human Voice Rating: {voice.get('human_ratings', {}).get('average')}/5
Total Cost: ${cost.get('total_cost_usd'):.4f} (₹{cost.get('total_cost_inr'):.2f})
Key Strengths: {'; '.join(strengths)}
Key Problems: {'; '.join(problems)}

INSTRUCTIONS:
Write a 2-3 paragraph executive summary in simple, professional English for internal test evaluation.
1. Summarize how well the voice agent performed based on the metrics above.
2. Note key successes and biggest bottlenecks (latency, errors, or audio issues).
3. Do NOT make up any numbers or features not listed above.
"""

    if not api_key:
        return {
            "disclaimer": SUMMARY_DISCLAIMER,
            "text": generate_fallback_summary(report_payload),
            "generated_by": "deterministic_rules_fallback",
        }

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        # Use gemini-2.5-flash or fast standard model for text summary
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt_context,
        )
        ai_text = response.text.strip() if response and response.text else generate_fallback_summary(report_payload)
        return {
            "disclaimer": SUMMARY_DISCLAIMER,
            "text": ai_text,
            "generated_by": "gemini-2.5-flash",
        }
    except Exception as e:
        logger.warning(f"Could not generate LLM summary ({e}); using deterministic fallback.")
        return {
            "disclaimer": SUMMARY_DISCLAIMER,
            "text": generate_fallback_summary(report_payload),
            "generated_by": "deterministic_rules_fallback",
        }
