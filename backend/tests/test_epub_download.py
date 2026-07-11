from __future__ import annotations

import os

import pytest
from fastapi import HTTPException
from starlette.responses import FileResponse


def test_epub_endpoint_returns_download_response_and_never_json_path(monkeypatch, tmp_path):
    from app.api.v1 import complete_api
    from app.services import novel_export

    path = tmp_path / "book.epub"
    path.write_bytes(b"epub-test")
    monkeypatch.setattr(complete_api, "require_novel_member", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(novel_export, "export_novel_epub",
                        lambda _novel_id: {"status": "ok", "path": str(path), "chapter_count": 1})
    monkeypatch.setattr(novel_export, "get_novel_completion_status",
                        lambda _novel_id: {"title": "测试/书", "ready_for_release": False})

    response = complete_api.export_novel_epub_endpoint("novel-1", {"id": "user-1"})
    assert isinstance(response, FileResponse)
    assert response.media_type == "application/epub+zip"
    assert response.headers["x-novelcraft-ready-for-release"] == "false"
    assert str(path) not in response.headers.get("content-disposition", "")


def test_epub_endpoint_rejects_empty_and_unavailable(monkeypatch):
    from app.api.v1 import complete_api
    from app.services import novel_export

    monkeypatch.setattr(complete_api, "require_novel_member", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(novel_export, "export_novel_epub", lambda _id: {"status": "empty"})
    with pytest.raises(HTTPException) as empty:
        complete_api.export_novel_epub_endpoint("novel-1", {"id": "user-1"})
    assert empty.value.status_code == 409

    monkeypatch.setattr(novel_export, "export_novel_epub",
                        lambda _id: {"status": "unavailable", "message": "missing ebooklib"})
    with pytest.raises(HTTPException) as unavailable:
        complete_api.export_novel_epub_endpoint("novel-1", {"id": "user-1"})
    assert unavailable.value.status_code == 503
