"""Markdown exporter for Voice Form Tester reports.

Outputs clean, readable, GitHub-flavored Markdown covering all 10 sections.
"""

from typing import Dict, Any


def export_report_to_markdown(report: Dict[str, Any]) -> str:
    """Generate Markdown representation of the post-call report."""
    meta = report.get("metadata", {})
    call = report.get("call_info", {})
    score = report.get("scoring", {})
    sub = score.get("subscores", {})
    transcript = report.get("transcript", [])
    mis = report.get("mishearings", {})
    vq = report.get("voice_quality", {})
    lat = report.get("latency", {})
    lang = report.get("language", {})
    acc = report.get("accuracy", {})
    cost = report.get("cost", {})
    issues = report.get("issues_and_recommendations", [])
    ai = report.get("ai_summary", {})

    md = []

    # Banner
    md.append(f"> **{meta.get('banner_notice', 'TEST MODE - dummy data only')}**\n")
    if meta.get("security_warnings"):
        for w in meta.get("security_warnings", []):
            md.append(f"> ⚠️ **Security Notice**: {w}\n")

    # Title
    md.append(f"# Post-Call Report: {call.get('provider', '').title()} ({call.get('model', '')})\n")

    # 1. Summary
    md.append("## 1. Call Summary")
    md.append(f"- **Call ID**: `{call.get('call_id')}`")
    md.append(f"- **Provider**: {call.get('provider', '').title()} | **Model**: {call.get('model')}")
    md.append(f"- **Language**: {call.get('language')} | **Audio Mode**: {call.get('audio_mode')}")
    md.append(f"- **Duration**: {call.get('duration_formatted')} ({call.get('duration_seconds')} s)")
    md.append(f"- **Date**: {call.get('created_date')}")
    md.append(f"- **Overall Score**: **{score.get('overall_score')}/100** — *Verdict: {score.get('verdict')}*\n")

    md.append("### Subscores (0–100)")
    md.append(f"- Accuracy (35%): **{sub.get('accuracy', 0)}**")
    md.append(f"- Latency (20%): **{sub.get('latency', 0)}**")
    md.append(f"- Mishearings (15%): **{sub.get('mishearings', 0)}**")
    md.append(f"- Voice Quality (15%): **{sub.get('voice_quality', 0)}**")
    md.append(f"- Language Support (10%): **{sub.get('language_support', 0)}**")
    md.append(f"- Cost Efficiency (5%): **{sub.get('cost', 0)}**\n")

    md.append("### Key Strengths")
    for s in score.get("strengths", []):
        md.append(f"- ✅ {s}")
    md.append("\n### Key Problems")
    for p in score.get("problems", []):
        md.append(f"- ⚠️ {p}")
    md.append("\n---\n")

    # 10. AI-written summary (placed near top for executive overview)
    if ai.get("text"):
        md.append("## AI-Written Executive Summary")
        md.append(f"> *{ai.get('disclaimer')}*\n")
        md.append(f"{ai.get('text')}\n")
        md.append("---\n")

    # 2. Transcript
    md.append("## 2. Transcript")
    if not transcript:
        md.append("_No transcript recorded._\n")
    else:
        for turn in transcript:
            role = turn.get("role", "unknown").upper()
            time_str = turn.get("time", "")
            turn_lang = turn.get("language", "")
            lang_badge = f" `[{turn_lang}]`" if turn_lang else ""
            txt = turn.get("text", "")

            # Highlight indicators
            tags = []
            if turn.get("interrupted"):
                tags.append("🟣 Interrupted")
            if turn.get("is_correction"):
                tags.append("🔴 Correction")
            if turn.get("tool_call"):
                tags.append("🔵 Tool Call")
            tag_str = f" *({' | '.join(tags)})*" if tags else ""

            md.append(f"**[{time_str}] {role}{lang_badge}**{tag_str}: {txt}\n")
    md.append("---\n")

    # 3. Mishearings
    md.append("## 3. Mishearings & Understanding Errors")
    md.append(f"- **Total Mishearings**: {mis.get('total_mishearings', 0)}")
    md.append(f"- **Fixed During Call**: {mis.get('fixed_count', 0)} ({mis.get('resolution_rate_percent', 0)}%)")
    md.append(f"- **Unfixed Errors**: {mis.get('unfixed_count', 0)}")
    md.append(f"- **Overall WER**: {mis.get('overall_wer', 0.0) * 100:.1f}% | **CER**: {mis.get('overall_cer', 0.0) * 100:.1f}%\n")

    mis_items = mis.get("items", [])
    if mis_items:
        md.append("| Time | What Was Said | What AI Heard | Field Affected | Fixed Later? | Error Type |")
        md.append("|---|---|---|---|---|---|")
        for item in mis_items:
            fixed_icon = "✅ Yes" if item.get("fixed_later") else "❌ No"
            md.append(f"| {item.get('turn_time')} | {item.get('what_was_said')} | {item.get('what_ai_heard')} | `{item.get('field_affected')}` | {fixed_icon} | {item.get('error_type')} |")
        md.append("")
    else:
        md.append("_No mishearings or understanding errors logged._\n")
    md.append("---\n")

    # 4. Voice Quality
    md.append("## 4. Voice Quality & Audio Issues")
    ratings = vq.get("human_ratings", {})
    md.append(f"- **Human Rating**: **{ratings.get('average', 0)} / 5.0**")
    md.append(f"  - Naturalness: {ratings.get('naturalness', 0)}/5")
    md.append(f"  - Clarity: {ratings.get('clarity', 0)}/5")
    md.append(f"  - Pronunciation: {ratings.get('pronunciation', 0)}/5")
    md.append(f"  - Accent Fit: {ratings.get('accent_fit', 0)}/5")
    md.append(f"  - Politeness/Tone: {ratings.get('politeness', 0)}/5")
    if vq.get("automatic_mos"):
        md.append(f"- **Automatic MOS Score (UTMOS)**: **{vq.get('automatic_mos')} / 5.0**")

    audio_issues = vq.get("audio_issues", [])
    if audio_issues:
        md.append("\n**Audio Issues Detected:**")
        for ai_issue in audio_issues:
            md.append(f"- ⚠️ **{ai_issue.get('type')}** ({ai_issue.get('severity')}): {ai_issue.get('description')}")
    else:
        md.append("\n_No audio anomalies (silences > 2s, robotic repetition, or cut-offs) detected._")
    md.append("\n---\n")

    # 5. Latency
    md.append("## 5. Latency & Response Times")
    md.append(f"- **Average Reply Time**: **{lat.get('average_ms', 0)} ms** (Rating: **{lat.get('rating')}**)")
    md.append(f"- **Median**: {lat.get('median_ms', 0)} ms | **p90**: {lat.get('p90_ms', 0)} ms | **Max**: {lat.get('max_ms', 0)} ms\n")

    slow_turns = lat.get("slowest_turns", [])
    if slow_turns:
        md.append("### Slowest 3 Turns")
        for st in slow_turns:
            md.append(f"- **Turn {st.get('turn_index')}** ({st.get('latency_ms')} ms): {st.get('reason')}")
            if st.get("user_said"):
                md.append(f"  - *Caller*: \"{st.get('user_said')}\"")
            if st.get("agent_replied"):
                md.append(f"  - *Agent*: \"{st.get('agent_replied')}\"")
    md.append("\n---\n")

    # 6. Language Support
    md.append("## 6. Language Support")
    md.append(f"- **Selected Language**: {lang.get('selected_language')}")
    md.append(f"- **Detected Caller Languages**: {', '.join(lang.get('detected_caller_languages', []))}")
    md.append(f"- **Agent Language Adherence**: **{lang.get('agent_adherence_percent')}%**")
    md.append(f"- **Code-Mixing Handling**: {lang.get('code_mixing_rating')}/5 ({lang.get('code_mixing_description')})")
    md.append(f"- **Language-Specific Mishearings**: {lang.get('language_specific_mishearings_count')}\n")
    md.append("---\n")

    # 7. Accuracy
    md.append("## 7. Form Data Accuracy")
    md.append(f"- **Field Accuracy**: **{acc.get('field_accuracy_percent')}%** ({acc.get('correct_fields_count')}/{acc.get('filled_fields_count')} fields correct)")
    md.append(f"- **Completion Rate**: **{acc.get('completion_percent')}%**")
    t_stats = acc.get("tool_call_stats", {})
    md.append(f"- **Tool Call Success**: {t_stats.get('success_rate_percent', 100)}% ({t_stats.get('successful_calls', 0)}/{t_stats.get('total_calls', 0)} passed)")
    rec = acc.get("error_recovery", {})
    md.append(f"- **Error Recovery**: {rec.get('successfully_resolved', 0)}/{rec.get('retry_attempts', 0)} retries resolved\n")

    field_rows = acc.get("field_table", [])
    if field_rows:
        md.append("| Field | Expected | Saved | Correct? | Notes |")
        md.append("|---|---|---|---|---|")
        for row in field_rows:
            c_icon = "✅" if row.get("correct") else "❌"
            md.append(f"| {row.get('field_label')} | {row.get('expected')} | {row.get('saved')} | {c_icon} {row.get('verdict')} | {row.get('notes')} |")
    md.append("\n---\n")

    # 8. Cost
    md.append("## 8. Cost & Economics")
    md.append(f"- **Total Call Cost**: **${cost.get('total_cost_usd', 0):.4f}** (₹{cost.get('total_cost_inr', 0):.2f})")
    md.append(f"- **Cost per Minute**: ${cost.get('cost_per_minute_usd', 0):.4f} (₹{cost.get('cost_per_minute_inr', 0):.2f})")
    md.append(f"- **Cost per Completed Form**: ${cost.get('cost_per_completed_form_usd', 0):.4f}")
    proj = cost.get("projection_1000_calls", {})
    md.append(f"- **1,000 Similar Calls Projection**: **${proj.get('usd', 0):,.2f}** (₹{proj.get('inr', 0):,.2f})")
    md.append(f"- *Rates last updated: {cost.get('rates_last_updated')} (USD/INR: {cost.get('exchange_rate_usd_to_inr')}*\n")

    cost_items = cost.get("breakdown", [])
    if cost_items:
        md.append("| Item | Quantity | Unit Rate | USD | INR |")
        md.append("|---|---|---|---|---|")
        for ci in cost_items:
            md.append(f"| {ci.get('item')} | {ci.get('quantity')} | {ci.get('rate')} | ${ci.get('cost_usd'):.5f} | ₹{ci.get('cost_inr'):.2f} |")
    md.append("\n---\n")

    # 9. Issues & Recommendations
    md.append("## 9. Issues & Recommendations")
    if not issues:
        md.append("_No critical issues found. Performance was satisfactory._\n")
    else:
        for iss in issues:
            sev = iss.get("severity", "Medium")
            icon = "🔴" if sev == "High" else "🟡" if sev == "Medium" else "🟢"
            md.append(f"### {icon} [{sev.upper()}] {iss.get('title')}")
            md.append(f"- **Problem**: {iss.get('description')}")
            md.append(f"- **Recommendation**: {iss.get('suggestion')}\n")
    md.append("---\n")

    # Mandatory security footer
    md.append(f"*{meta.get('footer_notice', 'AI-assisted test report - must be reviewed by a team member before sharing outside EdZola.')}*\n")

    return "\n".join(md)
