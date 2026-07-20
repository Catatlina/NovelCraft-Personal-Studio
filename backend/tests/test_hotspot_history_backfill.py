"""NC-HM-001 T5 boundary: historical hotspot backfill from real configured archives.

The tests use a local opener stub to verify protocol, storage, and provenance.
They do not claim a real seven-day production run; real T5 still requires
authorized historical source URLs and/or long-running scheduler evidence.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class _ArchiveOpener:
    def __init__(self, seen_urls: list[str], title: str = "同一热点可跨天出现"):
        self.seen_urls = seen_urls
        self.title = title

    def open(self, req, timeout=10):
        url = req.full_url
        self.seen_urls.append(url)
        collection_date = url.rsplit("date=", 1)[-1]
        return _Response({
            "items": [
                {
                    "title": self.title,
                    "category": "tech",
                    "score": 100,
                    "url": f"https://archive.example/{collection_date}",
                }
            ]
        })


def _auth():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    token = client.post(
        "/api/v1/auth/register",
        json={"email": f"hotspot-history-{uuid.uuid4().hex[:8]}@nc.dev", "password": "test1234"},
    ).json()["data"]["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_backfill_history_uses_configured_archive_url_and_keeps_daily_provenance(monkeypatch):
    from app.db import connect
    from app.services import hotspot_collector as hc

    seen_urls: list[str] = []
    title = f"同一热点可跨天出现-{uuid.uuid4().hex[:6]}"
    monkeypatch.setattr(hc, "HOTSPOT_SOURCES", {
        "archive": {
            "name": "授权历史源",
            "history_url": "https://archive.example/hotspots?date={date}",
            "kind": "generic_json",
        }
    })
    monkeypatch.setattr(hc, "_hotspot_opener", lambda proxy_override="": _ArchiveOpener(seen_urls, title))

    result = hc.backfill_hotspot_history(days=7)

    assert result["status"] == "ok"
    assert result["fetched"] == 7
    assert result["inserted"] == 7
    assert len(result["dates_with_rows"]) == 7
    expected_dates = [(date.today() - timedelta(days=offset)).isoformat() for offset in range(6, -1, -1)]
    assert result["dates_with_rows"] == expected_dates
    assert all(f"date={day}" in url for day, url in zip(expected_dates, seen_urls))

    db = connect()
    rows = db.execute(
        """SELECT meta->>'collection_date' AS collection_date,
                  meta->>'source' AS source,
                  meta->>'collection_run_id' AS collection_run_id
           FROM knowledge_items
           WHERE kind='hotspot' AND meta->>'title'=%s
           ORDER BY collection_date ASC""",
        (title,),
    ).fetchall()
    db.close()

    assert [row["collection_date"] for row in rows[-7:]] == expected_dates
    assert {row["source"] for row in rows[-7:]} == {"archive"}
    assert len({row["collection_run_id"] for row in rows[-7:]}) == 1


def test_backfill_history_reports_unsupported_sources_without_synthetic_rows(monkeypatch):
    from app.db import connect
    from app.services import hotspot_collector as hc

    monkeypatch.setattr(hc, "HOTSPOT_SOURCES", {
        "current_only": {"name": "只有当前榜", "url": "https://current.example/list", "kind": "generic_json"}
    })

    result = hc.backfill_hotspot_history(days=7)

    assert result["status"] == "unsupported"
    assert result["fetched"] == 0
    assert result["inserted"] == 0
    assert result["unsupported_sources"] == ["current_only"]
    assert all(status["current_only"].startswith("unsupported_history") for status in result["sources"].values())

    db = connect()
    row = db.execute(
        "SELECT COUNT(*) AS c FROM knowledge_items WHERE kind='hotspot' AND meta->>'source'='current_only'"
    ).fetchone()
    db.close()
    assert row["c"] == 0


def test_history_backfill_endpoint_surfaces_unsupported_as_502(monkeypatch):
    import app.services.hotspot_collector as hc

    client, headers = _auth()
    monkeypatch.setattr(hc, "HOTSPOT_SOURCES", {
        "current_only": {"name": "只有当前榜", "url": "https://current.example/list", "kind": "generic_json"}
    })

    result = client.post("/api/v1/hotspots/history/backfill?days=7", headers=headers)

    assert result.status_code == 502
    body = result.json()["detail"]
    assert body["code"] == "HOTSPOT_HISTORY_UNSUPPORTED"
    assert body["data"]["status"] == "unsupported"


def test_history_report_endpoint_reads_stored_snapshot_counts(monkeypatch):
    from app.services import hotspot_collector as hc

    client, headers = _auth()
    seen_urls: list[str] = []
    title = f"历史报告热点-{uuid.uuid4().hex[:6]}"
    monkeypatch.setattr(hc, "HOTSPOT_SOURCES", {
        "archive": {
            "name": "授权历史源",
            "history_url": "https://archive.example/hotspots?date={date}",
            "kind": "generic_json",
        }
    })
    monkeypatch.setattr(hc, "_hotspot_opener", lambda proxy_override="": _ArchiveOpener(seen_urls, title))
    hc.backfill_hotspot_history(days=2)

    report = client.get("/api/v1/hotspots/history?days=7", headers=headers)

    assert report.status_code == 200
    data = report.json()["data"]
    assert data["total_rows"] >= 2
    assert date.today().isoformat() in data["dates"]
