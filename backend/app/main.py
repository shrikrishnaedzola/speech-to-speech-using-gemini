"""FastAPI app entry point.

Run (from the backend folder):
    .venv\\Scripts\\python -m uvicorn app.main:app --reload --port 8020
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import CORS_ORIGINS, has_api_key
from app.db import SessionLocal, init_db
from app.routers import calls, forms, reports, session, tools
from app.services.forms_loader import load_seed_forms
from app.services.gemini_live import end_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        with SessionLocal() as db:
            count = load_seed_forms(db)
        logger.info(f"Loaded {count} form(s) from seed_forms/")
    except Exception as e:
        logger.error(f"Error during DB initialization: {e}")

    if not has_api_key():
        logger.warning("GEMINI_API_KEY is not set: live calls are disabled, Simulate mode still works.")
    yield
    try:
        await end_all()
    except Exception:
        pass


app = FastAPI(title="Zolabs Voice Form Tester - Gemini 3.8 Live", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

for module in (forms, session, tools, calls, reports):
    app.include_router(module.router)



@app.get("/api/health")
def health():
    return {"ok": True, "api_key_configured": has_api_key()}
