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
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Reuse V6's DATABASE_URL
DB_URL = os.getenv("DATABASE_URL", "postgresql://genius@localhost/novelcraft_dev")

# Convert to async URL if needed
ASYNC_DB_URL = DB_URL.replace("postgresql://", "postgresql+asyncpg://") if DB_URL.startswith("postgresql://") else DB_URL

# Create sync engine
engine = create_engine(
    DB_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

# Create async engine
async_engine = create_async_engine(
    ASYNC_DB_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

# Sync session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: get sync database session.

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


async def get_async_db() -> AsyncSession:
    """FastAPI dependency: get async database session.

    Usage:
        @app.get("/items")
        async def list_items(db: AsyncSession = Depends(get_async_db)):
            ...
    
    Auto-commits on success, auto-rollbacks on error.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


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
    # Keep local development databases aligned with the Alembic migration even
    # when the caller uses the convenience initializer instead of ``alembic``.
    from ..services.ai_runtime import SHARED_LEDGER_DDL
    with engine.begin() as connection:
        # The shared DDL contains several PostgreSQL statements; execute it as
        # driver SQL so SQLAlchemy does not treat the semicolons as one text
        # clause with ambiguous bind parsing.
        connection.exec_driver_sql(SHARED_LEDGER_DDL)
