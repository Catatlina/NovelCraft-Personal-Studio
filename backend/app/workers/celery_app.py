"""Celery app — worker for async workflow execution."""
from __future__ import annotations

import os

from celery import Celery

from app.core.observability import init_sentry

init_sentry("celery")

celery_app = Celery(
    "novelcraft",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0").replace("/0", "/1"),
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
    imports=["app.workers.tasks", "app.workers.m3_tasks", "app.workers.m4_tasks"],
    beat_schedule={
        "auto-serial-check": {
            "task": "app.workers.tasks.auto_serial_check",
            "schedule": 3600.0,  # Every hour
        },
        "patrol-check": {
            "task": "app.workers.tasks.patrol_check",
            "schedule": 7200.0,  # Every 2 hours
        },
        "purge-stale-autosaves": {
            "task": "app.workers.tasks.purge_stale_autosaves",
            "schedule": 86400.0,  # Daily — C5-05 7-day retention
        },
        "daily-cost-report": {
            "task": "app.workers.tasks.daily_cost_report",
            "schedule": 86400.0,  # Daily — AI 用量/成本日报（Telegram）
        },
        "purge-stale-operational-data": {
            "task": "app.workers.tasks.purge_stale_operational_data",
            "schedule": 86400.0,
        },
    },
)
