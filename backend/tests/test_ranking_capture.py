"""Capture confidence and external metadata-validation contracts (NC-SC-001)."""
from __future__ import annotations

import json

import pytest


def test_browser_capture_preserves_provenance_and_confidence(tmp_path):
    from app.services.ranking_capture import load_capture_artifact

    path = tmp_path / "fanqie.json"
    path.write_text(json.dumps({
        "source": "fanqie", "status": "succeeded", "collector": "browser_ocr",
        "captured_at": "2026-07-11T00:00:00Z",
        "evidence": {"screenshot": "fanqie.png"},
        "items": [{"rank": 1, "title": "测试书", "author": "甲", "confidence": 0.94}],
    }), encoding="utf-8")

    items = load_capture_artifact(path, "fanqie").as_adapter_items()
    assert items[0]["collector"] == "browser_ocr"
    assert items[0]["confidence"] == 0.94
    assert items[0]["evidence"]["screenshot"] == "fanqie.png"


def test_challenge_capture_is_an_explicit_failure(tmp_path):
    from app.services.ranking_capture import load_capture_artifact

    path = tmp_path / "qidian.json"
    path.write_text(json.dumps({"source": "qidian", "status": "user_action_required", "items": []}), encoding="utf-8")
    item = load_capture_artifact(path, "qidian").as_adapter_items()[0]
    assert item["degraded"] is True
    assert item["capture_status"] == "user_action_required"


def test_manual_csv_import_requires_rank_and_title(tmp_path):
    from app.services.ranking_capture import import_ranking_file

    valid = tmp_path / "ranking.csv"
    valid.write_text("rank,title,author\n1,合法公开元数据,作者甲\n", encoding="utf-8")
    assert import_ranking_file(valid)[0]["collector"] == "manual_import"

    invalid = tmp_path / "invalid.csv"
    invalid.write_text("rank,author\n1,作者甲\n", encoding="utf-8")
    with pytest.raises(ValueError):
        import_ranking_file(invalid)


def test_capture_rejects_unapproved_source(tmp_path):
    from app.services.ranking_capture import load_capture_artifact

    path = tmp_path / "unknown.json"
    path.write_text(json.dumps({"source": "pirated_library", "items": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported capture source"):
        load_capture_artifact(path)


def test_low_confidence_capture_requires_review_instead_of_succeeded():
    from app.api.v1.ranking import _ranking_snapshot_status

    items = [
        {"rank_no": 1, "title": "OCR 模糊书名", "metrics": {"confidence": 0.49}},
        {"rank_no": 2, "title": "清晰书名", "metrics": {"confidence": 0.94}},
    ]

    assessment = _ranking_snapshot_status(items, min_confidence=0.70)

    assert assessment["status"] == "needs_review"
    assert assessment["min_confidence"] == 0.49
    assert assessment["threshold"] == 0.70
    assert assessment["low_confidence_count"] == 1


def test_high_confidence_capture_can_succeed():
    from app.api.v1.ranking import _ranking_snapshot_status

    assessment = _ranking_snapshot_status(
        [{"rank_no": 1, "title": "清晰书名", "metrics": {"confidence": 0.91}}],
        min_confidence=0.70,
    )
    assert assessment["status"] == "succeeded"
    assert assessment["low_confidence_count"] == 0


def test_open_library_not_found_is_validation_evidence_not_invalid_metadata(monkeypatch):
    from app.services import ranking_capture

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"numFound": 0, "docs": []}).encode()

    monkeypatch.setattr(ranking_capture.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())

    result = ranking_capture.validate_with_open_library("仅在中文平台连载的作品", "作者")

    assert result == {
        "provider": "open_library",
        "status": "not_found",
        "matches": [],
    }
    assert result["status"] != "invalid"


def test_metadata_validation_result_remains_traceable_after_normalization():
    from app.services.ranking_adapter import normalize_ranking_items
    from app.services.ranking_capture import CaptureResult

    validation = {"provider": "open_library", "status": "not_found", "matches": []}
    capture = CaptureResult(
        source="manual",
        status="succeeded",
        items=[{"rank": 1, "title": "本土平台作品", "author": "作者", "confidence": 0.93}],
        evidence={"collector": "manual_import", "metadata_validation": validation},
    )

    normalized = normalize_ranking_items("manual", capture.as_adapter_items())

    assert len(normalized) == 1
    evidence = normalized[0]["metrics"]["evidence"]
    assert evidence["metadata_validation"] == validation
    assert normalized[0]["metrics"]["confidence"] == 0.93


@pytest.mark.parametrize(
    ("item", "validation", "expected"),
    [
        ({"title": "同名书", "author": "作者甲"}, {"status": "matched", "matches": [
            {"title": "同名书", "author_name": ["作者甲"]}]}, "confirmed"),
        ({"title": "同名书", "author": ""}, {"status": "matched", "matches": [
            {"title": "同名书", "author_name": ["作者甲"]}]}, "partial_match"),
        ({"title": "同名书", "author": "作者甲"}, {"status": "matched", "matches": [
            {"title": "同名书", "author_name": ["作者乙"]},
            {"title": "同名书", "author_name": ["作者丙"]}]}, "ambiguous"),
        ({"title": "同名书", "author": "作者甲"}, {"status": "matched", "matches": [
            {"title": "同名书", "author_name": ["作者乙"]}]}, "conflict"),
        ({"title": "本土书", "author": "作者"}, {"status": "not_found", "matches": []}, "not_found"),
        ({"title": "本土书", "author": "作者"}, {"status": "unavailable", "matches": []}, "unavailable"),
    ],
)
def test_metadata_validation_classification_keeps_distinct_outcomes(item, validation, expected):
    from app.api.v1.ranking import _classify_metadata_validation

    status, evidence = _classify_metadata_validation(item, {"provider": "open_library", **validation})
    assert status == expected
    assert evidence["provider"] == "open_library"
    if expected == "conflict":
        assert evidence["conflicts"][0]["field"] == "author"


def test_capture_migration_separates_ingestion_capture_and_validation_state():
    from pathlib import Path

    migration = Path(__file__).resolve().parents[1] / "alembic/versions/e16a42c731d9_ranking_capture_and_validation.py"
    sql = migration.read_text(encoding="utf-8")
    assert "capture_status" in sql
    assert "validation_summary" in sql
    assert "metadata_status" in sql
    assert "CASE WHEN status='failed' THEN 'failed' ELSE 'succeeded' END" in sql
