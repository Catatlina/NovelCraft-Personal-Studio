"""Persistence contracts for chapter-directory import (NC-SC-004)."""
from __future__ import annotations

import json

import pytest
from fastapi import HTTPException


class _Cursor:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class _ImportDb:
    def __init__(self, *, role="owner", existing=None, fail_insert_at=None):
        self.role = role
        self.existing = list(existing or [])
        self.fail_insert_at = fail_insert_at
        self.statements = []
        self.inserted = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.statements.append((compact, params))
        if "SELECT * FROM contents WHERE id" in compact or "SELECT project_id" in compact and "contents" in compact:
            return _Cursor({"id": "novel-1", "project_id": "project-1", "type": "novel"})
        if "FROM project_members" in compact:
            return _Cursor({"role": self.role})
        if "MAX(" in compact and "contents" in compact:
            seqs = [int(row["meta"].get("seq", 0)) for row in self.existing + self.inserted]
            return _Cursor({"seq": max(seqs, default=0)})
        if compact.startswith("SELECT") and "FROM contents" in compact and "parent_id" in compact:
            return _Cursor(many=self.existing + self.inserted)
        if compact.startswith("INSERT INTO contents"):
            if self.fail_insert_at is not None and len(self.inserted) + 1 == self.fail_insert_at:
                raise RuntimeError("simulated insert failure")
            # The contract intentionally does not dictate SQL column order. Extract
            # encoded metadata/title from the values supplied by the implementation.
            decoded = []
            for value in params:
                if isinstance(value, str):
                    try:
                        decoded.append(json.loads(value))
                    except (TypeError, ValueError):
                        pass
                elif isinstance(value, dict):
                    decoded.append(value)
            meta = next((value for value in decoded if isinstance(value, dict) and "seq" in value), {})
            title = next((value for value in params if isinstance(value, str) and value.startswith("第")), "")
            chapter_id = str(params[0])
            self.inserted.append({"id": chapter_id, "title": title, "meta": meta})
            return _Cursor()
        return _Cursor()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True
        self.inserted.clear()

    def close(self):
        self.closed = True


def _call(monkeypatch, db, text, role_user="user-1"):
    from app.api.v1 import batch_endpoints

    monkeypatch.setattr(batch_endpoints, "connect", lambda: db)
    return batch_endpoints.import_chapters("novel-1", {"text": text}, {"id": role_user})


@pytest.mark.parametrize("role", ["owner", "editor"])
def test_owner_and_editor_import_real_chapter_contents(monkeypatch, role):
    db = _ImportDb(role=role)
    response = _call(monkeypatch, db, "第1章 初见\n第2章 迷雾")

    assert response["data"]["imported"] == 2
    assert response["data"]["skipped"] == 0
    assert len(response["data"]["ids"]) == 2
    assert len(db.inserted) == 2
    assert [row["meta"]["seq"] for row in db.inserted] == [1, 2]
    assert db.committed and db.closed


def test_viewer_is_forbidden_before_any_chapter_write(monkeypatch):
    db = _ImportDb(role="viewer")
    with pytest.raises(HTTPException) as exc_info:
        _call(monkeypatch, db, "第1章 不应写入")
    assert exc_info.value.status_code == 403
    assert db.inserted == []
    assert not db.committed


def test_parser_sequences_are_contiguous_not_physical_line_numbers():
    from app.services.batch_fixes import import_chapter_directory

    parsed = import_chapter_directory("说明文字\n\n第十章 开端\n忽略本行\n第20章 转折", "novel-1")
    assert [chapter["seq"] for chapter in parsed] == [1, 2]
    assert [chapter["title"] for chapter in parsed] == ["开端", "转折"]


def test_repeating_identical_import_is_idempotent(monkeypatch):
    db = _ImportDb()
    text = "第1章 初见\n第2章 迷雾"
    first = _call(monkeypatch, db, text)
    second = _call(monkeypatch, db, text)

    assert first["data"]["imported"] == 2
    assert second["data"]["imported"] == 0
    assert second["data"]["skipped"] == 2
    assert second["data"]["ids"] == []
    assert len(db.inserted) == 2


def test_import_appends_after_existing_chapters_with_contiguous_order(monkeypatch):
    existing = [
        {"id": "chapter-1", "title": "第一章", "meta": {"seq": 1}},
        {"id": "chapter-3", "title": "第三章", "meta": {"seq": 3}},
    ]
    db = _ImportDb(existing=existing)
    response = _call(monkeypatch, db, "第8章 新篇\n第20章 再会")

    assert response["data"]["imported"] == 2
    assert [row["meta"]["seq"] for row in db.inserted] == [4, 5]


def test_empty_and_duplicate_titles_are_skipped_deterministically(monkeypatch):
    db = _ImportDb()
    response = _call(monkeypatch, db, "第1章   \n第2章 同名\n第3章 同名")

    assert response["data"]["imported"] == 1
    assert response["data"]["skipped"] == 2
    assert len(response["data"]["ids"]) == 1
    assert len(db.inserted) == 1


def test_insert_failure_rolls_back_entire_import(monkeypatch):
    db = _ImportDb(fail_insert_at=2)
    with pytest.raises(RuntimeError, match="simulated insert failure"):
        _call(monkeypatch, db, "第1章 初见\n第2章 迷雾")

    assert db.rolled_back is True
    assert db.committed is False
    assert db.inserted == []
    assert db.closed is True


def test_response_always_contains_imported_skipped_and_ids(monkeypatch):
    db = _ImportDb()
    data = _call(monkeypatch, db, "无有效章节行")["data"]
    assert set(data) >= {"imported", "skipped", "ids"}
    assert data["imported"] == 0
    assert data["ids"] == []
