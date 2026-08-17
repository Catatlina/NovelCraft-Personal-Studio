from __future__ import annotations

import pytest

from app.v7.quality.writing_methodology import (
    build_writing_workflow_contract,
    register_external_evaluation,
    render_writing_methodology_contract,
    text_sha256,
    transition_workflow_status,
    validate_writing_workflow,
)


def _ready_brief() -> dict:
    return {
        "chapter_contract": {
            "core_problem": "主角必须在封锁前拿到证据",
            "observable_payoff": "证据在众人面前被投屏",
            "cost": "主角暴露身份并失去退路",
            "next_inevitable_event": "幕后人立即启动第二道封锁",
        },
        "causal_ledger": [
            {
                "event": "主角夺回硬盘",
                "knower": "主角知道硬盘在仓库，守卫只知道有人闯入",
                "motive": "监控显示硬盘将在十分钟后被转移",
                "cost": "主角暴露身份并受伤",
                "next_effect": "幕后人确认主角已经拿到证据",
            }
        ],
        "state_delta": {"changed": ["硬盘归主角"], "unchanged": ["封锁仍有效"]},
    }


def test_methodology_contract_is_fail_closed_until_five_columns_are_complete():
    pending = build_writing_workflow_contract(
        3,
        plot_brief={"must_accomplish": ["完成一次主动选择"]},
    )
    assert pending["status"] == "input_pending"
    assert pending["validation"]["passed"] is False
    assert "causal_ledger" in pending["validation"]["missing"]

    ready = build_writing_workflow_contract(3, plot_brief=_ready_brief())
    assert ready["status"] == "causal_ready"
    assert validate_writing_workflow(ready)["passed"] is True
    rendered = render_writing_methodology_contract(ready)
    assert "五列因果账本" in rendered
    assert "事件先于解释" in rendered
    assert "固定反转" in rendered


def test_methodology_preserves_unknowns_instead_of_inventing_state():
    workflow = build_writing_workflow_contract(1, plot_brief=_ready_brief())
    assert workflow["current_state"]["time"] == "unknown"
    assert workflow["current_state"]["location"] == "unknown"


def test_external_evaluation_is_bound_to_exact_text_and_real_score():
    text = "主角把证据按在投影台上。"
    evaluation = register_external_evaluation(
        text,
        {
            "provider": "zhuque",
            "scope": "chapter-1",
            "input_hash": text_sha256(text),
            "status": "completed",
            "human_score": 95.0,
            "suspected_ai_score": 5.0,
            "ai_feature_score": 0.0,
            "flagged_segments": [],
        },
    )
    assert evaluation["status"] == "external_95_5_0"
    assert evaluation["target_passed"] is True
    assert evaluation["input_hash"] == text_sha256(text)

    with pytest.raises(ValueError, match="input_hash"):
        register_external_evaluation(
            text + "改过了",
            {
                "provider": "zhuque",
                "scope": "chapter-1",
                "input_hash": text_sha256(text),
                "status": "completed",
                "human_score": 95.0,
                "suspected_ai_score": 5.0,
                "ai_feature_score": 0.0,
            },
        )


def test_workflow_status_transition_does_not_skip_external_gate():
    workflow = build_writing_workflow_contract(1, plot_brief=_ready_brief())
    transition_workflow_status(workflow, "drafted")
    transition_workflow_status(workflow, "causal_passed")
    transition_workflow_status(workflow, "external_pending")
    assert workflow["status"] == "external_pending"
    with pytest.raises(ValueError, match="invalid writing workflow transition"):
        transition_workflow_status(workflow, "published")


def test_external_evaluation_fails_closed_when_target_is_not_met():
    text = "主角把证据按在投影台上。"
    evaluation = register_external_evaluation(
        text,
        {
            "provider": "zhuque",
            "scope": "chapter-1",
            "input_hash": text_sha256(text),
            "status": "completed",
            "human_score": 0.0,
            "suspected_ai_score": 42.68,
            "ai_feature_score": 57.32,
        },
    )
    assert evaluation["status"] == "external_failed"
    assert evaluation["target_passed"] is False
