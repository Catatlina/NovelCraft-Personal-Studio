from __future__ import annotations

import importlib.util
import json
import csv
from pathlib import Path


def _load_harness():
    path = Path(__file__).parents[2] / "scripts" / "v6v7_20_chapter_quality.py"
    spec = importlib.util.spec_from_file_location("v6v7_quality_harness", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_dual_track_automated_metrics_and_blind_packet_are_deterministic():
    harness = _load_harness()
    old = [
        {
            "chapter_number": i,
            "text": f"旧链第{i}章，门仍然没有打开。",
            "status": "reviewed",
            "review_score": 86,
            "transition_contract": {"chapter_number": i},
        }
        for i in range(1, 4)
    ]
    new = [
        {
            "chapter_number": i,
            "text": f"新链第{i}章，门仍然没有打开。",
            "status": "reviewed",
            "review_score": 88,
            "transition_contract": {"chapter_number": i},
        }
        for i in range(1, 4)
    ]

    packet_a, mapping_a = harness._blind_packet(old, new)
    packet_b, mapping_b = harness._blind_packet(old, new)

    assert harness._metrics(new)["chapters"] == 3
    assert harness._metrics(new)["average_review_score"] == 88.0
    assert packet_a == packet_b
    assert mapping_a == mapping_b
    assert all("old" not in json.dumps(case, ensure_ascii=False) for case in packet_a)


def test_blind_summary_requires_two_distinct_reviewer_ids(tmp_path):
    harness = _load_harness()
    packet = [{"case_id": "case-1", "chapter_number": 1}]
    private_map = {"case-1": "sample_a=new"}
    score_path = tmp_path / "scores.csv"
    fields = ["case_id", "reviewer_id"] + [
        f"{sample}_{dimension}"
        for sample in ("sample_a", "sample_b")
        for dimension in harness.KEY_DIMENSIONS
    ]
    with score_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for reviewer in ("reviewer-a", "reviewer-a"):
            row = {"case_id": "case-1", "reviewer_id": reviewer}
            for sample in ("sample_a", "sample_b"):
                for dimension in harness.KEY_DIMENSIONS:
                    row[f"{sample}_{dimension}"] = 90
            writer.writerow(row)

    summary = harness._manual_summary(packet, score_path, private_map)
    assert summary["status"] == "pending"
    assert summary["cases_with_two_reviewers"] == 0
    assert summary["distinct_reviewer_count"] == 0
