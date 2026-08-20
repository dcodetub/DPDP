"""
database.py
-----------
SQLAlchemy engine, session factory, and base declarative class.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

try:
    from app.config import settings
except ModuleNotFoundError:
    from config import settings

# `check_same_thread` is only needed for SQLite (used in local dev / tests).
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and ensures it's closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Called once at application startup."""
    try:
        from app import models  # noqa: F401 — ensures models are registered on Base
    except ModuleNotFoundError:
        import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
