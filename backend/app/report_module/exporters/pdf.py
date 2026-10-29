"""PDF report exporter using ReportLab and Matplotlib.

Features:
- Professional layout with header badges, tables, and typography.
- Embedded Matplotlib charts:
  - Response Latency per Turn chart (with Good/OK/Poor reference bands)
  - Cost Breakdown / Subscores chart
- Security requirements:
  - "TEST MODE - dummy data only" banner and header
  - Footer on every page: "AI-assisted test report - must be reviewed by a team member before sharing outside EdZola."
"""

import io
from typing import Dict, Any, List

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Canvas that adds running headers, running footers, and page numbers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#DC2626"))
        # Top banner
        self.drawString(54, 755, "TEST MODE - DUMMY DATA ONLY")

        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawRightString(558, 755, "Zolabs Voice Form Tester Report")

        # Bottom footer line & text
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)

        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawString(54, 32, "AI-assisted test report - must be reviewed by a team member before sharing outside EdZola.")
        self.drawRightString(558, 32, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def render_latency_chart_png(turn_data: List[Dict[str, Any]]) -> io.BytesIO:
    """Generate Matplotlib latency chart image in memory."""
    buf = io.BytesIO()
    fig, ax = plt.subplots(figsize=(7.0, 2.5), dpi=150)

    turns = [t.get("turn_index", i + 1) for i, t in enumerate(turn_data)]
    totals = [t.get("total_ms", 0) for t in turn_data]

    if not turns:
        turns = [1]
        totals = [0]

    # Benchmark zones
    ax.axhspan(0, 1000, color="#ECFDF5", alpha=0.8, label="Good (<1000ms)")
    ax.axhspan(1000, 1500, color="#FEF3C7", alpha=0.8, label="OK (1000-1500ms)")
    max_limit = max(2000, max(totals) * 1.2) if totals else 2000
    ax.axhspan(1500, max_limit, color="#FEE2E2", alpha=0.8, label="Poor (>1500ms)")

    # Line + marker for Gemini turn latency
    ax.plot(turns, totals, color="#059669", marker="o", linewidth=2, markersize=5, label="Turn Latency")

    ax.set_title("Response Latency per Turn (ms)", fontsize=10, fontweight="bold", pad=8)
    ax.set_xlabel("Turn Number", fontsize=8)
    ax.set_ylabel("Latency (ms)", fontsize=8)
    ax.set_ylim(0, max_limit)
    ax.tick_params(labelsize=8)
    ax.grid(True, linestyle="--", alpha=0.4, axis="y")
    ax.legend(loc="upper right", fontsize=7, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def render_subscores_chart_png(subscores: Dict[str, float]) -> io.BytesIO:
    """Generate horizontal bar chart of 6 subscores."""
    buf = io.BytesIO()
    fig, ax = plt.subplots(figsize=(7.0, 1.8), dpi=150)

    categories = ["Accuracy", "Latency", "Mishearing", "Voice Qual.", "Language", "Cost"]
    scores = [
        subscores.get("accuracy", 0),
        subscores.get("latency", 0),
        subscores.get("mishearings", 0),
        subscores.get("voice_quality", 0),
        subscores.get("language_support", 0),
        subscores.get("cost", 0),
    ]

    colors_list = ["#10B981" if s >= 80 else "#F59E0B" if s >= 60 else "#EF4444" for s in scores]
    y_pos = range(len(categories))

    bars = ax.barh(y_pos, scores, color=colors_list, height=0.55)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(categories, fontsize=8)
    ax.set_xlim(0, 105)
    ax.set_xlabel("Score (0–100)", fontsize=8)
    ax.set_title("Component Performance Breakdown", fontsize=9, fontweight="bold", pad=6)
    ax.tick_params(labelsize=8)
    ax.grid(True, linestyle="--", alpha=0.3, axis="x")

    for bar, val in zip(bars, scores):
        ax.text(val + 1.5, bar.get_y() + bar.get_height() / 2, f"{val:.0f}", va="center", fontsize=7.5, fontweight="bold")

    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def export_report_to_pdf(report: Dict[str, Any]) -> bytes:
    """Compile the entire 10-section report into a high quality PDF byte stream."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )
    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )
    bold_body = ParagraphStyle(
        "BoldBody",
        parent=body_style,
        fontName="Helvetica-Bold",
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=body_style,
        fontName="Helvetica-Oblique",
        fontSize=8,
        textColor=colors.HexColor("#64748B"),
    )

    story = []

    call = report.get("call_info", {})
    score = report.get("scoring", {})
    sub = score.get("subscores", {})

    # Header
    story.append(Paragraph(f"Voice AI Performance Report · {call.get('provider', '').title()}", title_style))
    story.append(Paragraph(f"Model: {call.get('model')} | Language: {call.get('language')} | Date: {call.get('created_date')} | Duration: {call.get('duration_formatted')}", disclaimer_style))
    story.append(Spacer(1, 8))

    # Verdict Score Card Box
    verdict_color = "#10B981" if score.get("overall_score", 0) >= 80 else "#F59E0B" if score.get("overall_score", 0) >= 60 else "#EF4444"
    score_table_data = [
        [
            Paragraph(f"<b>Overall Score: {score.get('overall_score')}/100</b>", ParagraphStyle("ScoreL", fontName="Helvetica-Bold", fontSize=13, textColor=colors.HexColor(verdict_color))),
            Paragraph(f"<b>Verdict: {score.get('verdict')}</b>", ParagraphStyle("ScoreR", fontName="Helvetica-Bold", fontSize=13, textColor=colors.HexColor(verdict_color))),
        ]
    ]
    score_table = Table(score_table_data, colWidths=[250, 250])
    score_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor(verdict_color)),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 8))

    # Strengths and Problems
    sp_data = [
        [
            Paragraph("<b>Key Strengths</b>", bold_body),
            Paragraph("<b>Key Problems</b>", bold_body),
        ],
        [
            Paragraph("<br/>".join([f"• {s}" for s in score.get("strengths", [])]), body_style),
            Paragraph("<br/>".join([f"• {p}" for p in score.get("problems", [])]), body_style),
        ]
    ]
    sp_table = Table(sp_data, colWidths=[250, 250])
    sp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#F0FDF4")),
        ('BACKGROUND', (1, 0), (1, -1), colors.HexColor("#FEF2F2")),
        ('BOX', (0, 0), (0, -1), 0.5, colors.HexColor("#BBF7D0")),
        ('BOX', (1, 0), (1, -1), 0.5, colors.HexColor("#FECACA")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(sp_table)
    story.append(Spacer(1, 10))

    # Component Scores Chart
    chart_buf = render_subscores_chart_png(sub)
    story.append(Image(chart_buf, width=500, height=130))
    story.append(Spacer(1, 10))

    # Latency Section & Chart
    lat = report.get("latency", {})
    story.append(Paragraph(f"Latency Analysis (Avg: {lat.get('average_ms', 0)} ms — Rating: {lat.get('rating')})", h2_style))
    lat_chart_buf = render_latency_chart_png(lat.get("turn_chart_data", []))
    story.append(Image(lat_chart_buf, width=500, height=175))
    story.append(Spacer(1, 8))

    # Accuracy & Form Table
    acc = report.get("accuracy", {})
    story.append(Paragraph(f"Form Field Accuracy ({acc.get('field_accuracy_percent')}% accuracy | {acc.get('completion_percent')}% completion)", h2_style))
    field_rows = [["Field", "Expected", "Saved", "Verdict"]]
    for f in acc.get("field_table", [])[:8]:  # Limit table rows to keep PDF tidy
        v_str = "Correct" if f.get("correct") else "Wrong"
        field_rows.append([
            f.get("field_label", ""),
            str(f.get("expected", ""))[:20],
            str(f.get("saved", ""))[:20],
            v_str
        ])
    field_pdf_table = Table(field_rows, colWidths=[140, 140, 140, 80])
    field_pdf_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(field_pdf_table)
    story.append(Spacer(1, 10))

    # Mishearings Section
    mis = report.get("mishearings", {})
    story.append(Paragraph(f"Mishearings & Understanding Errors ({mis.get('total_mishearings', 0)} total, {mis.get('fixed_count', 0)} fixed)", h2_style))
    if mis.get("items"):
        mis_rows = [["Time", "What Caller Said", "What AI Heard", "Fixed?"]]
        for m in mis.get("items")[:5]:
            mis_rows.append([
                str(m.get("turn_time")),
                str(m.get("what_was_said"))[:30],
                str(m.get("what_ai_heard"))[:30],
                "Yes" if m.get("fixed_later") else "No"
            ])
        mis_table = Table(mis_rows, colWidths=[60, 200, 180, 60])
        mis_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#FEF2F2")),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#FECACA")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(mis_table)
    else:
        story.append(Paragraph("No mishearings or understanding errors logged.", body_style))
    story.append(Spacer(1, 10))

    # Cost Summary
    cost = report.get("cost", {})
    proj = cost.get("projection_1000_calls", {})
    story.append(Paragraph(f"Cost & Economics (Call: ${cost.get('total_cost_usd', 0):.4f} / ₹{cost.get('total_cost_inr', 0):.2f})", h2_style))
    cost_text = f"Rate per minute: ${cost.get('cost_per_minute_usd', 0):.4f} (₹{cost.get('cost_per_minute_inr', 0):.2f}) | Projection for 1,000 calls: ${proj.get('usd', 0):,.2f} (₹{proj.get('inr', 0):,.2f})"
    story.append(Paragraph(cost_text, body_style))
    story.append(Spacer(1, 10))

    # Recommendations
    story.append(Paragraph("Priority Issues & Recommendations", h2_style))
    issues = report.get("issues_and_recommendations", [])
    if issues:
        for iss in issues[:3]:
            sev = iss.get("severity", "Medium")
            txt = f"<b>[{sev}] {iss.get('title')}</b>: {iss.get('suggestion')}"
            story.append(Paragraph(txt, body_style))
            story.append(Spacer(1, 3))
    else:
        story.append(Paragraph("All performance thresholds met cleanly.", body_style))

    # Build document with running headers/footers
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()
