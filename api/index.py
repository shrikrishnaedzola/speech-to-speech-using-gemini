"""
Vercel serverless entry-point — Zolabs Voice Form Tester (Gemini).

Vercel routes every /api/* request here (see vercel.json).
Mangum adapts FastAPI (ASGI) to the serverless request/response format.

IMPORTANT NOTES FOR VERCEL DEPLOYMENT:
  • SQLite files are NOT persisted between serverless invocations.
    The post-call report module uses sample JSON data so it works fine.
    Live call DB data needs a persistent server (Railway / Render / Fly.io).
  • Set GEMINI_API_KEY in the Vercel dashboard → Settings → Environment Variables.
    Never put it in this file or commit it to git.
  • The /ws WebSocket endpoint for Gemini Live will NOT work on Vercel
    (Vercel serverless does not support persistent WebSocket connections).
    For live voice calls, run the backend on a persistent server.
"""

import sys
import os

# Make the backend package importable from this api/ directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from mangum import Mangum          # noqa: E402 (import after sys.path patch)
from app.main import app           # noqa: E402

# handler is what Vercel calls for each incoming request.
handler = Mangum(app, lifespan="off")

