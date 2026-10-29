"""Automated issues and actionable recommendations module.

Generates problems found during the call, ranked by severity:
- High: Uncorrected field errors, call failure, high latency > 2s, severe mishearings.
- Medium: Long pauses > 2s, barge-in / interruptions, moderate latency, retry loops.
- Low: Minor WER divergence, slight code-mixed phrasing slips.

Each issue comes with an actionable recommendation in plain English.
"""

from typing import List, Dict, Any


def generate_issues_and_recommendations(
    accuracy_data: Dict[str, Any],
    latency_data: Dict[str, Any],
    mishearing_data: Dict[str, Any],
    voice_quality_data: Dict[str, Any],
    language_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Synthesize issues and actionable recommendations sorted by severity."""
    issues: List[Dict[str, Any]] = []

    # 1. Uncorrected mishearings or number confusions
    for m in mishearing_data.get("items", []):
        if not m.get("fixed_later"):
            field = m.get("field_affected", "field")
            what_heard = m.get("what_ai_heard")
            what_said = m.get("what_was_said")
            err_type = m.get("error_type", "Mishearing")

            if "Number" in err_type:
                issues.append({
                    "severity": "High",
                    "category": "Understanding",
                    "title": f"Acoustic number confusion on '{field}'",
                    "description": f"Caller said '{what_said}', but AI recorded '{what_heard}'. This error was not caught or fixed.",
                    "suggestion": f"Add an explicit digit-by-digit or word confirmation step for '{field}' (e.g., 'To confirm, is that 1-5 or 5-0?').",
                })
            else:
                issues.append({
                    "severity": "High",
                    "category": "Understanding",
                    "title": f"Uncorrected mishearing in {field}",
                    "description": f"AI misunderstood '{what_said}' as '{what_heard}'.",
                    "suggestion": "Implement a clarification prompt when caller repeats or corrects an answer.",
                })

    # 2. Form accuracy & completion
    completion = accuracy_data.get("completion_percent", 100.0)
    if completion < 100.0:
        issues.append({
            "severity": "High",
            "category": "Form Completion",
            "title": f"Incomplete form completion ({completion}%)",
            "description": "Call ended before all required form fields were collected.",
            "suggestion": "Adjust prompt system instructions to prevent early call termination before required fields are verified.",
        })

    tool_stats = accuracy_data.get("tool_call_stats", {})
    failed_tools = tool_stats.get("failed_calls", 0)
    if failed_tools > 0:
        issues.append({
            "severity": "High",
            "category": "Tool Calls",
            "title": f"{failed_tools} tool call execution failure(s)",
            "description": "Backend tool returned schema or validation errors during execution.",
            "suggestion": "Check tool parameter definitions and ensure strict type validation on the caller arguments.",
        })

    # 3. Latency issues
    avg_lat = latency_data.get("average_ms", 0.0)
    max_lat = latency_data.get("max_ms", 0.0)
    if avg_lat > 1500.0:
        issues.append({
            "severity": "High",
            "category": "Latency",
            "title": f"High average reply latency ({int(avg_lat)} ms)",
            "description": "Average response time exceeded the 1500 ms threshold.",
            "suggestion": "Reduce prompt token overhead, optimize tool latency, or switch to a faster voice model profile.",
        })
    elif max_lat > 2500.0:
        issues.append({
            "severity": "Medium",
            "category": "Latency",
            "title": f"Spike in response latency ({int(max_lat)} ms)",
            "description": "At least one turn suffered from a significant delay (> 2.5s).",
            "suggestion": "Review the slowest turns; implement filler phrases ('Let me check that for you...') during heavy backend operations.",
        })

    # 4. Audio & Voice issues
    for audio_issue in voice_quality_data.get("audio_issues", []):
        itype = audio_issue.get("type")
        sev = audio_issue.get("severity", "Medium")
        cnt = audio_issue.get("count", 1)

        if itype == "Long silence":
            issues.append({
                "severity": sev,
                "category": "Voice Flow",
                "title": f"{cnt} long silence pause(s) (> 2.0s)",
                "description": audio_issue.get("description"),
                "suggestion": "Calibrate Server VAD sensitivity or reduce turn buffer delays.",
            })
        elif "Interruption" in itype:
            issues.append({
                "severity": sev,
                "category": "Turn Taking",
                "title": f"{cnt} conversation interruption(s)",
                "description": audio_issue.get("description"),
                "suggestion": "Make agent answers more concise so caller is less likely to speak over them.",
            })

    # 5. Language support
    adherence = language_data.get("agent_adherence_percent", 100.0)
    selected_lang = language_data.get("selected_language", "English")
    if adherence < 85.0:
        issues.append({
            "severity": "Medium",
            "category": "Language Support",
            "title": f"Language drift detected ({adherence}% adherence)",
            "description": f"Agent drifted away from {selected_lang} during portions of the conversation.",
            "suggestion": f"Reinforce language instruction: 'Always converse strictly in {selected_lang} unless caller explicitly switches.'",
        })

    # Sort issues by severity: High -> Medium -> Low
    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    issues.sort(key=lambda x: severity_order.get(x.get("severity", "Low"), 3))

    return issues
