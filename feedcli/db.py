"""SQLAlchemy engine and session factory."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from feedcli.config import load_config
from feedcli.models import Base

_engine = None
_SessionFactory = None


def get_engine(db_path: str | None = None):
    """Get or create the SQLAlchemy engine."""
    global _engine
    if _engine is None or db_path is not None:
        if db_path is None:
            db_path = load_config()["db_path"]
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(_engine)
    return _engine


def get_session(db_path: str | None = None) -> Session:
    """Create a new session."""
    global _SessionFactory
    engine = get_engine(db_path)
    if _SessionFactory is None or db_path is not None:
        _SessionFactory = sessionmaker(bind=engine)
    return _SessionFactory()


def reset_engine():
    """Reset the global engine (for testing)."""
    global _engine, _SessionFactory
    _engine = None
    _SessionFactory = None
