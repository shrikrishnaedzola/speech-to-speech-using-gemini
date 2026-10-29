"""Form data accuracy and tool execution metrics module.

Calculates:
- Field Accuracy: (correct fields / filled fields) * 100
- Form Completion: (filled required fields / total required fields) * 100
- Follow-up Correctness: Appropriateness of follow-up questions
- Error Recovery: Re-asking after validation rejections & saving corrections
- Tool Call Success Rate: (successful tool executions / total tool calls) * 100
- Detailed Field Comparison Table: Field | Expected | Saved | Correct? | Notes
"""

from typing import List, Dict, Any, Optional


def analyze_accuracy(
    form_definition: Dict[str, Any],
    answers: List[Dict[str, Any]],
    reviews: List[Dict[str, Any]],
    tool_calls: List[Dict[str, Any]],
    transcript: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Analyze form field accuracy, completion rate, tool calls, and error recovery."""
    fields_def = form_definition.get("fields", []) if form_definition else []
    required_field_ids = {f["id"] for f in fields_def if f.get("required", False)}
    all_field_ids = [f["id"] for f in fields_def] if fields_def else []

    answer_map = {a.get("field_id"): a for a in answers}
    review_map = {r.get("field_id"): r for r in reviews}

    # If no fields in definition, fall back to whatever answers exist
    if not all_field_ids:
        all_field_ids = list(set(list(answer_map.keys()) + list(review_map.keys())))

    field_table: List[Dict[str, Any]] = []
    filled_count = 0
    correct_count = 0
    required_filled_count = 0
    error_recovery_attempts = 0
    error_recovery_successes = 0

    for fid in all_field_ids:
        ans = answer_map.get(fid, {})
        rev = review_map.get(fid, {})

        saved_value = ans.get("value")
        raw_val = ans.get("raw_value")
        attempts = ans.get("attempts", 1)
        expected_val = rev.get("expected_value")
        verdict = rev.get("verdict", "").lower()
        note = ans.get("note") or rev.get("note") or ""

        is_filled = saved_value is not None and str(saved_value).strip() != ""
        if is_filled:
            filled_count += 1
            if fid in required_field_ids:
                required_filled_count += 1

        # Determine correctness:
        # 1. From human review verdict if present ("correct" / "wrong")
        # 2. Or from exact equality with expected_value if provided
        # 3. Default to correct if filled and no negative review
        if verdict == "correct":
            is_correct = True
        elif verdict == "wrong":
            is_correct = False
        elif expected_val is not None:
            is_correct = (str(saved_value).strip().lower() == str(expected_val).strip().lower())
        else:
            is_correct = is_filled  # Assumed correct if filled and not marked wrong

        if is_filled and is_correct:
            correct_count += 1

        # Track error recovery (attempts > 1 means model had to retry/recover)
        if attempts > 1:
            error_recovery_attempts += (attempts - 1)
            if is_correct:
                error_recovery_successes += 1

        # Build notes
        notes_list = []
        if attempts > 1:
            notes_list.append(f"Retried ({attempts} attempts)")
        if raw_val and str(raw_val) != str(saved_value):
            notes_list.append(f"Normalized from '{raw_val}'")
        if note:
            notes_list.append(note)

        field_table.append({
            "field_id": fid,
            "field_label": next((f.get("label", fid) for f in fields_def if f.get("id") == fid), fid),
            "required": fid in required_field_ids,
            "expected": expected_val if expected_val is not None else "(Not set)",
            "saved": saved_value if saved_value is not None else "(None)",
            "correct": is_correct,
            "verdict": "Correct" if is_correct else "Incorrect",
            "notes": "; ".join(notes_list) if notes_list else "—",
        })

    # Calculations
    total_required = len(required_field_ids) if required_field_ids else max(1, len(all_field_ids))
    field_accuracy_pct = round((correct_count / max(1, filled_count)) * 100, 1)
    completion_pct = round((required_filled_count / total_required) * 100, 1)

    # Tool calls analysis
    total_tool_calls = len(tool_calls)
    successful_tool_calls = sum(1 for t in tool_calls if t.get("success", False))
    failed_tool_calls = total_tool_calls - successful_tool_calls
    tool_success_rate = round((successful_tool_calls / max(1, total_tool_calls)) * 100, 1) if total_tool_calls > 0 else 100.0

    # Follow-up correctness estimation
    # Follow-ups were good if required fields were completed without excessive retries
    if error_recovery_attempts == 0:
        follow_up_rating = "High (Optimal turns, no redundant queries)"
        follow_up_score = 100.0
    elif error_recovery_successes == error_recovery_attempts:
        follow_up_rating = "Good (All re-asked questions successfully resolved)"
        follow_up_score = 90.0
    else:
        follow_up_rating = "Needs attention (Some validation errors remained unfixed)"
        follow_up_score = 65.0

    return {
        "field_accuracy_percent": field_accuracy_pct,
        "completion_percent": completion_pct,
        "correct_fields_count": correct_count,
        "filled_fields_count": filled_count,
        "total_fields_count": len(all_field_ids),
        "required_fields_count": total_required,
        "tool_call_stats": {
            "total_calls": total_tool_calls,
            "successful_calls": successful_tool_calls,
            "failed_calls": failed_tool_calls,
            "success_rate_percent": tool_success_rate,
        },
        "error_recovery": {
            "retry_attempts": error_recovery_attempts,
            "successfully_resolved": error_recovery_successes,
            "recovery_rate_percent": round((error_recovery_successes / max(1, error_recovery_attempts)) * 100, 1) if error_recovery_attempts > 0 else 100.0,
        },
        "follow_up_correctness": {
            "rating": follow_up_rating,
            "score": follow_up_score,
        },
        "field_table": field_table,
    }
