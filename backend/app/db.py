"""SQLite database setup (SQLAlchemy)."""

import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

actual_db_url = DATABASE_URL
if actual_db_url.startswith("sqlite:///"):
    raw_path = actual_db_url.removeprefix("sqlite:///")
    try:
        Path(raw_path).parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Fallback to system temp directory (writable on Vercel / serverless)
        tmp_db = Path(tempfile.gettempdir()) / "tester.db"
        actual_db_url = f"sqlite:///{tmp_db}"

# check_same_thread=False lets FastAPI threads and the Gemini session task share SQLite.
engine = create_engine(actual_db_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: one DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401  (registers the tables)

    Base.metadata.create_all(engine)
