"""Provider-call retry with decoupled backoff policies (P1-T1).

Two independent backoff policies, both without external dependencies
(``tenacity`` is intentionally not used):

* ``RATE_LIMIT_POLICY``  — for HTTP 429 (ProviderRateLimitError):
  base=1s, factor=2, cap=30s, max_retries=3.
* ``TRANSPORT_POLICY``   — for transport / network / 5xx (ProviderError):
  base=0.5s, cap=10s, max_retries=3.

``with_provider_retry`` wraps a callable and retries only on the configured
exception types. Crucially, the optional ``on_final_failure`` callback fires
ONLY after every retry is exhausted — so transient provider blips never trip
the circuit breaker prematurely (the breaker is incremented solely on terminal
failure). This is what keeps retry and ``circuit_breaker`` cooperating.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

T = TypeVar("T")


class RetryPolicy:
    """Exponential backoff policy with a hard ceiling."""

    def __init__(
        self,
        *,
        base: float = 1.0,
        factor: float = 2.0,
        cap: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.base = base
        self.factor = factor
        self.cap = cap
        self.max_retries = max_retries

    def backoff_seconds(self, attempt: int) -> float:
        """Seconds to wait before ``attempt`` (1-based) given the policy ceiling."""
        return min(self.cap, self.base * (self.factor ** max(0, attempt - 1)))


# Policy presets (P1-T1 decision).
RATE_LIMIT_POLICY = RetryPolicy(base=1.0, factor=2.0, cap=30.0, max_retries=3)
TRANSPORT_POLICY = RetryPolicy(base=0.5, factor=2.0, cap=10.0, max_retries=3)


def with_provider_retry(
    *,
    rate_limit_exc: tuple[type[BaseException], ...] = (),
    transport_exc: tuple[type[BaseException], ...] = (),
    no_retry_exc: tuple[type[BaseException], ...] = (),
    rate_limit_policy: RetryPolicy = RATE_LIMIT_POLICY,
    transport_policy: RetryPolicy = TRANSPORT_POLICY,
    sleep: Callable[[float], None] = time.sleep,
    on_final_failure: Callable[[Exception], None] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorate a callable so transport/429 failures retry with backoff.

    Exception routing:
      * ``rate_limit_exc``  -> ``rate_limit_policy`` (HTTP 429).
      * ``transport_exc``   -> ``transport_policy`` (network / 5xx / ProviderError).
      * ``no_retry_exc``    -> re-raised immediately (e.g. OutputValidationError,
        which is a schema-contract concern handled by the caller's own retry).

    ``on_final_failure`` (if given) is invoked exactly once, with the last
    exception, when retries are exhausted and before the exception is re-raised.
    """
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            policy: RetryPolicy | None = None
            attempt = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except BaseException as exc:  # noqa: BLE001 - intentional catch-all
                    if isinstance(exc, no_retry_exc):
                        raise
                    if isinstance(exc, rate_limit_exc):
                        policy = rate_limit_policy
                    elif isinstance(exc, transport_exc):
                        policy = transport_policy
                    else:
                        raise
                    attempt += 1
                    if attempt > policy.max_retries:
                        if on_final_failure is not None:
                            on_final_failure(exc)
                        raise
                    sleep(policy.backoff_seconds(attempt))
        return wrapper
    return decorator
