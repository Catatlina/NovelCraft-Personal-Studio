"""M1: Three-level circuit breaker for AI provider resilience."""
from __future__ import annotations

import os
import time

import redis as redis_lib

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis: redis_lib.Redis | None = None


def _get_redis() -> redis_lib.Redis:
    global _redis
    if _redis is None:
        _redis = redis_lib.from_url(REDIS_URL, decode_responses=True)
    return _redis


BREAKER_PREFIX = "cb:"
BREAKER_THRESHOLD = 3
BREAKER_COOLDOWN = 60


def circuit_breaker(provider: str) -> bool:
    """True if provider is healthy, False if circuit is open."""
    try:
        r = _get_redis()
        key = f"{BREAKER_PREFIX}{provider}:failures"
        failures = int(r.get(key) or 0)  # type: ignore[arg-type]
        if failures >= BREAKER_THRESHOLD:
            last_fail = float(r.get(f"{BREAKER_PREFIX}{provider}:last_fail") or 0)  # type: ignore[arg-type]
            if time.time() - last_fail < BREAKER_COOLDOWN:
                return False
        return True
    except Exception:
        return True  # Redis down → allow traffic


def record_failure(provider: str) -> None:
    try:
        r = _get_redis()
        r.incr(f"{BREAKER_PREFIX}{provider}:failures")
        r.set(f"{BREAKER_PREFIX}{provider}:last_fail", int(time.time()))
    except Exception:
        pass


def record_success(provider: str) -> None:
    try:
        r = _get_redis()
        r.delete(f"{BREAKER_PREFIX}{provider}:failures", f"{BREAKER_PREFIX}{provider}:last_fail")
    except Exception:
        pass
