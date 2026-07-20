"""Product API for visible-browser/OCR ranking capture artifacts.

These tests keep the automation boundary honest: browser/OCR artifacts are
imported automatically when evidence is good enough; low-confidence OCR needs an
editor confirmation; challenge pages become evidence-bearing failures.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _auth_project():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    token = client.post(
        "/api/v1/auth/register",
        json={"email": f"ranking-capture-{uuid.uuid4().hex[:8]}@nc.dev", "password": "test1234"},
    ).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return client, headers, project_id


def test_capture_import_route_is_registered():
    from app.main import app

    routes = {(path, method.upper()) for path, operations in app.openapi()["paths"].items() for method in operations}
    assert ("/api/v1/ranking/capture-import", "POST") in routes
    assert ("/api/v1/ranking/snapshots/{snapshot_id}/confirm-capture", "POST") in routes


def test_fanqie_ocr_low_confidence_import_requires_review_then_can_be_confirmed():
    client, headers, project_id = _auth_project()
    payload = {
        "source": "fanqie",
        "status": "succeeded",
        "collector": "browser_ocr",
        "captured_at": "2026-07-14T10:00:00Z",
        "source_url": "https://fanqienovel.com/rank/all",
        "evidence": {"screenshot": "fanqie-rank.png", "ocr_engine": "paddleocr"},
        "items": [
            {
                "rank": 1,
                "title": "雾城修理铺",
                "author": "测试作者",
                "category": "科幻",
                "confidence": 0.72,
                "evidence": {"bbox": [10, 20, 200, 60]},
            },
            {
                "rank": 2,
                "title": "星海旧账",
                "author": "作者乙",
                "category": "科幻",
                "confidence": 0.94,
            },
        ],
    }

    imported = client.post(
        f"/api/v1/ranking/capture-import?project_id={project_id}",
        headers=headers,
        json=payload,
    )

    assert imported.status_code == 200
    data = imported.json()["data"]
    assert data["source"] == "fanqie"
    assert data["item_count"] == 2
    assert data["capture_status"] == "needs_review"
    snapshot_id = data["snapshot_id"]

    blocked = client.post(f"/api/v1/ranking/snapshots/{snapshot_id}/analyze", headers=headers, json={})
    assert blocked.status_code == 409
    assert "requires review" in str(blocked.json())

    confirmed = client.post(f"/api/v1/ranking/snapshots/{snapshot_id}/confirm-capture", headers=headers)
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["capture_status"] == "succeeded"

    detail = client.get(f"/api/v1/ranking/snapshots/{snapshot_id}", headers=headers)
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["capture_status"] == "succeeded"
    assert detail_data["items"][0]["metrics"]["collector"] == "browser_ocr"
    assert detail_data["items"][0]["metrics"]["evidence"]["screenshot"] == "fanqie-rank.png"


def test_qidian_challenge_capture_import_records_failure_not_empty_success():
    client, headers, project_id = _auth_project()
    payload = {
        "source": "qidian",
        "status": "user_action_required",
        "collector": "visible_browser",
        "source_url": "https://www.qidian.com/rank/",
        "evidence": {"screenshot": "qidian-challenge.png"},
        "error": "browser still shows a challenge page",
        "items": [],
    }

    imported = client.post(
        f"/api/v1/ranking/capture-import?project_id={project_id}",
        headers=headers,
        json=payload,
    )

    assert imported.status_code == 200
    data = imported.json()["data"]
    assert data["status"] == "failed"
    assert data["item_count"] == 0
    snapshot = client.get(f"/api/v1/ranking/snapshots/{data['snapshot_id']}", headers=headers)
    assert snapshot.status_code == 200
    snapshot_data = snapshot.json()["data"]
    assert snapshot_data["status"] == "failed"
    assert snapshot_data["capture_status"] == "user_action_required"
    assert "challenge" in snapshot_data["error"]
