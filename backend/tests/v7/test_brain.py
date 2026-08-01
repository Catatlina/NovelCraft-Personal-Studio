"""
V7 Novel Brain Core Tests
==========================

Tests for Novel Brain subsystems.
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.v7.brain.state_manager import StoryStateManager
from app.v7.brain.goal_system import GoalSystem
from app.v7.brain.constraint_system import ConstraintSystem
from app.v7.brain.version_control import VersionControl
from app.v7.brain.novel_brain import NovelBrain


class TestStoryStateManager:
    """Test StoryStateManager."""

    def test_update_state_high_confidence(self, db_session: Session, novel_id: str):
        """Test updating state with high confidence - auto approved."""
        manager = StoryStateManager(db_session)

        result = manager.update_state(
            novel_id=novel_id,
            state_type="character",
            state_key="protagonist.name",
            state_value={"name": "张三"},
            confidence=0.95,
            source="test",
            source_run_id="test-run",
        )

        assert result["status"] == "updated"
        assert result["state"].is_active is True
        assert result["state"].is_pending_review is False

    def test_update_state_medium_confidence(self, db_session: Session, novel_id: str):
        """Test updating state with medium confidence - needs review."""
        manager = StoryStateManager(db_session)

        result = manager.update_state(
            novel_id=novel_id,
            state_type="character",
            state_key="protagonist.name",
            state_value={"name": "张三"},
            confidence=0.8,
            source="test",
            source_run_id="test-run",
        )

        assert result["status"] == "pending_review"
        assert result["state"].is_active is False
        assert result["state"].is_pending_review is True

    def test_update_state_low_confidence(self, db_session: Session, novel_id: str):
        """Test updating state with low confidence - discarded."""
        manager = StoryStateManager(db_session)

        result = manager.update_state(
            novel_id=novel_id,
            state_type="character",
            state_key="protagonist.name",
            state_value={"name": "张三"},
            confidence=0.4,
            source="test",
            source_run_id="test-run",
        )

        assert result["status"] == "discarded"
        assert result["state"] is None

    def test_approve_state(self, db_session: Session, novel_id: str):
        """Test approving a pending state."""
        manager = StoryStateManager(db_session)

        # Create a pending state
        result = manager.update_state(
            novel_id=novel_id,
            state_type="character",
            state_key="protagonist.name",
            state_value={"name": "张三"},
            confidence=0.7,
            source="test",
            source_run_id="test-run",
        )

        assert result["status"] == "pending_review"
        state_id = result["state"].id

        # Approve it
        approved = manager.approve_state(state_id)

        assert approved.is_active is True
        assert approved.is_pending_review is False

    def test_reject_state(self, db_session: Session, novel_id: str):
        """Test rejecting a pending state."""
        manager = StoryStateManager(db_session)

        result = manager.update_state(
            novel_id=novel_id,
            state_type="character",
            state_key="protagonist.name",
            state_value={"name": "张三"},
            confidence=0.7,
            source="test",
            source_run_id="test-run",
        )

        state_id = result["state"].id

        rejected = manager.reject_state(state_id, reason="测试拒绝")

        assert rejected.is_active is False
        assert rejected.is_pending_review is False

    def test_get_pending_review(self, db_session: Session, novel_id: str):
        """Test getting pending review states."""
        manager = StoryStateManager(db_session)

        # Create some states
        for i in range(3):
            manager.update_state(
                novel_id=novel_id,
                state_type="character",
                state_key=f"char_{i}",
                state_value={"name": f"角色{i}"},
                confidence=0.7,  # pending
                source="test",
                source_run_id="test-run",
            )

        for i in range(2):
            manager.update_state(
                novel_id=novel_id,
                state_type="character",
                state_key=f"auto_{i}",
                state_value={"name": f"自动{i}"},
                confidence=0.95,  # auto approved
                source="test",
                source_run_id="test-run",
            )

        pending = manager.get_pending_review(novel_id)
        assert len(pending) == 3

    def test_state_change_history(self, db_session: Session, novel_id: str):
        """Test state change history is recorded."""
        manager = StoryStateManager(db_session)

        # First update
        result1 = manager.update_state(
            novel_id=novel_id,
            state_type="character",
            state_key="protagonist.name",
            state_value={"name": "张三"},
            confidence=0.95,
            source="test",
            source_run_id="run-1",
        )

        state_id = result1["state"].id

        # Second update
        manager.update_state(
            novel_id=novel_id,
            state_type="character",
            state_key="protagonist.name",
            state_value={"name": "李四"},
            confidence=0.95,
            source="test",
            source_run_id="run-2",
        )

        # Check history
        changes = manager.get_state_changes(state_id)
        assert len(changes) >= 2


class TestGoalSystem:
    """Test GoalSystem."""

    def test_create_goal(self, db_session: Session, novel_id: str):
        """Test creating a goal."""
        system = GoalSystem(db_session)

        goal = system.create_goal(
            novel_id=novel_id,
            goal_type="plot",
            goal_name="主线剧情",
            description="完成主线剧情",
            priority="high",
        )

        assert goal.id is not None
        assert goal.goal_name == "主线剧情"
        assert goal.status == "pending"

    def test_update_progress(self, db_session: Session, novel_id: str):
        """Test updating goal progress."""
        system = GoalSystem(db_session)

        goal = system.create_goal(
            novel_id=novel_id,
            goal_type="plot",
            goal_name="测试目标",
            priority="medium",
        )

        updated = system.update_progress(goal.id, 0.5, 10)

        assert updated.progress == 0.5
        assert updated.completed_chapter == 10
        assert updated.status == "in_progress"

    def test_goal_tree(self, db_session: Session, novel_id: str):
        """Test goal tree structure."""
        system = GoalSystem(db_session)

        # Create parent goal
        parent = system.create_goal(
            novel_id=novel_id,
            goal_type="plot",
            goal_name="第一卷",
            priority="high",
        )

        # Create child goals
        for i in range(3):
            system.create_goal(
                novel_id=novel_id,
                goal_type="plot",
                goal_name=f"第{i+1}章",
                parent_goal_id=parent.id,
                goal_order=i,
                priority="medium",
            )

        tree = system.get_goal_tree(novel_id)
        # At least the parent should be in the tree
        assert len(tree) >= 1


class TestConstraintSystem:
    """Test ConstraintSystem."""

    def test_create_constraint(self, db_session: Session, novel_id: str):
        """Test creating a constraint."""
        system = ConstraintSystem(db_session)

        constraint = system.create_constraint(
            novel_id=novel_id,
            constraint_type="character",
            constraint_name="主角不能死",
            description="主角在任何情况下都不能死亡",
            severity="critical",
        )

        assert constraint.id is not None
        assert constraint.violation_count == 0

    def test_check_constraints(self, db_session: Session, novel_id: str):
        """Test checking constraints."""
        system = ConstraintSystem(db_session)

        system.create_constraint(
            novel_id=novel_id,
            constraint_type="character",
            constraint_name="测试约束",
            severity="warning",
            check_method="manual",
        )

        # Manual check method should return no violations
        violations = system.check_constraints(novel_id, "chapter_content", "测试内容")
        assert isinstance(violations, list)

    def test_record_violation(self, db_session: Session, novel_id: str):
        """Test recording a violation."""
        system = ConstraintSystem(db_session)

        constraint = system.create_constraint(
            novel_id=novel_id,
            constraint_type="character",
            constraint_name="测试约束",
            severity="warning",
        )

        assert constraint.violation_count == 0

        system.record_violation(constraint.id, "测试违规原因")

        updated = system.get_constraint(constraint.id)
        assert updated.violation_count == 1


class TestVersionControl:
    """Test VersionControl."""

    def test_create_version(self, db_session: Session, novel_id: str):
        """Test creating a version."""
        vc = VersionControl(db_session)

        version = vc.create_version(
            novel_id=novel_id,
            version_type="minor",
            description="测试版本",
            created_by="test",
        )

        assert version.id is not None
        assert version.version_number == 1

    def test_create_snapshot(self, db_session: Session, novel_id: str):
        """Test creating a snapshot."""
        vc = VersionControl(db_session)

        version = vc.create_version(novel_id, "minor", "v1", "test")

        snapshot = vc.create_snapshot(
            novel_id=novel_id,
            version_id=version.id,
            snapshot_type="full",
            state_data={"test": "data"},
            description="测试快照",
        )

        assert snapshot.id is not None
        assert snapshot.version_id == version.id

    def test_get_latest_version(self, db_session: Session, novel_id: str):
        """Test getting latest version."""
        vc = VersionControl(db_session)

        vc.create_version(novel_id, "minor", "v1", "test")
        vc.create_version(novel_id, "minor", "v2", "test")

        latest = vc.get_latest_version(novel_id)
        assert latest.version_number == 2


class TestNovelBrain:
    """Test NovelBrain main class."""

    def test_get_overview(self, db_session: Session, novel_id: str):
        """Test getting brain overview."""
        brain = NovelBrain(db_session)

        # Add some test data
        brain.state.update_state(
            novel_id, "character", "protagonist", {"name": "张三"}, 0.9, "test", "run-1"
        )
        brain.goals.create_goal(
            novel_id, "plot", "主线", priority="high"
        )
        brain.constraints.create_constraint(
            novel_id, "character", "主角不死", severity="critical"
        )

        overview = brain.get_overview(novel_id)

        assert overview["novel_id"] == novel_id
        assert "state_count" in overview
        assert "goal_count" in overview
        assert "constraint_count" in overview
        assert "version_count" in overview

    def test_record_decision(self, db_session: Session, novel_id: str):
        """Test recording a decision."""
        brain = NovelBrain(db_session)

        decision = brain.record_decision(
            novel_id=novel_id,
            decision_type="character_action",
            decision="主角决定去北京",
            decision_reason="剧情需要",
            confidence=0.85,
            permission_level="auto",
            status="approved",
            run_id="test-run",
        )

        assert decision.id is not None
        assert decision.decision_type == "character_action"

    def test_get_decision_logs(self, db_session: Session, novel_id: str):
        """Test getting decision logs."""
        brain = NovelBrain(db_session)

        for i in range(5):
            brain.record_decision(
                novel_id=novel_id,
                decision_type=f"type_{i}",
                decision=f"决策{i}",
                decision_reason="测试",
                confidence=0.8,
                permission_level="auto",
                status="approved",
                run_id="test-run",
            )

        logs = brain.get_decision_logs(novel_id, limit=10)
        assert len(logs) == 5
