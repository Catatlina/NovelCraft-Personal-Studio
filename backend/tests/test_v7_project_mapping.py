from __future__ import annotations

import pytest

from app.v7.integration import project_mapping


class _FakeResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _FakeConnection:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.sql = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def execute(self, sql, params=()):
        self.sql.append((str(sql), params))
        return _FakeResult(next(self.rows, None))

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_project_mapping_validates_pair_and_persists_link(monkeypatch):
    conn = _FakeConnection([
        {"id": "novel-1", "project_id": "project-1"},
        None,
        None,
    ])
    monkeypatch.setattr(project_mapping, "connect", lambda: conn)

    result = project_mapping.ensure_novel_project_link("novel-1", "project-1")

    assert result == {
        "novel_id": "novel-1",
        "project_id": "project-1",
        "source": "v7_director",
    }
    assert conn.committed is True
    assert conn.rolled_back is False
    assert conn.closed is True
    assert "v7_novel_project_links" in conn.sql[-1][0]


def test_project_mapping_rejects_cross_project_pair(monkeypatch):
    conn = _FakeConnection([{"id": "novel-1", "project_id": "project-1"}])
    monkeypatch.setattr(project_mapping, "connect", lambda: conn)

    with pytest.raises(ValueError, match="belongs to project"):
        project_mapping.ensure_novel_project_link("novel-1", "project-2")

    assert conn.committed is False
    assert conn.rolled_back is True
