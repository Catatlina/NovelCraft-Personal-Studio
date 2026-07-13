"""Hardening contracts for complete_api: project isolation, compliant fusion boundary,
and real chapter-body extraction for exports (docs 23/25 gates)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[2]


class _Cursor:
    def __init__(self, one=None):
        self.one = one

    def fetchone(self):
        return self.one

    def fetchall(self):
        return []


class _MembershipDb:
    """Resolves a novel to project-1 and answers membership lookups with `role`."""

    def __init__(self, role=None, novel_exists=True):
        self.role = role
        self.novel_exists = novel_exists

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        if "FROM contents WHERE id" in compact:
            return _Cursor({"project_id": "project-1"} if self.novel_exists else None)
        if "SELECT role FROM project_members" in compact:
            return _Cursor({"role": self.role} if self.role else None)
        return _Cursor()

    def close(self):
        pass


# --- project isolation -------------------------------------------------------

def test_export_rejects_non_member(monkeypatch):
    from app.api.v1 import complete_api

    monkeypatch.setattr(complete_api, "connect", lambda: _MembershipDb(role=None))
    with pytest.raises(HTTPException) as exc_info:
        complete_api.require_novel_member("novel-1", {"id": "stranger"})
    assert exc_info.value.status_code == 403


def test_export_returns_404_for_unknown_novel(monkeypatch):
    from app.api.v1 import complete_api

    monkeypatch.setattr(complete_api, "connect", lambda: _MembershipDb(novel_exists=False))
    with pytest.raises(HTTPException) as exc_info:
        complete_api.require_novel_member("missing", {"id": "user-1"})
    assert exc_info.value.status_code == 404


def test_member_can_access_novel_export_guard(monkeypatch):
    from app.api.v1 import complete_api

    monkeypatch.setattr(complete_api, "connect", lambda: _MembershipDb(role="viewer"))
    assert complete_api.require_novel_member("novel-1", {"id": "member"}) is None


def test_project_scoped_endpoints_require_project_id():
    from app.api.v1 import complete_api

    with pytest.raises(HTTPException) as exc_info:
        complete_api.require_project_member("", {"id": "user-1"})
    assert exc_info.value.status_code == 422


def test_model_routes_have_one_canonical_api():
    from app.main import app

    paths = list(app.openapi()["paths"])
    assert "/api/v1/model-routes" not in paths
    assert paths.count("/api/v1/admin/model-routes") == 1


def test_gemini_credentials_are_sent_in_header_not_url():
    sources = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in ("backend/app/ai/providers.py", "backend/app/services/providers_and_adapters.py")
    )
    assert "generateContent?key=" not in sources
    assert "x-goog-api-key" in sources


def test_export_routes_enforce_membership_before_service(monkeypatch):
    from app.api.v1 import complete_api

    monkeypatch.setattr(complete_api, "connect", lambda: _MembershipDb(role=None))
    called = []
    monkeypatch.setattr(
        "app.services.novel_export.export_novel_txt", lambda novel_id: called.append(novel_id)
    )
    with pytest.raises(HTTPException):
        complete_api.export_novel_txt_endpoint("novel-1", {"id": "stranger"})
    assert called == []


# --- compliance boundary (docs/25): no anti-bot scraping entry ---------------

def test_stealth_scrape_endpoint_is_removed():
    from app.main import app

    paths = set(app.openapi()["paths"])
    assert "/api/v1/scrape/browseract" not in paths


def test_stealth_scrape_service_is_removed():
    from app.services import fusion_browseract_insprira as fusion

    assert not hasattr(fusion, "scrape_ranking_with_browseract")


# --- failure semantics (docs/23 §4): no silent-empty success -----------------

def test_community_skills_fetch_failure_is_explicit(monkeypatch):
    import urllib.request
    from app.services.fusion_browseract_insprira import fetch_community_skills

    def _boom(*args, **kwargs):
        raise OSError("network unreachable")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    result = fetch_community_skills()
    assert result["status"] == "unavailable"
    assert result["skill_count"] == 0
    assert "network unreachable" in result["error"]


# --- export body extraction ---------------------------------------------------

PERSISTED_DOC = {
    "type": "doc",
    "content": [
        {"type": "paragraph", "text": "第一段正文。"},
        {"type": "paragraph", "text": "第二段正文。"},
    ],
}

TIPTAP_DOC = {
    "type": "doc",
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "嵌套文本节点。"}]},
    ],
}


def test_extract_body_text_reads_persisted_doc_format():
    from app.services.novel_export import extract_body_text

    assert extract_body_text(PERSISTED_DOC) == "第一段正文。\n第二段正文。"


def test_extract_body_text_reads_nested_tiptap_and_plain_shapes():
    from app.services.novel_export import extract_body_text

    assert extract_body_text(TIPTAP_DOC) == "嵌套文本节点。"
    assert extract_body_text("纯文本正文") == "纯文本正文"
    assert extract_body_text({"text": "旧格式"}) == "旧格式"
    assert extract_body_text(None) == ""


def test_txt_export_includes_chapter_body_from_doc_format(monkeypatch):
    from app.services import novel_export

    class _ExportDb:
        def execute(self, sql, params=()):
            compact = " ".join(sql.split())
            if "type = 'novel'" in compact:
                return _Cursor({"id": "novel-1", "title": "雾城修理铺", "meta": {}})
            if "type = 'chapter'" in compact:
                cursor = _Cursor()
                cursor.fetchall = lambda: [
                    {"title": "初雾", "body": PERSISTED_DOC, "meta": {"seq": 1}, "status": "reviewed"}
                ]
                return cursor
            return _Cursor()

        def close(self):
            pass

    monkeypatch.setattr(novel_export, "connect", lambda: _ExportDb())
    result = novel_export.export_novel_txt("novel-1")
    assert result["status"] == "ok"
    assert "第一段正文。" in result["content"]
    assert "第二段正文。" in result["content"]

    status = novel_export.get_novel_completion_status("novel-1")
    assert status["total_words"] == len("第一段正文。\n第二段正文。")
