"""Logging configuration — structured JSON logging for production."""
from __future__ import annotations

import logging
import os
import sys

LOG_LEVEL = os.getenv("NOVELCRAFT_LOG_LEVEL", "INFO")


def setup_logging() -> None:
    """Configure root logger with JSON format in production, plain text in dev."""
    handler = logging.StreamHandler(sys.stderr)
    if os.getenv("NOVELCRAFT_ENV", "").startswith("dev"):
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    else:
        handler.setFormatter(logging.Formatter('{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'))

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    root.handlers = [handler]

    # Silence noisy libs
    logging.getLogger("celery").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
