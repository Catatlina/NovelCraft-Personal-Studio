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
