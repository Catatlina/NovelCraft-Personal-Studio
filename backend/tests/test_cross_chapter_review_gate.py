"""Regression coverage for the V7 cross-chapter reviewed gate."""


def test_failed_continuity_is_a_blocking_quality_risk():
    from app.services.quality_risks import build_quality_repair_contract

    contract = build_quality_repair_contract(
        {"overall_score": 95, "dimension_scores": {"continuity": 95}, "issues": []},
        continuity={
            "status": "broken",
            "checked": True,
            "passed": False,
            "issues": [{"severity": "high", "message": "时间线冲突"}],
        },
    )
    assert contract["passed"] is False
    assert "continuity" in contract["blocking_categories"]


def test_v7_reviewed_gate_rejects_high_score_with_failed_continuity():
    from app.v7.quality.review_gate import reviewed_gate_failures

    failures = reviewed_gate_failures({
        "canonical_engine": "v7",
        "continuity": {"status": "broken", "checked": True, "passed": False},
        "final_continuity_audit": {
            "continuity": {"status": "broken", "checked": True, "passed": False},
        },
        "review_evidence": {"passed": True},
    })
    assert failures
    assert any(item["dimension"] == "continuity" for item in failures)


def test_worker_cannot_mark_canonical_v7_reviewed_when_continuity_failed(monkeypatch):
    from app.workers import tasks

    class Cursor:
        def fetchone(self):
            return None

    class Db:
        def __init__(self):
            self.statements = []

        def execute(self, sql, params=()):
            self.statements.append((" ".join(sql.split()), params))
            return Cursor()

        def commit(self):
            pass

        def close(self):
            pass

    db = Db()
    body = ["正文" + ("内容" * 900)]
    review = {
        "canonical_engine": "v7",
        "score": 95,
        "overall_score": 95,
        "dimensions": {"continuity": 95, "plot_logic": 95, "pacing": 95, "writing_quality": 95},
        "dimension_scores": {"consistency": 95, "character_voice": 95, "plot_logic": 95, "pacing": 95, "writing_quality": 95, "constraint_compliance": 95},
        "issues": [],
        "continuity": {"status": "broken", "checked": True, "passed": False},
        "final_continuity_audit": {"continuity": {"status": "broken", "checked": True, "passed": False}},
        "review_evidence": {"passed": True},
    }
    monkeypatch.setattr(tasks, "connect", lambda: db)
    monkeypatch.setattr(tasks, "_try_canonical_v7_review", lambda *args, **kwargs: review)

    result = tasks._review_and_finalize_chapter(
        "chapter-1", "novel-1", "project-1", 2, "chapter-key", "第二章", body, {"status": "clean"},
        max_rewrites=0,
    )

    assert result["accepted"] is False
    assert result["review_status"] == "needs_rewrite"
    assert any("status='needs_rewrite'" in sql for sql, _ in db.statements)
    assert not any("status='reviewed'" in sql for sql, _ in db.statements)
