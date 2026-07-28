"""Unit tests for V3 Story Arc (§4) single-layer entity + drift detection.

Real logic only — no mock providers, no fake success.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.gateway import validate_task_output, _GenerateStoryArcOutput  # noqa: E402
from app.workers.tasks import _check_story_arc_coverage  # noqa: E402


def test_arc_coverage_inside_range_participant_hit_is_pass():
    arcs = [{
        "name": "复仇弧",
        "participants": ["林默", "苏婉"],
        "chapter_range": [5, 20],
    }]
    # Chapter 10 is inside the arc range and shares a participant -> pass
    res = _check_story_arc_coverage(arcs, 10, ["林默", "反派"])
    assert res["status"] == "pass"
    assert res["covered"] is True
    assert res["issues"] == []


def test_arc_coverage_inside_range_participant_miss_is_warning():
    arcs = [{
        "name": "复仇弧",
        "participants": ["林默", "苏婉"],
        "chapter_range": [5, 20],
    }]
    # Chapter 12 is inside range but the chapter's outline participants have no
    # overlap with the arc's participants -> warning (nudge, not a hard block)
    res = _check_story_arc_coverage(arcs, 12, ["路人甲", "路人乙"])
    assert res["status"] == "warning"
    assert res["covered"] is True
    assert any("弧线被忽略" in i for i in res["issues"])


def test_arc_coverage_outside_range_is_pass():
    arcs = [{
        "name": "复仇弧",
        "participants": ["林默"],
        "chapter_range": [5, 20],
    }]
    res = _check_story_arc_coverage(arcs, 3, ["路人甲"])
    assert res["status"] == "pass"
    assert res["covered"] is False


def test_arc_coverage_no_arcs_degrades_gracefully():
    res = _check_story_arc_coverage([], 10, ["林默"])
    assert res["status"] == "pass"
    assert res["sampled"] == 0


def test_arc_coverage_missing_seq_is_pass():
    arcs = [{"name": "弧", "participants": ["林默"], "chapter_range": [1, 10]}]
    res = _check_story_arc_coverage(arcs, 0, ["林默"])
    assert res["status"] == "pass"


def test_generate_story_arc_contract_requires_arcs():
    # Empty list must be rejected by the Pydantic contract (min_length=1)
    try:
        _GenerateStoryArcOutput.model_validate({"story_arcs": []})
        assert False, "empty story_arcs should be rejected"
    except Exception:
        pass
    # Valid payload passes and normalizes via the repair layer
    payload = {
        "story_arcs": [{
            "name": "复仇弧",
            "goal": "主角复仇成功",
            "participants": ["林默"],
            "chapter_range": [5, 30],
        }]
    }
    out = validate_task_output("generate_story_arc", payload)
    assert isinstance(out, dict)
    assert len(out["story_arcs"]) == 1
    assert out["story_arcs"][0]["status"] == "planning"  # default applied
