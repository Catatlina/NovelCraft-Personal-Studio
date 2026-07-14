"""长篇一致性推进到待验收：百章压力（真库100章）、写后 reconcile、卷级门禁。

真实 Provider 的百章 T5 长周期验收另行执行；此处以真实 Postgres 数据钉住
协议、检索窗口、矛盾检测与门禁语义。
"""
from __future__ import annotations

import time
import uuid

from fastapi.testclient import TestClient


def _auth_project():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"lc-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return client, headers, project_id


def _make_novel_with_chapters(project_id: str, chapter_count: int, volume_plan: list[dict],
                              status: str = "reviewed", with_summary: bool = True) -> tuple[str, list[str]]:
    from app.db import connect, encode, new_id

    novel_id = new_id()
    db = connect()
    db.execute(
        "INSERT INTO contents (id,project_id,type,title,body,meta,status) VALUES (%s,%s,'novel','百章一致性小说',%s,%s,'draft')",
        (novel_id, project_id, encode({"type": "doc", "content": []}),
         encode({"volume_plan": volume_plan})),
    )
    chapter_ids = []
    for seq in range(1, chapter_count + 1):
        cid = new_id()
        meta = {"seq": seq, "word_count": 2000}
        if with_summary:
            meta["chapter_summary"] = f"第{seq}章摘要：主角推进主线，遇到第{seq}号障碍。"
        db.execute(
            "INSERT INTO contents (id,project_id,parent_id,type,title,body,meta,status) VALUES (%s,%s,%s,'chapter',%s,%s,%s,%s)",
            (cid, project_id, novel_id, f"第{seq}章",
             encode({"type": "doc", "content": [{"type": "paragraph", "text": f"林昭在第{seq}章继续冒险。"}]}),
             encode(meta), status),
        )
        chapter_ids.append(cid)
    db.commit(); db.close()
    return novel_id, chapter_ids


def test_write_before_search_handles_100_chapter_window_fast():
    """百章压力：写前检索在 100 章真库数据上返回完整窗口且耗时可控。"""
    from app.workers.tasks import _write_before_search

    _, _, project_id = _auth_project()
    novel_id, _ = _make_novel_with_chapters(
        project_id, 100, [{"number": 1, "start_chapter": 1, "end_chapter": 100}])

    started = time.monotonic()
    ctx = _write_before_search(novel_id, chapter_seq=101, window_size=100)
    elapsed = time.monotonic() - started

    assert ctx["total_retrieved"] == 100
    assert ctx["recent_chapters"][0]["seq"] == 1
    assert ctx["recent_chapters"][-1]["seq"] == 100
    assert all(c["summary"] for c in ctx["recent_chapters"])
    assert elapsed < 5, f"100-chapter retrieval took {elapsed:.2f}s"


def test_write_after_reconcile_flags_new_entities():
    from app.db import connect, new_id
    from app.workers.tasks import _write_after_reconcile

    _, _, project_id = _auth_project()
    novel_id, chapter_ids = _make_novel_with_chapters(
        project_id, 3, [{"number": 1, "start_chapter": 1, "end_chapter": 3}])

    db = connect()
    db.execute(
        "INSERT INTO entity_states (id, chapter_id, entity_type, entity_name, location) VALUES (%s,%s,'character','林昭','青云城')",
        (new_id(), chapter_ids[0]),
    )
    db.commit(); db.close()

    report = _write_after_reconcile(novel_id, chapter_ids[2], "林昭抵达了魔都，见到了神秘人物赫连觉。")
    assert "林昭" in report["mentioned"]
    assert report["new_entities_detected"] > 0
    assert report["reconciliation_needed"] is True


def test_volume_gate_passes_clean_volume_and_persists(monkeypatch):
    import app.gateway as gateway

    client, headers, project_id = _auth_project()
    novel_id, _ = _make_novel_with_chapters(
        project_id, 10,
        [{"number": 1, "title": "第一卷", "start_chapter": 1, "end_chapter": 10},
         {"number": 2, "title": "第二卷", "start_chapter": 11, "end_chapter": 20}])

    monkeypatch.setattr(gateway, "complete",
                        lambda **kwargs: {"summary": "第一卷汇总：主角完成第一段冒险。"})
    result = client.post(f"/api/v1/novels/{novel_id}/volume-gate/1", headers=headers)
    assert result.status_code == 200
    gate = result.json()["data"]
    assert gate["passed"] is True
    assert gate["blockers"] == []
    assert gate["volume_summary"].startswith("第一卷汇总")

    stored = client.get(f"/api/v1/novels/{novel_id}/volume-gates", headers=headers).json()["data"]
    assert stored["volume_gates"]["1"]["passed"] is True
    assert len(stored["volume_plan"]) == 2


def test_volume_gate_blocks_on_missing_chapters_unreviewed_and_foreshadow():
    from app.db import connect, encode, new_id

    client, headers, project_id = _auth_project()
    # Only 8 of 10 planned chapters; chapters unreviewed (draft)
    novel_id, chapter_ids = _make_novel_with_chapters(
        project_id, 8, [{"number": 1, "start_chapter": 1, "end_chapter": 10}],
        status="needs_review", with_summary=False)

    db = connect()
    db.execute(
        "INSERT INTO foreshadowings (id, chapter_id, content, planned_resolve_chapter, status) VALUES (%s,%s,'神秘玉佩的来历',5,'planted')",
        (new_id(), chapter_ids[0]),
    )
    db.commit(); db.close()

    gate = client.post(f"/api/v1/novels/{novel_id}/volume-gate/1", headers=headers).json()["data"]
    assert gate["passed"] is False
    joined = "；".join(gate["blockers"])
    assert "缺少章节" in joined
    assert "未过审" in joined
    assert "伏笔" in joined
    assert any("缺少章节摘要" in w for w in gate["warnings"])

    # Gate for an unplanned volume fails explicitly instead of pretending
    unplanned = client.post(f"/api/v1/novels/{novel_id}/volume-gate/9", headers=headers).json()["data"]
    assert unplanned["passed"] is False and "分卷规划" in unplanned["blockers"][0]


def test_volume_gate_detects_entity_contradiction():
    from app.db import connect, new_id

    client, headers, project_id = _auth_project()
    novel_id, chapter_ids = _make_novel_with_chapters(
        project_id, 5, [{"number": 1, "start_chapter": 1, "end_chapter": 5}])

    db = connect()
    for location in ("北境雪原", "南疆火山"):
        db.execute(
            "INSERT INTO entity_states (id, chapter_id, entity_type, entity_name, location) VALUES (%s,%s,'character','林昭',%s)",
            (new_id(), chapter_ids[2], location),
        )
    db.commit(); db.close()

    gate = client.post(f"/api/v1/novels/{novel_id}/volume-gate/1", headers=headers).json()["data"]
    assert gate["passed"] is False
    assert any("矛盾" in b for b in gate["blockers"])


def test_batch_creation_blocked_by_failed_previous_volume_gate():
    client, headers, project_id = _auth_project()
    # Volume 1 planned as 10 chapters but only 10 drafts exist and gate will fail (needs_review)
    novel_id, _ = _make_novel_with_chapters(
        project_id, 10,
        [{"number": 1, "start_chapter": 1, "end_chapter": 10},
         {"number": 2, "start_chapter": 11, "end_chapter": 20}],
        status="needs_review")

    gate = client.post(f"/api/v1/novels/{novel_id}/volume-gate/1", headers=headers).json()["data"]
    assert gate["passed"] is False

    blocked = client.post(f"/api/v1/novels/{novel_id}/chapters/batch", headers=headers,
                          json={"chapter_count": 5})
    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert detail["code"] == "VOLUME_GATE_FAILED"
    assert detail["blockers"]

    # After the volume passes review, the gate clears and the batch is accepted
    from app.db import connect
    db = connect()
    db.execute("UPDATE contents SET status='reviewed' WHERE parent_id=%s AND type='chapter'", (novel_id,))
    db.commit(); db.close()
    regate = client.post(f"/api/v1/novels/{novel_id}/volume-gate/1", headers=headers).json()["data"]
    assert regate["passed"] is True

    allowed = client.post(f"/api/v1/novels/{novel_id}/chapters/batch", headers=headers,
                          json={"chapter_count": 5})
    assert allowed.status_code == 200


def test_summarizer_no_longer_stores_fake_summary(monkeypatch):
    """docs/23: AI 摘要失败必须显式失败，不得返回伪造摘要字符串。"""
    import pytest

    import app.gateway as gateway
    from app.services.summarizer import summarize_chapter

    _, _, project_id = _auth_project()
    novel_id, chapter_ids = _make_novel_with_chapters(
        project_id, 1, [{"number": 1, "start_chapter": 1, "end_chapter": 1}])

    def failing_complete(**kwargs):
        raise gateway.ProviderError("summarizer provider down")

    monkeypatch.setattr(gateway, "complete", failing_complete)
    with pytest.raises(gateway.ProviderError):
        summarize_chapter(chapter_ids[0], "正文")
