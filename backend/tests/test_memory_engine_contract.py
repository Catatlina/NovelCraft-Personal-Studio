import asyncio

from app.v7.engines.base import EngineResult
from app.v7.engines.memory_engine import MemoryEngine, normalize_memory_conflicts
from app.v7.quality.continuity import validate_transition_contract


class _Gateway:
    async def generate_json(self, *_args, **_kwargs):
        return {
            "data": {
                "character_updates": [
                    {
                        "key": "主角.伤势",
                        "summary": "左臂受伤",
                        "detail": "暂时无法发力",
                        "confidence": 0.9,
                        "evidence": "他抬不起左臂",
                    }
                ],
                "world_facts": [],
                "plot_events": [],
                "foreshadowing": [],
                "conflicts": [],
                "chapter_summary": "主角带伤离开",
            },
            "usage": {"tokens_input": 1, "tokens_output": 1, "cost": 0.0},
        }


def _execute_result(apply_updates: bool) -> EngineResult:
    engine = object.__new__(MemoryEngine)
    engine.ai_gateway = _Gateway()
    engine.record_usage = lambda _usage: None
    return asyncio.run(
        engine.execute(
            EngineResult(
                success=True,
                result={
                    "chapter_number": 1,
                    "run_id": "run-1",
                    "chapter_text": "他抬不起左臂。",
                    "existing_snapshot": {},
                    "apply_updates": apply_updates,
                },
            )
        )
    )


def test_memory_execute_preserves_dry_run_flag():
    result = _execute_result(False)

    assert result.success is True
    assert result.result["apply_updates"] is False


def test_memory_execute_keeps_commit_mode_enabled_when_requested():
    result = _execute_result(True)

    assert result.success is True
    assert result.result["apply_updates"] is True


def test_memory_conflict_normalizes_resolved_strategic_reveal_without_erasing_evidence():
    conflicts = normalize_memory_conflicts(
        [
            {
                "key": "季无咎的路线指令",
                "description": "季无咎表面让顾沉往北走，实际利用顾沉点灯",
                "severity": "high",
            }
        ]
    )

    assert conflicts[0]["conflict_type"] == "strategic_reveal"
    assert conflicts[0]["resolution_status"] == "resolved"
    assert conflicts[0]["original_severity"] == "high"
    assert conflicts[0]["severity"] == "medium"


def test_memory_conflict_recognizes_identity_and_setting_reveals():
    conflicts = normalize_memory_conflicts(
        [
            {
                "key": "灯中人身份",
                "description": "季无咎真名纪无咎，与灯中声音一字之差，现揭示为同一人",
                "severity": "high",
            },
            {
                "key": "命灯用途",
                "description": "已知命灯用于献祭，现揭示为封印天渊裂口",
                "severity": "high",
            },
        ]
    )

    assert all(item["conflict_type"] == "strategic_reveal" for item in conflicts)
    assert all(item["resolution_status"] == "resolved" for item in conflicts)
    assert all(item["severity"] == "medium" for item in conflicts)


def test_memory_conflict_downgrades_an_interrupted_plan_to_plot_evidence():
    conflicts = normalize_memory_conflicts(
        [
            {
                "key": "闭关计划",
                "description": "周衡计划闭关避劫，但林逸提前挑战，导致计划受挫。",
                "severity": "high",
            }
        ]
    )

    assert conflicts[0]["conflict_type"] == "plot_disruption"
    assert conflicts[0]["resolution_status"] == "resolved"
    assert conflicts[0]["original_severity"] == "high"
    assert conflicts[0]["severity"] == "medium"


def test_continuity_does_not_block_resolved_plot_disruption():
    result = validate_transition_contract(
        {
            "schema_version": "v2",
            "chapter_number": 1,
            "end_state": {"last_tail": "挑战", "summary": "计划被打断"},
            "next_chapter_bridge": "挑战",
            "state_delta": {},
            "open_threads": [],
        },
        chapter_number=1,
        state_conflicts=[
            {
                "key": "闭关计划",
                "description": "计划被提前挑战打断",
                "severity": "high",
                "conflict_type": "plot_disruption",
                "resolution_status": "resolved",
            }
        ],
    )

    assert result["passed"] is True
    assert result["issues"] == []


def test_unresolved_plot_disruption_remains_evidence_without_blocking():
    conflicts = normalize_memory_conflicts(
        [
            {
                "key": "第七层争夺",
                "description": "白面具人欲取第七层，苏长庚必须守护。",
                "severity": "high",
                "conflict_type": "plot_disruption",
                "resolution_status": "unresolved",
            }
        ]
    )

    result = validate_transition_contract(
        {
            "schema_version": "v2",
            "chapter_number": 9,
            "start_state": {"previous_transition_contract": {"chapter_number": 8}},
            "end_state": {"last_tail": "守护", "summary": "敌人留下威胁"},
            "next_chapter_bridge": "守护",
            "state_delta": {},
            "open_threads": [{"key": "第七层争夺"}],
        },
        chapter_number=9,
        previous_contract={"chapter_number": 8},
        state_conflicts=conflicts,
    )

    assert conflicts[0]["severity"] == "medium"
    assert conflicts[0]["resolution_status"] == "unresolved"
    assert result["passed"] is True


def test_memory_conflict_recognizes_untyped_open_pressure_as_plot_evidence():
    conflicts = normalize_memory_conflicts(
        [
            {
                "key": "封印时限",
                "description": "封印磨损加速，苏长庚离开后可能更快裂开，时间紧迫。",
                "severity": "high",
            }
        ]
    )

    assert conflicts[0]["conflict_type"] == "plot_disruption"
    assert conflicts[0]["resolution_status"] == "unresolved"
    assert conflicts[0]["original_severity"] == "high"
    assert conflicts[0]["severity"] == "medium"


def test_memory_conflict_treats_resource_cost_against_goal_as_plot_pressure():
    conflicts = normalize_memory_conflicts(
        [
            {
                "key": "主角寿元",
                "description": "寿元仅剩四十七年，与长期生存目标冲突",
                "severity": "high",
            }
        ]
    )

    assert conflicts[0]["conflict_type"] == "plot_disruption"
    assert conflicts[0]["resolution_status"] == "unresolved"
    assert conflicts[0]["original_severity"] == "high"
    assert conflicts[0]["severity"] == "medium"


def test_memory_conflict_normalizes_legacy_unresolved_plot_type():
    conflicts = normalize_memory_conflicts(
        [
            {
                "key": "敌人威胁",
                "description": "白面具人留下威胁，下一步可能袭击宗门。",
                "severity": "high",
                "conflict_type": "unresolved_plot",
                "resolution_status": "unresolved",
            }
        ]
    )

    assert conflicts[0]["conflict_type"] == "plot_disruption"
    assert conflicts[0]["resolution_status"] == "unresolved"
    assert conflicts[0]["severity"] == "medium"


def test_continuity_does_not_block_resolved_strategic_reveal():
    result = validate_transition_contract(
        {
            "schema_version": "v2",
            "chapter_number": 10,
            "start_state": {
                "previous_transition_contract": {"chapter_number": 9}
            },
            "end_state": {"last_tail": "入口", "summary": "摘要"},
            "next_chapter_bridge": "入口",
            "state_delta": {},
            "open_threads": [],
        },
        chapter_number=10,
        previous_contract={"chapter_number": 9},
        state_conflicts=[
            {
                "key": "路线指令",
                "description": "表面路线与实际意图不同",
                "severity": "high",
                "conflict_type": "strategic_reveal",
                "resolution_status": "resolved",
            }
        ],
    )

    assert result["passed"] is True
    assert result["issues"] == []


def test_continuity_still_blocks_unresolved_hard_conflict():
    result = validate_transition_contract(
        {
            "schema_version": "v2",
            "chapter_number": 10,
            "start_state": {
                "previous_transition_contract": {"chapter_number": 9}
            },
            "end_state": {"last_tail": "入口", "summary": "摘要"},
            "next_chapter_bridge": "入口",
            "state_delta": {},
            "open_threads": [],
        },
        chapter_number=10,
        previous_contract={"chapter_number": 9},
        state_conflicts=[
            {
                "key": "资源库存",
                "description": "已经消耗的灵石再次出现",
                "severity": "high",
                "conflict_type": "resource",
                "resolution_status": "unresolved",
            }
        ],
    )

    assert result["passed"] is False
    assert any(item["code"] == "state_conflict" for item in result["issues"])
