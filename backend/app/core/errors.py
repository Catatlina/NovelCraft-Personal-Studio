"""Safe public error messaging — never echo internal details (paths/stacks/secrets) to clients.

P2-T8 / G9: 对外错误不回显内部细节。All user-facing error envelopes should call
``public_message(exc)`` so the real exception is logged server-side (with a trace id
for support) while the client only receives a generic, safe message.
"""
from __future__ import annotations

import logging
import uuid

_logger = logging.getLogger("app.errors")


def public_message(exc: Exception, fallback: str = "服务处理异常，请稍后重试") -> str:
    """Log the real exception server-side with a trace id; return a safe, generic client message."""
    trace_id = uuid.uuid4().hex[:12]
    _logger.warning("public_error trace=%s type=%s msg=%s", trace_id, type(exc).__name__, exc)
    return f"{fallback}（追踪码 {trace_id}）"
