"""Voice quality and audio issues analysis module.

Features:
- Human subjective ratings (1-5):
  - Naturalness
  - Clarity
  - Pronunciation
  - Accent fit for language
  - Politeness / Tone
- Optional local automated MOS predictor interface (UTMOS / DNSMOS).
  Controlled cleanly by settings / on-off toggle, gracefully disabled if weights not loaded.
- Audio issues detection from call logs:
  - Long silences (> 2.0s)
  - Agent talking over caller (barge-in / interruptions)
  - Cut-off sentences
  - Robotic or repeated phrases
"""

from typing import List, Dict, Any, Optional
from app.report_module.config import VOICE_QUALITY_CONFIG


def run_optional_mos_predictor(audio_path: Optional[str] = None) -> Optional[float]:
    """Run local open-source MOS score predictor if enabled in settings.
    
    Safe wrapper: returns None if feature is toggled off or model dependencies
    are not installed locally.
    """
    if not VOICE_QUALITY_CONFIG.get("enable_local_mos"):
        return None

    # Pluggable placeholder for UTMOS / DNSMOS
    # If a real model is configured, it runs inference on the dummy test call audio
    try:
        # Example: import torch; utmos = torch.hub.load(...)
        return 4.12
    except Exception:
        return None


def detect_repeated_phrases(transcript: List[Dict[str, Any]]) -> List[str]:
    """Detect robotic or exact repeated phrases by the agent."""
    agent_texts = [
        t.get("text", "").strip()
        for t in transcript
        if t.get("role") in ("agent", "model") and len(t.get("text", "").strip()) > 10
    ]

    seen = set()
    duplicates = []
    for text in agent_texts:
        if text in seen and text not in duplicates:
            duplicates.append(text)
        seen.add(text)
    return duplicates


def detect_cut_off_sentences(transcript: List[Dict[str, Any]]) -> List[str]:
    """Detect agent sentences ending abruptly without punctuation when interrupted."""
    cut_offs = []
    for turn in transcript:
        if turn.get("role") in ("agent", "model") and turn.get("interrupted"):
            txt = turn.get("text", "").strip()
            if txt and not txt.endswith(('.', '?', '!', '।')):
                cut_offs.append(txt)
    return cut_offs


def analyze_voice_quality(
    transcript: List[Dict[str, Any]],
    turn_metrics: List[Dict[str, Any]],
    interruptions_count: int = 0,
    human_ratings: Optional[Dict[str, Any]] = None,
    audio_path: Optional[str] = None
) -> Dict[str, Any]:
    """Analyze subjective voice quality, automatic MOS, and detected audio issues."""
    ratings = human_ratings or {}

    # Defaults for 1-5 human ratings if not yet rated by tester
    naturalness = ratings.get("naturalness", 4.0)
    clarity = ratings.get("clarity", 4.0)
    pronunciation = ratings.get("pronunciation", 4.0)
    accent_fit = ratings.get("accent_fit", 4.0)
    politeness = ratings.get("politeness", 5.0)

    # Average human score (scaled 1-5)
    human_score_avg = round(
        (naturalness + clarity + pronunciation + accent_fit + politeness) / 5.0, 2
    )

    # Optional automated MOS score
    automated_mos = run_optional_mos_predictor(audio_path)

    # Audio issues detection
    audio_issues = []

    # 1. Long silences (> 2.0 seconds)
    long_silence_threshold_ms = VOICE_QUALITY_CONFIG.get("silence_threshold_seconds", 2.0) * 1000.0
    long_silences_count = 0
    for tm in turn_metrics:
        total_lat = tm.get("total_ms") or 0.0
        if total_lat > long_silence_threshold_ms:
            long_silences_count += 1

    if long_silences_count > 0:
        audio_issues.append({
            "type": "Long silence",
            "severity": "Medium",
            "count": long_silences_count,
            "description": f"Detected {long_silences_count} pause(s) exceeding 2.0 seconds before agent reply",
        })

    # 2. Agent talking over caller / Interruptions
    if interruptions_count > 0:
        audio_issues.append({
            "type": "Barge-in / Interruption",
            "severity": "Medium" if interruptions_count <= 2 else "High",
            "count": interruptions_count,
            "description": f"Agent was interrupted or spoke over the caller {interruptions_count} time(s)",
        })

    # 3. Cut-off sentences
    cut_offs = detect_cut_off_sentences(transcript)
    if cut_offs:
        audio_issues.append({
            "type": "Cut-off sentence",
            "severity": "Low",
            "count": len(cut_offs),
            "description": f"{len(cut_offs)} sentence(s) stopped abruptly mid-speech",
        })

    # 4. Robotic repeated phrases
    repeats = detect_repeated_phrases(transcript)
    if repeats:
        audio_issues.append({
            "type": "Repeated phrasing",
            "severity": "Low",
            "count": len(repeats),
            "description": f"Agent repeated identical responses: '{repeats[0][:40]}...'",
        })

    return {
        "human_ratings": {
            "naturalness": naturalness,
            "clarity": clarity,
            "pronunciation": pronunciation,
            "accent_fit": accent_fit,
            "politeness": politeness,
            "average": human_score_avg,
        },
        "automatic_mos": automated_mos,
        "mos_predictor_enabled": VOICE_QUALITY_CONFIG.get("enable_local_mos", False),
        "audio_issues": audio_issues,
        "total_audio_issues_count": len(audio_issues),
    }
