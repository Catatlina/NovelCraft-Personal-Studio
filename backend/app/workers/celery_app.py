"""Celery app — worker for async workflow execution."""
from __future__ import annotations

from celery import Celery

celery_app = Celery(
    "novelcraft",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    imports=["app.workers.tasks"],
    beat_schedule={
        "auto-serial-check": {
            "task": "app.workers.tasks.auto_serial_check",
            "schedule": 3600.0,  # Every hour
        },
        "patrol-check": {
            "task": "app.workers.tasks.patrol_check",
            "schedule": 7200.0,  # Every 2 hours
        },
    },
)
