"""
V7 Test Configuration
=====================

V7 models use PostgreSQL-specific column types (``JSONB`` / ``UUID``) and every
repository method is ``async`` (``AsyncSession``). The suite therefore MUST run
against a real PostgreSQL instance — SQLite cannot compile those types and a
sync ``Session`` cannot drive the repositories.

Set ``DATABASE_URL`` (or ``V7_TEST_DATABASE_URL`` to override) to a PostgreSQL
DSN before running. CI already provides ``DATABASE_URL``.

Isolation strategy: each test runs inside an outer transaction on a dedicated
connection and is rolled back afterwards, so tests never leak data into the
database even when the code under test calls ``commit()``.
"""
from __future__ import annotations

import os
import uuid as _uuid

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

_RAW_URL = os.getenv("V7_TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or ""
TEST_DB_URL = _RAW_URL
ASYNC_TEST_DB_URL = (
    _RAW_URL.replace("postgresql://", "postgresql+asyncpg://")
    if _RAW_URL.startswith("postgresql://")
    else _RAW_URL
)

_SKIP_REASON = (
    "V7 tests require PostgreSQL (JSONB/UUID column types). "
    "Set DATABASE_URL or V7_TEST_DATABASE_URL."
)


def _require_pg() -> None:
    if not TEST_DB_URL.startswith("postgresql"):
        pytest.skip(_SKIP_REASON)


def _import_all_models():
    from app.v7.models.base import Base
    from app.v7.models import (  # noqa: F401 - import all models for metadata
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

    return Base


@pytest.fixture(scope="session")
def _schema_ready() -> bool:
    """Ensure all V7 tables exist (no-op when alembic already created them)."""
    _require_pg()
    base = _import_all_models()
    sync_engine = create_engine(TEST_DB_URL, echo=False, future=True)
    base.metadata.create_all(bind=sync_engine, checkfirst=True)
    sync_engine.dispose()
    return True


@pytest_asyncio.fixture
async def async_engine(_schema_ready):
    """Per-test async engine (avoids cross-event-loop pool reuse)."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False, poolclass=None)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncSession:
    """Transaction-isolated async session; everything is rolled back."""
    async with async_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()


@pytest.fixture
def novel_id() -> _uuid.UUID:
    """Unique test novel ID (avoids cross-test interference).

    ``NovelScopedMixin.novel_id`` is a PostgreSQL ``UUID`` column, so this must
    be a real ``uuid.UUID`` — a slug string like ``"test-novel-ab12"`` makes
    asyncpg reject every INSERT.
    """
    return _uuid.uuid4()
