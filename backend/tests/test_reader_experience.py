"""V3 §11.1 reader-experience review dimension — deterministic helpers."""

from app.gateway import validate_task_output
from app.services.reader_experience import (
    READER_EXPERIENCE_KEYS,
    normalize_reader_experience,
    reader_experience_issues,
    summarize_reader_experience,
)


class TestNormalize:
    def test_full_block(self):
        rx = {"expectation": 80, "conflict": 75, "payoff": 70,
              "emotion_shift": 78, "worth_continuing": 82}
        out = normalize_reader_experience(rx)
        assert out == {k: float(v) for k, v in rx.items()}

    def test_clamps_out_of_range(self):
        out = normalize_reader_experience({"expectation": 150, "payoff": -5})
        assert out == {"expectation": 100.0, "payoff": 0.0}

    def test_ignores_unknown_and_non_numeric(self):
        out = normalize_reader_experience({"expectation": "high", "bogus": 90,
                                           "conflict": True, "payoff": 66})
        assert out == {"payoff": 66.0}

    def test_none_and_non_dict(self):
        assert normalize_reader_experience(None) is None
        assert normalize_reader_experience("x") is None
        assert normalize_reader_experience({}) is None


class TestSummarize:
    def test_all_strong_passes(self):
        rx = dict.fromkeys(READER_EXPERIENCE_KEYS, 80)
        summary = summarize_reader_experience(rx)
        assert summary["status"] == "pass"
        assert summary["weak_dimensions"] == []
        assert summary["avg"] == 80.0

    def test_weak_dimension_warns_not_blocks(self):
        rx = {"expectation": 80, "conflict": 40, "payoff": 55,
              "emotion_shift": 78, "worth_continuing": 82}
        summary = summarize_reader_experience(rx)
        assert summary["status"] == "warning"
        assert set(summary["weak_dimensions"]) == {"conflict", "payoff"}

    def test_missing_block_skips(self):
        summary = summarize_reader_experience(None)
        assert summary == {"status": "skip", "scores": None,
                           "weak_dimensions": [], "avg": None}


class TestIssues:
    def test_warning_renders_labels(self):
        summary = summarize_reader_experience({"expectation": 80, "conflict": 40,
                                               "payoff": 55, "emotion_shift": 78,
                                               "worth_continuing": 82})
        issues = reader_experience_issues(summary)
        assert len(issues) == 2
        assert any("冲突感" in i for i in issues)
        assert any("爽点" in i for i in issues)

    def test_pass_and_skip_render_nothing(self):
        assert reader_experience_issues(summarize_reader_experience(None)) == []
        assert reader_experience_issues(
            summarize_reader_experience(dict.fromkeys(READER_EXPERIENCE_KEYS, 90))) == []
        assert reader_experience_issues("junk") == []


class TestGatewayContract:
    BASE = {"score": 85,
            "dimensions": {"prose": 85, "plot": 80, "character_ooc": 90,
                           "world_conflict": 85, "logic_consistency": 80,
                           "pace": 75, "foreshadowing": 70},
            "issues": ["问题"]}

    def test_legacy_output_without_block_still_validates(self):
        out = validate_task_output("review_7dim", dict(self.BASE))
        assert out["reader_experience"] is None

    def test_output_with_block_validates(self):
        payload = dict(self.BASE)
        payload["reader_experience"] = {"expectation": 80, "conflict": 75,
                                        "payoff": 70, "emotion_shift": 78,
                                        "worth_continuing": 82}
        out = validate_task_output("review_7dim", payload)
        assert out["reader_experience"]["payoff"] == 70
