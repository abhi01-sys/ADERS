"""
database/db.py
──────────────
Creates the SQLAlchemy engine and session factory.
Every other file imports `SessionLocal` and `engine` from here.
"""

from pathlib import Path
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Load DB URL from config.yaml
ROOT = Path(__file__).resolve().parent.parent
_cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
DATABASE_URL = _cfg["database"]["url"]

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + FastAPI
    echo=False,
)

# Enable WAL journal mode for safe concurrent multi-thread writes (P1-7 fix)
with engine.connect() as _conn:
    _conn.execute(__import__("sqlalchemy").text("PRAGMA journal_mode=WAL"))
    _conn.commit()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    """FastAPI dependency — yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

