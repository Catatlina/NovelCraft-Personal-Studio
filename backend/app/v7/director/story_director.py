"""Story Director - Sprint 2 Alpha.

The decision-making layer that coordinates all engines.
AI is the writer, human is the producer.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..brain.novel_brain import NovelBrain
from ..trace.tracer import ExecutionTracer
from ..events.event_bus import EventBus
from ..engines.plot_engine import PlotEngine
from ..engines.memory_engine import MemoryEngine
from ..engines.review_engine import ReviewEngine
from ..repositories.decision import DecisionPermissionRepository


class DecisionPermissionSystem:
    """
    Decision permission system.
    
    Permission levels:
    - auto: AI can decide automatically
    - notify: AI decides, but human is notified
    - approve: AI proposes, human must approve
    - forbidden: AI cannot decide, only human can
    """

    def __init__(self, db: AsyncSession, novel_id: uuid.UUID):
        self.db = db
        self.novel_id = novel_id
        self.perm_repo = DecisionPermissionRepository(db)

    async def get_permission(self, decision_type: str) -> str:
        """Get permission level for a decision type."""
        perm = await self.perm_repo.get_by_type(self.novel_id, decision_type)
        if perm:
            return perm.permission_level
        return "auto"  # default

    async def can_auto_decide(self, decision_type: str, confidence: float = 0.9) -> bool:
        """Check if AI can auto-decide."""
        level = await self.get_permission(decision_type)
        
        if level == "auto":
            return True
        elif level == "notify":
            return True  # Can decide, but will notify
        elif level == "approve":
            return False  # Needs human approval
        elif level == "forbidden":
            return False
        return True

    async def needs_approval(self, decision_type: str) -> bool:
        """Check if decision needs human approval."""
        level = await self.get_permission(decision_type)
        return level in ("approve", "forbidden")


class StoryDirector:
    """
    Story Director - the decision-making layer.
    
    Coordinates all engines and makes high-level decisions.
    Sprint 2 Alpha: Basic chapter generation loop.
    """

    def __init__(
        self,
        db: AsyncSession,
        novel_id: uuid.UUID,
        brain: NovelBrain,
        tracer: ExecutionTracer,
        event_bus: EventBus,
    ):
        self.db = db
        self.novel_id = novel_id
        self.brain = brain
        self.tracer = tracer
        self.event_bus = event_bus
        self.permission_system = DecisionPermissionSystem(db, novel_id)

        # Engines
        self.plot_engine = PlotEngine(db, novel_id, brain, tracer, event_bus)
        self.memory_engine = MemoryEngine(db, novel_id, brain, tracer, event_bus)
        self.review_engine = ReviewEngine(db, novel_id, brain, tracer, event_bus)

    async def generate_chapter(
        self,
        chapter_number: int,
        *,
        prompt: str | None = None,
        outline: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a complete chapter.
        
        Sprint 2 Alpha: Full pipeline with trace and review.
        Actual text generation will be added in Sprint 2 final.
        """
        # Start run
        run_id = await self.tracer.start_run(
            "chapter_generation",
            trigger="manual",
            chapter_number=chapter_number,
            input_data={"chapter_number": chapter_number, "prompt": prompt},
        )

        try:
            # Step 1: Planning
            async with self.tracer.trace_step(
                "director.planning",
                "planning",
                input_summary=f"Plan chapter {chapter_number}",
            ):
                plan = await self._plan_chapter(chapter_number, prompt, outline)

            # Step 2: Plot analysis
            async with self.tracer.trace_step(
                "director.plot_analysis",
                "analysis",
                input_summary="Analyze plot structure",
            ):
                plot_result = await self.plot_engine.analyze({
                    "chapter_number": chapter_number,
                    "outline": outline or "",
                })

            # Step 3: Memory extraction (after generation, placeholder for now)
            async with self.tracer.trace_step(
                "director.memory_update",
                "update",
                input_summary="Update story memory",
            ):
                memory_result = await self.memory_engine.run({
                    "chapter_text": outline or "",
                    "chapter_number": chapter_number,
                })

            # Step 4: Review
            async with self.tracer.trace_step(
                "director.review",
                "review",
                input_summary="Review generated content",
            ):
                review_result = await self.review_engine.run({
                    "chapter_text": outline or "",
                    "chapter_number": chapter_number,
                })

            # Step 5: Finalize
            async with self.tracer.trace_step(
                "director.finalize",
                "finalize",
                input_summary="Finalize chapter",
            ):
                result = await self._finalize_chapter(
                    chapter_number,
                    plan,
                    plot_result,
                    memory_result,
                    review_result,
                )

            # Complete run
            await self.tracer.complete_run(
                run_id,
                output_data=result,
            )

            # Publish event
            await self.event_bus.publish(
                "chapter_generated",
                f"Chapter {chapter_number} generated",
                "generation",
                source_run_id=run_id,
                event_data={"chapter_number": chapter_number, "result": "success"},
            )

            return {
                "run_id": str(run_id),
                "chapter_number": chapter_number,
                "status": "completed",
                "review_score": review_result.result.get("overall_score", 0) if review_result.result else 0,
                "result": result,
            }

        except Exception as e:
            await self.tracer.complete_run(
                run_id,
                error_message=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def _plan_chapter(
        self,
        chapter_number: int,
        prompt: str | None,
        outline: str | None,
    ) -> dict[str, Any]:
        """Plan a chapter."""
        # Check if we can auto-plan
        can_auto = await self.permission_system.can_auto_decide("chapter_plan")
        
        if not can_auto:
            # Record pending decision
            await self.brain.record_decision(
                "chapter_plan",
                "pending_human_approval",
                decision_reason="Chapter planning requires human approval",
                confidence=0.5,
                permission_level="approve",
                status="pending",
                decided_by="ai",
            )
            return {
                "status": "pending_approval",
                "message": "Chapter plan requires human approval",
            }

        # Alpha: Simple planning
        plan = {
            "chapter_number": chapter_number,
            "prompt": prompt,
            "outline": outline,
            "goals_to_advance": [],
            "constraints_to_respect": [],
            "status": "planned",
        }

        # Record decision
        await self.brain.record_decision(
            "chapter_plan",
            f"Chapter {chapter_number} planned",
            decision_reason="Auto-planned by director",
            confidence=0.7,
            permission_level="auto",
            status="completed",
            decided_by="ai",
        )

        return plan

    async def _finalize_chapter(
        self,
        chapter_number: int,
        plan: dict[str, Any],
        plot_result: Any,
        memory_result: Any,
        review_result: Any,
    ) -> dict[str, Any]:
        """Finalize chapter generation."""
        # Check review score
        score = 0
        if review_result and review_result.result:
            score = review_result.result.get("overall_score", 0)

        # Check if score is acceptable
        # Alpha: threshold is 60 (very low for testing)
        passed = score >= 60

        if not passed:
            # Record decision about rework
            await self.brain.record_decision(
                "chapter_quality",
                "needs_rework",
                decision_reason=f"Review score {score} below threshold",
                confidence=0.8,
                permission_level="notify",
                status="completed",
                decided_by="ai",
            )

        return {
            "chapter_number": chapter_number,
            "passed_review": passed,
            "review_score": score,
            "plot_analyzed": plot_result.success if plot_result else False,
            "memory_updated": memory_result.success if memory_result else False,
        }

    async def get_decision_queue(self) -> list[dict[str, Any]]:
        """Get decisions pending human approval."""
        decisions = await self.brain.get_decision_logs(status="pending", limit=50)
        return decisions
