"""Distributed lock — Redis-based mutex for task idempotency."""
from __future__ import annotations

import os
import time

import redis as redis_lib

from .celery_app import celery_app

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _get_redis():
    return redis_lib.from_url(REDIS_URL)


def acquire_lock(lock_key: str, ttl: int = 300) -> bool:
    """Try to acquire a distributed lock. Returns True if acquired.

    P2-T4 / Q10: fail-closed. If Redis is unavailable we MUST NOT grant the
    lock, otherwise mutual exclusion is lost and concurrent tasks can corrupt
    shared state (e.g. two generations writing the same chapter slot). Callers
    treat a ``False`` return as "queue / skip / retry later".
    """
    try:
        r = _get_redis()
        return bool(r.set(lock_key, "1", nx=True, ex=ttl))
    except Exception:
        return False  # fail-closed: deny the lock when the store is unreachable


def release_lock(lock_key: str) -> None:
    try:
        r = _get_redis()
        r.delete(lock_key)
    except Exception:
        pass
