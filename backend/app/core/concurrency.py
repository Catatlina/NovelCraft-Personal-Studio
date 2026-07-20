"""P2-T5 / Q11: Global AI concurrency semaphore (Redis-backed).

A single 50-chapter batch (or an auto-serial burst) must not monopolise the
provider or overwhelm DeepSeek. This module provides a process-agnostic counter
that caps the number of provider calls *in flight* across all Celery workers.

The counter is best-effort: if Redis is unavailable the semaphore fails OPEN
(allows the call) so a Redis outage never hard-stops generation — it merely
loses the concurrency guard.
"""
from __future__ import annotations

import os

import redis as redis_lib

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
AI_SEMAPHORE_KEY = "nc:ai_semaphore"
AI_SEMAPHORE_LIMIT = int(os.getenv("AI_CONCURRENCY_LIMIT", "8"))

_redis: "redis_lib.Redis | None" = None


def _get_redis() -> "redis_lib.Redis":
    global _redis
    if _redis is None:
        _redis = redis_lib.from_url(REDIS_URL, decode_responses=True)
    return _redis


def acquire_ai_slot(timeout: float = 5.0) -> bool:
    """Attempt to take one global AI slot.

    Returns ``True`` if a slot was acquired (caller must ``release_ai_slot``
    afterwards), or ``False`` if the global limit is reached. Fails OPEN (True)
    when Redis is unavailable.

    The ``timeout`` argument is accepted for API compatibility; the fixed-window
    counter already provides implicit backoff for callers that retry.
    """
    try:
        r = _get_redis()
        n = r.incr(AI_SEMAPHORE_KEY)
        if n == 1:
            # Keep the key alive long enough to cover any single generation.
            r.expire(AI_SEMAPHORE_KEY, 3600)
        if n > AI_SEMAPHORE_LIMIT:
            # Over the limit: roll the counter back so we don't leak slots.
            r.decr(AI_SEMAPHORE_KEY)
            return False
        return True
    except Exception:
        return True  # fail-open


def release_ai_slot() -> None:
    """Release a previously acquired AI slot."""
    try:
        r = _get_redis()
        cur = r.decr(AI_SEMAPHORE_KEY)
        if cur is not None and cur < 0:
            r.set(AI_SEMAPHORE_KEY, 0)
    except Exception:
        pass
