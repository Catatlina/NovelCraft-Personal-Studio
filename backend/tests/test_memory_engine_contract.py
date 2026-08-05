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
