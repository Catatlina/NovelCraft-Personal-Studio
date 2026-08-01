"""
V7 Database Session Manager — SQLAlchemy
=========================================

V7 uses SQLAlchemy ORM, separate from V6's psycopg2 raw connections.
Both can coexist because V7 tables use v7_ prefix.

Reuses DATABASE_URL from V6 environment.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Reuse V6's DATABASE_URL
DB_URL = os.getenv("DATABASE_URL", "postgresql://genius@localhost/novelcraft_dev")

# Create engine
engine = create_engine(
    DB_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: get database session.

    Usage:
        @app.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for database sessions.

    Usage:
        with session_scope() as db:
            db.add(...)
            # auto-commit on success, auto-rollback on error
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_v7_db() -> None:
    """Initialize V7 database tables.

    Note: In production, use Alembic migrations instead.
    This is for development/testing convenience.
    """
    from .models.base import Base
    from .models import (  # noqa: F401 - import all models to register them
        version,
        state,
        goal,
        constraint,
        decision,
        human,
        plot,
        trace,
        prompt,
        cost,
        event,
        seed,
    )

    Base.metadata.create_all(bind=engine)
