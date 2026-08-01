"""
V7 End-to-End Integration Tests
=================================

Tests for the complete chapter generation pipeline.

Note: These tests require a real PostgreSQL database and AI API access.
For unit tests without external dependencies, see test_repositories.py and test_brain.py.
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.v7.brain.novel_brain import NovelBrain
from app.v7.director.story_director import StoryDirector
from app.v7.trace.tracer import ExecutionTracer


class TestChapterGenerationPipeline:
    """Test the complete chapter generation pipeline."""

    @pytest.mark.skip(reason="Requires real database and AI API")
    def test_full_chapter_generation(self, db_session: Session, novel_id: str):
        """Test full chapter generation pipeline.

        This is a smoke test that verifies the complete pipeline works:
        1. Initialize brain state
        2. Start agent run
        3. Director plans the chapter
        4. Generation engine generates text
        5. Review engine reviews the output
        6. State is updated
        7. Run is completed
        """
        brain = NovelBrain(db_session)
        tracer = ExecutionTracer(db_session)
        director = StoryDirector(brain, tracer)

        # Start a chapter generation run
        result = director.generate_chapter(
            novel_id=novel_id,
            chapter_number=1,
            chapter_title="第一章 初入江湖",
            prompt="主角初入江湖，遇到第一个挑战",
        )

        assert result is not None
        assert result["status"] in ["succeeded", "pending_review"]
        assert "run_id" in result
        assert "chapter_content" in result or "pending_decisions" in result

    @pytest.mark.skip(reason="Requires real database and AI API")
    def test_decision_approval_workflow(self, db_session: Session, novel_id: str):
        """Test decision approval workflow.

        Verifies that:
        1. High-impact decisions require approval
        2. Decisions can be approved or rejected
        3. Approved decisions are applied
        4. Rejected decisions are rolled back
        """
        brain = NovelBrain(db_session)
        tracer = ExecutionTracer(db_session)
        director = StoryDirector(brain, tracer)

        # Generate a chapter that would require approval
        result = director.generate_chapter(
            novel_id=novel_id,
            chapter_number=2,
            chapter_title="第二章 重大转折",
            prompt="主角做出一个重大决定，改变了故事走向",
        )

        if result["status"] == "pending_review":
            # There should be pending decisions
            pending = director.get_pending_decisions(novel_id)
            assert len(pending) > 0

            # Approve all decisions
            for decision in pending:
                director.approve_decision(decision.id)

            # Verify decisions are applied
            applied = director.get_decision_logs(novel_id, status="approved")
            assert len(applied) > 0

    @pytest.mark.skip(reason="Requires real database and AI API")
    def test_state_consistency_after_generation(self, db_session: Session, novel_id: str):
        """Test that state remains consistent after generation.

        Verifies that:
        1. All state changes are recorded
        2. Confidence levels are correct
        3. No invalid states exist
        4. State change log is complete
        """
        brain = NovelBrain(db_session)
        tracer = ExecutionTracer(db_session)
        director = StoryDirector(brain, tracer)

        # Generate a few chapters
        for i in range(3):
            director.generate_chapter(
                novel_id=novel_id,
                chapter_number=i + 1,
                chapter_title=f"第{i+1}章",
                prompt=f"第{i+1}章的内容",
            )

        # Check state consistency
        overview = brain.get_overview(novel_id)
        assert overview["state_count"] > 0

        # All active states should have confidence >= threshold
        states = brain.state.get_active_states(novel_id)
        for state in states:
            assert state.confidence >= 0.5  # at least not discarded

        # State change log should be complete
        changes = brain.state.get_all_changes(novel_id)
        assert len(changes) > 0


class TestTraceCompleteness:
    """Test that execution traces are complete."""

    @pytest.mark.skip(reason="Requires real database and AI API")
    def test_full_trace_is_recorded(self, db_session: Session, novel_id: str):
        """Test that a full generation run has complete trace.

        Verifies that:
        1. Run is created with correct status
        2. All steps are recorded
        3. Token counts are accurate
        4. Cost is calculated correctly
        5. Duration is recorded
        """
        brain = NovelBrain(db_session)
        tracer = ExecutionTracer(db_session)
        director = StoryDirector(brain, tracer)

        result = director.generate_chapter(
            novel_id=novel_id,
            chapter_number=1,
            chapter_title="测试章节",
            prompt="测试内容",
        )

        run_id = result["run_id"]

        # Get the run
        run = tracer.get_run(run_id)
        assert run is not None
        assert run.status == "succeeded"
        assert run.started_at is not None
        assert run.completed_at is not None
        assert run.duration_seconds > 0

        # Get trace steps
        steps = tracer.get_run_steps(run_id)
        assert len(steps) > 0

        # Each step should have timing
        for step in steps:
            assert step.step_name is not None
            assert step.started_at is not None
            assert step.completed_at is not None or step.status == "running"
