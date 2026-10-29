# Post-Call Report Module — Zolabs Voice Form Tester (Gemini)

> **TEST MODE — dummy data only.**
> This module generates evaluation reports for Gemini Live API test calls.
> It must never be used with real user data.

---

## What it does

After every Gemini test call, this module automatically generates a
**10-section post-call report** that shows:

| # | Section | What it covers |
|---|---------|---------------|
| 1 | Call Summary | Score (0-100), verdict, strengths, problems |
| 2 | Transcript | Full chat with colour highlights |
| 3 | Mishearings | WER/CER, what was said vs what AI heard |
| 4 | Voice Quality | Naturalness, clarity, silences, robotic phrases |
| 5 | Latency | Avg/p90/max reply time, per-turn chart |
| 6 | Language Support | Language adherence %, code-mixing handling |
| 7 | Accuracy | Field accuracy, completion, tool call success |
| 8 | Cost | USD/INR breakdown, per-minute, 1,000-call projection |
| 9 | Issues | Auto-generated High/Medium/Low recommendations |
| 10 | AI Summary | Optional plain-English summary from Gemini |

---

## Project structure

```
backend/app/report_module/
├── __init__.py           — package marker + docstring
├── config.py             — weights, cost rates, exchange rate, MOS toggle
├── security.py           — PII masking (phone numbers, Aadhaar)
├── mishearing.py         — WER/CER, correction detection, number errors
├── latency.py            — avg/median/p90/max, ratings, slowest turns
├── accuracy.py           — field accuracy, completion, tool calls
├── cost.py               — Gemini pricing, USD/INR, 1,000-call projection
├── language.py           — language adherence, script detection
├── voice_quality.py      — human ratings, silence, repeated phrases
├── scoring.py            — weighted 0-100 score, verdict, strengths/problems
├── issues.py             — prioritized recommendations
├── report_builder.py     — main orchestrator (call this to build a report)
├── summary_llm.py        — optional AI summary (uses GEMINI_API_KEY)
├── exporters/
│   ├── json_schema.py    — fixed JSON schema for all providers
│   ├── markdown.py       — GitHub-flavoured Markdown export
│   └── pdf.py            — ReportLab + matplotlib PDF export
├── sample_data/
│   └── gemini_call.json  — dummy Gemini call (address change, number mishearing)
└── README.md             — this file
```

---

## Quick start

### 1. Build a report from a real call

```python
from app.report_module.report_builder import build_post_call_report

call_data = {
    "call_id": "abc123",
    "provider": "gemini",          # always "gemini" for this tester
    "model": "gemini-3.8-flash",
    "voice": "Aoede",
    "language": "en",
    "audio_mode": "normal",
    "started_at": "2024-01-15T10:30:00",
    "duration_seconds": 180,
    "transcript": [
        {"role": "agent", "text": "Hello, how can I help?", "ts": 0.0},
        {"role": "caller", "text": "I want to change my address", "ts": 3.5},
        # ... more turns
    ],
    "answers": {
        "new_address": {"value": "42 Main St", "correct": True, "expected": "42 Main St"},
    },
    "turn_metrics": [
        {"turn": 1, "latency_ms": 850},
        # ...
    ],
    "tool_calls": [],
    "usage": {"input_tokens": 1200, "output_tokens": 800},
    "human_ratings": {},           # filled by tester after the call
}

report = build_post_call_report(call_data)
print(report["overall_score"])    # e.g. 82
print(report["verdict"])          # "Good" / "Needs improvement" / "Poor"
```

### 2. Build a report with AI-written summary (async)

```python
import asyncio
from app.report_module.report_builder import build_full_post_call_report

report = asyncio.run(build_full_post_call_report(call_data))
print(report["ai_summary"]["summary_text"])
```

### 3. Export as PDF / Markdown / JSON

```python
from app.report_module.exporters.pdf import export_pdf
from app.report_module.exporters.markdown import export_markdown
from app.report_module.exporters.json_schema import export_json

pdf_bytes = export_pdf(report)           # returns bytes → write to file or send as response
md_text   = export_markdown(report)     # returns str
json_str  = export_json(report)         # returns str (validated schema)
```

---

## API endpoints (FastAPI)

The module is wired into the backend via `backend/app/routers/reports.py`.
After starting the backend (`uvicorn app.main:app`), these are available:

| Method | Path | What it does |
|--------|------|-------------|
| `GET` | `/api/sample-reports` | List available sample providers |
| `GET` | `/api/sample-reports/gemini` | Run report on dummy Gemini call |
| `POST` | `/api/calls/{call_id}/report` | Generate / regenerate report |
| `GET` | `/api/calls/{call_id}/report` | Fetch cached report (JSON) |
| `POST` | `/api/calls/{call_id}/ratings` | Save tester 1-5 human ratings |
| `GET` | `/api/calls/{call_id}/report/export?format=pdf\|md\|json` | Download export |

---

## Configuration

Edit `config.py` to change:

```python
# Scoring weights (must add up to 1.0)
SCORE_WEIGHTS = {
    "accuracy":      0.35,
    "latency":       0.20,
    "mishearings":   0.15,
    "voice_quality": 0.15,
    "language":      0.10,
    "cost":          0.05,
}

# Exchange rate for INR display
INR_PER_USD = 83.5

# Enable/disable local MOS predictor (off by default — requires extra install)
VOICE_QUALITY_CONFIG = {
    "enable_local_mos": False,
}
```

---

## Environment variables

In `backend/.env`:

```
GEMINI_API_KEY=your_key_here          # for live calls + optional AI summary
AI_SUMMARY_ENABLED=true               # set false to skip Section 10
```

**Never** put keys in report files, logs, or git.

---

## Running tests

```powershell
cd "d:\voice agent with gemini\backend"
.venv\Scripts\pytest tests/test_report_module.py -v
```

All 14 report-module tests should pass (WER/CER, mishearings, latency,
accuracy, cost, scoring, PII masking, all 4 sample fixtures).

---

## Vercel deployment notes

- **Static frontend** (`frontend/dist`) is served by Vercel CDN.
- **API routes** (`/api/*`) run as Vercel Python serverless functions via `api/index.py` + Mangum.
- **SQLite DB** is ephemeral on Vercel — data is lost between invocations.
  The report module uses sample JSON data, so it works fine.
- **WebSocket** (`/ws`) for Gemini Live **does NOT work on Vercel**.
  For live voice calls, deploy the backend on Railway / Render / Fly.io and point the frontend's `/api` and `/ws` proxy to that URL.
- Set `GEMINI_API_KEY` in Vercel → Project Settings → Environment Variables.

---

## Security

- ✅ Every report page shows **"TEST MODE — dummy data only"**
- ✅ PDF footer: "AI-assisted test report — must be reviewed by a team member before sharing outside EdZola."
- ✅ PII masking: 10-digit phone numbers and 12-digit Aadhaar-style numbers are masked before any report is generated (`security.py`)
- ✅ AI summary is clearly labelled: "AI-generated summary — review before sharing."
- ✅ API keys only from `.env`, never in reports or logs

