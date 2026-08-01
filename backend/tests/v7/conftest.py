"""
V7 Test Configuration
=====================

Uses SQLite in-memory database for fast unit tests.
SQLAlchemy makes this easy - just change the connection string.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Use SQLite in-memory for tests
TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    """Create test engine."""
    from app.v7.models.base import Base
    from app.v7.models import (  # noqa: F401 - import all models
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

    engine = create_engine(TEST_DB_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session(engine) -> Session:
    """Get a database session for testing."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def novel_id() -> str:
    """Test novel ID."""
    return "test-novel-001"
