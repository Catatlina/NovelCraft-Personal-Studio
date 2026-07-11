"""API contracts for user-authorized ranking metadata import (NC-SC-001)."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError


def _valid_item(rank: int = 1, title: str = "雾城修理铺") -> dict:
    return {
        "rank": rank,
        "title": title,
        "author": "测试作者",
        "category": "科幻",
        "confidence": 0.96,
        "evidence": {"collector": "visible_browser", "capture_id": "capture-1"},
    }


def test_ranking_import_route_is_registered():
    from app.main import app

    routes = {(route.path, method) for route in app.routes for method in getattr(route, "methods", set())}
    assert ("/api/v1/ranking/import", "POST") in routes


@pytest.mark.parametrize("role", ["owner", "editor"])
def test_owner_and_editor_have_import_permission(role):
    from app.api.v1.ranking import require_member

    class Db:
        def execute(self, _sql, _params):
            return self

        def fetchone(self):
            return {"role": role}

    assert require_member(Db(), "project-1", {"id": "user-1"}, write=True) is None


def test_viewer_cannot_import_ranking_metadata():
    from app.api.v1.ranking import require_member

    class Db:
        def execute(self, _sql, _params):
            return self

        def fetchone(self):
            return {"role": "viewer"}

    with pytest.raises(HTTPException) as exc_info:
        require_member(Db(), "project-1", {"id": "user-1"}, write=True)
    assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    "items",
    [
        [],
        [_valid_item(index, f"书名 {index}") for index in range(1, 202)],
        [{"title": "缺少排名"}],
        [{"rank": 1}],
        [{"rank": 1, "title": "   "}],
    ],
)
def test_import_rejects_empty_oversized_or_incomplete_items(items):
    from app.api.v1.ranking import RankingImportRequest

    with pytest.raises(ValidationError):
        RankingImportRequest(source_key="manual", items=items)


def test_valid_import_uses_shared_snapshot_persistence(monkeypatch):
    from app.api.v1 import ranking

    calls = []

    class Db:
        def close(self):
            pass

    db = Db()
    monkeypatch.setattr(ranking, "connect", lambda: db)
    monkeypatch.setattr(ranking, "require_member", lambda *_args, **_kwargs: None)

    def fake_persist(*args, **kwargs):
        calls.append((args, kwargs))
        return {
            "snapshot_id": "snapshot-import-1",
            "source": "manual",
            "item_count": 1,
            "status": "succeeded",
        }

    monkeypatch.setattr(ranking, "_persist_ranking_snapshot", fake_persist)
    payload = ranking.RankingImportRequest(source_key="manual", items=[_valid_item()])

    response = ranking.import_ranking(payload, "project-1", {"id": "user-1"})

    assert response["data"]["snapshot_id"] == "snapshot-import-1"
    assert response["data"]["status"] == "succeeded"
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] is db
    assert kwargs["project_id"] == "project-1"
    assert kwargs["source_key"] == "manual"
    assert kwargs["normalized_items"][0]["title"] == "雾城修理铺"


def test_scan_and_import_are_wired_to_the_same_persistence_function():
    """Protect against a second, semantically divergent snapshot write path."""
    from app.api.v1 import ranking

    assert "_persist_ranking_snapshot" in ranking._scan_source.__code__.co_names
    assert "_persist_ranking_snapshot" in ranking.import_ranking.__code__.co_names
