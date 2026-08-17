"""Permission and project-scope guards for the v0.9.2 publishing API."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.v1 import publishing


class _Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class _Db:
    def __init__(self, row):
        self.row = row

    def execute(self, _sql, _params=()):
        return _Cursor(self.row)


def test_chapter_scope_requires_project_membership(monkeypatch):
    calls = []
    monkeypatch.setattr(
        publishing,
        "require_member",
        lambda _db, project_id, _user, write=False: calls.append((project_id, write)),
    )

    chapter = publishing._load_chapter_scope(
        _Db({"id": "chapter-1", "project_id": "project-1", "parent_id": "novel-1", "type": "chapter"}),
        "chapter-1",
        {"id": "user-1"},
        write=True,
    )

    assert chapter["parent_id"] == "novel-1"
    assert calls == [("project-1", True)]


def test_variant_scope_resolves_through_novel(monkeypatch):
    calls = []
    monkeypatch.setattr(
        publishing,
        "require_member",
        lambda _db, project_id, _user, write=False: calls.append((project_id, write)),
    )

    variant = publishing._load_variant_scope(
        _Db({"id": "variant-1", "novel_id": "novel-1", "novel_project_id": "project-1", "novel_type": "novel"}),
        "variant-1",
        {"id": "user-1"},
        write=False,
    )

    assert variant["novel_id"] == "novel-1"
    assert calls == [("project-1", False)]


def test_variant_cannot_be_used_for_a_chapter_from_another_novel():
    with pytest.raises(HTTPException) as exc:
        publishing._assert_variant_chapter_scope(
            {"parent_id": "novel-1"},
            {"novel_id": "novel-2"},
            "chapter-1",
        )

    assert exc.value.status_code == 409
