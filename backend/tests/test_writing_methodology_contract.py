from __future__ import annotations

import pytest

from app.v7.quality.writing_methodology import (
    build_behavior_sample_query,
    build_model_adaptation_record,
    build_writing_workflow_contract,
    normalize_causal_audit,
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
            "human_score": 92.0,
            "suspected_ai_score": 8.0,
            "flagged_segments": [],
        },
    )
    assert evaluation["status"] == "external_90_plus"
    assert evaluation["input_hash"] == text_sha256(text)

    with pytest.raises(ValueError, match="input_hash"):
        register_external_evaluation(
            text + "改过了",
            {
                "provider": "zhuque",
                "scope": "chapter-1",
                "input_hash": text_sha256(text),
                "status": "completed",
                "human_score": 92.0,
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


def test_fact_card_and_behavior_contract_are_project_ready():
    workflow = build_writing_workflow_contract(2, plot_brief=_ready_brief())
    assert workflow["fact_card"]["schema_version"] == "fact-card-v1"
    assert workflow["validation"]["fact_card"]["passed"] is True
    assert "对抗" in build_behavior_sample_query({
        "chapter_type": "对抗",
        "pov_character": "主角",
        "payoff_contract": {"payoff_type": "反击"},
    })


def test_causal_audit_preserves_red_issue_and_repair_boundary():
    audit = normalize_causal_audit({
        "conclusion": "return_scene",
        "red_issues": [{"location": "第3段", "gap": "知情越界", "repair": "补可见证据"}],
        "repair_boundaries": ["仓库夺证事件单元"],
    })
    assert audit["schema_version"] == "causal-audit-v1"
    assert audit["red_issues"][0]["gap"] == "知情越界"
    assert audit["repair_boundaries"] == ["仓库夺证事件单元"]


def test_model_adaptation_record_is_explicit():
    record = build_model_adaptation_record(
        provider="deepseek",
        model="deepseek-chat",
        prompt_version="1.6.0",
        temperature=0.85,
        max_tokens=2400,
        behavior_sample_count=2,
    )
    assert record["schema_version"] == "model-adaptation-v1"
    assert record["parameters"]["temperature"] == 0.85
    assert record["behavior_sample_count"] == 2


def test_workflow_rebuild_preserves_generation_sample_and_model_provenance():
    seed = build_writing_workflow_contract(2, plot_brief=_ready_brief())
    seed["fact_card"]["behavior_samples"] = [{"id": "sample-1", "annotation": "主动选择"}]
    seed["model_adaptation"] = {"schema_version": "model-adaptation-v1", "model": "deepseek-chat"}
    rebuilt = build_writing_workflow_contract(
        2,
        plot_brief=_ready_brief(),
        writing_workflow=seed,
    )
    assert rebuilt["fact_card"]["behavior_samples"][0]["id"] == "sample-1"
    assert rebuilt["model_adaptation"]["model"] == "deepseek-chat"
