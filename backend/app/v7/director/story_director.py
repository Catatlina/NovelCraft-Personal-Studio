"""Story Director - Sprint 2.

The decision-making layer that coordinates all engines through a real 7-step
agent loop:

    perceive -> assess -> decide -> plan -> execute -> observe -> update

AI is the writer, human is the producer: the permission system and the
confidence gate are enforced in `decide` and cannot be bypassed.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..brain.novel_brain import NovelBrain
from ..trace.tracer import ExecutionTracer
from ..events.event_bus import EventBus
from ..events.subscribers import BrainStateSubscribers
from ..engines.plot_engine import PlotEngine
from ..engines.memory_engine import MemoryEngine
from ..engines.review_engine import ReviewEngine
from ..generation.generation_engine import (
    CHAPTER_STATE_TYPE,
    GenerationEngine,
    chapter_state_key,
    chinese_word_count,
)
from ..repositories.decision import DecisionPermissionRepository
from ..integration.quality import (
    MAX_REWORKS,
    QUALITY_REWORK_SCORE,
    evaluate_review,
)
from ..integration.v6_bridge import (
    build_transition_contract,
    persist_accepted_v7_chapter,
)

AGENT_LOOP_STEPS: tuple[str, ...] = (
    "perceive",
    "assess",
    "decide",
    "plan",
    "execute",
    "observe",
    "update",
)

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

    async def get_confidence_threshold(self, decision_type: str) -> float:
        """Minimum AI confidence required for this decision type."""
        perm = await self.perm_repo.get_by_type(self.novel_id, decision_type)
        threshold = getattr(perm, "confidence_threshold", None) if perm else None
        return float(threshold) if threshold is not None else 0.7

    async def evaluate(
        self, decision_type: str, confidence: float
    ) -> dict[str, Any]:
        """
        Combined permission + confidence gate.

        Returns {allowed, level, threshold, blocked_reason}.
        """
        level = await self.get_permission(decision_type)
        threshold = await self.get_confidence_threshold(decision_type)

        if level == "forbidden":
            return {
                "allowed": False,
                "level": level,
                "threshold": threshold,
                "blocked_reason": "decision type is forbidden for AI",
            }
        if level == "approve":
            return {
                "allowed": False,
                "level": level,
                "threshold": threshold,
                "blocked_reason": "human approval required",
            }
        if confidence < threshold:
            return {
                "allowed": False,
                "level": level,
                "threshold": threshold,
                "blocked_reason": (
                    f"confidence {confidence:.2f} below threshold {threshold:.2f}"
                ),
            }
        return {
            "allowed": True,
            "level": level,
            "threshold": threshold,
            "blocked_reason": None,
        }

    async def can_auto_decide(self, decision_type: str, confidence: float = 0.9) -> bool:
        """Check if AI can auto-decide."""
        return (await self.evaluate(decision_type, confidence))["allowed"]

    async def needs_approval(self, decision_type: str) -> bool:
        """Check if decision needs human approval."""
        level = await self.get_permission(decision_type)
        return level in ("approve", "forbidden")


class StoryDirector:
    """Story Director - runs the 7-step agent loop for chapter generation."""

    def __init__(
        self,
        db: AsyncSession,
        novel_id: uuid.UUID,
        brain: NovelBrain,
        tracer: ExecutionTracer,
        event_bus: EventBus,
        project_id: str | None = None,
        user_id: str | None = None,
        provider_config: dict[str, str] | None = None,
        generation_metadata: dict[str, Any] | None = None,
    ):
        self.db = db
        self.novel_id = novel_id
        self.brain = brain
        self.tracer = tracer
        self.event_bus = event_bus
        self.project_id = project_id
        self.user_id = user_id
        self.provider_config = provider_config or {}
        self.generation_metadata = generation_metadata or {}
        self.permission_system = DecisionPermissionSystem(db, novel_id)

        # Engines
        self.plot_engine = PlotEngine(
            db, novel_id, brain, tracer, event_bus,
            project_id=project_id,
            provider_config=self.provider_config,
        )
        self.memory_engine = MemoryEngine(
            db, novel_id, brain, tracer, event_bus,
            project_id=project_id,
            provider_config=self.provider_config,
        )
        self.review_engine = ReviewEngine(
            db, novel_id, brain, tracer, event_bus,
            project_id=project_id,
            provider_config=self.provider_config,
        )
        self.generation_engine = GenerationEngine(
            db, novel_id, brain, tracer, event_bus,
            project_id=project_id,
            provider_config=self.provider_config,
        )

        # Event-driven state projection
        self.subscribers = BrainStateSubscribers(brain, event_bus)
        self.subscribers.register()

    # ── main entry point ────────────────────────────────────────────────
    async def generate_chapter(
        self,
        chapter_number: int,
        *,
        prompt: str | None = None,
        outline: str | None = None,
        target_word_count: int = 3000,
        allow_rework: bool = True,
    ) -> dict[str, Any]:
        """Run the full 7-step agent loop for one chapter."""
        run_id = await self.tracer.start_run(
            "chapter_generation",
            trigger="manual",
            chapter_number=chapter_number,
            input_data={
                "chapter_number": chapter_number,
                "prompt": prompt,
                "outline": outline,
                "target_word_count": target_word_count,
            },
        )

        try:
            # ── 1. PERCEIVE ────────────────────────────────────────────
            async with self.tracer.trace_step(
                "director.perceive", "perceive",
                input_summary=f"Perceive story state before chapter {chapter_number}",
            ) as step:
                perception = await self._perceive(chapter_number)
                step.set_output(
                    f"{perception['state_total']} states, "
                    f"{perception['pending_review']} pending, "
                    f"last chapter={perception['last_chapter']}",
                    data=perception,
                )

            # ── 2. ASSESS ──────────────────────────────────────────────
            async with self.tracer.trace_step(
                "director.assess", "assess",
                input_summary="Assess plot situation",
            ) as step:
                assessment = await self._assess(chapter_number, outline, perception)
                step.set_output(
                    assessment["summary"],
                    data={"plot_success": assessment["plot_success"]},
                    confidence=assessment["confidence"],
                )

            # ── 3. DECIDE (permission + confidence gate) ───────────────
            async with self.tracer.trace_step(
                "director.decide", "decide",
                input_summary="Apply permission and confidence gate",
            ) as step:
                decision = await self._decide(
                    chapter_number, assessment, run_id=run_id
                )
                step.set_output(
                    f"gate={'allowed' if decision['allowed'] else 'blocked'} "
                    f"({decision['level']}, thr={decision['threshold']})",
                    data=decision,
                    confidence=assessment["confidence"],
                )

            if not decision["allowed"]:
                result = {
                    "run_id": str(run_id),
                    "chapter_number": chapter_number,
                    "status": "pending_approval",
                    "blocked_reason": decision["blocked_reason"],
                    "permission_level": decision["level"],
                    "decision_id": decision.get("decision_id"),
                    "steps_executed": ["perceive", "assess", "decide"],
                }
                await self.tracer.complete_run(run_id, output_data=result)
                return result

            # ── 4. PLAN ────────────────────────────────────────────────
            async with self.tracer.trace_step(
                "director.plan", "plan",
                input_summary=f"Plan chapter {chapter_number}",
            ) as step:
                plan = await self._plan(
                    chapter_number, prompt, outline, assessment, perception,
                    target_word_count=target_word_count,
                )
                step.set_output(
                    f"target {plan['target_word_count']} chars, "
                    f"{len(plan['goals_to_advance'])} goal(s), "
                    f"{len(plan['constraints_to_respect'])} constraint(s)",
                    data=plan,
                )

            # ── 5. EXECUTE (real AI generation) ────────────────────────
            async with self.tracer.trace_step(
                "director.execute", "execute",
                input_summary="Generate chapter text with AI",
            ) as step:
                generation = await self.generation_engine.generate_chapter(
                    chapter_number,
                    prompt=plan["prompt"],
                    outline=plan["outline"],
                    target_word_count=plan["target_word_count"],
                    plot_brief=plan.get("plot_brief"),
                )
                step.set_output(
                    f"{generation['word_count']} chars "
                    f"(target {generation['target_word_count']})",
                    data={
                        "word_count": generation["word_count"],
                        "meets_target": generation["meets_target"],
                        "title": generation["title"],
                    },
                )

            # ── 6. OBSERVE (7-dimension review + quality gate) ─────────
            async with self.tracer.trace_step(
                "director.observe", "observe",
                input_summary="Review generated chapter (7 dimensions)",
            ) as step:
                observation = await self._observe(
                    chapter_number,
                    generation,
                    allow_rework=allow_rework,
                    plan=plan,
                )
                generation = observation["generation"]
                step.set_output(
                    f"score={observation['review_score']} "
                    f"passed={observation['passed_review']} "
                    f"rework={observation['rework_count']}",
                    data={
                        "review_score": observation["review_score"],
                        "dimension_scores": observation["dimension_scores"],
                        "rework_count": observation["rework_count"],
                    },
                    confidence=observation["review_confidence"],
                )

            # ── 7. UPDATE (persist chapter + memory extraction) ────────
            async with self.tracer.trace_step(
                "director.update", "update",
                input_summary="Persist chapter and update Novel Brain",
            ) as step:
                update_result = await self._update(
                    chapter_number, generation, observation, run_id=run_id
                )
                step.set_output(
                    f"states applied={update_result['states_applied']} "
                    f"pending={update_result['states_pending_review']}",
                    data=update_result,
                )

            result = {
                "run_id": str(run_id),
                "chapter_number": chapter_number,
                "status": "completed" if observation["passed_review"] else "needs_review",
                "title": generation["title"],
                "content": generation["text"],
                "word_count": generation["word_count"],
                "meets_target": generation["meets_target"],
                "deai": generation["deai"],
                "scene_plan": generation["scene_plan"],
                "review_score": observation["review_score"],
                "dimension_scores": observation["dimension_scores"],
                "passed_review": observation["passed_review"],
                "rework_count": observation["rework_count"],
                "memory": {
                    "states_applied": update_result["states_applied"],
                    "states_pending_review": update_result["states_pending_review"],
                    "states_discarded": update_result["states_discarded"],
                    "conflicts_found": update_result["conflicts_found"],
                },
                "transition_contract": update_result.get("transition_contract", {}),
                "v6_content": update_result.get("v6_content"),
                "v6_content_id": (update_result.get("v6_content") or {}).get("content_id"),
                "steps_executed": list(AGENT_LOOP_STEPS),
                "usage": generation["usage"],
            }

            # The chapter body is already persisted as a story state; keep the
            # run output_data lean so v7_agent_runs stays queryable.  V6 is
            # only updated when the strict quality gate passed.
            run_output = {k: v for k, v in result.items() if k not in ("content", "scene_plan")}
            run_stats = await self.tracer.complete_run(run_id, output_data=run_output)
            result["run_stats"] = run_stats

            await self.event_bus.publish(
                "chapter_generated",
                f"Chapter {chapter_number} generated",
                "generation",
                source="director",
                source_run_id=run_id,
                event_data={
                    "chapter_number": chapter_number,
                    "word_count": generation["word_count"],
                    "review_score": observation["review_score"],
                    "passed_review": observation["passed_review"],
                    "run_id": str(run_id),
                    "title": generation["title"],
                },
            )

            return result

        except Exception as e:
            await self.tracer.complete_run(
                run_id,
                error_message=str(e),
                error_type=type(e).__name__,
            )
            raise

    # ── step 1 ──────────────────────────────────────────────────────────
    async def _perceive(self, chapter_number: int) -> dict[str, Any]:
        overview = await self.brain.get_overview()
        progress_state = await self.brain.state.get_state("global", "story_progress")
        progress = (progress_state or {}).get("value") or {}
        pending_states = await self.brain.state.get_pending_review(limit=20)
        previous = await self.generation_engine.context_assembler.load_previous_chapters(
            chapter_number, count=1
        )

        return {
            "chapter_number": chapter_number,
            "state_total": overview.get("states", {}).get("total", 0),
            "pending_review": overview.get("states", {}).get("pending_review", 0),
            "goals": overview.get("goals", {}),
            "constraints": overview.get("constraints", {}),
            "last_chapter": progress.get("last_chapter"),
            "chapters_done": progress.get("chapter_count", 0),
            "total_words": progress.get("total_words", 0),
            "pending_review_keys": [
                s.get("key") for s in (pending_states or [])
            ][:20],
            "has_previous_chapter": bool(previous),
        }

    # ── step 2 ──────────────────────────────────────────────────────────
    async def _assess(
        self,
        chapter_number: int,
        outline: str | None,
        perception: dict[str, Any],
    ) -> dict[str, Any]:
        # Pre-generation assessment: the plot engine looks at goals, open
        # threads and the previous chapter node, then reports how safe it is to
        # auto-generate this chapter. It runs the full 5-phase engine contract
        # so the plot tree is actually written before we start writing prose.
        plot_run = await self.plot_engine.run(
            {
                "chapter_number": chapter_number,
                "outline": outline or "",
                "perception": perception,
                "mode": "assess",
            }
        )

        phases = plot_run.metadata.get("phases") or {}
        analyze_phase = phases.get("analyze") or {}
        assessment_data = analyze_phase.get("result") or {}
        execute_phase = phases.get("execute") or {}

        gaps: list[str] = list(assessment_data.get("signals") or [])
        blockers: list[str] = list(assessment_data.get("blockers") or [])

        # The gate must key off the assessment's own confidence, not the
        # confidence of the last phase (which only reflects state persistence).
        confidence = float(analyze_phase.get("confidence") or 0.0)
        if not plot_run.success:
            blockers.append(plot_run.reason or "plot engine pipeline failed")
            confidence = min(confidence, 0.4)

        return {
            "plot_success": bool(plot_run.success),
            "plot_result": assessment_data,
            "plot_execute": execute_phase.get("result"),
            "plot_warnings": list(plot_run.warnings or []),
            "must_accomplish": assessment_data.get("must_accomplish") or [],
            "suggested_beats": assessment_data.get("suggested_beats") or [],
            "chapter_title_hint": assessment_data.get("chapter_title_hint"),
            "gaps": gaps,
            "blockers": blockers,
            "confidence": round(confidence, 3),
            "usage": plot_run.metadata.get("usage"),
            "summary": (
                f"plot={'ok' if plot_run.success else 'failed'}, "
                f"objectives={len(assessment_data.get('must_accomplish') or [])}, "
                f"gaps={len(gaps)}, blockers={len(blockers)}, "
                f"confidence={confidence:.2f}"
            ),
        }

    # ── step 3 ──────────────────────────────────────────────────────────
    async def _decide(
        self,
        chapter_number: int,
        assessment: dict[str, Any],
        *,
        run_id: uuid.UUID,
    ) -> dict[str, Any]:
        gate = await self.permission_system.evaluate(
            "chapter_plan", assessment["confidence"]
        )

        # `decision` is a short verb column (varchar 50) — the human-readable
        # explanation belongs in decision_reason / context.
        if not gate["allowed"]:
            decision = await self.brain.record_decision(
                "chapter_plan",
                "escalate",
                decision_reason=(
                    f"Chapter {chapter_number} blocked: {gate['blocked_reason']}"
                ),
                confidence=assessment["confidence"],
                permission_level=gate["level"],
                status="pending",
                run_id=run_id,
                decided_by="ai",
                context={
                    "chapter_number": chapter_number,
                    "gaps": assessment["gaps"],
                    "blockers": assessment.get("blockers") or [],
                    "threshold": gate["threshold"],
                },
            )
            return {**gate, "decision_id": decision["id"]}

        decision = await self.brain.record_decision(
            "chapter_plan",
            "approve",
            decision_reason=(
                f"Chapter {chapter_number} approved for auto-generation: "
                f"confidence {assessment['confidence']:.2f} >= "
                f"threshold {gate['threshold']:.2f}, permission={gate['level']}"
            ),
            confidence=assessment["confidence"],
            permission_level=gate["level"],
            status="completed",
            run_id=run_id,
            decided_by="ai",
            context={"chapter_number": chapter_number, "gaps": assessment["gaps"]},
        )
        return {**gate, "decision_id": decision["id"]}

    # ── step 4 ──────────────────────────────────────────────────────────
    async def _plan(
        self,
        chapter_number: int,
        prompt: str | None,
        outline: str | None,
        assessment: dict[str, Any],
        perception: dict[str, Any],
        *,
        target_word_count: int = 3000,
    ) -> dict[str, Any]:
        goals = await self.brain.goals.list_goals(limit=50)
        goals_to_advance = [
            {"id": g["id"], "name": g["name"], "progress": g.get("progress")}
            for g in goals
            if g.get("status") in ("in_progress", "pending")
        ][:5]

        constraints = await self.brain.constraints.list_constraints(limit=50)
        constraints_to_respect = [
            {"name": c["name"], "severity": c["severity"]} for c in constraints
        ]

        return {
            "chapter_number": chapter_number,
            "prompt": prompt,
            "outline": outline,
            "goals_to_advance": goals_to_advance,
            "constraints_to_respect": constraints_to_respect,
            "target_word_count": target_word_count,
            "plot_hint": assessment.get("plot_result"),
            "plot_brief": {
                "must_accomplish": assessment.get("must_accomplish") or [],
                "suggested_beats": assessment.get("suggested_beats") or [],
                "chapter_title_hint": assessment.get("chapter_title_hint"),
                "tension_target": (assessment.get("plot_result") or {}).get(
                    "tension_target"
                ),
                "pacing_advice": (assessment.get("plot_result") or {}).get(
                    "pacing_advice"
                ),
                "risks": (assessment.get("plot_result") or {}).get("risks") or [],
            },
            "status": "planned",
        }

    # ── step 5 is generation_engine.generate_chapter ────────────────────

    # ── step 6 ──────────────────────────────────────────────────────────
    async def _observe(
        self,
        chapter_number: int,
        generation: dict[str, Any],
        *,
        allow_rework: bool,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        def review_input(current: dict[str, Any]) -> dict[str, Any]:
            return {
                "chapter_text": current["text"],
                "chapter_number": chapter_number,
                "previous_chapter_tail": current.get("context", {}).get("previous_tail", ""),
                "previous_transition_contract": current.get("context", {}).get(
                    "previous_transition_contract", {}
                ),
            }

        review = await self.review_engine.run(review_input(generation))
        review_data = review.result or {}
        score = float(review_data.get("overall_score") or 0.0)
        rework_count = 0

        if not review.success:
            raise RuntimeError(f"Review failed: {review.reason}")

        # Rework is bounded, but the gate is not fail-open: after the retry
        # budget is exhausted the chapter remains needs_review and never enters
        # the V6 library as a reviewed chapter.
        while (
            allow_rework
            and not evaluate_review(review_data)["passed"]
            and rework_count < MAX_REWORKS
            and await self.permission_system.can_auto_decide("chapter_rework", 0.9)
        ):
            gate = evaluate_review(review_data)
            rework_count += 1
            issues = review_data.get("issues") or []
            failures = "；".join(
                f"{item['dimension']} {item['actual']:.0f}/{item['minimum']:.0f}"
                for item in gate["failures"][:8]
            )
            issue_text = "；".join(
                f"{i.get('dimension')}: {i.get('description')}" for i in issues[:5]
            )
            feedback = f"质量门禁未通过：{failures}。{issue_text}".strip("；")
            await self.brain.record_decision(
                "chapter_rework",
                "rework",
                decision_reason=(
                    f"Chapter {chapter_number} rewrite {rework_count}/{MAX_REWORKS}; "
                    f"score {score:.1f}, rework threshold {QUALITY_REWORK_SCORE:.0f}: {feedback}"
                ),
                confidence=0.85,
                permission_level="notify",
                status="completed",
                decided_by="ai",
            )
            generation = await self.generation_engine.generate_chapter(
                chapter_number,
                prompt=(plan.get("prompt") or "")
                + f"\n\n上一稿未通过严格质量门禁（{score:.1f}分），必须修复：{feedback}",
                outline=plan.get("outline"),
                target_word_count=plan["target_word_count"],
            )
            review = await self.review_engine.run(review_input(generation))
            if not review.success:
                raise RuntimeError(f"Review failed after rework: {review.reason}")
            review_data = review.result or {}
            score = float(review_data.get("overall_score") or 0.0)

        gate = evaluate_review(review_data)
        blocking = gate["blocking_violations"]
        passed = gate["passed"]

        await self.event_bus.publish(
            "review_completed",
            f"Chapter {chapter_number} reviewed",
            "review",
            source="director",
            event_data={
                "chapter_number": chapter_number,
                "overall_score": score,
                "dimension_scores": review_data.get("dimension_scores", {}),
                "reader_experience": review_data.get("reader_experience", {}),
                "blocking_violations": blocking,
            },
        )

        if not passed:
            await self.brain.record_decision(
                "chapter_quality",
                "needs_human_attention",
                decision_reason=(
                    f"quality gate failures: {gate['failures']}"
                ),
                confidence=review.confidence,
                permission_level="notify",
                status="completed",
                decided_by="ai",
            )

        return {
            "generation": generation,
            "review_score": score,
            "dimension_scores": review_data.get("dimension_scores", {}),
            "reader_experience": review_data.get("reader_experience", {}),
            "issues": review_data.get("issues", []),
            "constraint_violations": review_data.get("constraint_violations", []),
            "blocking_violations": blocking,
            "passed_review": passed,
            "rework_count": rework_count,
            "review_confidence": review.confidence,
            "quality_gate": gate,
        }

    # ── step 7 ──────────────────────────────────────────────────────────
    async def _update(
        self,
        chapter_number: int,
        generation: dict[str, Any],
        observation: dict[str, Any],
        *,
        run_id: uuid.UUID,
    ) -> dict[str, Any]:
        memory = await self.memory_engine.run(
            {
                "chapter_text": generation["text"],
                "chapter_number": chapter_number,
                "run_id": str(run_id),
            }
        )
        memory_data = memory.result or {}
        summary = memory_data.get("chapter_summary") or ""

        transition_contract = build_transition_contract(
            chapter_number=chapter_number,
            title=generation["title"],
            text=generation["text"],
            summary=summary,
            word_count=generation["word_count"],
            review_score=observation["review_score"],
            dimension_scores=observation["dimension_scores"],
            reader_experience=observation.get("reader_experience"),
            previous_context=generation.get("context"),
            memory_items=memory_data.get("extracted_items") or [],
            constraints=(generation.get("context") or {}).get("constraints") or [],
        )

        v6_result: dict[str, Any] | None = None
        if observation["passed_review"]:
            v6_result = await asyncio.to_thread(
                persist_accepted_v7_chapter,
                novel_id=str(self.novel_id),
                project_id=self.project_id,
                chapter_number=chapter_number,
                title=generation["title"],
                text=generation["text"],
                review_score=observation["review_score"],
                dimension_scores=observation["dimension_scores"],
                run_id=str(run_id),
                chapter_summary=summary,
                deai=generation.get("deai") or {},
                transition_contract=transition_contract,
                extra_meta=self.generation_metadata,
            )

        await self.brain.state.update_state(
            CHAPTER_STATE_TYPE,
            chapter_state_key(chapter_number),
            {
                "chapter_number": chapter_number,
                "title": generation["title"],
                "text": generation["text"],
                "summary": summary,
                "word_count": generation["word_count"],
                "review_score": observation["review_score"],
                "reader_experience": observation.get("reader_experience", {}),
                "passed_review": observation["passed_review"],
                "rework_count": observation["rework_count"],
                "run_id": str(run_id),
                "transition_contract": transition_contract,
                "v6_content_id": (v6_result or {}).get("content_id"),
            },
            0.95,
            source="generation_engine",
            source_run_id=run_id,
            reason=f"chapter {chapter_number} generated and reviewed",
        )

        return {
            "chapter_persisted": bool(v6_result),
            "v6_content": v6_result,
            "transition_contract": transition_contract,
            "chapter_summary": summary,
            "states_applied": memory_data.get("states_applied", 0),
            "states_pending_review": memory_data.get("states_pending_review", 0),
            "states_discarded": memory_data.get("states_discarded", 0),
            "conflicts_found": memory_data.get("conflicts_found", 0),
            "memory_success": memory.success,
        }

    # ── helpers ─────────────────────────────────────────────────────────
    async def get_decision_queue(self) -> list[dict[str, Any]]:
        """Get decisions pending human approval."""
        return await self.brain.get_decision_logs(status="pending", limit=50)

    async def get_chapter(self, chapter_number: int) -> dict[str, Any] | None:
        """Read a previously generated chapter back out of the Novel Brain."""
        state = await self.brain.state.get_state(
            CHAPTER_STATE_TYPE, chapter_state_key(chapter_number)
        )
        if not state:
            return None
        value = state.get("value") or {}
        return {
            **value,
            "confidence": state.get("confidence"),
            "version": state.get("version"),
        }

    async def list_chapters(self) -> list[dict[str, Any]]:
        """List generated chapters (metadata only, no full text)."""
        states = await self.brain.state.list_states(CHAPTER_STATE_TYPE, limit=500)
        chapters = []
        for s in states:
            value = s.get("value") or {}
            chapters.append(
                {
                    "chapter_number": value.get("chapter_number"),
                    "title": value.get("title"),
                    "summary": value.get("summary"),
                    "word_count": value.get(
                        "word_count", chinese_word_count(value.get("text", ""))
                    ),
                    "review_score": value.get("review_score"),
                    "passed_review": value.get("passed_review"),
                    "version": s.get("version"),
                }
            )
        chapters.sort(key=lambda c: c.get("chapter_number") or 0)
        return chapters
