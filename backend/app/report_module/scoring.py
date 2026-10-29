"""Overall scoring and verdict module for Voice Form Tester reports.

Features:
- Standard 0-100 weighted score:
  - Accuracy: 35%
  - Latency: 20%
  - Mishearings: 15%
  - Voice Quality: 15%
  - Language Support: 10%
  - Cost Efficiency: 5%
- Simple verdicts:
  - "Good" (>= 80.0)
  - "Needs improvement" (60.0 - 79.9)
  - "Poor" (< 60.0)
- 3 Key Strengths and 3 Key Problems in clear, simple English.
"""

from typing import Dict, Any, List, Optional, Tuple
from app.report_module.config import DEFAULT_WEIGHTS, VERDICT_THRESHOLDS


def compute_component_scores(
    accuracy_data: Dict[str, Any],
    latency_data: Dict[str, Any],
    mishearing_data: Dict[str, Any],
    voice_quality_data: Dict[str, Any],
    language_data: Dict[str, Any],
    cost_data: Dict[str, Any]
) -> Dict[str, float]:
    """Normalize all metrics to standard 0-100 sub-scores."""
    # 1. Accuracy score (0-100)
    # Blend of field accuracy (70%) and form completion (30%)
    field_acc = accuracy_data.get("field_accuracy_percent", 100.0)
    completion = accuracy_data.get("completion_percent", 100.0)
    accuracy_score = (field_acc * 0.7) + (completion * 0.3)

    # 2. Latency score (0-100)
    # 500ms or lower -> 100. 1000ms -> 85. 1500ms -> 65. 2500ms+ -> 30.
    avg_lat = latency_data.get("average_ms", 1000.0)
    if avg_lat <= 600:
        latency_score = 100.0
    elif avg_lat <= 1000:
        latency_score = 100.0 - ((avg_lat - 600) / 400.0) * 15.0  # 100 -> 85
    elif avg_lat <= 1500:
        latency_score = 85.0 - ((avg_lat - 1000) / 500.0) * 20.0  # 85 -> 65
    elif avg_lat <= 2500:
        latency_score = 65.0 - ((avg_lat - 1500) / 1000.0) * 35.0  # 65 -> 30
    else:
        latency_score = max(10.0, 30.0 - ((avg_lat - 2500) / 1000.0) * 15.0)

    # 3. Mishearings score (0-100)
    # Base 100 minus penalty per mishearing, plus resolution recovery
    total_mishearings = mishearing_data.get("total_mishearings", 0)
    fixed_mishearings = mishearing_data.get("fixed_count", 0)
    unfixed = total_mishearings - fixed_mishearings

    # Each unfixed mishearing deducts 15 points, fixed mishearing deducts 5 points
    mishearing_penalty = (unfixed * 15.0) + (fixed_mishearings * 5.0)
    # Extra WER penalty if WER > 0.10
    wer = mishearing_data.get("overall_wer", 0.0)
    if wer > 0.10:
        mishearing_penalty += (wer * 20.0)

    mishearing_score = max(0.0, min(100.0, 100.0 - mishearing_penalty))

    # 4. Voice quality score (0-100)
    # Scaled from 1-5 human average and audio issues
    human_avg_5 = voice_quality_data.get("human_ratings", {}).get("average", 4.0)
    base_vq = (human_avg_5 / 5.0) * 100.0
    audio_issues_count = voice_quality_data.get("total_audio_issues_count", 0)
    vq_penalty = audio_issues_count * 5.0
    voice_quality_score = max(0.0, min(100.0, base_vq - vq_penalty))

    # 5. Language support score (0-100)
    adherence = language_data.get("agent_adherence_percent", 100.0)
    cm_rating_5 = language_data.get("code_mixing_rating", 4)
    cm_score = (cm_rating_5 / 5.0) * 100.0
    language_score = (adherence * 0.7) + (cm_score * 0.3)

    # 6. Cost score (0-100)
    # Cost per minute benchmark (under $0.03/min -> 100, above $0.15/min -> drops)
    cpm = cost_data.get("cost_per_minute_usd", 0.03)
    if cpm <= 0.02:
        cost_score = 100.0
    elif cpm <= 0.06:
        cost_score = 90.0
    elif cpm <= 0.12:
        cost_score = 75.0
    else:
        cost_score = 60.0

    return {
        "accuracy": round(accuracy_score, 1),
        "latency": round(latency_score, 1),
        "mishearings": round(mishearing_score, 1),
        "voice_quality": round(voice_quality_score, 1),
        "language_support": round(language_score, 1),
        "cost": round(cost_score, 1),
    }


def compute_overall_score(
    subscores: Dict[str, float],
    custom_weights: Optional[Dict[str, float]] = None
) -> Tuple[float, str]:
    """Calculate weighted overall score (0-100) and simple verdict."""
    weights = custom_weights or DEFAULT_WEIGHTS
    total_score = 0.0

    for cat, weight in weights.items():
        score = subscores.get(cat, 80.0)
        total_score += (score * weight)

    final_score = round(max(0.0, min(100.0, total_score)), 1)

    if final_score >= VERDICT_THRESHOLDS["good"]:
        verdict = "Good"
    elif final_score >= VERDICT_THRESHOLDS["needs_improvement"]:
        verdict = "Needs improvement"
    else:
        verdict = "Poor"

    return final_score, verdict


def generate_key_strengths_and_problems(
    subscores: Dict[str, float],
    accuracy_data: Dict[str, Any],
    latency_data: Dict[str, Any],
    mishearing_data: Dict[str, Any],
    voice_quality_data: Dict[str, Any],
    language_data: Dict[str, Any],
    cost_data: Dict[str, Any]
) -> Tuple[List[str], List[str]]:
    """Synthesize 3 key strengths and 3 key problems in plain simple English."""
    strengths: List[str] = []
    problems: List[str] = []

    # Accuracy checks
    field_acc = accuracy_data.get("field_accuracy_percent", 0)
    completion = accuracy_data.get("completion_percent", 0)
    if field_acc >= 90.0 and completion == 100.0:
        strengths.append(f"High data accuracy: captured {field_acc}% of form fields correctly with 100% completion.")
    elif completion < 100.0:
        problems.append(f"Incomplete form: missed required fields (completion rate was only {completion}%).")
    elif field_acc < 80.0:
        problems.append(f"Form field accuracy was low ({field_acc}%); some answers did not match expected values.")

    # Latency checks
    avg_lat = latency_data.get("average_ms", 0)
    if avg_lat < 1000.0:
        strengths.append(f"Fast response speed: replied in an average of {int(avg_lat)} ms without conversational lag.")
    elif avg_lat > 1500.0:
        problems.append(f"High response latency: average reply time was {int(avg_lat)} ms, creating noticeable pauses.")
    else:
        strengths.append(f"Acceptable response time averaging {int(avg_lat)} ms.")

    # Mishearings
    total_mis = mishearing_data.get("total_mishearings", 0)
    fixed_mis = mishearing_data.get("fixed_count", 0)
    if total_mis == 0:
        strengths.append("Flawless understanding: no caller corrections or acoustic mishearings detected.")
    elif fixed_mis == total_mis and total_mis > 0:
        strengths.append(f"Good error recovery: successfully corrected all {total_mis} misunderstood turn(s) during the call.")
    elif (total_mis - fixed_mis) > 0:
        problems.append(f"Misunderstood caller {total_mis} time(s); {total_mis - fixed_mis} error(s) remained uncorrected.")

    # Voice quality
    human_vq = voice_quality_data.get("human_ratings", {}).get("average", 4.0)
    audio_issues = voice_quality_data.get("audio_issues", [])
    if human_vq >= 4.2 and not audio_issues:
        strengths.append(f"High voice naturalness and pleasant tone rated {human_vq} out of 5 by tester.")
    elif audio_issues:
        issue_names = ", ".join(i.get("type") for i in audio_issues[:2])
        problems.append(f"Audio issues observed: {issue_names}.")

    # Language support
    adherence = language_data.get("agent_adherence_percent", 100)
    if adherence >= 95.0:
        strengths.append(f"Strong language adherence ({adherence}% of replies were in the selected language).")
    else:
        problems.append(f"Language drift: agent slipped out of the target language on {100 - adherence}% of turns.")

    # Cost
    total_cost_usd = cost_data.get("total_cost_usd", 0)
    cost_inr = cost_data.get("total_cost_inr", 0)
    if cost_inr < 5.0:
        strengths.append(f"Cost-effective execution: total call cost was only ${total_cost_usd:.4f} (₹{cost_inr:.2f}).")
    else:
        problems.append(f"Higher call cost: ${total_cost_usd:.4f} (₹{cost_inr:.2f}) per test session.")

    # Ensure exactly 3 strengths and 3 problems (pad with sensible defaults if needed)
    fallback_strengths = [
        "Prompt handling was polite and well-structured throughout.",
        "Tool calls and backend validations executed without system crashes.",
        "Smooth conversation flow without abrupt line drops.",
    ]
    fallback_problems = [
        "Could reduce prompt verbosity on standard confirmation turns.",
        "Acoustic number verification step should be tightened.",
        "Background noise handling could be improved in noisy testing environments.",
    ]

    for fs in fallback_strengths:
        if len(strengths) < 3 and fs not in strengths:
            strengths.append(fs)

    for fp in fallback_problems:
        if len(problems) < 3 and fp not in problems:
            problems.append(fp)

    return strengths[:3], problems[:3]
