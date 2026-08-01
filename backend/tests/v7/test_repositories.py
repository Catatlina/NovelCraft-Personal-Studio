"""
V7 Repository Layer Tests
==========================

Tests for all V7 repository classes.
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.v7.repositories.state import StoryStateRepository, StateChangeRepository
from app.v7.repositories.goal import GoalRepository, IntentRepository
from app.v7.repositories.constraint import ConstraintRepository
from app.v7.repositories.decision import DecisionPermissionRepository, DecisionLogRepository
from app.v7.repositories.version import VersionRepository, SnapshotRepository
from app.v7.repositories.trace import AgentRunRepository, AgentTraceRepository
from app.v7.repositories.event import EventLogRepository
from app.v7.models.state import StoryState, StateChange
from app.v7.models.goal import StoryGoal, AuthorIntent
from app.v7.models.constraint import Constraint
from app.v7.models.decision import DecisionPermission, DecisionLog
from app.v7.models.version import StoryVersion, BrainSnapshot
from app.v7.models.trace import AgentRun, AgentTrace
from app.v7.models.event import EventLog


class TestBaseRepository:
    """Test BaseRepository common functionality."""

    def test_create_and_get(self, db_session: Session, novel_id: str):
        """Test create and get operations."""
        repo = StoryStateRepository(db_session)

        state = repo.create({
            "novel_id": novel_id,
            "state_type": "character",
            "state_key": "protagonist.name",
            "state_value": {"name": "张三", "age": 25},
            "confidence": 0.95,
            "source": "test",
        })

        assert state.id is not None
        assert state.novel_id == novel_id
        assert state.state_type == "character"
        assert state.state_key == "protagonist.name"
        assert state.confidence == 0.95

        fetched = repo.get(state.id)
        assert fetched is not None
        assert fetched.id == state.id
        assert fetched.state_key == "protagonist.name"

    def test_list_and_count(self, db_session: Session, novel_id: str):
        """Test list and count operations."""
        repo = StoryStateRepository(db_session)

        for i in range(5):
            repo.create({
                "novel_id": novel_id,
                "state_type": "character",
                "state_key": f"char_{i}",
                "state_value": {"name": f"角色{i}"},
                "confidence": 0.8,
                "source": "test",
            })

        items = repo.list(novel_id=novel_id)
        assert len(items) == 5

        count = repo.count(novel_id=novel_id)
        assert count == 5

    def test_update(self, db_session: Session, novel_id: str):
        """Test update operation."""
        repo = StoryStateRepository(db_session)

        state = repo.create({
            "novel_id": novel_id,
            "state_type": "character",
            "state_key": "protagonist.name",
            "state_value": {"name": "张三"},
            "confidence": 0.8,
            "source": "test",
        })

        updated = repo.update(state.id, {
            "state_value": {"name": "李四"},
            "confidence": 0.9,
        })

        assert updated.state_value["name"] == "李四"
        assert updated.confidence == 0.9

    def test_delete(self, db_session: Session, novel_id: str):
        """Test delete operation."""
        repo = StoryStateRepository(db_session)

        state = repo.create({
            "novel_id": novel_id,
            "state_type": "character",
            "state_key": "test",
            "state_value": {},
            "confidence": 0.5,
            "source": "test",
        })

        assert repo.exists(state.id) is True

        repo.delete(state.id)

        assert repo.exists(state.id) is False
        assert repo.get(state.id) is None


class TestStoryStateRepository:
    """Test StoryStateRepository specific functionality."""

    def test_get_by_key(self, db_session: Session, novel_id: str):
        """Test get by state key."""
        repo = StoryStateRepository(db_session)

        repo.create({
            "novel_id": novel_id,
            "state_type": "character",
            "state_key": "protagonist.name",
            "state_value": {"name": "张三"},
            "confidence": 0.9,
            "source": "test",
        })

        state = repo.get_by_key(novel_id, "character", "protagonist.name")
        assert state is not None
        assert state.state_value["name"] == "张三"

    def test_list_by_type(self, db_session: Session, novel_id: str):
        """Test list by state type."""
        repo = StoryStateRepository(db_session)

        for i in range(3):
            repo.create({
                "novel_id": novel_id,
                "state_type": "character",
                "state_key": f"char_{i}",
                "state_value": {},
                "confidence": 0.8,
                "source": "test",
            })

        for i in range(2):
            repo.create({
                "novel_id": novel_id,
                "state_type": "plot",
                "state_key": f"plot_{i}",
                "state_value": {},
                "confidence": 0.8,
                "source": "test",
            })

        characters = repo.list_by_type(novel_id, "character")
        assert len(characters) == 3

        plots = repo.list_by_type(novel_id, "plot")
        assert len(plots) == 2

    def test_confidence_gate_high(self, db_session: Session, novel_id: str):
        """Test confidence gate - high confidence auto-approves."""
        repo = StoryStateRepository(db_session)

        state = repo.update_with_confidence(
            novel_id, "character", "protagonist.name",
            {"name": "张三"}, 0.95, "test", "test-run"
        )

        assert state.is_active is True
        assert state.is_pending_review is False

    def test_confidence_gate_medium(self, db_session: Session, novel_id: str):
        """Test confidence gate - medium confidence needs review."""
        repo = StoryStateRepository(db_session)

        state = repo.update_with_confidence(
            novel_id, "character", "protagonist.name",
            {"name": "张三"}, 0.8, "test", "test-run"
        )

        assert state.is_active is False
        assert state.is_pending_review is True

    def test_confidence_gate_low(self, db_session: Session, novel_id: str):
        """Test confidence gate - low confidence is discarded."""
        repo = StoryStateRepository(db_session)

        state = repo.update_with_confidence(
            novel_id, "character", "protagonist.name",
            {"name": "张三"}, 0.4, "test", "test-run"
        )

        assert state is None  # discarded


class TestGoalRepository:
    """Test GoalRepository specific functionality."""

    def test_create_goal(self, db_session: Session, novel_id: str):
        """Test creating a goal."""
        repo = GoalRepository(db_session)

        goal = repo.create({
            "novel_id": novel_id,
            "goal_type": "plot",
            "goal_name": "主线剧情",
            "description": "完成主线剧情",
            "status": "in_progress",
            "progress": 0.3,
            "priority": "high",
            "confidence": 0.9,
        })

        assert goal.id is not None
        assert goal.goal_name == "主线剧情"
        assert goal.progress == 0.3

    def test_update_progress(self, db_session: Session, novel_id: str):
        """Test updating goal progress."""
        repo = GoalRepository(db_session)

        goal = repo.create({
            "novel_id": novel_id,
            "goal_type": "plot",
            "goal_name": "测试目标",
            "status": "in_progress",
            "progress": 0.0,
            "priority": "medium",
            "confidence": 0.8,
        })

        updated = repo.update_progress(goal.id, 0.5, 5)

        assert updated.progress == 0.5
        assert updated.completed_chapter == 5


class TestConstraintRepository:
    """Test ConstraintRepository specific functionality."""

    def test_create_constraint(self, db_session: Session, novel_id: str):
        """Test creating a constraint."""
        repo = ConstraintRepository(db_session)

        constraint = repo.create({
            "novel_id": novel_id,
            "constraint_type": "character",
            "constraint_name": "主角不能死",
            "description": "主角在任何情况下都不能死亡",
            "severity": "critical",
            "priority": 1,
            "is_active": True,
        })

        assert constraint.id is not None
        assert constraint.constraint_name == "主角不能死"
        assert constraint.severity == "critical"
        assert constraint.violation_count == 0

    def test_record_violation(self, db_session: Session, novel_id: str):
        """Test recording a violation."""
        repo = ConstraintRepository(db_session)

        constraint = repo.create({
            "novel_id": novel_id,
            "constraint_type": "character",
            "constraint_name": "测试约束",
            "severity": "warning",
            "priority": 1,
            "is_active": True,
        })

        assert constraint.violation_count == 0

        updated = repo.record_violation(constraint.id, "测试违规")

        assert updated.violation_count == 1
        assert updated.last_violation_at is not None


class TestDecisionPermissionRepository:
    """Test DecisionPermissionRepository specific functionality."""

    def test_get_permission_level(self, db_session: Session, novel_id: str):
        """Test getting permission level for a decision type."""
        repo = DecisionPermissionRepository(db_session)

        repo.create({
            "novel_id": novel_id,
            "decision_type": "character_death",
            "permission_level": "approve",
            "confidence_threshold": 0.9,
            "max_retries": 3,
            "is_active": True,
            "priority": 1,
        })

        level = repo.get_permission_level(novel_id, "character_death")
        assert level == "approve"

    def test_default_permission(self, db_session: Session, novel_id: str):
        """Test default permission for unknown decision type."""
        repo = DecisionPermissionRepository(db_session)

        level = repo.get_permission_level(novel_id, "unknown_decision")
        assert level == "auto"  # default


class TestVersionRepository:
    """Test VersionRepository specific functionality."""

    def test_create_version(self, db_session: Session, novel_id: str):
        """Test creating a version."""
        repo = VersionRepository(db_session)

        version = repo.create_version(
            novel_id=novel_id,
            version_type="major",
            description="测试版本",
            created_by="test",
        )

        assert version.id is not None
        assert version.version_number == 1
        assert version.version_type == "major"

    def test_get_latest(self, db_session: Session, novel_id: str):
        """Test getting latest version."""
        repo = VersionRepository(db_session)

        repo.create_version(novel_id, "minor", "v1", "test")
        repo.create_version(novel_id, "minor", "v2", "test")
        repo.create_version(novel_id, "major", "v3", "test")

        latest = repo.get_latest(novel_id)
        assert latest is not None
        assert latest.version_number == 3

    def test_get_next_version_number(self, db_session: Session, novel_id: str):
        """Test getting next version number."""
        repo = VersionRepository(db_session)

        next_num = repo.get_next_version_number(novel_id)
        assert next_num == 1

        repo.create_version(novel_id, "minor", "v1", "test")

        next_num = repo.get_next_version_number(novel_id)
        assert next_num == 2


class TestAgentRunRepository:
    """Test AgentRunRepository specific functionality."""

    def test_start_and_complete_run(self, db_session: Session, novel_id: str):
        """Test starting and completing a run."""
        repo = AgentRunRepository(db_session)

        run = repo.start_run(
            novel_id=novel_id,
            run_type="chapter_generation",
            trigger="manual",
            input_data={"chapter": 1},
        )

        assert run.id is not None
        assert run.status == "running"
        assert run.started_at is not None
        assert run.completed_at is None

        completed = repo.complete_run(
            run.id,
            status="succeeded",
            output_data={"result": "success"},
            total_tokens=1000,
            total_cost=0.01,
            step_count=5,
        )

        assert completed.status == "succeeded"
        assert completed.completed_at is not None
        assert completed.duration_seconds > 0
        assert completed.total_tokens == 1000
        assert completed.total_cost == 0.01


class TestEventLogRepository:
    """Test EventLogRepository specific functionality."""

    def test_record_event(self, db_session: Session, novel_id: str):
        """Test recording an event."""
        repo = EventLogRepository(db_session)

        event = repo.record_event(
            novel_id=novel_id,
            event_type="state_updated",
            event_name="状态更新",
            event_category="brain",
            event_data={"key": "value"},
            source="test",
            severity="info",
            description="测试事件",
        )

        assert event.id is not None
        assert event.event_type == "state_updated"
        assert event.event_time is not None

    def test_list_by_correlation(self, db_session: Session, novel_id: str):
        """Test listing events by correlation ID."""
        repo = EventLogRepository(db_session)

        correlation_id = "corr-001"

        for i in range(3):
            repo.record_event(
                novel_id=novel_id,
                event_type="test",
                event_name=f"事件{i}",
                event_category="test",
                source="test",
                severity="info",
                correlation_id=correlation_id,
            )

        events = repo.list_by_correlation(novel_id, correlation_id)
        assert len(events) == 3
