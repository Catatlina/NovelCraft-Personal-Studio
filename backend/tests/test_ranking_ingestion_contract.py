"""NC-SC-001 ranking ingestion contracts.

These tests describe the next delivery boundary.  They intentionally exercise no
live ranking website; adapters must normalize unstable upstream payloads before
the API persists them.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "backend/alembic/versions"


def test_normalizer_emits_source_independent_traceable_fields():
    from app.services.ranking_adapter import normalize_ranking_items

    fetched_at = datetime(2026, 7, 11, 4, 5, 6, tzinfo=timezone.utc)
    items = normalize_ranking_items(
        "qidian",
        [
            {
                "rank": "2",
                "bookId": 12345,
                "title": "  测试 小说  ",
                "author": " 作者甲 ",
                "category": "玄幻",
                "url": "https://www.qidian.com/book/12345/",
                "readers": 998,
                "status": "ongoing",
                "last_update": "今天",
            }
        ],
        fetched_at=fetched_at,
    )

    assert len(items) == 1
    assert items[0] | {} == {
            "source_key": "qidian",
            "external_id": "12345",
            "rank_no": 2,
            "title": "测试 小说",
            "author": "作者甲",
            "category": "玄幻",
            "source_url": "https://www.qidian.com/book/12345/",
            "metrics": {"readers": "998", "status": "ongoing", "last_update": "今天"},
            "fetched_at": fetched_at,
            "dedupe_key": items[0]["dedupe_key"],
        }
    assert len(items[0]["dedupe_key"]) == 64


def test_normalizer_deduplicates_one_snapshot_by_identity_and_keeps_best_rank():
    from app.services.ranking_adapter import normalize_ranking_items

    items = normalize_ranking_items(
        "fanqie",
        [
            {"rank": 9, "book_id": "book-1", "title": "同一本书", "author": "甲"},
            {"rank": 3, "book_id": "book-1", "title": "同一本书", "author": "甲"},
            # When an upstream has no stable id, normalized title + author is the fallback identity.
            {"rank": 8, "title": "  无编号作品 ", "author": " 乙 "},
            {"rank": 5, "title": "无编号作品", "author": "乙"},
        ],
    )

    assert [(item["external_id"], item["rank_no"]) for item in items] == [
        ("book-1", 3),
        (None, 5),
    ]
    assert len({item["dedupe_key"] for item in items}) == 2


def test_schema_records_fetch_time_capture_time_and_snapshot_identity():
    sql = "\n".join(path.read_text(encoding="utf-8") for path in MIGRATIONS.glob("*.py")).lower()

    assert "fetched_at timestamptz" in sql
    assert "captured_at timestamptz" in sql
    assert "external_id" in sql
    assert "dedupe_key" in sql
    assert "unique(snapshot_id, dedupe_key)" in sql
    assert "retry_of_snapshot_id" in sql


def test_failed_snapshot_has_a_registered_replay_endpoint():
    from app.main import app

    routes = {(route.path, method) for route in app.routes for method in getattr(route, "methods", set())}
    assert ("/api/v1/ranking/snapshots/{snapshot_id}/retry", "POST") in routes


class _PermissionDb:
    def __init__(self, row):
        self.row = row
        self.query = None
        self.params = None

    def execute(self, query, params=()):
        self.query = " ".join(query.split())
        self.params = params
        return self

    def fetchone(self):
        return self.row


@pytest.mark.parametrize("row", [None, {"role": "viewer"}])
def test_ranking_mutations_reject_non_member_and_read_only_member(row):
    from app.api.v1.ranking import require_member

    db = _PermissionDb(row)
    with pytest.raises(HTTPException) as exc_info:
        require_member(db, "project-a", {"id": "user-a"}, write=True)

    assert exc_info.value.status_code == 403
    assert db.params == ("project-a", "user-a")


@pytest.mark.parametrize("role", ["owner", "editor"])
def test_ranking_mutations_allow_project_owner_and_editor(role):
    from app.api.v1.ranking import require_member

    require_member(_PermissionDb({"role": role}), "project-a", {"id": "user-a"}, write=True)


def test_ranking_reads_allow_project_viewer():
    from app.api.v1.ranking import require_member

    require_member(_PermissionDb({"role": "viewer"}), "project-a", {"id": "user-a"})
