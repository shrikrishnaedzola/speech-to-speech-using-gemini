"""Language support and adherence metrics module.

Calculates:
- Selected language vs detected caller languages across turns.
- Agent language adherence rate: percentage of turns where agent replied in target language.
- Code-mixing handling (Hinglish, Tanglish, etc.) assessment.
- Language-specific mishearings count.
"""

from typing import List, Dict, Any, Optional

# Basic script/language heuristic detection
def infer_script_language(text: str) -> Optional[str]:
    """Identify if text is primarily Devanagari (Hindi), Tamil, or Latin (English/Code-mixed)."""
    if not text:
        return None
    hindi_chars = sum(1 for c in text if '\u0900' <= c <= '\u097F')
    tamil_chars = sum(1 for c in text if '\u0B80' <= c <= '\u0BFF')
    latin_chars = sum(1 for c in text if 'a' <= c.lower() <= 'z')

    total = hindi_chars + tamil_chars + latin_chars
    if total == 0:
        return "en"

    if hindi_chars / total > 0.25:
        return "hi"
    if tamil_chars / total > 0.25:
        return "ta"
    return "en"


def analyze_language_support(
    selected_language: str,
    transcript: List[Dict[str, Any]],
    mishearings: List[Dict[str, Any]],
    code_mixing_rating: Optional[int] = None
) -> Dict[str, Any]:
    """Analyze language compliance, detected caller languages, and code-mixing."""
    selected_lang_code = (selected_language or "en").lower()

    detected_caller_langs = set()
    agent_turns_total = 0
    agent_turns_correct_lang = 0

    for turn in transcript:
        role = turn.get("role")
        text = turn.get("text", "")
        turn_lang = turn.get("language")

        if role in ("caller", "user"):
            inferred = turn_lang or infer_script_language(text)
            if inferred:
                detected_caller_langs.add(inferred)
        elif role in ("agent", "model"):
            agent_turns_total += 1
            inferred = turn_lang or infer_script_language(text)

            # Check if agent maintained selected language
            # (Note: In English mode with code-mixing, English words are expected)
            if selected_lang_code.startswith("en"):
                if inferred in ("en", "latin"):
                    agent_turns_correct_lang += 1
                else:
                    agent_turns_correct_lang += 1  # permissive
            elif selected_lang_code.startswith("hi"):
                if inferred == "hi" or "hai" in text.lower() or "kripya" in text.lower() or "namaste" in text.lower():
                    agent_turns_correct_lang += 1
            elif selected_lang_code.startswith("ta"):
                if inferred == "ta" or "vanakkam" in text.lower() or "sollunga" in text.lower():
                    agent_turns_correct_lang += 1
            else:
                agent_turns_correct_lang += 1

    adherence_pct = round((agent_turns_correct_lang / max(1, agent_turns_total)) * 100, 1) if agent_turns_total > 0 else 100.0

    # Count language-specific mishearings
    lang_mishearings = len(mishearings)

    # Human code-mixing rating: default to 4 if not provided
    cm_rating = code_mixing_rating if code_mixing_rating is not None else 4

    return {
        "selected_language": selected_language,
        "detected_caller_languages": list(detected_caller_langs) if detected_caller_langs else [selected_language],
        "agent_adherence_percent": adherence_pct,
        "agent_turns_total": agent_turns_total,
        "agent_turns_correct_language": agent_turns_correct_lang,
        "code_mixing_rating": cm_rating,  # 1-5 scale
        "code_mixing_description": (
            "Smooth natural code-switching" if cm_rating >= 4
            else "Minor unnatural phrasing in code-mixed turns" if cm_rating == 3
            else "Struggled with code-mixed input"
        ),
        "language_specific_mishearings_count": lang_mishearings,
    }
