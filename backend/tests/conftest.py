"""Test configuration — reset connection pool between test files."""
import pytest
from app.db import close_pool


@pytest.fixture(autouse=True)
def _reset_db_pool():
    """Reset connection pool before each test file to prevent PoolError."""
    close_pool()
    yield
    close_pool()
