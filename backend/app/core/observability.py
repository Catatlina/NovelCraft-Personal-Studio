"""Optional observability: Sentry error tracking + Prometheus /metrics.

Both are opt-in via environment so a bare personal deployment carries zero
external dependencies: set SENTRY_DSN to enable error tracking; /metrics is
disabled by default and must also be protected by METRICS_TOKEN."""
from __future__ import annotations

import os


def init_sentry(integration: str) -> bool:
    """integration: 'fastapi' | 'celery'. Returns True when Sentry is active."""
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("NOVELCRAFT_ENV", "development"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0")),
        # 不上传本地变量，避免章节正文/凭据进入第三方
        include_local_variables=False,
        send_default_pii=False,
    )
    return True


def init_metrics(app) -> bool:
    if os.getenv("METRICS_ENABLED", "false").lower() != "true":
        return False
    if not os.getenv("METRICS_TOKEN", "").strip():
        raise RuntimeError("METRICS_TOKEN is required when METRICS_ENABLED=true")
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator(excluded_handlers=["/metrics", "/api/v1/healthz"]).instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )
    return True
