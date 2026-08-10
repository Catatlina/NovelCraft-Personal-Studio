from app.v7.quality.consistency_checker import ConsistencyChecker


def test_consistency_checker_fails_closed_on_missing_json():
    result = ConsistencyChecker(None)._parse_response("不是 JSON", "正文")

    assert result.passed is False
    assert result.score == 0.0
    assert result.issues[0]["severity"] == "严重"


def test_consistency_checker_fails_closed_on_incomplete_contract():
    result = ConsistencyChecker(None)._parse_response(
        '{"consistency_score": 95, "issues": [], "summary": "看起来没问题"}',
        "正文",
    )

    assert result.passed is False
    assert "必需字段" in result.issues[0]["description"]


def test_consistency_checker_high_issue_overrides_model_pass():
    result = ConsistencyChecker(None)._parse_response(
        '{"consistency_score": 95, "passed": true, "issues": [{"severity": "严重", "description": "地点跳变"}]}',
        "正文",
    )

    assert result.passed is False
