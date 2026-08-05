import asyncio

from app.v7.engines.base import EngineResult
from app.v7.engines.memory_engine import MemoryEngine


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
