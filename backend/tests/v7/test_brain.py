"""
V7 Novel Brain Core Tests
==========================

Tests for the Novel Brain subsystems (``app/v7/brain``).

All brain subsystems are constructed as ``Subsystem(db, novel_id)`` and expose
``async`` methods that return plain ``dict`` / ``list[dict]`` payloads (never
ORM instances). These tests run against a real PostgreSQL database through the
async ``db_session`` fixture; ``asyncio_mode = "auto"`` means no
``@pytest.mark.asyncio`` decorators are needed.

CONFIDENCE GATING — ACTUAL BEHAVIOUR
------------------------------------
``StoryStateManager`` documents four tiers, but the implementation gates on a
single ``confidence_threshold`` (0.7) plus a hard 0.5 discard floor. The
``hard_threshold=0.9`` parameter is accepted and never used, so 0.7-0.9 is NOT
flagged for review. Tests below assert the real behaviour and mark the gap.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.v7.brain.state_manager import StoryStateManager
from app.v7.brain.goal_system import GoalSystem
from app.v7.brain.constraint_system import ConstraintSystem
from app.v7.brain.version_control import VersionControl
from app.v7.brain.novel_brain import NovelBrain
from app.v7.repositories.state import StoryStateRepository


# ---------------------------------------------------------------------------
# StoryStateManager
# ---------------------------------------------------------------------------
class TestStoryStateManager:
    async def test_update_state_very_high_confidence_creates(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        """Tier 1 (>= 0.9): stored immediately, no review flag."""
        manager = StoryStateManager(db_session, novel_id)

        result = await manager.update_state(
            "character", "protagonist.name", {"name": "张三"}, 0.95, source="test"
        )

        assert result["action"] == "created"
        assert result["confidence"] == 0.95
        assert result["state"]["value"] == {"name": "张三"}
        assert result["state"]["confidence"] == 0.95
        assert result["state"]["version"] == 1
        assert result["state"]["is_pending_review"] is False

    async def test_update_state_high_confidence_updates_existing(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        """Tier 2 (>= 0.7 with an existing row): in-place update + version bump."""
        manager = StoryStateManager(db_session, novel_id)
        await manager.update_state(
            "character", "protagonist.name", {"name": "张三"}, 0.95, source="test"
        )

        result = await manager.update_state(
            "character", "protagonist.name", {"name": "李四"}, 0.75, source="test"
        )

        assert result["action"] == "updated"
        assert result["state"]["value"] == {"name": "李四"}
        assert result["state"]["version"] == 2
        # GAP(prod): the docstring promises 0.7-0.9 is "flagged for review", but
        # ``hard_threshold`` is never applied — see report.
        assert result["state"]["is_pending_review"] is False

    async def test_update_state_low_confidence_pending_review(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        """Tier 3 (0.5 <= c < 0.7): persisted but held for human review."""
        manager = StoryStateManager(db_session, novel_id)

        result = await manager.update_state(
            "character", "protagonist.name", {"name": "张三"}, 0.6, source="test"
        )

        assert result["action"] == "pending_review"
        assert result["state"]["is_pending_review"] is True
        assert result["state"]["confidence"] == 0.6

    async def test_update_state_very_low_confidence_discarded(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        """Tier 4 (< 0.5): dropped entirely, nothing is written."""
        manager = StoryStateManager(db_session, novel_id)

        result = await manager.update_state(
            "character", "protagonist.name", {"name": "张三"}, 0.4, source="test"
        )

        assert result["action"] == "discarded"
        assert result["state"] is None
        assert result["confidence"] == 0.4
        assert "0.5" in result["reason"]

        assert await manager.get_state("character", "protagonist.name") is None
        assert await manager.list_states("character") == []

    async def test_discard_does_not_overwrite_existing_state(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        manager = StoryStateManager(db_session, novel_id)
        await manager.update_state("world", "capital", {"name": "洛阳"}, 0.95)

        result = await manager.update_state("world", "capital", {"name": "垃圾"}, 0.1)

        assert result["action"] == "discarded"
        kept = await manager.get_state("world", "capital")
        assert kept["value"] == {"name": "洛阳"}
        assert kept["confidence"] == 0.95

    async def test_discard_records_warning_event(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        manager = StoryStateManager(db_session, novel_id)
        await manager.update_state("character", "x", {"a": 1}, 0.2)

        events = await manager.event_repo.list_by_novel(novel_id)
        assert [e.event_type for e in events] == ["state_update_discarded"]
        assert events[0].severity == "warning"
        assert events[0].event_data["confidence"] == 0.2

    async def test_update_state_records_change_and_event(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        manager = StoryStateManager(db_session, novel_id)
        run_id = uuid.uuid4()

        result = await manager.update_state(
            "character",
            "protagonist.name",
            {"name": "张三"},
            0.95,
            source="ai_extracted",
            source_run_id=run_id,
            reason="首次抽取",
        )
        state_id = uuid.UUID(result["state"]["id"])

        changes = await manager.get_state_changes(state_id)
        assert len(changes) == 1
        assert changes[0]["change_type"] == "create"
        assert changes[0]["new_value"] == {"name": "张三"}
        assert changes[0]["old_value"] is None
        assert changes[0]["reason"] == "首次抽取"

        events = await manager.event_repo.list_by_novel(novel_id)
        assert [e.event_type for e in events] == ["state_created"]
        assert events[0].source_run_id == run_id

    async def test_pending_review_event_is_warning(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        manager = StoryStateManager(db_session, novel_id)
        await manager.update_state("character", "x", {"a": 1}, 0.55)

        events = await manager.event_repo.list_by_novel(novel_id)
        assert [e.event_type for e in events] == ["state_pending_review"]
        assert events[0].severity == "warning"

    async def test_custom_confidence_threshold(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        manager = StoryStateManager(db_session, novel_id)

        result = await manager.update_state(
            "character", "x", {"a": 1}, 0.55, confidence_threshold=0.5
        )
        assert result["action"] == "created"
        assert result["state"]["is_pending_review"] is False

    async def test_get_state(self, db_session: AsyncSession, novel_id: uuid.UUID):
        manager = StoryStateManager(db_session, novel_id)
        assert await manager.get_state("character", "missing") is None

        await manager.update_state(
            "character", "protagonist.name", {"name": "张三"}, 0.95, source="human_set"
        )

        state = await manager.get_state("character", "protagonist.name")
        assert state == {
            "value": {"name": "张三"},
            "confidence": 0.95,
            "version": 1,
            "source": "human_set",
            "is_pending_review": False,
        }

    async def test_list_states(self, db_session: AsyncSession, novel_id: uuid.UUID):
        manager = StoryStateManager(db_session, novel_id)
        for i in range(3):
            await manager.update_state("character", f"char_{i}", {"i": i}, 0.9)
        await manager.update_state("plot", "beat_0", {"i": 0}, 0.9)

        chars = await manager.list_states("character")
        assert len(chars) == 3
        assert {c["key"] for c in chars} == {"char_0", "char_1", "char_2"}
        assert all(c["updated_at"] is not None for c in chars)

        assert len(await manager.list_states("plot")) == 1
        assert await manager.list_states("world") == []
        assert len(await manager.list_states("character", limit=2)) == 2

    async def test_approve_state(self, db_session: AsyncSession, novel_id: uuid.UUID):
        manager = StoryStateManager(db_session, novel_id)
        pending = await manager.update_state("character", "p", {"name": "张三"}, 0.6)
        assert pending["action"] == "pending_review"
        state_id = uuid.UUID(pending["state"]["id"])

        approved = await manager.approve_state(state_id, reason="人工确认")

        assert approved["id"] == str(state_id)
        assert approved["is_pending_review"] is False
        assert approved["confidence"] == 0.9  # boosted on approval

        assert await manager.get_pending_review() == []

        changes = await manager.get_state_changes(state_id)
        assert "approve" in {c["change_type"] for c in changes}
        approve_change = next(c for c in changes if c["change_type"] == "approve")
        assert approve_change["reason"] == "人工确认"
        assert approve_change["source"] == "human"

        types = {
            e.event_type for e in await manager.event_repo.list_by_novel(novel_id)
        }
        assert "state_approved" in types

    async def test_approve_state_keeps_higher_confidence(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        manager = StoryStateManager(db_session, novel_id)
        created = await manager.update_state("character", "p", {"n": 1}, 0.97)
        state_id = uuid.UUID(created["state"]["id"])

        approved = await manager.approve_state(state_id)
        assert approved["confidence"] == 0.97

    async def test_approve_missing_state_raises(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        manager = StoryStateManager(db_session, novel_id)
        with pytest.raises(ValueError):
            await manager.approve_state(uuid.uuid4())

    async def test_reject_state(self, db_session: AsyncSession, novel_id: uuid.UUID):
        manager = StoryStateManager(db_session, novel_id)
        pending = await manager.update_state("character", "p", {"name": "张三"}, 0.6)
        state_id = uuid.UUID(pending["state"]["id"])

        rejected = await manager.reject_state(
            state_id, user_id=uuid.uuid4(), reason="测试拒绝"
        )

        assert rejected["id"] == str(state_id)
        assert rejected["is_active"] is False
        # deactivated states disappear from the active lookup
        assert await manager.get_state("character", "p") is None
        assert await manager.list_states("character") == []

        events = await manager.event_repo.list_by_novel(novel_id)
        rejected_events = [e for e in events if e.event_type == "state_rejected"]
        assert len(rejected_events) == 1
        assert rejected_events[0].severity == "warning"
        assert rejected_events[0].event_data["reason"] == "测试拒绝"

    async def test_get_pending_review(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        manager = StoryStateManager(db_session, novel_id)
        for i in range(3):
            await manager.update_state("character", f"char_{i}", {"i": i}, 0.6)
        for i in range(2):
            await manager.update_state("character", f"auto_{i}", {"i": i}, 0.95)

        pending = await manager.get_pending_review()
        assert len(pending) == 3
        assert {p["key"] for p in pending} == {"char_0", "char_1", "char_2"}
        assert all(p["type"] == "character" for p in pending)
        assert all(p["created_at"] is not None for p in pending)

        assert len(await manager.get_pending_review(limit=2)) == 2

    async def test_state_change_history_accumulates(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        manager = StoryStateManager(db_session, novel_id)

        first = await manager.update_state(
            "character", "protagonist.name", {"name": "张三"}, 0.95
        )
        state_id = uuid.UUID(first["state"]["id"])

        await manager.update_state(
            "character", "protagonist.name", {"name": "李四"}, 0.95
        )

        changes = await manager.get_state_changes(state_id)
        assert len(changes) == 2
        by_type = {c["change_type"] for c in changes}
        assert by_type == {"create", "update"}

        update_change = next(c for c in changes if c["change_type"] == "update")
        assert update_change["old_value"] == {"name": "张三"}
        assert update_change["new_value"] == {"name": "李四"}
        assert update_change["old_confidence"] == 0.95

    async def test_manager_is_scoped_to_its_novel(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        other_novel = uuid.uuid4()
        mine = StoryStateManager(db_session, novel_id)
        theirs = StoryStateManager(db_session, other_novel)

        await mine.update_state("character", "shared_key", {"who": "mine"}, 0.95)
        await theirs.update_state("character", "shared_key", {"who": "theirs"}, 0.95)

        assert (await mine.get_state("character", "shared_key"))["value"] == {
            "who": "mine"
        }
        assert (await theirs.get_state("character", "shared_key"))["value"] == {
            "who": "theirs"
        }


# ---------------------------------------------------------------------------
# GoalSystem
# ---------------------------------------------------------------------------
class TestGoalSystem:
    async def test_create_goal(self, db_session: AsyncSession, novel_id: uuid.UUID):
        system = GoalSystem(db_session, novel_id)

        goal = await system.create_goal(
            "plot",
            "主线剧情",
            description="完成主线剧情",
            target_chapter=100,
            priority=90,
            confidence=0.95,
            metadata={"arc": "A"},
        )

        assert uuid.UUID(goal["id"])
        assert goal["name"] == "主线剧情"
        assert goal["type"] == "plot"
        assert goal["description"] == "完成主线剧情"
        assert goal["status"] == "pending"
        assert goal["progress"] == 0.0
        assert goal["target_chapter"] == 100
        assert goal["completed_chapter"] is None
        assert goal["priority"] == 90
        assert goal["confidence"] == 0.95
        assert goal["parent_goal_id"] is None

        events = await system.event_repo.list_by_novel(novel_id)
        assert [e.event_type for e in events] == ["goal_created"]

    async def test_list_goals_with_filters(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        system = GoalSystem(db_session, novel_id)
        await system.create_goal("plot", "A", goal_order=1)
        await system.create_goal("plot", "B", goal_order=0)
        await system.create_goal("character", "C", goal_order=2)

        # ordered by goal_order asc
        assert [g["name"] for g in await system.list_goals()] == ["B", "A", "C"]
        assert [g["name"] for g in await system.list_goals(goal_type="plot")] == [
            "B",
            "A",
        ]
        assert len(await system.list_goals(status="pending")) == 3
        assert await system.list_goals(status="completed") == []
        assert len(await system.list_goals(limit=1)) == 1

    async def test_update_goal(self, db_session: AsyncSession, novel_id: uuid.UUID):
        system = GoalSystem(db_session, novel_id)
        goal = await system.create_goal("plot", "旧名")

        updated = await system.update_goal(
            uuid.UUID(goal["id"]), {"goal_name": "新名", "status": "in_progress"}
        )

        assert updated["name"] == "新名"
        assert updated["status"] == "in_progress"

        types = [e.event_type for e in await system.event_repo.list_by_novel(novel_id)]
        assert "goal_updated" in types

    async def test_update_progress(self, db_session: AsyncSession, novel_id: uuid.UUID):
        system = GoalSystem(db_session, novel_id)
        goal = await system.create_goal("plot", "测试目标")
        goal_id = uuid.UUID(goal["id"])

        half = await system.update_progress(goal_id, 0.5)
        assert half["progress"] == 0.5
        assert half["status"] == "in_progress"

        done = await system.update_progress(goal_id, 1.0)
        assert done["progress"] == 1.0
        assert done["status"] == "completed"

        types = [e.event_type for e in await system.event_repo.list_by_novel(novel_id)]
        assert types.count("goal_progress_updated") == 2

    async def test_update_progress_with_explicit_status(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        system = GoalSystem(db_session, novel_id)
        goal = await system.create_goal("plot", "g")

        result = await system.update_progress(
            uuid.UUID(goal["id"]), 0.3, status="failed", source="human"
        )
        assert result["status"] == "failed"
        assert result["progress"] == 0.3

    async def test_delete_goal_is_soft(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        system = GoalSystem(db_session, novel_id)
        goal = await system.create_goal("plot", "待删除")

        await system.delete_goal(uuid.UUID(goal["id"]))

        assert await system.list_goals() == []
        deleted = [
            e
            for e in await system.event_repo.list_by_novel(novel_id)
            if e.event_type == "goal_deleted"
        ]
        assert len(deleted) == 1
        assert deleted[0].severity == "warning"

    async def test_get_goal_tree(self, db_session: AsyncSession, novel_id: uuid.UUID):
        system = GoalSystem(db_session, novel_id)
        parent = await system.create_goal("plot", "第一卷", goal_order=0)
        for i in range(3):
            await system.create_goal(
                "plot",
                f"第{i + 1}章",
                parent_goal_id=uuid.UUID(parent["id"]),
                goal_order=i + 1,
            )

        tree = await system.get_goal_tree()
        assert len(tree) == 1
        assert tree[0]["name"] == "第一卷"
        assert [c["name"] for c in tree[0]["children"]] == ["第1章", "第2章", "第3章"]

        assert await system.get_goal_tree(goal_type="market") == []

    async def test_create_and_list_intents(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        system = GoalSystem(db_session, novel_id)

        intent = await system.create_intent(
            "theme",
            "core",
            {"text": "成长与救赎"},
            description="核心主题",
            priority=80,
        )
        assert uuid.UUID(intent["id"])
        assert intent["type"] == "theme"
        assert intent["key"] == "core"
        assert intent["value"] == {"text": "成长与救赎"}

        await system.create_intent("style", "tone", {"text": "冷峻"}, priority=10)

        # ordered by priority desc
        assert [i["key"] for i in await system.list_intents()] == ["core", "tone"]
        assert [i["key"] for i in await system.list_intents(intent_type="style")] == [
            "tone"
        ]
        assert (await system.list_intents())[0]["description"] == "核心主题"

        types = [e.event_type for e in await system.event_repo.list_by_novel(novel_id)]
        assert types.count("intent_created") == 2

    async def test_update_intent(self, db_session: AsyncSession, novel_id: uuid.UUID):
        system = GoalSystem(db_session, novel_id)
        intent = await system.create_intent("theme", "core", {"text": "旧"})

        updated = await system.update_intent(
            uuid.UUID(intent["id"]), {"intent_value": {"text": "新"}}
        )

        assert updated["value"] == {"text": "新"}
        types = [e.event_type for e in await system.event_repo.list_by_novel(novel_id)]
        assert "intent_updated" in types


# ---------------------------------------------------------------------------
# ConstraintSystem
# ---------------------------------------------------------------------------
class TestConstraintSystem:
    async def test_create_constraint(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        system = ConstraintSystem(db_session, novel_id)

        constraint = await system.create_constraint(
            "character_ooc",
            "主角不能死",
            {"character": "protagonist", "forbid": "death"},
            description="主角在任何情况下都不能死亡",
            severity="blocking",
            priority=99,
        )

        assert uuid.UUID(constraint["id"])
        assert constraint["name"] == "主角不能死"
        assert constraint["type"] == "character_ooc"
        assert constraint["severity"] == "blocking"
        assert constraint["check_method"] == "ai_review"
        assert constraint["priority"] == 99
        assert constraint["violation_count"] == 0
        assert constraint["last_violation_at"] is None

        events = await system.event_repo.list_by_novel(novel_id)
        assert [e.event_type for e in events] == ["constraint_created"]

    async def test_list_constraints_with_filters(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        system = ConstraintSystem(db_session, novel_id)
        await system.create_constraint(
            "style", "S", {}, severity="warning", priority=10
        )
        await system.create_constraint(
            "world_rule", "W", {}, severity="blocking", priority=80
        )

        # ordered by priority desc
        assert [c["name"] for c in await system.list_constraints()] == ["W", "S"]
        assert [
            c["name"] for c in await system.list_constraints(constraint_type="style")
        ] == ["S"]
        assert [
            c["name"] for c in await system.list_constraints(severity="blocking")
        ] == ["W"]
        assert len(await system.list_constraints(limit=1)) == 1

    async def test_update_constraint(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        system = ConstraintSystem(db_session, novel_id)
        constraint = await system.create_constraint("style", "S", {})

        updated = await system.update_constraint(
            uuid.UUID(constraint["id"]), {"severity": "error"}
        )

        assert updated["severity"] == "error"
        assert updated["is_active"] is True
        types = [e.event_type for e in await system.event_repo.list_by_novel(novel_id)]
        assert "constraint_updated" in types

    async def test_delete_constraint_is_soft(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        system = ConstraintSystem(db_session, novel_id)
        constraint = await system.create_constraint("style", "S", {})

        await system.delete_constraint(uuid.UUID(constraint["id"]))

        assert await system.list_constraints() == []
        assert [c["name"] for c in await system.list_constraints(is_active=False)] == [
            "S"
        ]
        deleted = [
            e
            for e in await system.event_repo.list_by_novel(novel_id)
            if e.event_type == "constraint_deleted"
        ]
        assert len(deleted) == 1
        assert deleted[0].severity == "warning"

    async def test_record_violation(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        system = ConstraintSystem(db_session, novel_id)
        constraint = await system.create_constraint(
            "style", "测试约束", {}, severity="warning"
        )
        constraint_id = uuid.UUID(constraint["id"])

        first = await system.record_violation(constraint_id, details="第3章语气不符")
        assert first["violation_count"] == 1
        assert first["severity"] == "warning"

        second = await system.record_violation(constraint_id)
        assert second["violation_count"] == 2

        violations = [
            e
            for e in await system.event_repo.list_by_novel(novel_id)
            if e.event_type == "constraint_violation"
        ]
        assert len(violations) == 2
        # severity "warning" maps to a warning-level event
        assert {v.severity for v in violations} == {"warning"}
        assert violations[0].event_data["details"] in ("第3章语气不符", None)

    async def test_record_violation_escalates_event_severity(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        system = ConstraintSystem(db_session, novel_id)
        constraint = await system.create_constraint(
            "world_rule", "硬规则", {}, severity="blocking"
        )

        await system.record_violation(uuid.UUID(constraint["id"]))

        violation = next(
            e
            for e in await system.event_repo.list_by_novel(novel_id)
            if e.event_type == "constraint_violation"
        )
        assert violation.severity == "error"

    async def test_check_constraints_returns_only_ai_review(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        system = ConstraintSystem(db_session, novel_id)
        await system.create_constraint(
            "style", "AI审查", {}, check_method="ai_review", priority=50
        )
        await system.create_constraint(
            "style", "人工", {}, check_method="human", priority=40
        )
        await system.create_constraint(
            "style", "规则", {}, check_method="rule_based", priority=30
        )

        result = await system.check_constraints("第一章的正文内容")

        assert isinstance(result, list)
        assert [c["name"] for c in result] == ["AI审查"]
        assert result[0]["check_method"] == "ai_review"

    async def test_check_constraints_type_filter(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        system = ConstraintSystem(db_session, novel_id)
        await system.create_constraint("style", "S", {})
        await system.create_constraint("world_rule", "W", {})

        assert [
            c["name"] for c in await system.check_constraints("t", constraint_types=["world_rule"])
        ] == ["W"]
        assert await system.check_constraints("t", constraint_types=["plot_continuity"]) == []

    async def test_check_constraints_skips_deleted(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        system = ConstraintSystem(db_session, novel_id)
        constraint = await system.create_constraint("style", "S", {})
        await system.delete_constraint(uuid.UUID(constraint["id"]))

        assert await system.check_constraints("t") == []


# ---------------------------------------------------------------------------
# VersionControl
# ---------------------------------------------------------------------------
class TestVersionControl:
    async def test_create_snapshot(self, db_session: AsyncSession, novel_id: uuid.UUID):
        vc = VersionControl(db_session, novel_id)
        state_manager = StoryStateManager(db_session, novel_id)
        await state_manager.update_state("character", "protagonist", {"name": "张三"}, 0.95)
        await state_manager.update_state("world", "capital", {"name": "洛阳"}, 0.95)

        snapshot = await vc.create_snapshot(description="测试快照")

        assert uuid.UUID(snapshot["id"])
        assert snapshot["snapshot_type"] == "full"
        assert snapshot["description"] == "测试快照"
        assert snapshot["size_bytes"] > 0
        assert snapshot["created_at"] is not None

        stored = await vc.snapshot_repo.get(uuid.UUID(snapshot["id"]))
        assert set(stored.state_data) == {
            "global",
            "character",
            "world",
            "plot",
            "reader",
        }
        assert stored.state_data["character"] == [
            {"key": "protagonist", "value": {"name": "张三"}, "confidence": 0.95}
        ]
        assert stored.state_data["plot"] == []

        types = [e.event_type for e in await vc.event_repo.list_by_novel(novel_id)]
        assert "snapshot_created" in types

    async def test_create_version_also_creates_snapshot(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        vc = VersionControl(db_session, novel_id)

        version = await vc.create_version(
            version_type="manual", description="测试版本", created_by="human"
        )

        assert uuid.UUID(version["id"])
        assert version["version_number"] == 1
        assert version["version_type"] == "manual"
        assert version["description"] == "测试版本"
        assert version["branch_name"] == "main"
        assert version["created_by"] == "human"

        snapshots = await vc.list_snapshots()
        assert len(snapshots) == 1

        stored = await vc.version_repo.get(uuid.UUID(version["id"]))
        assert stored.snapshot_data == {"snapshot_id": snapshots[0]["id"]}

        types = [e.event_type for e in await vc.event_repo.list_by_novel(novel_id)]
        assert "version_created" in types

    async def test_sequential_versions_increment_number(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        """FIXED(2026-08-02): ``StoryVersion.__mapper_args__["version_id_col"]``
        previously made SQLAlchemy overwrite the computed ``version_number``
        with its own optimistic-locking counter, so every INSERT landed on 1.
        The mapper config was removed; now versions must increment 1, 2, ..."""
        vc = VersionControl(db_session, novel_id)

        v1 = await vc.create_version(description="v1")
        v2 = await vc.create_version(description="v2")

        assert v1["version_number"] == 1
        assert v2["version_number"] == 2
        assert v1["id"] != v2["id"]

    async def test_list_versions_and_branch_filter(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        vc = VersionControl(db_session, novel_id)
        await vc.create_version(description="m1")
        await vc.create_version(description="d1", branch_name="dev")

        assert len(await vc.list_versions()) == 2
        assert [v["description"] for v in await vc.list_versions(branch_name="dev")] == [
            "d1"
        ]
        assert len(await vc.list_versions(limit=1)) == 1

    async def test_get_latest_version(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        vc = VersionControl(db_session, novel_id)
        assert await vc.get_latest_version() is None

        await vc.create_version(description="v1", version_type="manual")

        latest = await vc.get_latest_version()
        assert latest is not None
        assert latest["description"] == "v1"
        assert latest["version_type"] == "manual"
        assert latest["created_at"] is not None

        assert await vc.get_latest_version(branch_name="dev") is None

    async def test_list_snapshots(self, db_session: AsyncSession, novel_id: uuid.UUID):
        vc = VersionControl(db_session, novel_id)
        assert await vc.list_snapshots() == []

        await vc.create_snapshot(description="s0")
        await vc.create_snapshot(description="s1", snapshot_type="partial")

        snapshots = await vc.list_snapshots()
        assert len(snapshots) == 2
        assert {s["description"] for s in snapshots} == {"s0", "s1"}
        assert {s["snapshot_type"] for s in snapshots} == {"full", "partial"}
        assert len(await vc.list_snapshots(limit=1)) == 1

    async def test_rollback_to_snapshot(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        vc = VersionControl(db_session, novel_id)
        snapshot = await vc.create_snapshot(description="回滚点")
        snapshot_id = uuid.UUID(snapshot["id"])

        result = await vc.rollback_to_snapshot(
            snapshot_id, user_id=uuid.uuid4(), reason="生成结果不佳"
        )

        assert result["snapshot_id"] == str(snapshot_id)
        assert result["status"] == "rolled_back"
        assert uuid.UUID(result["version_id"])

        version = await vc.version_repo.get(uuid.UUID(result["version_id"]))
        assert version.version_type == "rollback"
        assert version.snapshot_data["rollback_to_snapshot"] == str(snapshot_id)
        assert version.created_by == "human"

        rollback_events = [
            e
            for e in await vc.event_repo.list_by_novel(novel_id)
            if e.event_type == "rollback"
        ]
        assert len(rollback_events) == 1
        assert rollback_events[0].severity == "warning"
        assert rollback_events[0].event_data["reason"] == "生成结果不佳"

    async def test_rollback_to_missing_snapshot_raises(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        vc = VersionControl(db_session, novel_id)
        with pytest.raises(ValueError):
            await vc.rollback_to_snapshot(uuid.uuid4())


# ---------------------------------------------------------------------------
# NovelBrain
# ---------------------------------------------------------------------------
class TestNovelBrain:
    async def test_subsystems_are_wired(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        brain = NovelBrain(db_session, novel_id)

        assert isinstance(brain.state, StoryStateManager)
        assert isinstance(brain.goals, GoalSystem)
        assert isinstance(brain.constraints, ConstraintSystem)
        assert isinstance(brain.versions, VersionControl)
        for subsystem in (brain.state, brain.goals, brain.constraints, brain.versions):
            assert subsystem.novel_id == novel_id
            assert subsystem.db is db_session

    async def test_get_overview_empty(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        brain = NovelBrain(db_session, novel_id)

        overview = await brain.get_overview()

        assert overview["novel_id"] == str(novel_id)
        assert overview["states"]["total"] == 0
        assert overview["states"]["pending_review"] == 0
        assert set(overview["states"]["by_type"]) == {
            "global",
            "character",
            "world",
            "plot",
            "reader",
        }
        assert overview["goals"] == {
            "total": 0,
            "completed": 0,
            "in_progress": 0,
            "pending": 0,
        }
        assert overview["constraints"] == {"total": 0, "active": 0}
        assert overview["latest_version"] is None
        assert overview["recent_events"] == []

    async def test_get_overview_with_data(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        brain = NovelBrain(db_session, novel_id)

        await brain.state.update_state("character", "protagonist", {"name": "张三"}, 0.95)
        await brain.state.update_state("world", "capital", {"name": "洛阳"}, 0.6)
        goal = await brain.goals.create_goal("plot", "主线")
        await brain.goals.update_progress(uuid.UUID(goal["id"]), 1.0)
        await brain.goals.create_goal("plot", "支线")
        await brain.constraints.create_constraint(
            "character_ooc", "主角不死", {}, severity="blocking"
        )
        await brain.versions.create_version(description="v1")

        overview = await brain.get_overview()

        assert overview["novel_id"] == str(novel_id)
        assert overview["states"]["by_type"]["character"] == 1
        assert overview["states"]["by_type"]["world"] == 1
        assert overview["states"]["total"] == 2
        assert overview["states"]["pending_review"] == 1
        assert overview["goals"]["total"] == 2
        assert overview["goals"]["completed"] == 1
        assert overview["goals"]["pending"] == 1
        assert overview["constraints"]["total"] == 1
        assert overview["constraints"]["active"] == 1
        assert overview["latest_version"]["description"] == "v1"
        assert 0 < len(overview["recent_events"]) <= 10
        assert all(
            {"id", "type", "name", "category", "severity", "time"} <= set(e)
            for e in overview["recent_events"]
        )

    async def test_record_decision(self, db_session: AsyncSession, novel_id: uuid.UUID):
        brain = NovelBrain(db_session, novel_id)
        run_id = uuid.uuid4()

        decision = await brain.record_decision(
            "character_action",
            "approve",
            decision_reason="剧情需要",
            confidence=0.85,
            permission_level="notify",
            status="completed",
            run_id=run_id,
            context={"chapter": 3},
            alternatives=[{"decision": "reject", "score": 0.2}],
            decided_by="ai",
        )

        assert uuid.UUID(decision["id"])
        assert decision["decision_type"] == "character_action"
        assert decision["decision"] == "approve"
        assert decision["confidence"] == 0.85
        assert decision["status"] == "completed"
        assert decision["decided_by"] == "ai"

        stored = await brain.decision_repo.get(uuid.UUID(decision["id"]))
        assert stored.context == {"chapter": 3}
        assert stored.alternatives == [{"decision": "reject", "score": 0.2}]
        assert stored.permission_level == "notify"
        assert stored.run_id == run_id

        events = await brain.event_repo.list_by_novel(novel_id)
        assert [e.event_type for e in events] == ["decision_made"]
        assert events[0].event_data["decision_type"] == "character_action"

    async def test_get_decision_logs(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        brain = NovelBrain(db_session, novel_id)

        for i in range(5):
            await brain.record_decision(
                f"type_{i}",
                "approve",
                decision_reason="测试",
                confidence=0.8,
                status="completed" if i % 2 == 0 else "pending",
            )

        logs = await brain.get_decision_logs(limit=10)
        assert len(logs) == 5
        assert {l["decision_type"] for l in logs} == {f"type_{i}" for i in range(5)}
        assert all(l["created_at"] is not None for l in logs)
        assert all(l["reason"] == "测试" for l in logs)

        assert len(await brain.get_decision_logs(decision_type="type_1")) == 1
        assert len(await brain.get_decision_logs(status="pending")) == 2
        assert len(await brain.get_decision_logs(limit=2)) == 2

    async def test_get_events(self, db_session: AsyncSession, novel_id: uuid.UUID):
        brain = NovelBrain(db_session, novel_id)

        await brain.state.update_state("character", "p", {"n": 1}, 0.95)
        await brain.goals.create_goal("plot", "g")
        await brain.record_decision("plot_branch", "approve")

        events = await brain.get_events()
        assert len(events) == 3
        assert {e["category"] for e in events} == {"state", "goal", "decision"}
        assert all(e["time"] is not None for e in events)
        assert all(isinstance(e["data"], dict) for e in events)

        assert len(await brain.get_events(event_category="goal")) == 1
        assert len(await brain.get_events(event_type="decision_made")) == 1
        assert len(await brain.get_events(severity="info")) == 3
        assert len(await brain.get_events(limit=1)) == 1

    async def test_brain_is_scoped_to_its_novel(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        mine = NovelBrain(db_session, novel_id)
        theirs = NovelBrain(db_session, uuid.uuid4())

        await mine.record_decision("t", "approve")

        assert len(await mine.get_decision_logs()) == 1
        assert await theirs.get_decision_logs() == []
        assert (await theirs.get_overview())["states"]["total"] == 0
