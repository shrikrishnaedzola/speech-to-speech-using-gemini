"""Latency analysis module for Voice Form Tester reports (Gemini).

Calculates:
- Average, median, 90th percentile (p90), and maximum reply latency (ms).
- Rating category:
    - "Good": < 1000 ms
    - "OK": 1000 - 1500 ms
    - "Poor": > 1500 ms
- Per-turn latency series for charts.
- Slowest 3 turns with context (tool calls, query details, token length).
"""

import math
from typing import List, Dict, Any, Optional


def classify_latency_rating(avg_ms: float) -> str:
    """Classify latency into Good / OK / Poor based on benchmarks."""
    if avg_ms < 1000.0:
        return "Good"
    elif avg_ms <= 1500.0:
        return "OK"
    else:
        return "Poor"


def calculate_percentile(values: List[float], percentile: float) -> float:
    """Calculate the p-th percentile of a list of floats (0 to 100)."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(sorted_vals[int(k)], 1)
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return round(d0 + d1, 1)


def analyze_latency(
    turn_metrics: List[Dict[str, Any]],
    tool_calls: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Analyze turn metrics to compute comprehensive latency statistics.
    
    Args:
        turn_metrics: List of TurnMetric records {turn_index, total_ms, stt_ms, llm_ttft_ms, tts_ttfb_ms, tool_ms, user_text, agent_text, ...}
        tool_calls: Optional tool calls list for identifying activity during slowest turns
    """
    if not turn_metrics:
        return {
            "average_ms": 0.0,
            "median_ms": 0.0,
            "p90_ms": 0.0,
            "max_ms": 0.0,
            "rating": "Good",
            "turn_chart_data": [],
            "slowest_turns": [],
        }

    valid_latencies = []
    turn_chart_data = []

    for tm in turn_metrics:
        total_ms = tm.get("total_ms") or 0.0
        if total_ms > 0:
            valid_latencies.append(total_ms)

        stt = tm.get("stt_ms")
        llm = tm.get("llm_ttft_ms")
        tts = tm.get("tts_ttfb_ms")

        turn_chart_data.append({
            "turn_index": tm.get("turn_index", len(turn_chart_data) + 1),
            "total_ms": round(total_ms, 1),
            "tool_ms": round(tm.get("tool_ms") or 0.0, 1),
            "user_text": tm.get("user_text", ""),
            "agent_text": tm.get("agent_text", ""),
        })

    if not valid_latencies:
        valid_latencies = [0.0]

    avg_ms = round(sum(valid_latencies) / len(valid_latencies), 1)
    median_ms = calculate_percentile(valid_latencies, 50.0)
    p90_ms = calculate_percentile(valid_latencies, 90.0)
    max_ms = round(max(valid_latencies), 1)
    rating = classify_latency_rating(avg_ms)

    # Find the 3 slowest turns and explain what happened
    sorted_turns = sorted(turn_metrics, key=lambda x: x.get("total_ms") or 0.0, reverse=True)
    slowest_3 = []
    for tm in sorted_turns[:3]:
        lat = tm.get("total_ms") or 0.0
        if lat <= 0:
            continue

        tool_time = tm.get("tool_ms") or 0.0
        explanation_parts = []
        if tool_time > 0:
            explanation_parts.append(f"Tool execution took {round(tool_time, 1)} ms")
        if tm.get("interrupted"):
            explanation_parts.append("Caller interrupted the agent")
        if tm.get("stt_ms") and tm.get("stt_ms") > 800:
            explanation_parts.append(f"Slow STT transcription ({round(tm['stt_ms'], 1)} ms)")
        if not explanation_parts:
            user_text_len = len(tm.get("user_text") or "")
            agent_text_len = len(tm.get("agent_text") or "")
            if agent_text_len > 120 or user_text_len > 80:
                explanation_parts.append("Long multi-sentence response generation")
            else:
                explanation_parts.append("Model audio synthesis buffer delay")

        slowest_3.append({
            "turn_index": tm.get("turn_index", 1),
            "latency_ms": round(lat, 1),
            "user_said": tm.get("user_text", ""),
            "agent_replied": tm.get("agent_text", ""),
            "reason": "; ".join(explanation_parts),
        })

    return {
        "average_ms": avg_ms,
        "median_ms": median_ms,
        "p90_ms": p90_ms,
        "max_ms": max_ms,
        "rating": rating,
        "turn_chart_data": turn_chart_data,
        "slowest_turns": slowest_3,
    }
