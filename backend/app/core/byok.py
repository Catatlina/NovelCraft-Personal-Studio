"""P2-T3 / Q5: Bring-your-own-key (BYOK) reference indirection.

Problem: the API layer read the user's provider API key from a request header
and forwarded the *plaintext* key straight into the Celery broker (Redis) via
``.delay(api_key=...)``. Anyone with broker access could read customer keys.

Fix: the API layer stores the key under a short-lived, random reference in
Redis (``nc:byok:{ref}``) and only the reference travels in the task payload.
The worker resolves the reference at execution time. On Redis failure the
helpers fail safe (empty key) so generation falls back to the server default.

Backward compatible: tasks still accept a legacy plaintext ``api_key`` argument
and use it directly when no reference is supplied (transition period).
"""
from __future__ import annotations

import os
import uuid

import redis as redis_lib

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
BYOK_PREFIX = "nc:byok:"
BYOK_TTL = int(os.getenv("BYOK_REF_TTL_SECONDS", "3600"))

_redis: "redis_lib.Redis | None" = None


def _get_redis() -> "redis_lib.Redis":
    global _redis
    if _redis is None:
        _redis = redis_lib.from_url(REDIS_URL, decode_responses=True)
    return _redis


def stash_byok_key(api_key: str) -> str:
    """Store ``api_key`` in Redis under a random ref; return the ref.

    Returns ``""`` when ``api_key`` is empty or Redis is unavailable, so the
    caller can safely pass the (empty) ref and the worker will fall back to the
    server default key.
    """
    if not api_key:
        return ""
    ref = uuid.uuid4().hex
    try:
        _get_redis().set(f"{BYOK_PREFIX}{ref}", api_key, ex=BYOK_TTL)
    except Exception:
        return ""  # fail safe: no ref → worker uses default key
    return ref


def resolve_byok_key(api_key_ref: str = "", api_key: str = "") -> str:
    """Resolve a BYOK reference to the real key, falling back to legacy input.

    Priority: reference (if present and resolvable) → legacy plaintext
    ``api_key`` (transition period) → empty string (server default).
    """
    if api_key_ref:
        try:
            key = _get_redis().get(f"{BYOK_PREFIX}{api_key_ref}")
            if key:
                return key
        except Exception:
            pass
    return api_key
