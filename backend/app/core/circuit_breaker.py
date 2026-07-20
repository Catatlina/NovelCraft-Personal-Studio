"""M1: Three-state circuit breaker + per-provider token bucket (P2-T9 / Q5).

The original breaker was global per provider and had no half-open state, so a
single tenant's 429 storm would fuse the *entire* site for the full cooldown.

This rewrite adds:
  * **State machine** CLOSED → OPEN → HALF_OPEN → CLOSED. After the cooldown
    expires the breaker admits a few probe requests (HALF_OPEN); a probe success
    closes it, a probe failure re-opens it.
  * **Scope dimension** (default ``"global"``, or a ``project_id``) so failures
    are attributed per-tenant / per-queue instead of globally.
  * **Token bucket** (``acquire_provider_token``) that rate-limits outbound
    provider calls per provider + scope (e.g. N tokens / second) to avoid
    overwhelming DeepSeek during batch fan-out.

All Redis access is best-effort: if Redis is unavailable the breaker fails OPEN
(allow traffic) and the token bucket fails OPEN (allow), so the system degrades
gracefully instead of locking users out.

Public function signatures keep their original arity for backward compatibility;
the new ``scope`` argument defaults to ``"global"``.
"""
from __future__ import annotations

import json
import os
import time

import redis as redis_lib

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis: "redis_lib.Redis | None" = None


def _get_redis() -> "redis_lib.Redis":
    global _redis
    if _redis is None:
        _redis = redis_lib.from_url(REDIS_URL, decode_responses=True)
    return _redis


# ── Tunables ────────────────────────────────────────────────────────────────
BREAKER_PREFIX = "cb:"
THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "3"))
COOLDOWN = int(os.getenv("CB_COOLDOWN_SECONDS", "60"))
HALF_OPEN_PROBES = int(os.getenv("CB_HALF_OPEN_PROBES", "2"))

TOKEN_PREFIX = "pt:"
DEFAULT_TOKEN_RATE = int(os.getenv("PROVIDER_TOKEN_RATE", "8"))  # tokens / second
TOKEN_WINDOW = 1  # seconds (fixed window)


def _breaker_key(provider: str, scope: str) -> str:
    return f"{BREAKER_PREFIX}{provider}:{scope or 'global'}"


def _load_state(key: str) -> dict:
    try:
        raw = _get_redis().get(key)
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _save_state(key: str, state: dict) -> None:
    try:
        _get_redis().set(key, json.dumps(state), ex=max(COOLDOWN * 2, 300))
    except Exception:
        pass


def circuit_breaker(provider: str, scope: str = "global") -> bool:
    """Return ``True`` if traffic to ``provider`` (within ``scope``) is allowed.

    Implements CLOSED → OPEN → HALF_OPEN → CLOSED with cooldown-based half-open
    probing. Returns ``True`` (allow) on any Redis error (fail-open).
    """
    key = _breaker_key(provider, scope)
    try:
        state = _load_state(key)
        if not state:
            return True  # CLOSED by default
        now = time.time()
        if state.get("state") == "open":
            if now - float(state.get("opened_at", 0)) >= COOLDOWN:
                # Cooldown elapsed → enter HALF_OPEN for a limited number of probes.
                state["state"] = "half_open"
                state["probes"] = 0
                _save_state(key, state)
                return True
            return False
        if state.get("state") == "half_open":
            if int(state.get("probes", 0)) < HALF_OPEN_PROBES:
                state["probes"] = int(state.get("probes", 0)) + 1
                _save_state(key, state)
                return True
            # Probes exhausted without resolution → re-open and cool down again.
            state = {"state": "open", "failures": THRESHOLD,
                     "opened_at": now, "probes": 0}
            _save_state(key, state)
            return False
        return True  # CLOSED
    except Exception:
        return True


def record_failure(provider: str, scope: str = "global") -> None:
    """Record a terminal provider failure; trip the breaker at threshold."""
    key = _breaker_key(provider, scope)
    try:
        state = _load_state(key)
        if state.get("state") == "half_open":
            # A failure during half-open → reopen fully.
            _save_state(key, {"state": "open", "failures": THRESHOLD,
                             "opened_at": time.time(), "probes": 0})
            return
        failures = int(state.get("failures", 0)) + 1
        if failures >= THRESHOLD:
            _save_state(key, {"state": "open", "failures": failures,
                              "opened_at": time.time(), "probes": 0})
        else:
            _save_state(key, {"state": "closed", "failures": failures, "probes": 0})
    except Exception:
        pass


def record_success(provider: str, scope: str = "global") -> None:
    """Record a success; closes the breaker if it was half-open."""
    key = _breaker_key(provider, scope)
    try:
        state = _load_state(key)
        if not state:
            return
        if state.get("state") == "half_open":
            # Probe succeeded → fully close.
            _save_state(key, {"state": "closed", "failures": 0, "probes": 0})
            return
        # CLOSED: reset failure counter.
        _save_state(key, {"state": "closed", "failures": 0, "probes": 0})
    except Exception:
        pass


def acquire_provider_token(provider: str, scope: str = "global",
                           max_rate: int | None = None, timeout: float = 0) -> bool:
    """Acquire one token from the per-provider, per-scope bucket.

    Uses a fixed 1-second window. Returns ``True`` if a token was granted (or
    Redis is unavailable — fail-open). Returns ``False`` if the rate limit is
    exceeded.

    Args:
        provider: Provider name (e.g. ``"deepseek"``).
        scope: Tenant / queue scope (default ``"global"``).
        max_rate: Override for the tokens-per-second limit.
        timeout: Accepted for API compatibility (best-effort backoff is provided
            by the retry callers).
    """
    rate = max_rate if max_rate is not None else DEFAULT_TOKEN_RATE
    if rate <= 0:
        return True
    key = f"{TOKEN_PREFIX}{provider}:{scope or 'global'}"
    try:
        r = _get_redis()
        n = r.incr(key)
        if n == 1:
            r.expire(key, TOKEN_WINDOW)
        return n <= rate
    except Exception:
        return True  # fail-open
