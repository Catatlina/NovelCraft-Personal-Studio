"""Rate limiting configuration for public and cost-sensitive endpoints."""
from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.extension import _rate_limit_exceeded_handler


def _key_func(request):
    user = getattr(request.state, "user", None)
    if isinstance(user, dict) and user.get("id"):
        return f"user:{user['id']}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=_key_func,
    default_limits=[os.getenv("NOVELCRAFT_DEFAULT_RATE_LIMIT", "120/minute")],
)


def install_rate_limiter(app) -> None:
    app.state.limiter = limiter
    if os.getenv("NOVELCRAFT_DISABLE_RATE_LIMIT", "").lower() in {"1", "true", "yes"}:
        return
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
