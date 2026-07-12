from __future__ import annotations

import json
import io
import urllib.error

import pytest

from app.services.t5_long_run import (
    ApiClient,
    Checkpoint,
    LongRunRunner,
    T5Config,
    T5RunError,
    adjacent_repeat_scores,
    build_evidence,
    write_evidence,
)


def _chapter(seq: int, text: str, status: str = "reviewed") -> dict:
    return {"id": f"c{seq}", "status": status,
            "body": {"type": "doc", "content": [{"type": "paragraph", "text": text}]},
            "meta": {"seq": seq, "review_score": 85, "continuity": {"status": "clean"}}}


def test_cost_guard_and_checkpoint_target_guard(tmp_path):
    with pytest.raises(T5RunError, match="exceeds configured cap"):
        T5Config("p", "n", target_new_chapters=100, cost_cap_cny=1).validate()
    path = tmp_path / "checkpoint.json"
    path.write_text(json.dumps({"project_id": "p", "novel_id": "n", "target_new_chapters": 2,
                                "baseline_chapters": 0, "batch_ids": [], "resume_attempts": {},
                                "started_at": "x", "updated_at": "x"}))
    runner = LongRunRunner(object(), T5Config("p", "n", target_new_chapters=3), path)
    with pytest.raises(T5RunError, match="target differs"):
        runner._load_or_create(0)


def test_api_client_reauthenticates_once_after_access_token_expiry(monkeypatch):
    calls = []

    class Response:
        def __init__(self, payload): self.payload = payload
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self): return json.dumps(self.payload).encode()

    def fake_urlopen(request, timeout=0):
        calls.append((request.full_url, request.headers.get("Authorization")))
        if request.full_url.endswith("/auth/login"):
            return Response({"data": {"access_token": "fresh-token"}})
        if len([url for url, _auth in calls if url.endswith("/contents/n")]) == 1:
            raise urllib.error.HTTPError(request.full_url, 401, "expired", {}, io.BytesIO(b'{"detail":"invalid token"}'))
        return Response({"data": {"id": "n"}})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = ApiClient("http://example.test", token="expired")
    client._email, client._password = "t5@example.test", "password"
    assert client.request("GET", "/contents/n") == {"id": "n"}
    assert calls[-1][1] == "Bearer fresh-token"


def test_evidence_is_computed_from_real_chapter_fields(tmp_path):
    chapters = [_chapter(1, "地底传来一阵低沉嗡鸣"), _chapter(2, "他走进大厅，看见陌生来客")]
    checkpoint = Checkpoint("p", "n", 2, baseline_chapters=0)
    evidence = build_evidence(chapters, checkpoint, [{"id": "b1", "status": "succeeded"}])
    assert evidence["accepted"] is True
    assert evidence["average_review_score"] == 85
    assert adjacent_repeat_scores(chapters)[0]["jaccard_5gram"] == 0
    json_path, report_path = write_evidence(evidence, tmp_path)
    assert json.loads(json_path.read_text())["new_chapters"] == 2
    assert "验收结论：通过" in report_path.read_text()


def test_restart_recovers_checkpointed_provider_batch_before_creating_new_one(tmp_path):
    class FakeClient:
        def __init__(self):
            self.chapters = []
            self.batch_reads = 0
            self.created = 0
            self.resumed = 0

        def request(self, method, path, body=None):
            if path == "/contents/n":
                return {"id": "n", "project_id": "p", "type": "novel"}
            if path.startswith("/contents?"):
                return self.chapters
            if path == "/generation-batches/b-existing":
                self.batch_reads += 1
                if self.resumed:
                    self.chapters = [_chapter(1, "第一章正文"), _chapter(2, "第二章正文")]
                    return {"id": "b-existing", "status": "succeeded"}
                return {"id": "b-existing", "status": "pending_provider", "error": "temporary"}
            if path == "/generation-batches/b-existing/resume":
                self.resumed += 1
                return {"status": "pending"}
            if path == "/novels/n/chapters/batch":
                self.created += 1
                return {"batch_id": "unexpected"}
            raise AssertionError((method, path, body))

    checkpoint = Checkpoint("p", "n", 2, baseline_chapters=0, batch_ids=["b-existing"])
    path = tmp_path / "checkpoint.json"
    path.write_text(json.dumps(checkpoint.__dict__))
    client = FakeClient()
    runner = LongRunRunner(client, T5Config("p", "n", target_new_chapters=2, poll_seconds=0), path,
                           sleep=lambda _seconds: None)
    saved, chapters, batches = runner.run()
    assert len(chapters) == 2 and batches[0]["status"] == "succeeded"
    assert client.resumed == 1
    assert client.created == 0


def test_chapter_listing_paginates_beyond_200(tmp_path):
    class FakeClient:
        def request(self, _method, path, _body=None):
            offset = int(path.split("offset=")[1])
            return [_chapter(i, f"正文{i}") for i in range(offset, min(offset + 200, 250))]

    runner = LongRunRunner(FakeClient(), T5Config("p", "n", target_new_chapters=1),
                           tmp_path / "checkpoint.json")
    assert len(runner._chapters()) == 250


def test_narrative_ai_calls_are_charged_to_the_content_project(monkeypatch):
    import app.gateway as gateway
    from app.db import connect, encode, new_id
    from app.services.entity_tracker import extract_and_store
    from app.services.foreshadowing import extract_and_store_foreshadowing
    from app.services.summarizer import summarize_book, summarize_chapter, summarize_volume
    from app.services.timeline import extract_timeline, update_arcs

    db = connect()
    project = db.execute("SELECT id FROM projects ORDER BY created_at DESC LIMIT 1").fetchone()
    assert project is not None
    novel_id, chapter_id = new_id(), new_id()
    db.execute(
        "INSERT INTO contents (id,project_id,type,title,body,meta,status) VALUES (%s,%s,'novel','T5归属',%s,%s,'draft')",
        (novel_id, project["id"], encode({"type": "doc", "content": []}),
         encode({"idea": "项目归属测试", "genre": "悬疑", "style": "克制"})),
    )
    db.execute(
        "INSERT INTO contents (id,project_id,parent_id,type,title,body,meta,status) VALUES (%s,%s,%s,'chapter','第一章',%s,%s,'draft')",
        (chapter_id, project["id"], novel_id, encode({"type": "doc", "content": []}), encode({"seq": 1})),
    )
    db.commit(); db.close()

    seen = []
    def fake_complete(**kwargs):
        seen.append(kwargs["project_id"])
        return {}
    monkeypatch.setattr(gateway, "complete", fake_complete)
    extract_and_store(chapter_id, novel_id, "正文")
    extract_and_store_foreshadowing(chapter_id, 1, "正文")
    extract_timeline(chapter_id, "正文")
    update_arcs(novel_id, "正文")
    summarize_chapter(chapter_id, "正文")
    summarize_volume(novel_id, 1, ["摘要"])
    summarize_book(novel_id, ["卷摘要"])
    assert seen == [project["id"]] * 7
