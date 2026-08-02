from __future__ import annotations

import importlib.util
import json
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
