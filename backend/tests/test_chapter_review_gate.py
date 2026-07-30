from __future__ import annotations

from pathlib import Path


class _Cursor:
    def __init__(self, one=None):
        self.one = one

    def fetchone(self):
        return self.one


class _Db:
    def __init__(self):
        self.statements = []

    def execute(self, sql, params=()):
        self.statements.append((" ".join(sql.split()), params))
        return _Cursor()

    def commit(self):
        pass

    def close(self):
        pass


def _review(score: int):
    return {"score": score, "dimensions": {"prose": score, "plot": score, "character_ooc": score,
            "world_conflict": score, "logic_consistency": score, "pace": score, "foreshadowing": score},
            "issues": [] if score >= 80 else ["冲突不足"]}


def _long_body(prefix: str = "正文"):
    # 45 段 × ~96 字 ≈ 4300 字，稳定超过 3000 字硬门禁下限。
    para = (
        "{prefix}里，主角沿着潮湿的街道向前走，手里的旧书不断发烫。雾从巷口压下来，路灯像被水泡过，光线散得很慢。"
        "他听见身后有人踩碎瓦片，声音很轻，却刚好落在他的心跳之间。为了甩开追踪者，他没有回头，只把书塞进外套内侧，"
        "绕进父亲生前常去的旧书铺。柜台后的老人抬眼看他，像早知道他会来，又像等这一刻等了很多年。"
        "这一段继续推进冲突、动作、心理和场景细节，保证章节长度达到真实网文最低要求，字数稳定超过三千。"
    )
    return [para.format(prefix=f"{prefix}{i}") for i in range(45)]


def _short_body():
    return ["第一章很短，只有这一句话。", "第二句话也补上一点内容。", "第三句仍然不够长。"]


def _review_calls(calls):
    return [c for c in calls if c["task_type"] == "review_7dim"]


def _rewrite_calls(calls):
    return [c for c in calls if c["task_type"] == "gen_next_chapter"]


def test_passing_chapter_is_accepted_and_reviewed(monkeypatch):
    from app.workers import tasks

    db = _Db(); calls = []
    monkeypatch.setattr(tasks, "connect", lambda: db)
    monkeypatch.setattr(tasks, "complete", lambda **kwargs: calls.append(kwargs) or _review(90))
    result = tasks._review_and_finalize_chapter(
        "chapter-1", "novel-1", "project-1", 2, "chapter-key", "第二章", _long_body(), {"status": "clean"}
    )
    assert result["accepted"] is True
    assert result["review_status"] == "reviewed"
    assert len(_review_calls(calls)) == 1
    assert calls[0]["task_type"] == "review_7dim"
    assert calls[0]["client_mutation_id"] == "chapter-key:review:0:v1"
    assert any("status='reviewed'" in sql for sql, _ in db.statements)


def test_low_score_rewrite_until_passing_then_accepted(monkeypatch):
    from app.workers import tasks

    db = _Db()
    outputs = iter([_review(65), {"chapter": {"title": "改写章", "body": _long_body("改写")}}, _review(90)])
    calls = []
    monkeypatch.setattr(tasks, "connect", lambda: db)
    monkeypatch.setattr(tasks, "complete", lambda **kwargs: calls.append(kwargs) or next(outputs))
    result = tasks._review_and_finalize_chapter(
        "chapter-1", "novel-1", "project-1", 2, "chapter-key", "第二章", _long_body(), {"status": "flagged"}
    )
    assert result["accepted"] is True
    assert result["review_status"] == "reviewed"
    assert result["rewrite_attempts"] == 1
    assert [call["task_type"] for call in calls] == ["review_7dim", "gen_next_chapter", "review_7dim"]


def test_rewrite_exhaustion_never_reports_success(monkeypatch):
    from app.workers import tasks

    db = _Db(); outputs = iter([
        _review(60), {"chapter": {"title": "改1", "body": _long_body("改1")}},
        _review(62), {"chapter": {"title": "改2", "body": _long_body("改2")}}, _review(59),
    ])
    monkeypatch.setattr(tasks, "connect", lambda: db)
    monkeypatch.setattr(tasks, "complete", lambda **_kwargs: next(outputs))
    result = tasks._review_and_finalize_chapter(
        "chapter-1", "novel-1", "project-1", 2, "chapter-key", "第二章", _long_body(),
        {"status": "clean"}, max_rewrites=2
    )
    assert result["accepted"] is False
    assert result["review_status"] == "needs_rewrite"
    assert any("status='needs_rewrite'" in sql for sql, _ in db.statements)


def test_short_chapter_is_flagged_and_delivered_as_needs_rewrite(monkeypatch):
    from app.workers import tasks

    db = _Db()
    # 评审给高分也无用：字数不足会强制分数低于阈值，触发重写；用尽后标记待人工重写。
    outputs = iter([
        _review(95), {"chapter": {"title": "短1", "body": _short_body()}},
        _review(95), {"chapter": {"title": "短2", "body": _short_body()}},
        _review(95), {"chapter": {"title": "短3", "body": _short_body()}}, _review(95),
    ])
    monkeypatch.setattr(tasks, "connect", lambda: db)
    monkeypatch.setattr(tasks, "complete", lambda **_kwargs: next(outputs))
    result = tasks._review_and_finalize_chapter(
        "chapter-1", "novel-1", "project-1", 2, "chapter-key", "第二章", _short_body(),
        {"status": "clean"}, max_rewrites=3
    )
    assert result["accepted"] is False
    assert result["review_status"] == "needs_rewrite"
    assert any("status='needs_rewrite'" in sql for sql, _ in db.statements)
    assert "chars" in result["quality_reason"]


def test_default_allows_three_rewrites(monkeypatch):
    from app.workers import tasks

    db = _Db()
    outputs = iter([
        _review(60), {"chapter": {"title": "改0", "body": _long_body("改0")}},
        _review(61), {"chapter": {"title": "改1", "body": _long_body("改1")}},
        _review(62), {"chapter": {"title": "改2", "body": _long_body("改2")}}, _review(63),
    ])
    calls = []
    monkeypatch.setattr(tasks, "connect", lambda: db)
    monkeypatch.setattr(tasks, "complete", lambda **kwargs: calls.append(kwargs) or next(outputs))
    result = tasks._review_and_finalize_chapter(
        "chapter-1", "novel-1", "project-1", 2, "chapter-key", "第二章", _long_body(), {"status": "clean"}
    )
    assert result["review_status"] == "needs_rewrite"
    assert len(_review_calls(calls)) == 4
    assert len(_rewrite_calls(calls)) == 3


def test_review_gate_migration_tracks_truthful_batch_counts():
    root = Path(__file__).resolve().parents[2]
    sql = (root / "backend/alembic/versions/nc_sc004_review_gate.py").read_text(encoding="utf-8")
    for field in ("generated_count", "reviewed_count", "accepted_count", "needs_review_count"):
        assert field in sql
    assert "reviews_generation_uq" in sql
