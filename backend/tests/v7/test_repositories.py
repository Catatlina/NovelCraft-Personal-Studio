"""
V7 Repository Layer Tests
==========================

Tests for all V7 repository classes.

Every repository method is ``async`` and takes an ``AsyncSession`` — these
tests therefore run against a real PostgreSQL database through the async
``db_session`` fixture (``tests/v7/conftest.py``). ``asyncio_mode = "auto"``
is configured in ``pyproject.toml``, so plain ``async def test_*`` works
without ``@pytest.mark.asyncio``.

NOTE ON ORDERING ASSERTIONS
---------------------------
Each test runs inside a single PostgreSQL transaction, and ``func.now()`` is
the *transaction* timestamp — so every row created by one test shares the same
``created_at`` / ``updated_at`` / ``event_time``. Assertions therefore never
depend on timestamp ordering; only explicitly ordered columns
(``step_order``, ``goal_order``, ``priority``, ``state_key``) are order-checked.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.v7.repositories.base import BaseRepository
from app.v7.repositories.state import StoryStateRepository, StateChangeRepository
from app.v7.repositories.goal import GoalRepository, IntentRepository
from app.v7.repositories.constraint import ConstraintRepository
from app.v7.repositories.decision import (
    DecisionPermissionRepository,
    DecisionLogRepository,
)
from app.v7.repositories.version import VersionRepository, SnapshotRepository
from app.v7.repositories.trace import AgentRunRepository, AgentTraceRepository
from app.v7.repositories.event import EventLogRepository
from app.v7.models.state import StoryState


def _unique(prefix: str) -> str:
    """Globally unique name — ``v7_decision_permissions.decision_type`` has a
    table-wide UNIQUE constraint, not a per-novel one."""
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


async def _mk_state(
    repo: StoryStateRepository,
    novel_id: uuid.UUID,
    key: str,
    *,
    state_type: str = "character",
    confidence: float = 0.8,
    value: dict | None = None,
) -> StoryState:
    return await repo.create(
        {
            "novel_id": novel_id,
            "state_type": state_type,
            "state_key": key,
            "state_value": value if value is not None else {"k": key},
            "confidence": confidence,
            "source": "test",
        }
    )


# ---------------------------------------------------------------------------
# BaseRepository
# ---------------------------------------------------------------------------
class TestBaseRepository:
    """Generic CRUD contract, exercised through StoryStateRepository."""

    async def test_create_and_get(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = StoryStateRepository(db_session)

        state = await repo.create(
            {
                "novel_id": novel_id,
                "state_type": "character",
                "state_key": "protagonist.name",
                "state_value": {"name": "张三", "age": 25},
                "confidence": 0.95,
                "source": "test",
            }
        )

        assert isinstance(state.id, uuid.UUID)
        assert state.novel_id == novel_id
        assert state.state_type == "character"
        assert state.state_key == "protagonist.name"
        assert state.confidence == 0.95
        # Column defaults applied on flush
        assert state.version == 1
        assert state.is_active is True
        assert state.is_pending_review is False

        fetched = await repo.get(state.id)
        assert fetched is not None
        assert fetched.id == state.id
        assert fetched.state_value == {"name": "张三", "age": 25}

    async def test_get_missing_returns_none(self, db_session: AsyncSession):
        repo = StoryStateRepository(db_session)
        assert await repo.get(uuid.uuid4()) is None

    async def test_get_or_404_raises(self, db_session: AsyncSession):
        repo = StoryStateRepository(db_session)
        missing = uuid.uuid4()

        with pytest.raises(ValueError, match="StoryState not found"):
            await repo.get_or_404(missing)

    async def test_list_and_count(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = StoryStateRepository(db_session)
        for i in range(5):
            await _mk_state(repo, novel_id, f"char_{i}")

        filters = {"novel_id": novel_id}
        items = await repo.list(filters=filters)
        assert len(items) == 5
        assert {i.state_key for i in items} == {f"char_{i}" for i in range(5)}

        assert await repo.count(filters=filters) == 5
        assert await repo.count(filters={"novel_id": uuid.uuid4()}) == 0

    async def test_list_filters_by_multiple_columns(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = StoryStateRepository(db_session)
        await _mk_state(repo, novel_id, "c1", state_type="character")
        await _mk_state(repo, novel_id, "p1", state_type="plot")
        await _mk_state(repo, novel_id, "p2", state_type="plot")

        plots = await repo.list(filters={"novel_id": novel_id, "state_type": "plot"})
        assert {p.state_key for p in plots} == {"p1", "p2"}

        assert await repo.count(
            filters={"novel_id": novel_id, "state_type": "character"}
        ) == 1

    async def test_list_unknown_filter_key_is_ignored(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = StoryStateRepository(db_session)
        await _mk_state(repo, novel_id, "only")

        items = await repo.list(
            filters={"novel_id": novel_id, "no_such_column": "whatever"}
        )
        assert len(items) == 1

    async def test_list_ordering_and_pagination(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = StoryStateRepository(db_session)
        for i in range(5):
            await _mk_state(repo, novel_id, f"char_{i}")

        filters = {"novel_id": novel_id}

        asc = await repo.list(filters=filters, order_by="state_key")
        assert [s.state_key for s in asc] == [f"char_{i}" for i in range(5)]

        desc = await repo.list(filters=filters, order_by="state_key", order_desc=True)
        assert [s.state_key for s in desc] == [f"char_{i}" for i in reversed(range(5))]

        page = await repo.list(filters=filters, order_by="state_key", skip=1, limit=2)
        assert [s.state_key for s in page] == ["char_1", "char_2"]

    async def test_update(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = StoryStateRepository(db_session)
        state = await _mk_state(repo, novel_id, "protagonist.name", value={"name": "张三"})

        updated = await repo.update(
            state.id, {"state_value": {"name": "李四"}, "confidence": 0.9}
        )

        assert updated.id == state.id
        assert updated.state_value["name"] == "李四"
        assert updated.confidence == 0.9

        reread = await repo.get(state.id)
        assert reread.state_value["name"] == "李四"

    async def test_update_ignores_unknown_keys(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = StoryStateRepository(db_session)
        state = await _mk_state(repo, novel_id, "k")

        updated = await repo.update(state.id, {"confidence": 0.42, "bogus": 1})
        assert updated.confidence == 0.42
        assert not hasattr(updated, "bogus")

    async def test_update_missing_raises(self, db_session: AsyncSession):
        repo = StoryStateRepository(db_session)
        with pytest.raises(ValueError):
            await repo.update(uuid.uuid4(), {"confidence": 0.1})

    async def test_delete_and_exists(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = StoryStateRepository(db_session)
        state = await _mk_state(repo, novel_id, "disposable", confidence=0.5)

        assert await repo.exists(state.id) is True

        await repo.delete(state.id)

        assert await repo.exists(state.id) is False
        assert await repo.get(state.id) is None

    async def test_delete_missing_raises(self, db_session: AsyncSession):
        repo = StoryStateRepository(db_session)
        with pytest.raises(ValueError):
            await repo.delete(uuid.uuid4())

    async def test_generic_base_repository_usable_directly(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        """BaseRepository is generic — it works with any model class."""
        repo = BaseRepository(StoryState, db_session)
        obj = await repo.create(
            {
                "novel_id": novel_id,
                "state_type": "world",
                "state_key": "capital",
                "state_value": {"name": "洛阳"},
                "confidence": 0.9,
                "source": "test",
            }
        )
        assert repo.model is StoryState
        assert await repo.exists(obj.id) is True


# ---------------------------------------------------------------------------
# StoryStateRepository
# ---------------------------------------------------------------------------
class TestStoryStateRepository:
    async def test_get_by_key(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = StoryStateRepository(db_session)
        await _mk_state(
            repo, novel_id, "protagonist.name", confidence=0.9, value={"name": "张三"}
        )

        state = await repo.get_by_key(novel_id, "character", "protagonist.name")
        assert state is not None
        assert state.state_value["name"] == "张三"

        assert await repo.get_by_key(novel_id, "character", "nope") is None
        assert await repo.get_by_key(novel_id, "plot", "protagonist.name") is None
        assert await repo.get_by_key(uuid.uuid4(), "character", "protagonist.name") is None

    async def test_get_by_key_skips_inactive(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = StoryStateRepository(db_session)
        state = await _mk_state(repo, novel_id, "gone")

        await repo.update(state.id, {"is_active": False})

        assert await repo.get_by_key(novel_id, "character", "gone") is None

    async def test_list_by_type(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = StoryStateRepository(db_session)
        for i in range(3):
            await _mk_state(repo, novel_id, f"char_{i}", state_type="character")
        for i in range(2):
            await _mk_state(repo, novel_id, f"plot_{i}", state_type="plot")

        characters = await repo.list_by_type(novel_id, "character")
        assert len(characters) == 3
        assert {c.state_key for c in characters} == {"char_0", "char_1", "char_2"}

        plots = await repo.list_by_type(novel_id, "plot")
        assert len(plots) == 2

        assert await repo.list_by_type(novel_id, "world") == []

    async def test_list_by_type_pagination(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = StoryStateRepository(db_session)
        for i in range(4):
            await _mk_state(repo, novel_id, f"char_{i}")

        assert len(await repo.list_by_type(novel_id, "character", limit=2)) == 2
        assert len(await repo.list_by_type(novel_id, "character", skip=3)) == 1

    async def test_list_pending_review(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = StoryStateRepository(db_session)
        clean = await _mk_state(repo, novel_id, "clean")
        dirty = await _mk_state(repo, novel_id, "dirty")
        await repo.update(dirty.id, {"is_pending_review": True})

        pending = await repo.list_pending_review(novel_id)
        assert [p.id for p in pending] == [dirty.id]
        assert clean.id not in {p.id for p in pending}

    # --- confidence gating: four tiers -------------------------------------
    # ``update_with_confidence`` gates on a single ``confidence_threshold``
    # (default 0.7). Tiers below are asserted against the REAL behaviour.

    async def test_confidence_gate_very_high_creates_active(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        """Tier 1 (>= 0.9): create, active, no review flag."""
        repo = StoryStateRepository(db_session)

        state, action = await repo.update_with_confidence(
            novel_id, "character", "protagonist.name", {"name": "张三"}, 0.95
        )

        assert action == "created"
        assert state.confidence == 0.95
        assert state.is_active is True
        assert state.is_pending_review is False
        assert state.version == 1
        assert state.source == "ai_extracted"

    async def test_confidence_gate_high_updates_existing(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        """Tier 2 (>= threshold, existing row): in-place update + version bump."""
        repo = StoryStateRepository(db_session)
        await repo.update_with_confidence(
            novel_id, "character", "protagonist.name", {"name": "张三"}, 0.95
        )

        state, action = await repo.update_with_confidence(
            novel_id, "character", "protagonist.name", {"name": "李四"}, 0.85
        )

        assert action == "updated"
        assert state.state_value == {"name": "李四"}
        assert state.confidence == 0.85
        assert state.version == 2
        assert state.is_pending_review is False

        # only one row exists for that key
        rows = await repo.list_by_type(novel_id, "character")
        assert len(rows) == 1

    async def test_confidence_gate_low_creates_pending(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        """Tier 3 (< threshold, no existing row): created but flagged."""
        repo = StoryStateRepository(db_session)

        state, action = await repo.update_with_confidence(
            novel_id, "character", "protagonist.name", {"name": "张三"}, 0.6
        )

        assert action == "pending_review"
        assert state.is_pending_review is True
        assert state.is_active is True
        assert state.confidence == 0.6

        assert [s.id for s in await repo.list_pending_review(novel_id)] == [state.id]

    async def test_confidence_gate_very_low_flags_existing_without_overwrite(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        """Tier 4 (< threshold, existing row): existing value is PROTECTED."""
        repo = StoryStateRepository(db_session)
        await repo.update_with_confidence(
            novel_id, "character", "protagonist.name", {"name": "张三"}, 0.95
        )

        state, action = await repo.update_with_confidence(
            novel_id, "character", "protagonist.name", {"name": "垃圾"}, 0.2
        )

        assert action == "pending_review"
        assert state.state_value == {"name": "张三"}  # untouched
        assert state.confidence == 0.95  # untouched
        assert state.version == 1  # untouched
        assert state.is_pending_review is True

    async def test_confidence_gate_respects_custom_threshold(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = StoryStateRepository(db_session)

        state, action = await repo.update_with_confidence(
            novel_id,
            "character",
            "k",
            {"v": 1},
            0.55,
            confidence_threshold=0.5,
        )
        assert action == "created"
        assert state.is_pending_review is False

    async def test_confidence_gate_records_source_metadata(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = StoryStateRepository(db_session)
        run_id = uuid.uuid4()

        state, _ = await repo.update_with_confidence(
            novel_id,
            "world",
            "capital",
            {"name": "洛阳"},
            0.99,
            source="human_set",
            source_run_id=run_id,
        )

        assert state.source == "human_set"
        assert state.source_run_id == run_id


# ---------------------------------------------------------------------------
# StateChangeRepository
# ---------------------------------------------------------------------------
class TestStateChangeRepository:
    async def test_record_change_and_list_by_state(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        state_repo = StoryStateRepository(db_session)
        change_repo = StateChangeRepository(db_session)
        state = await _mk_state(state_repo, novel_id, "protagonist.name")

        change = await change_repo.record_change(
            novel_id,
            state.id,
            "update",
            "character",
            "protagonist.name",
            old_value={"name": "张三"},
            new_value={"name": "李四"},
            old_confidence=0.8,
            new_confidence=0.95,
            reason="剧情推进",
            source="ai",
        )

        assert change.change_type == "update"
        assert change.old_value == {"name": "张三"}
        assert change.new_value == {"name": "李四"}
        assert change.old_confidence == 0.8
        assert change.new_confidence == 0.95
        assert change.reason == "剧情推进"

        listed = await change_repo.list_by_state(state.id)
        assert [c.id for c in listed] == [change.id]

    async def test_list_by_novel_and_by_run(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        change_repo = StateChangeRepository(db_session)
        run_id = uuid.uuid4()

        for i in range(3):
            await change_repo.record_change(
                novel_id,
                None,
                "create",
                "plot",
                f"beat_{i}",
                new_value={"i": i},
                source="ai",
                source_run_id=run_id if i < 2 else None,
            )

        assert len(await change_repo.list_by_novel(novel_id)) == 3
        assert len(await change_repo.list_by_run(run_id)) == 2
        assert await change_repo.list_by_novel(uuid.uuid4()) == []


# ---------------------------------------------------------------------------
# GoalRepository / IntentRepository
# ---------------------------------------------------------------------------
class TestGoalRepository:
    async def test_create_goal(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = GoalRepository(db_session)

        goal = await repo.create(
            {
                "novel_id": novel_id,
                "goal_type": "plot",
                "goal_name": "主线剧情",
                "description": "完成主线剧情",
                "status": "in_progress",
                "progress": 0.3,
                "priority": 90,
                "confidence": 0.9,
            }
        )

        assert isinstance(goal.id, uuid.UUID)
        assert goal.goal_name == "主线剧情"
        assert goal.progress == 0.3
        assert goal.priority == 90
        assert goal.is_active is True
        assert goal.extra_metadata == {}

    async def test_list_by_novel_with_filters(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = GoalRepository(db_session)
        await repo.create(
            {
                "novel_id": novel_id,
                "goal_type": "plot",
                "goal_name": "A",
                "goal_order": 1,
                "status": "pending",
            }
        )
        await repo.create(
            {
                "novel_id": novel_id,
                "goal_type": "plot",
                "goal_name": "B",
                "goal_order": 0,
                "status": "completed",
            }
        )
        await repo.create(
            {
                "novel_id": novel_id,
                "goal_type": "character",
                "goal_name": "C",
                "goal_order": 2,
                "status": "pending",
            }
        )

        # ordered by goal_order asc
        assert [g.goal_name for g in await repo.list_by_novel(novel_id)] == ["B", "A", "C"]
        assert [
            g.goal_name for g in await repo.list_by_novel(novel_id, goal_type="plot")
        ] == ["B", "A"]
        assert [
            g.goal_name for g in await repo.list_by_novel(novel_id, status="pending")
        ] == ["A", "C"]
        assert (
            await repo.list_by_novel(novel_id, goal_type="plot", status="completed")
        )[0].goal_name == "B"

    async def test_list_by_novel_hides_soft_deleted(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = GoalRepository(db_session)
        goal = await repo.create(
            {"novel_id": novel_id, "goal_type": "plot", "goal_name": "X"}
        )
        await repo.update(goal.id, {"is_active": False})

        assert await repo.list_by_novel(novel_id) == []

    async def test_update_progress(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = GoalRepository(db_session)
        goal = await repo.create(
            {
                "novel_id": novel_id,
                "goal_type": "plot",
                "goal_name": "测试目标",
                "status": "pending",
                "progress": 0.0,
            }
        )

        updated = await repo.update_progress(goal.id, 0.5)
        assert updated.progress == 0.5
        assert updated.status == "in_progress"

        updated = await repo.update_progress(goal.id, 1.0)
        assert updated.progress == 1.0
        assert updated.status == "completed"

    async def test_update_progress_clamps_and_honours_explicit_status(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = GoalRepository(db_session)
        goal = await repo.create(
            {"novel_id": novel_id, "goal_type": "plot", "goal_name": "clamp"}
        )

        assert (await repo.update_progress(goal.id, 5.0)).progress == 1.0
        assert (await repo.update_progress(goal.id, -3.0)).progress == 0.0

        forced = await repo.update_progress(goal.id, 0.9, status="failed")
        assert forced.status == "failed"

    async def test_get_goal_tree(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = GoalRepository(db_session)
        parent = await repo.create(
            {
                "novel_id": novel_id,
                "goal_type": "plot",
                "goal_name": "第一卷",
                "goal_order": 0,
            }
        )
        for i in range(3):
            await repo.create(
                {
                    "novel_id": novel_id,
                    "goal_type": "plot",
                    "goal_name": f"第{i + 1}章",
                    "parent_goal_id": parent.id,
                    "goal_order": i + 1,
                }
            )

        tree = await repo.get_goal_tree(novel_id)
        assert len(tree) == 1
        root = tree[0]
        assert root["id"] == str(parent.id)
        assert root["name"] == "第一卷"
        assert [c["name"] for c in root["children"]] == ["第1章", "第2章", "第3章"]
        assert all(c["children"] == [] for c in root["children"])

    async def test_get_goal_tree_filters_by_type(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = GoalRepository(db_session)
        await repo.create(
            {"novel_id": novel_id, "goal_type": "plot", "goal_name": "P"}
        )
        await repo.create(
            {"novel_id": novel_id, "goal_type": "market", "goal_name": "M"}
        )

        tree = await repo.get_goal_tree(novel_id, goal_type="market")
        assert [n["name"] for n in tree] == ["M"]


class TestIntentRepository:
    async def test_create_and_list_by_novel(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = IntentRepository(db_session)
        await repo.create(
            {
                "novel_id": novel_id,
                "intent_type": "theme",
                "intent_key": "core",
                "intent_value": {"text": "成长"},
                "priority": 10,
            }
        )
        await repo.create(
            {
                "novel_id": novel_id,
                "intent_type": "style",
                "intent_key": "tone",
                "intent_value": {"text": "冷峻"},
                "priority": 90,
            }
        )

        # ordered by priority desc
        assert [i.intent_key for i in await repo.list_by_novel(novel_id)] == [
            "tone",
            "core",
        ]
        assert [
            i.intent_key for i in await repo.list_by_novel(novel_id, intent_type="theme")
        ] == ["core"]

    async def test_list_by_novel_hides_soft_deleted(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = IntentRepository(db_session)
        intent = await repo.create(
            {
                "novel_id": novel_id,
                "intent_type": "theme",
                "intent_key": "k",
                "intent_value": {},
            }
        )
        await repo.update(intent.id, {"is_active": False})
        assert await repo.list_by_novel(novel_id) == []


# ---------------------------------------------------------------------------
# ConstraintRepository
# ---------------------------------------------------------------------------
class TestConstraintRepository:
    async def test_create_constraint(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = ConstraintRepository(db_session)

        constraint = await repo.create(
            {
                "novel_id": novel_id,
                "constraint_type": "character_ooc",
                "constraint_name": "主角不能死",
                "description": "主角在任何情况下都不能死亡",
                "constraint_value": {"character": "protagonist", "forbid": "death"},
                "severity": "blocking",
                "priority": 99,
            }
        )

        assert isinstance(constraint.id, uuid.UUID)
        assert constraint.constraint_name == "主角不能死"
        assert constraint.severity == "blocking"
        assert constraint.check_method == "ai_review"
        assert constraint.violation_count == 0
        assert constraint.last_violation_at is None
        assert constraint.is_active is True

    async def test_list_by_novel_with_filters(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = ConstraintRepository(db_session)
        await repo.create(
            {
                "novel_id": novel_id,
                "constraint_type": "style",
                "constraint_name": "S",
                "constraint_value": {},
                "severity": "warning",
                "priority": 10,
            }
        )
        await repo.create(
            {
                "novel_id": novel_id,
                "constraint_type": "world_rule",
                "constraint_name": "W",
                "constraint_value": {},
                "severity": "blocking",
                "priority": 80,
            }
        )

        # ordered by priority desc
        assert [c.constraint_name for c in await repo.list_by_novel(novel_id)] == ["W", "S"]
        assert [
            c.constraint_name
            for c in await repo.list_by_novel(novel_id, constraint_type="style")
        ] == ["S"]
        assert [
            c.constraint_name
            for c in await repo.list_by_novel(novel_id, severity="blocking")
        ] == ["W"]

    async def test_list_by_novel_is_active_flag(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = ConstraintRepository(db_session)
        c = await repo.create(
            {
                "novel_id": novel_id,
                "constraint_type": "style",
                "constraint_name": "S",
                "constraint_value": {},
            }
        )
        await repo.update(c.id, {"is_active": False})

        assert await repo.list_by_novel(novel_id) == []
        assert [
            x.constraint_name for x in await repo.list_by_novel(novel_id, is_active=False)
        ] == ["S"]

    async def test_check_violation_increments_counter(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = ConstraintRepository(db_session)
        constraint = await repo.create(
            {
                "novel_id": novel_id,
                "constraint_type": "style",
                "constraint_name": "测试约束",
                "constraint_value": {},
                "severity": "warning",
            }
        )
        assert constraint.violation_count == 0

        assert (await repo.check_violation(constraint.id)).violation_count == 1
        assert (await repo.check_violation(constraint.id)).violation_count == 2

        # BUG(prod): ConstraintRepository.check_violation never stamps
        # ``last_violation_at`` — see report. Asserted here so the gap is
        # visible and this test fails loudly once it is fixed.
        assert (await repo.get(constraint.id)).last_violation_at is None

    async def test_check_violation_missing_raises(self, db_session: AsyncSession):
        repo = ConstraintRepository(db_session)
        with pytest.raises(ValueError):
            await repo.check_violation(uuid.uuid4())


# ---------------------------------------------------------------------------
# DecisionPermissionRepository / DecisionLogRepository
# ---------------------------------------------------------------------------
class TestDecisionPermissionRepository:
    async def test_get_by_type_and_permission_level(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = DecisionPermissionRepository(db_session)
        decision_type = _unique("character_death")

        await repo.create(
            {
                "novel_id": novel_id,
                "decision_type": decision_type,
                "permission_level": "approve",
                "confidence_threshold": 0.9,
                "max_retries": 3,
                "priority": 90,
            }
        )

        perm = await repo.get_by_type(novel_id, decision_type)
        assert perm is not None
        assert perm.permission_level == "approve"
        assert perm.confidence_threshold == 0.9
        assert perm.escalation_rule == {}

        assert await repo.get_permission_level(novel_id, decision_type) == "approve"

    async def test_default_permission_level(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = DecisionPermissionRepository(db_session)
        assert await repo.get_permission_level(novel_id, _unique("unknown")) == "auto"

    async def test_inactive_permission_falls_back_to_default(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = DecisionPermissionRepository(db_session)
        decision_type = _unique("plot_twist")
        perm = await repo.create(
            {
                "novel_id": novel_id,
                "decision_type": decision_type,
                "permission_level": "forbidden",
            }
        )
        await repo.update(perm.id, {"is_active": False})

        assert await repo.get_by_type(novel_id, decision_type) is None
        assert await repo.get_permission_level(novel_id, decision_type) == "auto"

    async def test_list_by_novel_ordered_by_priority(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = DecisionPermissionRepository(db_session)
        low = _unique("low")
        high = _unique("high")
        await repo.create(
            {"novel_id": novel_id, "decision_type": low, "priority": 1}
        )
        await repo.create(
            {"novel_id": novel_id, "decision_type": high, "priority": 99}
        )

        assert [p.decision_type for p in await repo.list_by_novel(novel_id)] == [
            high,
            low,
        ]


class TestDecisionLogRepository:
    async def test_record_decision(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = DecisionLogRepository(db_session)
        run_id = uuid.uuid4()

        log = await repo.record_decision(
            novel_id,
            "character_action",
            "approve",
            decision_reason="剧情需要",
            confidence=0.85,
            permission_level="auto",
            status="completed",
            run_id=run_id,
            context={"chapter": 1},
            alternatives=[{"decision": "reject"}],
            decided_by="ai",
        )

        assert log.decision_type == "character_action"
        assert log.decision == "approve"
        assert log.confidence == 0.85
        assert log.context == {"chapter": 1}
        assert log.alternatives == [{"decision": "reject"}]
        assert log.run_id == run_id

    async def test_record_decision_defaults(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = DecisionLogRepository(db_session)
        log = await repo.record_decision(novel_id, "t", "approve")

        assert log.confidence == 0.9
        assert log.permission_level == "auto"
        assert log.status == "completed"
        assert log.decided_by == "ai"
        assert log.context == {}
        assert log.alternatives == []

    async def test_list_by_novel_and_run_with_filters(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = DecisionLogRepository(db_session)
        run_id = uuid.uuid4()

        await repo.record_decision(
            novel_id, "plot", "approve", status="completed", run_id=run_id
        )
        await repo.record_decision(
            novel_id, "plot", "reject", status="rejected", run_id=run_id
        )
        await repo.record_decision(novel_id, "style", "defer", status="pending")

        assert len(await repo.list_by_novel(novel_id)) == 3
        assert len(await repo.list_by_novel(novel_id, decision_type="plot")) == 2
        assert len(await repo.list_by_novel(novel_id, status="rejected")) == 1
        assert len(await repo.list_by_run(run_id)) == 2
        assert await repo.list_by_novel(uuid.uuid4()) == []


# ---------------------------------------------------------------------------
# VersionRepository / SnapshotRepository
# ---------------------------------------------------------------------------
class TestVersionRepository:
    async def test_create_version(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = VersionRepository(db_session)

        version = await repo.create_version(
            novel_id,
            version_type="manual",
            description="测试版本",
            created_by="test",
        )

        assert isinstance(version.id, uuid.UUID)
        assert version.version_number == 1
        assert version.version_type == "manual"
        assert version.description == "测试版本"
        assert version.branch_name == "main"
        assert version.created_by == "test"
        assert version.snapshot_data == {}

    async def test_sequential_versions_share_number_due_to_version_id_col(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        """BUG(prod): ``StoryVersion.__mapper_args__["version_id_col"]`` makes
        SQLAlchemy overwrite the computed ``version_number`` with its own
        optimistic-locking counter (always 1 on INSERT), so versions are NOT
        numbered 1, 2, 3. Asserted so the regression is explicit."""
        repo = VersionRepository(db_session)

        v1 = await repo.create_version(novel_id, description="v1")
        v2 = await repo.create_version(novel_id, description="v2")
        v3 = await repo.create_version(novel_id, description="v3")

        assert [v1.version_number, v2.version_number, v3.version_number] == [1, 1, 1]
        assert len({v1.id, v2.id, v3.id}) == 3

    async def test_get_next_version_number(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = VersionRepository(db_session)

        assert await repo.get_next_version_number(novel_id) == 1

        await repo.create_version(novel_id, description="v1")
        assert await repo.get_next_version_number(novel_id) == 2

        # separate branches keep separate counters
        assert await repo.get_next_version_number(novel_id, branch_name="dev") == 1

    async def test_get_latest(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = VersionRepository(db_session)
        assert await repo.get_latest(novel_id) is None

        await repo.create_version(novel_id, description="v1")
        latest = await repo.get_latest(novel_id)
        assert latest is not None
        assert latest.branch_name == "main"

        assert await repo.get_latest(novel_id, branch_name="dev") is None

    async def test_list_by_novel_branch_filter(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = VersionRepository(db_session)
        await repo.create_version(novel_id, description="m1")
        await repo.create_version(novel_id, description="d1", branch_name="dev")

        assert len(await repo.list_by_novel(novel_id)) == 2
        assert [
            v.description for v in await repo.list_by_novel(novel_id, branch_name="dev")
        ] == ["d1"]
        assert await repo.list_by_novel(uuid.uuid4()) == []

    async def test_create_version_with_parent_and_tag(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = VersionRepository(db_session)
        parent = await repo.create_version(novel_id, description="parent")

        child = await repo.create_version(
            novel_id,
            description="child",
            parent_version_id=parent.id,
            tag_name="v1.0",
            snapshot_data={"a": 1},
        )

        assert child.parent_version_id == parent.id
        assert child.tag_name == "v1.0"
        assert child.snapshot_data == {"a": 1}


class TestSnapshotRepository:
    async def test_create_snapshot(self, db_session: AsyncSession, novel_id: uuid.UUID):
        version_repo = VersionRepository(db_session)
        repo = SnapshotRepository(db_session)
        version = await version_repo.create_version(novel_id, description="v1")

        state_data = {"character": [{"key": "protagonist", "value": {"name": "张三"}}]}
        snapshot = await repo.create_snapshot(
            novel_id,
            state_data,
            snapshot_type="full",
            description="测试快照",
            version_id=version.id,
        )

        assert isinstance(snapshot.id, uuid.UUID)
        assert snapshot.version_id == version.id
        assert snapshot.snapshot_type == "full"
        assert snapshot.state_data == state_data
        assert snapshot.size_bytes > 0

    async def test_list_by_novel(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = SnapshotRepository(db_session)
        for i in range(3):
            await repo.create_snapshot(novel_id, {"i": i}, description=f"s{i}")

        snapshots = await repo.list_by_novel(novel_id)
        assert len(snapshots) == 3
        assert {s.description for s in snapshots} == {"s0", "s1", "s2"}

        assert len(await repo.list_by_novel(novel_id, limit=2)) == 2
        assert await repo.list_by_novel(uuid.uuid4()) == []


# ---------------------------------------------------------------------------
# AgentRunRepository / AgentTraceRepository
# ---------------------------------------------------------------------------
class TestAgentRunRepository:
    async def test_start_run(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = AgentRunRepository(db_session)

        run = await repo.start_run(
            novel_id,
            "chapter_generation",
            trigger="manual",
            input_data={"chapter": 1},
            chapter_number=1,
        )

        assert isinstance(run.id, uuid.UUID)
        assert run.status == "running"
        assert run.run_type == "chapter_generation"
        assert run.trigger == "manual"
        assert run.started_at is not None
        assert run.completed_at is None
        assert run.input_data == {"chapter": 1}
        assert run.chapter_number == 1
        assert run.total_tokens == 0
        assert run.total_cost == 0.0
        assert run.step_count == 0

    async def test_start_run_with_parent(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = AgentRunRepository(db_session)
        parent = await repo.start_run(novel_id, "planning")
        child = await repo.start_run(
            novel_id, "review", parent_run_id=parent.id, trigger="auto"
        )

        assert child.parent_run_id == parent.id
        assert child.trigger == "auto"

    async def test_update_run_stats(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = AgentRunRepository(db_session)
        run = await repo.start_run(novel_id, "chapter_generation")

        updated = await repo.update_run_stats(run.id, tokens=1000, cost=0.01)
        assert updated.total_tokens == 1000
        assert updated.total_cost == pytest.approx(0.01)
        assert updated.step_count == 1

        updated = await repo.update_run_stats(run.id, tokens=500, cost=0.02)
        assert updated.total_tokens == 1500
        assert updated.total_cost == pytest.approx(0.03)
        assert updated.step_count == 2

    async def test_list_by_novel_with_filters(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = AgentRunRepository(db_session)
        await repo.start_run(novel_id, "chapter_generation")
        await repo.start_run(novel_id, "review")

        assert len(await repo.list_by_novel(novel_id)) == 2
        assert len(await repo.list_by_novel(novel_id, run_type="review")) == 1
        assert len(await repo.list_by_novel(novel_id, status="running")) == 2
        assert len(await repo.list_by_novel(novel_id, status="completed")) == 0
        assert await repo.list_by_novel(uuid.uuid4()) == []

    async def test_complete_run_missing_raises(self, db_session: AsyncSession):
        repo = AgentRunRepository(db_session)
        with pytest.raises(ValueError):
            await repo.complete_run(uuid.uuid4())

    async def test_complete_run_success(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = AgentRunRepository(db_session)
        run = await repo.start_run(novel_id, "chapter_generation")
        assert run.started_at.tzinfo is not None

        completed = await repo.complete_run(run.id, output_data={"result": "success"})

        assert completed.status == "completed"
        assert completed.output_data == {"result": "success"}
        assert completed.completed_at is not None
        assert completed.completed_at.tzinfo is not None
        assert completed.duration_seconds is not None
        assert completed.duration_seconds >= 0
        assert completed.error_message is None

        assert len(await repo.list_by_novel(novel_id, status="completed")) == 1

    async def test_complete_run_with_error(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = AgentRunRepository(db_session)
        run = await repo.start_run(novel_id, "review")

        failed = await repo.complete_run(
            run.id, error_message="模型超时", error_type="TimeoutError"
        )

        assert failed.status == "failed"
        assert failed.error_message == "模型超时"
        assert failed.error_type == "TimeoutError"
        assert failed.output_data is None
        assert failed.completed_at is not None
        assert failed.duration_seconds is not None


class TestAgentTraceRepository:
    async def test_start_step(self, db_session: AsyncSession, novel_id: uuid.UUID):
        run_repo = AgentRunRepository(db_session)
        repo = AgentTraceRepository(db_session)
        run = await run_repo.start_run(novel_id, "chapter_generation")

        step = await repo.start_step(
            novel_id,
            run.id,
            "perceive",
            "perceive",
            step_order=0,
            input_summary="读取世界观",
            input_data={"scope": "world"},
        )

        assert isinstance(step.id, uuid.UUID)
        assert step.run_id == run.id
        assert step.status == "running"
        assert step.step_order == 0
        assert step.input_summary == "读取世界观"
        assert step.input_data == {"scope": "world"}
        assert step.completed_at is None

    async def test_start_step_with_parent(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        run_repo = AgentRunRepository(db_session)
        repo = AgentTraceRepository(db_session)
        run = await run_repo.start_run(novel_id, "chapter_generation")

        parent = await repo.start_step(novel_id, run.id, "plan", "plan")
        child = await repo.start_step(
            novel_id, run.id, "sub", "execute", step_order=1, parent_step_id=parent.id
        )

        assert child.parent_step_id == parent.id

    async def test_list_by_run_ordered_by_step_order(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        run_repo = AgentRunRepository(db_session)
        repo = AgentTraceRepository(db_session)
        run = await run_repo.start_run(novel_id, "chapter_generation")
        other_run = await run_repo.start_run(novel_id, "review")

        for order, name in ((2, "third"), (0, "first"), (1, "second")):
            await repo.start_step(novel_id, run.id, name, "execute", step_order=order)
        await repo.start_step(novel_id, other_run.id, "other", "review")

        steps = await repo.list_by_run(run.id)
        assert [s.step_name for s in steps] == ["first", "second", "third"]

        assert len(await repo.list_by_run(run.id, limit=2)) == 2
        assert len(await repo.list_by_run(other_run.id)) == 1
        assert await repo.list_by_run(uuid.uuid4()) == []

    async def test_complete_step_missing_raises(self, db_session: AsyncSession):
        repo = AgentTraceRepository(db_session)
        with pytest.raises(ValueError):
            await repo.complete_step(uuid.uuid4())

    async def test_complete_step_success(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        run_repo = AgentRunRepository(db_session)
        repo = AgentTraceRepository(db_session)
        run = await run_repo.start_run(novel_id, "chapter_generation")
        step = await repo.start_step(novel_id, run.id, "generate", "generate")
        assert step.started_at.tzinfo is not None

        completed = await repo.complete_step(
            step.id,
            output_summary="生成完毕",
            output_data={"chars": 3000},
            tokens_input=1200,
            tokens_output=3400,
            cost=0.031,
            model="gpt-4o",
            prompt_version="v3",
            confidence=0.88,
        )

        assert completed.status == "completed"
        assert completed.output_summary == "生成完毕"
        assert completed.output_data == {"chars": 3000}
        assert completed.tokens_input == 1200
        assert completed.tokens_output == 3400
        assert completed.cost == pytest.approx(0.031)
        assert completed.model == "gpt-4o"
        assert completed.prompt_version == "v3"
        assert completed.confidence == 0.88
        assert completed.completed_at is not None
        assert completed.duration_seconds is not None
        assert completed.duration_seconds >= 0

    async def test_complete_step_with_error(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        run_repo = AgentRunRepository(db_session)
        repo = AgentTraceRepository(db_session)
        run = await run_repo.start_run(novel_id, "chapter_generation")
        step = await repo.start_step(novel_id, run.id, "review", "review")

        failed = await repo.complete_step(step.id, error_message="校验失败")

        assert failed.status == "failed"
        assert failed.error_message == "校验失败"
        assert failed.output_summary is None
        assert failed.completed_at is not None


# ---------------------------------------------------------------------------
# EventLogRepository
# ---------------------------------------------------------------------------
class TestEventLogRepository:
    async def test_record_event(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = EventLogRepository(db_session)

        event = await repo.record_event(
            novel_id,
            "state_updated",
            "状态更新",
            "state",
            event_data={"key": "value"},
            source="ai",
            severity="info",
            description="测试事件",
        )

        assert isinstance(event.id, uuid.UUID)
        assert event.event_type == "state_updated"
        assert event.event_name == "状态更新"
        assert event.event_category == "state"
        assert event.event_data == {"key": "value"}
        assert event.severity == "info"
        assert event.description == "测试事件"
        assert event.event_time is not None
        assert event.version == 1

    async def test_record_event_defaults(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = EventLogRepository(db_session)
        event = await repo.record_event(novel_id, "t", "n", "system")

        assert event.source == "system"
        assert event.severity == "info"
        assert event.event_data == {}
        assert event.correlation_id is None

    async def test_list_by_novel_with_filters(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = EventLogRepository(db_session)
        await repo.record_event(novel_id, "a", "A", "state", severity="info")
        await repo.record_event(novel_id, "b", "B", "state", severity="warning")
        await repo.record_event(novel_id, "c", "C", "decision", severity="error")

        assert len(await repo.list_by_novel(novel_id)) == 3
        assert len(await repo.list_by_novel(novel_id, event_type="b")) == 1
        assert len(await repo.list_by_novel(novel_id, event_category="state")) == 2
        assert len(await repo.list_by_novel(novel_id, severity="error")) == 1
        assert len(await repo.list_by_novel(novel_id, limit=2)) == 2
        assert await repo.list_by_novel(uuid.uuid4()) == []

    async def test_list_by_run(self, db_session: AsyncSession, novel_id: uuid.UUID):
        repo = EventLogRepository(db_session)
        run_id = uuid.uuid4()

        for i in range(2):
            await repo.record_event(
                novel_id, "t", f"E{i}", "system", source_run_id=run_id
            )
        await repo.record_event(novel_id, "t", "other", "system")

        assert len(await repo.list_by_run(run_id)) == 2
        assert await repo.list_by_run(uuid.uuid4()) == []

    async def test_list_by_correlation(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = EventLogRepository(db_session)
        correlation_id = uuid.uuid4()

        for i in range(3):
            await repo.record_event(
                novel_id,
                "test",
                f"事件{i}",
                "system",
                source="ai",
                correlation_id=correlation_id,
            )
        await repo.record_event(novel_id, "test", "无关", "system")

        events = await repo.list_by_correlation(correlation_id)
        assert len(events) == 3
        assert {e.event_name for e in events} == {"事件0", "事件1", "事件2"}
        assert await repo.list_by_correlation(uuid.uuid4()) == []

    async def test_events_are_scoped_per_novel(
        self, db_session: AsyncSession, novel_id: uuid.UUID
    ):
        repo = EventLogRepository(db_session)
        other_novel = uuid.uuid4()

        await repo.record_event(novel_id, "t", "mine", "system")
        await repo.record_event(other_novel, "t", "theirs", "system")

        rows = await db_session.execute(
            select(EventLogRepository(db_session).model).where(
                EventLogRepository(db_session).model.novel_id == novel_id
            )
        )
        assert [r.event_name for r in rows.scalars().all()] == ["mine"]
