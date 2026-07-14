"""Regression tests for issues observed in production logs."""
from __future__ import annotations

import pytest


def test_generation_batches_closes_connection_when_query_fails(monkeypatch):
    from app import main

    closed = []

    class BrokenConn:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("synthetic query failure")

        def close(self):
            closed.append(True)

    monkeypatch.setattr(
        main,
        "load_content_for_user",
        lambda novel_id, user: (BrokenConn(), {"id": novel_id, "project_id": "project-1"}),
    )

    with pytest.raises(RuntimeError, match="synthetic query failure"):
        main.list_novel_generation_batches("novel-1", user={"id": "user-1"})

    assert closed == [True]
