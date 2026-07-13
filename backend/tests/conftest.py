"""Test configuration — explicit mock boundary and reset connection pool."""
import os

import pytest

os.environ["NOVELCRAFT_ENV"] = "test"
os.environ["NOVELCRAFT_ALLOW_MOCK"] = "true"
os.environ["NOVELCRAFT_JWT_SECRET"] = "novelcraft-test-secret-at-least-32-characters"

from app.db import close_pool


@pytest.fixture(autouse=True)
def _reset_db_pool():
    """Reset connection pool before each test file to prevent PoolError."""
    close_pool()
    yield
    close_pool()
