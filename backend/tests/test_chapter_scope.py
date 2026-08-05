"""Historical chapter scope reconciliation and V7 fail-closed contracts."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def scope_case():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"scope-{uuid.uuid4().hex[:10]}@nc.dev"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "test1234"},
    )
    assert registered.status_code == 200, registered.text
    headers = {"Authorization": f"Bearer {registered.json()['data']['access_token']}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    novel = client.post(
        f"/api/v1/projects/{project_id}/novels",
        headers=headers,
        json={"idea": "历史归属测试作品", "genre": "悬疑", "style": "紧凑", "target_words": 10000},
    )
    assert novel.status_code == 200, novel.text
    return client, headers, project_id, novel.json()["data"]["id"]


def _insert_orphan(project_id: str, *, meta: dict | None = None, title: str = "历史章节") -> str:
    from app.db import connect, encode, new_id

    chapter_id = new_id()
    db = connect()
    db.execute(
        """INSERT INTO contents
           (id, project_id, parent_id, type, title, body, meta, status, scope_status, seq)
           VALUES (%s,%s,NULL,'chapter',%s,%s,%s,'draft','legacy_unlinked',%s)""",
        (
            chapter_id,
            project_id,
            title,
            encode({"type": "doc", "content": [{"type": "paragraph", "text": "历史正文。"}]}),
            encode({"seq": 1, **(meta or {})}),
            1,
        ),
    )
    db.commit()
    db.close()
    return chapter_id


def _fetch_scope(chapter_id: str) -> dict:
    from app.db import connect

    db = connect()
    row = db.execute(
        "SELECT parent_id, scope_status FROM contents WHERE id=%s", (chapter_id,)
    ).fetchone()
    db.close()
    return dict(row)


def test_dry_run_never_mutates_an_ambiguous_legacy_chapter(scope_case):
    client, headers, project_id, novel_id = scope_case
    chapter_id = _insert_orphan(project_id)

    response = client.post(
        "/api/v1/chapter-scope/scan",
        headers=headers,
        json={"project_id": project_id, "apply": False},
    )
    assert response.status_code == 200, response.text
    item = next(item for item in response.json()["data"]["items"] if item["chapter_id"] == chapter_id)
    assert item["decision"] == "pending"
    assert item["selected_novel_id"] == novel_id
    assert _fetch_scope(chapter_id) == {"parent_id": None, "scope_status": "legacy_unlinked"}


def test_high_confidence_scan_can_bind_and_records_evidence(scope_case):
    client, headers, project_id, novel_id = scope_case
    chapter_id = _insert_orphan(project_id, meta={"novel_id": novel_id}, title="有明确来源")

    response = client.post(
        "/api/v1/chapter-scope/scan",
        headers=headers,
        json={"project_id": project_id, "apply": True, "auto_bind": True},
    )
    assert response.status_code == 200, response.text
    item = next(item for item in response.json()["data"]["items"] if item["chapter_id"] == chapter_id)
    assert item["decision"] == "auto_bound"
    assert response.json()["data"]["counts"]["auto_bound"] == 1
    assert _fetch_scope(chapter_id) == {"parent_id": novel_id, "scope_status": "legacy_resolved"}

    db = __import__("app.db", fromlist=["connect"]).connect()
    resolution = db.execute(
        "SELECT status, selected_novel_id, source FROM legacy_chapter_resolutions WHERE chapter_id=%s",
        (chapter_id,),
    ).fetchone()
    audit = db.execute(
        "SELECT action FROM audit_logs WHERE entity_id=%s ORDER BY created_at DESC LIMIT 1",
        (chapter_id,),
    ).fetchone()
    db.close()
    assert dict(resolution) == {
        "status": "auto_bound",
        "selected_novel_id": novel_id,
        "source": "legacy_reconciler",
    }
    assert audit["action"] == "legacy_chapter.auto_bound"


def test_auto_bind_disabled_persists_a_reviewable_proposal_only(scope_case):
    client, headers, project_id, novel_id = scope_case
    chapter_id = _insert_orphan(project_id, meta={"novel_id": novel_id}, title="待人工确认")

    response = client.post(
        "/api/v1/chapter-scope/scan",
        headers=headers,
        json={"project_id": project_id, "apply": True, "auto_bind": False},
    )
    assert response.status_code == 200, response.text
    counts = response.json()["data"]["counts"]
    assert counts["deferred"] == 1
    assert _fetch_scope(chapter_id) == {"parent_id": None, "scope_status": "legacy_pending"}

    db = __import__("app.db", fromlist=["connect"]).connect()
    resolution = db.execute(
        "SELECT status, selected_novel_id FROM legacy_chapter_resolutions WHERE chapter_id=%s",
        (chapter_id,),
    ).fetchone()
    db.close()
    assert dict(resolution) == {"status": "pending", "selected_novel_id": novel_id}


def test_human_bind_promotes_orphan_into_v7_scope(scope_case):
    client, headers, project_id, novel_id = scope_case
    chapter_id = _insert_orphan(project_id, title="人工选择")

    response = client.post(
        f"/api/v1/chapter-scope/chapters/{chapter_id}/bind",
        headers=headers,
        json={"novel_id": novel_id},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["resolution_status"] == "confirmed"
    assert _fetch_scope(chapter_id) == {"parent_id": novel_id, "scope_status": "legacy_resolved"}

    db = __import__("app.db", fromlist=["connect"]).connect()
    resolution = db.execute(
        "SELECT status, source, confidence FROM legacy_chapter_resolutions WHERE chapter_id=%s",
        (chapter_id,),
    ).fetchone()
    db.close()
    assert resolution["status"] == "confirmed"
    assert resolution["source"] == "human_confirmation"
    assert float(resolution["confidence"]) == 1.0


def test_orphan_is_hidden_from_normal_root_library_but_remains_readable(scope_case):
    client, headers, project_id, _novel_id = scope_case
    chapter_id = _insert_orphan(project_id)

    root = client.get(
        f"/api/v1/contents?project_id={project_id}", headers=headers
    )
    assert root.status_code == 200, root.text
    assert chapter_id not in {item["id"] for item in root.json()["data"]}

    detail = client.get(f"/api/v1/contents/{chapter_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["id"] == chapter_id


def test_orphan_edit_and_live_review_stop_before_version_or_provider(scope_case, monkeypatch):
    client, headers, project_id, _novel_id = scope_case
    chapter_id = _insert_orphan(project_id)

    import app.main as main_module

    monkeypatch.setattr(
        main_module,
        "complete",
        lambda **_kwargs: pytest.fail("orphan operation must not call a Provider"),
    )
    before = _version_count(chapter_id)
    edit = client.post(
        f"/api/v1/contents/{chapter_id}/ai/polish",
        headers=headers,
        json={"selection": "历史正文。" * 20, "instruction": "润色"},
    )
    review = client.post(
        f"/api/v1/contents/{chapter_id}/review",
        headers=headers,
        json={"selection": "历史正文。" * 20, "instruction": "检查"},
    )
    assert edit.status_code == 409
    assert review.status_code == 409
    assert _version_count(chapter_id) == before


def _version_count(chapter_id: str) -> int:
    from app.db import connect

    db = connect()
    row = db.execute(
        "SELECT COUNT(*) AS count FROM versions WHERE entity_type='content' AND entity_id=%s",
        (chapter_id,),
    ).fetchone()
    db.close()
    return int(row["count"])


def test_worker_regeneration_fails_closed_for_orphan(scope_case):
    from app.services.chapter_scope import ChapterScopeError
    from app.workers import tasks

    _client, _headers, project_id, _novel_id = scope_case
    chapter_id = _insert_orphan(project_id)
    with pytest.raises(ChapterScopeError) as exc:
        tasks.regenerate_chapter_task.run(chapter_id, "归属不明")
    assert exc.value.code == "CHAPTER_SCOPE_REQUIRED"
    assert _version_count(chapter_id) == 0
