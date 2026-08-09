"""P2-T3 / Q5: Bring-your-own-key (BYOK) reference indirection.

Problem: the API layer read the user's provider API key from a request header
and forwarded the *plaintext* key straight into the Celery broker (Redis) via
``.delay(api_key=...)``. Anyone with broker access could read customer keys.

Fix: the API layer stores the key under a short-lived, random reference in
Redis (``nc:byok:{ref}``) and only the reference travels in the task payload.
The worker resolves the reference at execution time. Redis failure is now a
hard error: a request-scoped key must never silently become the server key.

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


class BYOKUnavailableError(RuntimeError):
    """The request-scoped key cannot be safely stored or resolved."""


def _get_redis() -> "redis_lib.Redis":
    global _redis
    if _redis is None:
        _redis = redis_lib.from_url(REDIS_URL, decode_responses=True)
    return _redis


def stash_byok_key(api_key: str) -> str:
    """Store ``api_key`` in Redis under a random ref; return the ref.

    Returns ``""`` only when no request-scoped key was supplied. If Redis is
    unavailable, fail explicitly so the caller cannot fall back to another
    tenant's/server key.
    """
    if not api_key:
        return ""
    ref = uuid.uuid4().hex
    try:
        stored = _get_redis().set(f"{BYOK_PREFIX}{ref}", api_key, ex=BYOK_TTL)
        if not stored:
            raise BYOKUnavailableError("BYOK reference was not stored")
    except BYOKUnavailableError:
        raise
    except Exception as exc:
        raise BYOKUnavailableError("BYOK storage is unavailable") from exc
    return ref


def resolve_byok_key(api_key_ref: str = "", api_key: str = "") -> str:
    """Resolve a BYOK reference to the real key, falling back to legacy input.

    A reference is authoritative. A missing/expired reference is an error,
    not permission to use the server default. The legacy plaintext argument is
    accepted only for explicitly direct worker calls during the transition.
    """
    if api_key_ref:
        try:
            key = _get_redis().get(f"{BYOK_PREFIX}{api_key_ref}")
        except Exception as exc:
            raise BYOKUnavailableError("BYOK storage is unavailable") from exc
        if not key:
            raise BYOKUnavailableError("BYOK reference is missing or expired")
        return key
    return api_key
