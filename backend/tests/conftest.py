"""Test configuration and reset connection pool."""
import os

import pytest

os.environ["NOVELCRAFT_ENV"] = "test"
os.environ["NOVELCRAFT_JWT_SECRET"] = "novelcraft-test-secret-at-least-32-characters"
# Never let a test process enqueue Celery work onto the production broker
# (Redis DB 0).  Tests may override the dedicated endpoint explicitly; otherwise
# keep the environment's Redis host (CI uses localhost, compose uses "redis")
# and only force the isolated database 15.
def _isolated_test_redis_url() -> str:
    explicit = os.getenv("NOVELCRAFT_TEST_REDIS_URL", "").strip()
    if explicit:
        return explicit
    from urllib.parse import urlsplit, urlunsplit
    parts = urlsplit(os.getenv("REDIS_URL", "redis://redis:6379/0"))
    return urlunsplit((parts.scheme, parts.netloc, "/15", parts.query, parts.fragment))


os.environ["REDIS_URL"] = _isolated_test_redis_url()

from app.db import close_pool


@pytest.fixture(scope="session", autouse=True)
def _isolated_test_redis():
    """Start and finish with an empty test-only Redis database."""
    client = None
    try:
        import redis

        client = redis.Redis.from_url(os.environ["REDIS_URL"])
        client.flushdb()
    except Exception:
        client = None
    yield
    if client is not None:
        try:
            client.flushdb()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def _reset_db_pool():
    """Reset connection pool before each test file to prevent PoolError."""
    close_pool()
    yield
    close_pool()


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    """Provider failures recorded by one test must not open the breaker for
    the next (shared Redis) — that cross-pollution failed whole test files."""
    try:
        from app.core.circuit_breaker import _get_redis, BREAKER_PREFIX

        r = _get_redis()
        keys = r.keys(f"{BREAKER_PREFIX}*")
        if keys:
            r.delete(*keys)
    except Exception:
        pass
    yield
