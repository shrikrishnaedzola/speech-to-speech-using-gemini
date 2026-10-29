"""Mishearing and understanding error detection for Voice Form Testers.

Calculates:
- Word Error Rate (WER) & Character Error Rate (CER) for English, Hindi, and Tamil.
- Caller correction detection across languages ("No, I said...", "nahi, maine kaha...", "illa...").
- Number confusion detector ("fifteen" vs 50, digit swaps).
- Saved vs Expected field value discrepancy checks.
- Resolution tracking (whether mishearing was corrected in later turns).
"""

import re
from typing import List, Dict, Any, Optional, Tuple


# Levenshtein distance calculation for WER & CER
def levenshtein_distance(ref_tokens: List[str], hyp_tokens: List[str]) -> int:
    """Compute Levenshtein edit distance between two token lists (words or chars)."""
    n = len(ref_tokens)
    m = len(hyp_tokens)

    # Fast paths
    if n == 0:
        return m
    if m == 0:
        return n

    # Dynamic programming table (two rows to save memory)
    prev_row = list(range(m + 1))
    current_row = [0] * (m + 1)

    for i in range(1, n + 1):
        current_row[0] = i
        ref_char = ref_tokens[i - 1]
        for j in range(1, m + 1):
            cost = 0 if ref_char == hyp_tokens[j - 1] else 1
            current_row[j] = min(
                prev_row[j] + 1,       # deletion
                current_row[j - 1] + 1,   # insertion
                prev_row[j - 1] + cost    # substitution
            )
        prev_row = list(current_row)

    return current_row[m]


def normalize_text_for_error_rate(text: str) -> str:
    """Normalize text: strip punctuation and lowercase while preserving Unicode scripts."""
    if not text:
        return ""
    # Remove common punctuation but keep letters, digits, and Indian script diacritics
    cleaned = re.sub(r'[^\w\s\u0900-\u097F\u0B80-\u0BFF]', ' ', text)
    # Collapse multiple whitespaces
    return ' '.join(cleaned.lower().split())


def calculate_wer(reference: str, hypothesis: str) -> float:
    """Calculate Word Error Rate: (Substitutions + Deletions + Insertions) / Total Reference Words.
    
    Returns a float between 0.0 and 1.0 (capped at 1.0 for UI display clarity).
    """
    ref_norm = normalize_text_for_error_rate(reference)
    hyp_norm = normalize_text_for_error_rate(hypothesis)

    ref_words = ref_norm.split()
    hyp_words = hyp_norm.split()

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    dist = levenshtein_distance(ref_words, hyp_words)
    return round(min(1.0, dist / len(ref_words)), 4)


def calculate_cer(reference: str, hypothesis: str) -> float:
    """Calculate Character Error Rate: Better metric for Indic scripts (Hindi, Tamil, etc.).
    
    Returns a float between 0.0 and 1.0.
    """
    ref_norm = normalize_text_for_error_rate(reference)
    hyp_norm = normalize_text_for_error_rate(hypothesis)

    ref_chars = [c for c in ref_norm if not c.isspace()]
    hyp_chars = [c for c in hyp_norm if not c.isspace()]

    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0

    dist = levenshtein_distance(ref_chars, hyp_chars)
    return round(min(1.0, dist / len(ref_chars)), 4)


# Patterns where caller is explicitly correcting the voice agent
CORRECTION_PATTERNS = [
    # English
    r"\b(?:no|nope|not)\b[,\s]+(?:i\s+said|i\s+meant|actually|it\s+is|it\'s)\b",
    r"\b(?:i\s+said|i\s+told\s+you)\b",
    r"\bthat(?:'s|\s+is)\s+(?:wrong|incorrect|not\s+what\s+i\s+said)\b",
    # Hindi / Hinglish (Latin and Devanagari)
    r"\b(?:nahi|nahin|na)\b[,\s]+(?:maine\s+kaha|mera\s+matlab|vo\s+nahi)\b",
    r"\b(?:galat\s+hai|maine\s+kaha|ye\s+nahi)\b",
    r"(?:नहीं|नही)[,\s]*(?:मैंने\s*कहा|मेरा\s*मतलब|वो\s*नहीं)",
    r"(?:गलत\s*है|मैंने\s*कहा|ये\s*नहीं)",
    # Tamil / Tanglish (Latin and Tamil script)
    r"\b(?:illa|illai)\b[,\s]+(?:naan\s+sonnen|adhu\s+thappu)\b",
    r"\b(?:thappu|naan\s+sonnadhu)\b",
    r"(?:இல்லை|இல்ல)[,\s]*(?:நான்\s*சொன்ன|அது\s*தவறு|தப்பு)",
    r"(?:தவறு|தப்பு|நான்\s*சொன்னது)",
]

COMPILED_CORRECTION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in CORRECTION_PATTERNS]


def is_caller_correction(text: str) -> bool:
    """Check if the caller turn contains explicit correction indicators."""
    if not text:
        return False
    return any(p.search(text) for p in COMPILED_CORRECTION_PATTERNS)


# Pair mapping between teen words and their respective tens
TEEN_TY_PAIRS = {
    "thirteen": ("thirty", 13, 30),
    "fourteen": ("forty", 14, 40),
    "fifteen": ("fifty", 15, 50),
    "sixteen": ("sixty", 16, 60),
    "seventeen": ("seventy", 17, 70),
    "eighteen": ("eighty", 18, 80),
    "nineteen": ("ninety", 19, 90),
}


def detect_number_confusion(spoken_text: str, heard_or_saved_value: Any) -> Optional[str]:
    """Detect common acoustic number confusions (e.g. 15 vs 50, 14 vs 40)."""
    if not spoken_text:
        return None

    lower_text = spoken_text.lower()
    val_str = str(heard_or_saved_value).strip().lower()

    for teen, (ty, teen_num, ty_num) in TEEN_TY_PAIRS.items():
        if teen in lower_text:
            if val_str in (str(ty_num), ty):
                return f"Number confusion: caller said '{teen}' ({teen_num}), but AI recorded '{val_str}'"
        elif ty in lower_text:
            if val_str in (str(teen_num), teen):
                return f"Number confusion: caller said '{ty}' ({ty_num}), but AI recorded '{val_str}'"

    return None



def analyze_mishearings(
    transcript: List[Dict[str, Any]],
    answers: List[Dict[str, Any]],
    reviews: List[Dict[str, Any]],
    expected_script: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Perform comprehensive analysis of all mishearings and understanding errors.
    
    Args:
        transcript: List of bubbles {role, text, time, turn_index, language, ...}
        answers: List of saved answers {field_id, value, status, raw_value, ...}
        reviews: List of human reviews {field_id, verdict, expected_value, ...}
        expected_script: Optional scenario expected caller utterances per turn
    """
    mishearings_list: List[Dict[str, Any]] = []

    # Map reviews by field_id for quick lookups
    review_map = {r.get("field_id"): r for r in reviews}
    answer_map = {a.get("field_id"): a for a in answers}

    # 1. Script-based WER/CER if expected script is provided
    total_ref_text = []
    total_hyp_text = []

    if expected_script:
        # Match caller turns with expected caller turns
        caller_turns = [t for t in transcript if t.get("role") in ("caller", "user")]
        for i, turn in enumerate(caller_turns):
            if i < len(expected_script):
                exp_text = expected_script[i].get("text", "")
                actual_heard = turn.get("text", "")
                if exp_text:
                    total_ref_text.append(exp_text)
                    total_hyp_text.append(actual_heard)

                    # If significant divergence between expected script and transcribed text:
                    wer = calculate_wer(exp_text, actual_heard)
                    cer = calculate_cer(exp_text, actual_heard)
                    if wer > 0.35:
                        mishearings_list.append({
                            "turn_time": turn.get("time", "00:00"),
                            "turn_index": turn.get("turn_index", i + 1),
                            "what_was_said": exp_text,
                            "what_ai_heard": actual_heard,
                            "field_affected": turn.get("field_id") or "caller_turn",
                            "error_type": "Transcription divergence (WER)",
                            "wer": wer,
                            "cer": cer,
                            "fixed_later": False,  # Will check later in caller history
                        })

    overall_wer = calculate_wer(" ".join(total_ref_text), " ".join(total_hyp_text)) if total_ref_text else 0.0
    overall_cer = calculate_cer(" ".join(total_ref_text), " ".join(total_hyp_text)) if total_ref_text else 0.0

    # 2. Caller corrections detection ("No, I said...")
    for idx, turn in enumerate(transcript):
        role = turn.get("role")
        text = turn.get("text", "")
        if role in ("caller", "user") and is_caller_correction(text):
            # The PREVIOUS agent turn or earlier saved answer was misunderstood
            prev_agent_turn = transcript[idx - 1] if idx > 0 else {}
            affected_field = turn.get("field_id") or prev_agent_turn.get("field_id") or "general"

            # Check if this was resolved later
            # (i.e. did agent acknowledge and save properly afterwards?)
            fixed_later = False
            for future_turn in transcript[idx + 1:]:
                future_text = future_turn.get("text", "").lower()
                if "got it" in future_text or "noted" in future_text or "corrected" in future_text or "thank you" in future_text:
                    fixed_later = True
                    break

            mishearings_list.append({
                "turn_time": turn.get("time", "00:00"),
                "turn_index": turn.get("turn_index", idx),
                "what_was_said": text,
                "what_ai_heard": prev_agent_turn.get("text", "Misunderstood previous context"),
                "field_affected": affected_field,
                "error_type": "Caller correction",
                "fixed_later": fixed_later,
            })

    # 3. Field discrepancies (Saved value != Expected value)
    for field_id, review in review_map.items():
        verdict = review.get("verdict", "").lower()
        exp_val = review.get("expected_value")
        ans = answer_map.get(field_id, {})
        saved_val = ans.get("value")

        if verdict == "wrong" or (exp_val is not None and str(saved_val).strip() != str(exp_val).strip()):
            # Check for number confusion specifically
            num_note = detect_number_confusion(str(exp_val), saved_val)
            err_type = "Number confusion" if num_note else "Wrong field value"

            # Check if any turn later fixed it
            fixed = (verdict == "correct")

            mishearings_list.append({
                "turn_time": ans.get("updated_at", "End of call"),
                "turn_index": None,
                "what_was_said": str(exp_val),
                "what_ai_heard": str(saved_val),
                "field_affected": field_id,
                "error_type": err_type,
                "fixed_later": fixed,
                "note": num_note,
            })

    # Summary totals
    total_count = len(mishearings_list)
    fixed_count = sum(1 for m in mishearings_list if m.get("fixed_later"))
    unfixed_count = total_count - fixed_count

    return {
        "total_mishearings": total_count,
        "fixed_count": fixed_count,
        "unfixed_count": unfixed_count,
        "resolution_rate_percent": round((fixed_count / total_count * 100), 1) if total_count > 0 else 100.0,
        "overall_wer": overall_wer,
        "overall_cer": overall_cer,
        "items": mishearings_list,
    }
