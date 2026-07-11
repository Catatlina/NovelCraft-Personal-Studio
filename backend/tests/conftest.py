"""Test configuration — explicit mock boundary and reset connection pool."""
import os

import pytest
from app.db import close_pool

os.environ["NOVELCRAFT_ENV"] = "test"
os.environ["NOVELCRAFT_ALLOW_MOCK"] = "true"


@pytest.fixture(autouse=True)
def _reset_db_pool():
    """Reset connection pool before each test file to prevent PoolError."""
    close_pool()
    yield
    close_pool()
