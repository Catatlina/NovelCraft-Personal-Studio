"""Logging configuration — structured JSON logging for production."""
from __future__ import annotations

import logging
import os
import re
import sys

LOG_LEVEL = os.getenv("NOVELCRAFT_LOG_LEVEL", "INFO")

# P2-T8 / G9: never let secrets/keys land in logs. Redact value positions for
# known secret key names (api_key, token, secret, password, bearer, ...).
_SECRET_KEY_RE = re.compile(
    r"(?i)(api[_-]?key|apikey|secret|token|passwd|password|access[_-]?token|"
    r"refresh[_-]?token|authorization|client[_-]?secret|app[_-]?secret|"
    r"private[_-]?key|cookie|nc_token|nc_api_key)\s*[:=]\s*['\"]?[^\s'\",}]{3,}",
    re.IGNORECASE,
)


def _redact(text: str) -> str:
    if not isinstance(text, str):
        return text
    return _SECRET_KEY_RE.sub(lambda m: f"{m.group(1)}=***REDACTED***", text)


class SecretRedactingFilter(logging.Filter):
    """Strip secret values from log messages and their %-format args."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact(record.msg)
        if record.args:
            try:
                formatted = record.msg % record.args
                record.msg = _redact(formatted)
                record.args = ()
            except Exception:
                record.msg = _redact(str(record.msg))
        return True


def setup_logging() -> None:
    """Configure root logger with JSON format in production, plain text in dev."""
    handler = logging.StreamHandler(sys.stderr)
    if os.getenv("NOVELCRAFT_ENV", "").startswith("dev"):
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    else:
        handler.setFormatter(logging.Formatter('{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'))
    handler.addFilter(SecretRedactingFilter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    root.handlers = [handler]

    # Silence noisy libs
    logging.getLogger("celery").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
