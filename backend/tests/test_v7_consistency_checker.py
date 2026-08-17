from app.v7.quality.consistency_checker import ConsistencyChecker


class _GatewayReturningUsageEnvelope:
    async def generate(self, prompt, **kwargs):
        assert '"must_accomplish"' in prompt
        assert kwargs["prompt_name"] == "v7.consistency_check"
        return {
            "text": '{"consistency_score": 95, "passed": true, "issues": [], "summary": "承接正常"}'
        }


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


def test_consistency_checker_serializes_plot_brief_and_parses_gateway_envelope():
    import asyncio

    result = asyncio.run(
        ConsistencyChecker(_GatewayReturningUsageEnvelope()).check(
            chapter_text="正文",
            chapter_number=2,
            chapter_outline={"must_accomplish": ["承接上一章"], "suggested_beats": []},
            previous_chapter_tail="上一章结尾",
            previous_transition_contract={"end_state": {"summary": "上一章"}},
        )
    )

    assert result.passed is True
    assert result.score == 95


def test_first_chapter_does_not_fail_for_missing_previous_chapter_input():
    import asyncio

    class _FirstChapterGateway:
        async def generate(self, prompt, **kwargs):
            return {
                "text": (
                    '{"consistency_score": 90, "passed": false, "issues": '
                    '[{"type":"衔接","severity":"严重",'
                    '"description":"上一章结尾状态为空，无法验证承接。",'
                    '"suggestion":"提供上一章结尾"}], "summary":"首章"}'
                )
            }

    result = asyncio.run(
        ConsistencyChecker(_FirstChapterGateway()).check(
            chapter_text="门缝里透出一线光。",
            chapter_number=1,
            chapter_outline={"must_accomplish": ["出现异常"]},
        )
    )

    assert result.passed is True
    assert result.issues == []
    assert "首章无上一章可承接" in result.summary
