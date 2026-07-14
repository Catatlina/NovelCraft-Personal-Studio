"""Contracts for AI-backed ranking market analysis (NC-SC-002).

The ranking analyzer is not allowed to turn a provider outage into plausible-looking
static market advice.  These tests also keep copyrighted source material out of the
model request: the gateway receives aggregates and short catalogue metadata only.
"""
from __future__ import annotations

import json

import pytest
from fastapi import HTTPException


REQUIRED_OUTPUT_KEYS = {
    "market_signals",
    "audience",
    "title_patterns",
    "pacing",
    "originality_constraints",
    "topic_candidates",
}


def _items():
    return [
        {
            "rank_no": 1,
            "title": "末日经营指南",
            "author": "甲",
            "category": "科幻",
            "metrics": {"heat": 9800},
            "body": "NEVER_SEND_FULL_BOOK_BODY_" * 200,
        },
        {
            "rank_no": 2,
            "title": "我在废土开客栈",
            "author": "乙",
            "category": "科幻",
            "metrics": {"heat": 8700},
            "body": "NEVER_SEND_FULL_BOOK_BODY_" * 200,
        },
    ]


def _provider_output():
    return {
        "market_signals": [{"signal": "废土经营题材升温", "evidence": "top2 同类占比"}],
        "audience": {"primary": "偏好成长与经营反馈的读者", "needs": ["即时反馈"]},
        "title_patterns": [{"pattern": "身份场景 + 强动作", "examples": ["仅抽象结构"]}],
        "pacing": {"opening": "前三章建立危机与经营目标", "retention_hooks": ["阶段结算"]},
        "originality_constraints": ["不得复用样本人物、设定、专名或情节"],
        "topic_candidates": [
            {
                "title": "雾城修理铺",
                "premise": "灾后城市中，修理师用旧物记忆修复社区关系。",
                "genre": "科幻",
                "market_score": 82,
            }
        ],
    }


class _Cursor:
    def __init__(self, one=None, many=None):
        self._one = one
        self._many = many or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _AnalysisDb:
    def __init__(self, *, existing=None):
        self.existing = existing
        self.statements: list[tuple[str, tuple]] = []
        self.committed = False
        self.closed = False

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.statements.append((compact, params))
        if "FROM ranking_snapshots WHERE id=" in compact:
            return _Cursor(one={"id": "snapshot-1", "project_id": "project-1", "status": "succeeded"})
        if "FROM market_analyses WHERE snapshot_id=" in compact:
            return _Cursor(one=self.existing)
        if "FROM ranking_items WHERE snapshot_id=" in compact:
            return _Cursor(many=_items())
        if "FROM topic_candidates WHERE analysis_id=" in compact:
            return _Cursor(many=[])
        return _Cursor()

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_analysis_input_is_structured_aggregate_without_full_book_text():
    from app.api.v1.ranking import _build_market_analysis_variables

    variables = _build_market_analysis_variables(_items())

    assert isinstance(variables, dict)
    assert variables["sample_size"] == 2
    assert variables.get("category_counts")
    assert variables.get("title_samples")
    serialized = json.dumps(variables, ensure_ascii=False)
    assert "NEVER_SEND_FULL_BOOK_BODY" not in serialized
    assert not ({"body", "content", "full_text", "chapter_text"} & set(variables))


def test_analysis_output_schema_is_strict_and_complete():
    from app.api.v1.ranking import _validate_market_analysis_output

    validated = _validate_market_analysis_output(_provider_output())
    assert REQUIRED_OUTPUT_KEYS <= validated.keys()
    assert validated["topic_candidates"][0]["target_audience"] == "偏好成长与经营反馈的读者"
    assert validated["topic_candidates"][0]["market_evidence"] == ["top2 同类占比"]
    assert validated["topic_candidates"][0]["originality_notes"]

    legacy_real_shape = _provider_output()
    legacy_real_shape.pop("pacing")
    legacy_real_shape.pop("originality_constraints")
    normalized = _validate_market_analysis_output(legacy_real_shape)
    assert normalized["pacing"] == {}
    assert normalized["originality_constraints"]

    duplicate = _provider_output()
    duplicate["topic_candidates"][0]["title"] = "末日经营指南"
    with pytest.raises(ValueError, match="duplicates"):
        _validate_market_analysis_output(duplicate, ["末日经营指南"])


def test_analysis_uses_gateway_contract_and_persists_schema(monkeypatch):
    from app.api.v1 import ranking

    db = _AnalysisDb()
    calls = []
    monkeypatch.setattr(ranking, "connect", lambda: db)
    monkeypatch.setattr(ranking, "require_member", lambda *_args, **_kwargs: None)

    def fake_complete(**kwargs):
        calls.append(kwargs)
        return _provider_output()

    monkeypatch.setattr(ranking, "complete", fake_complete)
    response = ranking.analyze_snapshot("snapshot-1", {"id": "user-1"})
    data = response["data"]

    assert len(calls) == 1
    call = calls[0]
    assert call["task_type"] == "ranking_market_analysis"
    assert call["prompt_name"] == "ranking.market_analysis"
    assert call["project_id"] == "project-1"
    # Per-attempt mutation id (…:0 first try) so a schema-retry regenerates
    # instead of replaying the same invalid output from the ledger.
    assert call["client_mutation_id"] == "ranking-analysis:snapshot-1:0"
    assert "NEVER_SEND_FULL_BOOK_BODY" not in json.dumps(call["variables"], ensure_ascii=False)
    assert REQUIRED_OUTPUT_KEYS <= data.keys()
    assert REQUIRED_OUTPUT_KEYS <= _provider_output().keys()
    assert db.committed and db.closed


def test_same_snapshot_is_idempotent_and_does_not_call_provider(monkeypatch):
    from app.api.v1 import ranking

    output = _provider_output()
    existing = {
        "id": "analysis-1",
        "snapshot_id": "snapshot-1",
        "status": "succeeded",
        "summary": "已有分析",
        "signals": output,
    }
    db = _AnalysisDb(existing=existing)
    monkeypatch.setattr(ranking, "connect", lambda: db)
    monkeypatch.setattr(ranking, "require_member", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        ranking,
        "complete",
        lambda **_kwargs: pytest.fail("idempotent replay must not call the provider"),
    )

    response = ranking.analyze_snapshot("snapshot-1", {"id": "user-1"})

    assert response["data"]["analysis_id"] == "analysis-1"
    assert response["data"]["status"] == "already_analyzed"
    assert not any(sql.startswith("INSERT INTO market_analyses") for sql, _ in db.statements)
    assert db.closed


def test_provider_failure_is_explicit_and_never_fabricates_success(monkeypatch):
    from app.api.v1 import ranking
    from app.gateway import ProviderError

    db = _AnalysisDb()
    monkeypatch.setattr(ranking, "connect", lambda: db)
    monkeypatch.setattr(ranking, "require_member", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        ranking,
        "complete",
        lambda **_kwargs: (_ for _ in ()).throw(ProviderError("provider unavailable")),
    )

    with pytest.raises(HTTPException) as exc_info:
        ranking.analyze_snapshot("snapshot-1", {"id": "user-1"})

    assert exc_info.value.status_code in {502, 503}
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "MARKET_ANALYSIS_PROVIDER_FAILED"
    assert detail["status"] == "failed"
    writes = " ".join(sql for sql, _ in db.statements)
    assert "market_analyses" in writes
    assert "topic_candidates" not in writes
    assert "身份反差与成长" not in writes
    assert db.committed and db.closed
