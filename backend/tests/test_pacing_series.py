"""V3 §11.2 Pacing Engine visualization — deterministic series builder."""

from app.services.pacing_series import build_pacing_series


def _row(seq=1, **meta_extra):
    meta = {"seq": seq}
    meta.update(meta_extra)
    return {"id": f"ch-{seq}", "title": f"第{seq}章", "meta": meta, "pace": None}


class TestBuildPacingSeries:
    def test_full_signals(self):
        rows = [
            {"id": "ch-1", "title": "第1章", "pace": 72,
             "meta": {"seq": 1, "review_score": 84,
                      "pacing_check": {"status": "pass", "sampled": True},
                      "reader_experience": {"status": "pass",
                                            "scores": {"expectation": 80, "payoff": 70}}}},
        ]
        series = build_pacing_series(rows)
        assert len(series) == 1
        point = series[0]
        assert point["chapter_id"] == "ch-1"
        assert point["seq"] == 1
        assert point["review_score"] == 84.0
        assert point["pace"] == 72.0
        assert point["pacing_status"] == "pass"
        assert point["pacing_score"] == 90.0
        assert point["reader_experience"] == {"expectation": 80.0, "payoff": 70.0}

    def test_chapter_without_data_yields_nones(self):
        series = build_pacing_series([_row(seq=3)])
        point = series[0]
        assert point["review_score"] is None
        assert point["pace"] is None
        assert point["pacing_status"] is None
        assert point["pacing_score"] is None
        assert point["reader_experience"] is None

    def test_status_mapping_and_clamp(self):
        rows = [
            _row(seq=1, pacing_check={"status": "warning"}),
            _row(seq=2, pacing_check={"status": "fail"}, review_score=150),
        ]
        series = build_pacing_series(rows)
        assert series[0]["pacing_score"] == 65.0
        assert series[1]["pacing_score"] == 35.0
        assert series[1]["review_score"] == 100.0  # clamped

    def test_garbage_rows_skipped_and_bad_seq(self):
        series = build_pacing_series(["junk", None, {"id": "x", "title": "t",
                                                     "meta": {"seq": "abc"}}])
        assert len(series) == 1
        assert series[0]["seq"] is None

    def test_empty_input(self):
        assert build_pacing_series([]) == []
        assert build_pacing_series(None) == []
