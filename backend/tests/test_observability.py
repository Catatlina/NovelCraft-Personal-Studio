"""Stage-3 ②: monitoring & alerting — daily cost report, queue-backlog patrol,
batch failure alerts, and opt-in Sentry//metrics wiring."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_daily_cost_report_aggregates_last_24h(monkeypatch):
    from app.core import alerts
    from app.db import connect, encode, new_id
    from app.workers.tasks import daily_cost_report

    marker_task = f"obs-{uuid.uuid4().hex[:8]}"
    db = connect()
    db.execute(
        """INSERT INTO ai_calls (id, provider, model, prompt_name, task_type, input, output,
               prompt_tokens, completion_tokens, cost_cny, latency_ms, status)
           VALUES (%s,'deepseek','deepseek-chat','t','%s',%s,%s, 100, 50, 0.01, 900, 'succeeded')""".replace("'%s'", "%s"),
        (new_id("call"), marker_task, encode({}), encode({"text": "x"})),
    )
    db.commit()
    db.close()

    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(alerts, "send_alert", lambda message, level="warning": sent.append((message, level)) or True)
    # daily_cost_report 里是延迟导入 from app.core.alerts import send_alert
    result = daily_cost_report.run()
    assert result["calls"] >= 1
    assert result["tokens"] >= 150
    assert sent and sent[0][1] == "info"
    assert "成本日报" in sent[0][0]


def test_queue_backlog_detection(monkeypatch):
    import redis as redis_lib

    from app.workers.tasks import check_queue_backlog

    class FakeRedis:
        def __init__(self, depth): self.depth = depth
        def llen(self, _key): return self.depth

    monkeypatch.setattr(redis_lib, "from_url", lambda _url: FakeRedis(404))
    message = check_queue_backlog(threshold=50)
    assert message and "404" in message

    monkeypatch.setattr(redis_lib, "from_url", lambda _url: FakeRedis(3))
    assert check_queue_backlog(threshold=50) is None


def test_queue_backlog_silent_when_redis_down(monkeypatch):
    import redis as redis_lib

    from app.workers.tasks import check_queue_backlog

    def boom(_url):
        raise OSError("redis down")

    monkeypatch.setattr(redis_lib, "from_url", boom)
    assert check_queue_backlog(threshold=50) is None


def test_batch_failure_paths_send_alerts():
    source = (ROOT / "backend/app/workers/tasks.py").read_text(encoding="utf-8")
    assert "pending_provider：" in source and "批次" in source  # alert on provider wait
    assert "失败：" in source  # alert on hard failure


def test_sentry_is_optin_and_scrubbed(monkeypatch):
    from app.core.observability import init_sentry

    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert init_sentry("fastapi") is False  # 无 DSN 完全不启用

    source = (ROOT / "backend/app/core/observability.py").read_text(encoding="utf-8")
    assert "send_default_pii=False" in source
    assert "include_local_variables=False" in source  # 章节正文/凭据不出境


def test_metrics_endpoint_exposed():
    from fastapi.testclient import TestClient

    from app.main import app

    response = TestClient(app).get("/metrics")
    assert response.status_code == 200
    assert "http_request" in response.text  # prometheus 指标族存在


def test_beat_schedule_has_cost_report():
    from app.workers.celery_app import celery_app

    assert "daily-cost-report" in celery_app.conf.beat_schedule
