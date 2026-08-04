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
from ..engines.base import EngineResult
from ..generation.generation_engine import (
    CHAPTER_STATE_TYPE,
    GenerationEngine,
    chapter_state_key,
    chinese_word_count,
    is_retryable_provider_failure,
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
    persist_review_hold_v7_draft,
    persist_rejected_v7_draft,
)
from ..quality.continuity import validate_transition_contract
from ...services.quality_profiles import quality_profile_metadata, select_quality_profile

AGENT_LOOP_STEPS: tuple[str, ...] = (
    "perceive",
    "assess",
    "decide",
    "plan",
    "execute",
    "observe",
    "update",
)

# A long-run is a controlled quality-observation mode. It must not bypass
# structural blockers or the post-generation prose gate, but a plot engine
# confidence score in the 0.55--0.70 band is common when a novel is still
# bootstrapping its state. Blocking every such slot before any prose exists
# makes a 20-chapter diagnostic measure the permission model instead of the
# writing quality. The floor is deliberately explicit and only applies when
# the caller supplied a persisted batch id.
BATCH_AUTOGENERATION_CONFIDENCE_FLOOR = 0.55


def _format_quality_failure(item: dict[str, Any]) -> str:
    """Render a gate failure without assuming every value is numeric.

    Model-derived dimension failures use numeric scores, while deterministic
    risk failures intentionally use labels such as ``high``/``resolved``.
    Rework feedback must remain diagnostic for both shapes; formatting a
    string with ``:.0f`` used to crash the real-provider path before a rejected
    chapter could be persisted.
    """
    def render(value: Any) -> str:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f"{value:.0f}"
        return str(value or "—")

    dimension = str(item.get("dimension") or "质量项")
    return f"{dimension} {render(item.get('actual'))}/{render(item.get('minimum'))}"

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
        quality_profile: dict[str, Any] | None = None,
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
        self.quality_profile = quality_profile or select_quality_profile()
        self.permission_system = DecisionPermissionSystem(db, novel_id)

        # Engines
        self.plot_engine = PlotEngine(
            db, novel_id, brain, tracer, event_bus,
            project_id=project_id,
            provider_config=self.provider_config,
            quality_profile=self.quality_profile,
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
            quality_profile=self.quality_profile,
        )
        self.generation_engine = GenerationEngine(
            db, novel_id, brain, tracer, event_bus,
            project_id=project_id,
            provider_config=self.provider_config,
            quality_profile=self.quality_profile,
        )
        # Ordered batches are diagnostic runs: a rejected/held chapter remains
        # provisional context so the run can measure cross-chapter continuity.
        # It is never treated as accepted Novel Brain truth and single-chapter
        # generation keeps the strict block below.
        self.generation_engine.include_rejected_context = bool(
            self.generation_metadata.get("batch_id")
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

            if perception.get("blocked_by_quality"):
                result = {
                    "run_id": str(run_id),
                    "chapter_number": chapter_number,
                    "status": "blocked_quality",
                    "blocked_reason": perception["blocked_by_quality"],
                    "steps_executed": ["perceive"],
                }
                await self.tracer.complete_run(run_id, output_data=result)
                return result

            # ── 2. ASSESS ──────────────────────────────────────────────
            async with self.tracer.trace_step(
                "director.assess", "assess",
                input_summary="Assess plot situation",
            ) as step:
                # Bootstrap sometimes passes an empty JSON placeholder as the
                # chapter outline while the actual creative context is in the
                # prompt.  The pre-generation gate must assess the same story
                # brief that the writer will receive; otherwise a valid first
                # chapter is blocked as "low confidence" before any prose is
                # generated.
                assessment_outline = (outline or "").strip()
                if assessment_outline in {"", "{}", "[]", "null"}:
                    assessment_outline = (prompt or "").strip()
                assessment = await self._assess(
                    chapter_number, assessment_outline or None, perception
                )
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
                    # Planning/provider transport failures are operationally
                    # retryable, not human approval requests.  Keep the
                    # assessment evidence small but explicit so the worker
                    # can retry the same ordered batch slot without guessing.
                    "planning_assessment": {
                        "plot_success": bool(assessment.get("plot_success")),
                        "confidence": assessment.get("confidence"),
                        "blockers": list(assessment.get("blockers") or []),
                    },
                    "retryable_planning_failure": bool(
                        assessment.get("retryable_planning_failure")
                    ),
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
                "generation_quality": generation.get("generation_quality") or {},
                "reader_experience": observation.get("reader_experience", {}),
                "issues": observation.get("issues", []),
                "quality_gate": observation.get("quality_gate", {}),
                "audit_report": observation.get("audit_report", {}),
                "review_hold": observation.get("review_hold", False),
                "review_validation": observation.get("review_validation", []),
                "passed_review": observation["passed_review"],
                "rework_count": observation["rework_count"],
                "memory": {
                    "states_applied": update_result["states_applied"],
                    "states_pending_review": update_result["states_pending_review"],
                    "states_discarded": update_result["states_discarded"],
                    "conflicts_found": update_result["conflicts_found"],
                },
                "transition_contract": update_result.get("transition_contract", {}),
                "continuity": update_result.get("continuity", {}),
                "rule_learning": update_result.get("rule_learning", []),
                "v6_content": update_result.get("v6_content"),
                "v6_content_id": (update_result.get("v6_content") or {}).get("content_id"),
                "steps_executed": list(AGENT_LOOP_STEPS),
                "usage": generation["usage"],
            }

            # The chapter body is persisted as a story state and rejected
            # drafts remain visible in V6 as needs_rewrite; keep the run
            # output_data lean so v7_agent_runs stays queryable.
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
            chapter_number, count=1, include_rejected=True
        )
        blocked_by_quality = None
        batch_mode = bool(self.generation_metadata.get("batch_id"))
        if previous and previous[-1].get("passed_review") is False and not batch_mode:
            blocked_by_quality = (
                f"第{previous[-1].get('chapter_number')}章未通过质量门禁，"
                "必须先完成返工，不能继续生成下一章"
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
            "provisional_previous_chapter": bool(
                batch_mode and previous and previous[-1].get("passed_review") is False
            ),
            "blocked_by_quality": blocked_by_quality,
            "truth_domains": await self.brain.truth.digest(),
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
        plot_failure_reason = plot_run.reason or ""
        retryable_planning_failure = bool(
            not plot_run.success
            and is_retryable_provider_failure(plot_failure_reason)
        )
        if not plot_run.success:
            blockers.append(plot_failure_reason or "plot engine pipeline failed")
            confidence = min(confidence, 0.4)

        return {
            "plot_success": bool(plot_run.success),
            "plot_result": assessment_data,
            "plot_execute": execute_phase.get("result"),
            "plot_warnings": list(plot_run.warnings or []),
            "must_accomplish": assessment_data.get("must_accomplish") or [],
            "suggested_beats": assessment_data.get("suggested_beats") or [],
            "chapter_title_hint": assessment_data.get("chapter_title_hint"),
            "payoff_contract": assessment_data.get("payoff_contract") or {},
            "gaps": gaps,
            "blockers": blockers,
            "retryable_planning_failure": retryable_planning_failure,
            # A bootstrap first chapter is allowed to start when the writer
            # received a substantive creative brief.  The confidence number
            # still remains auditable; this is a narrowly scoped policy for
            # starting from a blank novel, while the independent quality gate
            # below remains fail-closed.
            "context_ready": len((outline or "").strip()) >= 200,
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

        confidence_block = (
            not gate["allowed"]
            and gate["level"] in {"auto", "notify"}
            and str(gate.get("blocked_reason") or "").startswith("confidence ")
        )
        batch_observation_mode = bool(
            getattr(self, "generation_metadata", {}).get("batch_id")
        )

        # Do not strand a new novel before the first word is written merely
        # because a model conservatively scores an otherwise complete brief
        # below the generic confidence threshold.  This does not bypass an
        # explicit human-only permission level or a structural blocker; it
        # only lets a context-complete first chapter reach the independent
        # prose quality gate.
        if (
            confidence_block
            and chapter_number == 1
            and assessment.get("plot_success")
            and assessment.get("context_ready")
            and not (assessment.get("blockers") or [])
        ):
            gate = {
                **gate,
                "allowed": True,
                "blocked_reason": None,
                "policy_override": "first_chapter_context_complete",
            }

        # Ordered 20-chapter diagnostics need to observe the actual prose
        # quality even while PlotEngine is still warming up its state. This
        # exception is narrower than the first-chapter bootstrap rule: it is
        # batch-only, requires a successful plot assessment and no structural
        # blockers, and still sends the resulting prose through every V7
        # generation/review/continuity gate. Explicit approve/forbidden
        # permissions never enter this branch.
        elif (
            confidence_block
            and batch_observation_mode
            and assessment.get("plot_success")
            and not (assessment.get("blockers") or [])
            and float(assessment.get("confidence") or 0.0)
            >= BATCH_AUTOGENERATION_CONFIDENCE_FLOOR
        ):
            gate = {
                **gate,
                "allowed": True,
                "blocked_reason": None,
                "policy_override": "batch_quality_observation",
                "confidence_floor": BATCH_AUTOGENERATION_CONFIDENCE_FLOOR,
            }

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
                (
                    f"Chapter {chapter_number} approved to reach the strict quality gate: "
                    + (
                        "first-chapter creative brief is complete; generic confidence "
                        "override is recorded and does not waive post-generation review"
                        if gate.get("policy_override") == "first_chapter_context_complete"
                        else (
                            "batch quality-observation mode is recorded; confidence "
                            f"floor is {BATCH_AUTOGENERATION_CONFIDENCE_FLOOR:.2f} and "
                            "post-generation review remains strict"
                        )
                    )
                )
                if gate.get("policy_override")
                else (
                    f"Chapter {chapter_number} approved for auto-generation: "
                    f"confidence {assessment['confidence']:.2f} >= "
                    f"threshold {gate['threshold']:.2f}, permission={gate['level']}"
                )
            ),
            confidence=assessment["confidence"],
            permission_level=gate["level"],
            status="completed",
            run_id=run_id,
            decided_by="ai",
            context={
                "chapter_number": chapter_number,
                "gaps": assessment["gaps"],
                "policy_override": gate.get("policy_override"),
                "confidence_floor": gate.get("confidence_floor"),
            },
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
                "reader_promise": assessment.get("reader_promise") or (assessment.get("plot_result") or {}).get("reader_promise"),
                "emotional_target": assessment.get("emotional_target") or (assessment.get("plot_result") or {}).get("emotional_target"),
                "opening_anchor": assessment.get("opening_anchor") or (assessment.get("plot_result") or {}).get("opening_anchor"),
                "hook": (assessment.get("plot_result") or {}).get("hook") or "",
                "payoff_contract": assessment.get("payoff_contract") or (assessment.get("plot_result") or {}).get("payoff_contract") or {},
            },
            "quality_profile": quality_profile_metadata(self.quality_profile),
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
            metrics = (current.get("deai") or {}).get("metrics") or {}
            return {
                "chapter_text": current["text"],
                "chapter_number": chapter_number,
                "previous_chapter_tail": current.get("context", {}).get("previous_tail", ""),
                "previous_transition_contract": current.get("context", {}).get(
                    "previous_transition_contract", {}
                ),
                "chapter_plan": plan.get("plot_brief") or {},
                "scene_plan": current.get("scene_plan") or {},
                "deai_metrics": metrics.get("after") or metrics,
                "pov_metrics": current.get("pov_metrics") or (current.get("generation_quality") or {}).get("pov_metrics") or {},
                "content_policy": current.get("content_policy") or (current.get("generation_quality") or {}).get("content_policy") or {},
                "generation_quality": current.get("generation_quality") or {},
                "quality_profile": current.get("quality_profile") or quality_profile_metadata(self.quality_profile),
                "payoff_contract": current.get("payoff_contract") or (plan.get("plot_brief") or {}).get("payoff_contract") or {},
            }

        review = await self.review_engine.run(review_input(generation))
        review_data = review.result or {}
        review_hold = False
        if not review.success:
            # Provider output/schema failures must not strand a generated
            # chapter as a Celery exception. Keep the real draft, expose the
            # failed review contract, and let the product mark it needs_review.
            raw = review_data.get("raw") if isinstance(review_data, dict) else {}
            raw = raw if isinstance(raw, dict) else {}
            validation_failures = review_data.get("validation_failures") or []
            if not validation_failures:
                validation_failures = [{
                    "code": "review_execution_failed",
                    "message": review.reason or "审稿输出未通过校验",
                }]
            review_data = {
                **raw,
                **review_data,
                "chapter_number": chapter_number,
                "overall_score": float(raw.get("overall_score") or 0.0),
                "dimension_scores": raw.get("dimension_scores") or {},
                "reader_experience": raw.get("reader_experience") or {},
                "issues": raw.get("issues") or [],
                "constraint_violations": raw.get("constraint_violations") or [],
                "audit_report": raw.get("audit_report") or {},
                "quality_profile": generation.get("quality_profile") or quality_profile_metadata(self.quality_profile),
                "payoff_contract": generation.get("payoff_contract") or (plan.get("plot_brief") or {}).get("payoff_contract") or {},
                "payoff_evidence": raw.get("payoff_evidence") or [],
                "validation_failures": validation_failures,
            }
            review_hold = True
        elif review_data.get("review_valid") is False:
            # The ReviewEngine keeps a structured but invalid contract alive
            # so the director can persist it as a review hold instead of
            # confusing it with a transport failure.
            review_hold = True
        score = float(review_data.get("overall_score") or 0.0)
        rework_count = 0

        # Rework is bounded, but the gate is not fail-open: after the retry
        # budget is exhausted the chapter remains needs_review and never enters
        # the V6 library as a reviewed chapter.
        while (
            allow_rework
            and not review_hold
            and not evaluate_review(review_data)["passed"]
            and rework_count < MAX_REWORKS
            and await self.permission_system.can_auto_decide("chapter_rework", 0.9)
        ):
            gate = evaluate_review(review_data)
            rework_count += 1
            issues = review_data.get("issues") or []
            failures = "；".join(
                _format_quality_failure(item)
                for item in gate["failures"][:8]
                if isinstance(item, dict)
            )
            issue_text = "；".join(
                (
                    f"{i.get('dimension') or i.get('type') or '问题'}: {i.get('description')}; "
                    f"建议：{i.get('suggestion') or '直接修复该问题'}"
                    if isinstance(i, dict)
                    else str(i)
                )
                for i in issues[:8]
            )
            repair_feedback = "；".join(
                str(item) for item in (gate.get("quality_repair_contract") or {}).get("required_repair_feedback") or []
            )
            feedback = f"质量门禁未通过：{failures}。{issue_text}。{repair_feedback}".strip("；。")
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
                + "\n\n【严格重写任务】\n"
                + f"上一稿未通过严格质量门禁（{score:.1f}分），必须修复：{feedback}\n"
                + "下面是上一稿正文。请保留已经成立的人物、地点、时间线和因果事实，"
                + "不要只做同义词替换；要重排场景动作、对白和信息揭示，使冲突真正推进，"
                + "并让章末钩子落到具体动作/发现/选择上。\n"
                + f"【上一稿正文】\n{generation.get('text', '')[:16000]}",
                outline=plan.get("outline"),
                target_word_count=plan["target_word_count"],
                plot_brief=plan.get("plot_brief"),
            )
            review = await self.review_engine.run(review_input(generation))
            if not review.success:
                raw = review.result.get("raw") if isinstance(review.result, dict) else {}
                raw = raw if isinstance(raw, dict) else {}
                review_data = {
                    **raw,
                    **(review.result or {}),
                    "chapter_number": chapter_number,
                    "overall_score": float(raw.get("overall_score") or 0.0),
                    "dimension_scores": raw.get("dimension_scores") or {},
                    "reader_experience": raw.get("reader_experience") or {},
                    "issues": raw.get("issues") or [],
                    "constraint_violations": raw.get("constraint_violations") or [],
                    "audit_report": raw.get("audit_report") or {},
                    "quality_profile": generation.get("quality_profile") or quality_profile_metadata(self.quality_profile),
                    "payoff_contract": generation.get("payoff_contract") or (plan.get("plot_brief") or {}).get("payoff_contract") or {},
                    "payoff_evidence": raw.get("payoff_evidence") or [],
                    "validation_failures": (review.result or {}).get("validation_failures") or [{
                        "code": "review_execution_failed",
                        "message": review.reason or "重写后的审稿输出未通过校验",
                    }],
                }
                review_hold = True
                score = 0.0
                break
            review_data = review.result or {}
            score = float(review_data.get("overall_score") or 0.0)

        gate = evaluate_review(review_data)
        validation_failures = review_data.get("validation_failures") or []
        if validation_failures:
            for failure in validation_failures:
                if not isinstance(failure, dict):
                    continue
                gate["failures"].append({
                    "dimension": str(failure.get("code") or "review_validation"),
                    "actual": "invalid",
                    "minimum": "valid",
                    "reason": str(failure.get("message") or "审稿契约校验失败"),
                })
            gate["passed"] = False
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

        issues = list(review_data.get("issues") or [])
        if validation_failures:
            issues.extend(
                {
                    "dimension": str(item.get("code") or "review_validation"),
                    "severity": "high",
                    "description": str(item.get("message") or "审稿契约校验失败"),
                    "suggestion": "重新执行审稿并确认评分、33维审计和爽点证据均可验证",
                }
                for item in validation_failures
                if isinstance(item, dict)
            )
        review_data["issues"] = issues

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
            "audit_report": review_data.get("audit_report", {}),
            "blocking_violations": blocking,
            "passed_review": passed,
            "rework_count": rework_count,
            "review_confidence": review.confidence,
            "quality_gate": gate,
            "review_hold": review_hold,
            "review_validation": validation_failures,
            "pov_metrics": review_data.get("pov_metrics") or generation.get("pov_metrics") or {},
            "content_policy": review_data.get("content_policy") or generation.get("content_policy") or {},
            "payoff_contract": review_data.get("payoff_contract") or generation.get("payoff_contract") or {},
            "payoff_evidence": review_data.get("payoff_evidence") or [],
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
                # Extract first; commit to Novel Brain only after the review
                # and continuity gates have accepted the final text.
                "apply_updates": False,
            }
        )
        memory_data = memory.result or {}
        summary = memory_data.get("chapter_summary") or ""
        memory_items = memory_data.get("valid_items") or memory_data.get("extracted_items") or []

        if not memory.success:
            observation["passed_review"] = False
            quality_gate = observation.get("quality_gate") or {}
            quality_gate["passed"] = False
            quality_gate["failures"] = [
                *(quality_gate.get("failures") or []),
                {
                    "dimension": "memory_state_extraction",
                    "actual": "failed",
                    "minimum": "succeeded",
                    "reason": memory.reason or "章节状态抽取失败，不能更新真相状态",
                },
            ]
            observation["quality_gate"] = quality_gate
            observation["issues"] = [
                *(observation.get("issues") or []),
                {
                    "dimension": "continuity",
                    "severity": "high",
                    "description": memory.reason or "章节状态抽取失败",
                    "suggestion": "修复状态抽取后重新提交，不能让未确认状态进入后续章节",
                },
            ]

        transition_contract = build_transition_contract(
            chapter_number=chapter_number,
            title=generation["title"],
            text=generation["text"],
            summary=summary,
            word_count=generation["word_count"],
            review_score=observation["review_score"],
            dimension_scores=observation["dimension_scores"],
            reader_experience=observation.get("reader_experience"),
            payoff_contract=generation.get("payoff_contract") or {},
            payoff_evidence=observation.get("payoff_evidence") or [],
            previous_context=generation.get("context"),
            memory_items=memory_items,
            constraints=(generation.get("context") or {}).get("constraints") or [],
            state_conflicts=memory_data.get("conflicts") or [],
        )
        continuity = validate_transition_contract(
            transition_contract,
            chapter_number=chapter_number,
            previous_contract=(generation.get("context") or {}).get(
                "previous_transition_contract", {}
            ),
            state_conflicts=memory_data.get("conflicts") or [],
        )
        transition_contract["continuity"] = continuity
        if not continuity["passed"]:
            # This is an application hard gate.  A high model score cannot
            # make a chapter publishable when its durable hand-off is broken.
            observation["passed_review"] = False
            quality_gate = observation.get("quality_gate") or {}
            quality_gate["passed"] = False
            quality_gate["continuity"] = continuity
            quality_gate["failures"] = [
                *(quality_gate.get("failures") or []),
                *[
                    {
                        "dimension": "continuity",
                        "actual": item["severity"],
                        "minimum": "resolved",
                        "reason": item["message"],
                    }
                    for item in continuity["issues"]
                    if item["severity"] == "high"
                ],
            ]
            observation["quality_gate"] = quality_gate
            observation["issues"] = [
                *(observation.get("issues") or []),
                *[
                    {
                        "dimension": "continuity",
                        "severity": item["severity"],
                        "description": item["message"],
                        "suggestion": "补齐上一章承接、状态变化和下一章入口后再提交",
                    }
                    for item in continuity["issues"]
                ],
            ]

        rule_learning = await self.brain.rules.observe(
            chapter_number=chapter_number,
            accepted=bool(observation["passed_review"]),
            deai_metrics=(generation.get("deai") or {}).get("metrics") or {},
            issues=observation.get("issues") or [],
            source_run_id=run_id,
        )

        # Commit extracted truth only after every quality gate has passed and
        # before the V6 boundary is allowed to call the chapter "reviewed".
        # Otherwise a database/state-write failure could leave an accepted V6
        # chapter behind a failed Novel Brain update.
        memory_update = memory
        if observation["passed_review"] and memory.success:
            try:
                async with self.db.begin_nested():
                    memory_update = await self.memory_engine.apply_validated_items(
                        {
                            **memory_data,
                            "valid_items": memory_items,
                            "chapter_number": chapter_number,
                            "run_id": str(run_id),
                        }
                    )
            except Exception as exc:  # noqa: BLE001 - convert to a visible gate failure
                observation["passed_review"] = False
                memory_update = EngineResult(
                    success=False,
                    reason=f"accepted chapter state write failed: {type(exc).__name__}",
                )
                quality_gate = observation.get("quality_gate") or {}
                quality_gate["passed"] = False
                quality_gate["failures"] = [
                    *(quality_gate.get("failures") or []),
                    {
                        "dimension": "memory_state_write",
                        "actual": "failed",
                        "minimum": "succeeded",
                        "reason": memory_update.reason,
                    },
                ]
                observation["quality_gate"] = quality_gate
                observation["issues"] = [
                    *(observation.get("issues") or []),
                    {
                        "dimension": "continuity",
                        "severity": "high",
                        "description": memory_update.reason,
                        "suggestion": "状态写回成功后才能把章节标记为已完成",
                    },
                ]
            if observation["passed_review"] and not memory_update.success:
                observation["passed_review"] = False
                quality_gate = observation.get("quality_gate") or {}
                quality_gate["passed"] = False
                quality_gate["failures"] = [
                    *(quality_gate.get("failures") or []),
                    {
                        "dimension": "memory_state_write",
                        "actual": "failed",
                        "minimum": "succeeded",
                        "reason": memory_update.reason or "章节状态写回未完成",
                    },
                ]
                observation["quality_gate"] = quality_gate
                observation["issues"] = [
                    *(observation.get("issues") or []),
                    {
                        "dimension": "continuity",
                        "severity": "high",
                        "description": memory_update.reason or "章节状态写回未完成",
                        "suggestion": "状态写回成功后才能把章节标记为已完成",
                    },
                ]

        # Persist both outcomes at the product boundary.  A failed quality
        # gate stays fail-closed (`needs_rewrite`), but the author must still
        # be able to inspect the actual draft and repair evidence.
        if observation["passed_review"]:
            bridge = persist_accepted_v7_chapter
        elif observation.get("review_hold"):
            bridge = persist_review_hold_v7_draft
        else:
            bridge = persist_rejected_v7_draft
        bridge_kwargs: dict[str, Any] = {
            "novel_id": str(self.novel_id),
            "project_id": self.project_id,
            "chapter_number": chapter_number,
            "title": generation["title"],
            "text": generation["text"],
            "review_score": observation["review_score"],
            "dimension_scores": observation["dimension_scores"],
            "run_id": str(run_id),
            "chapter_summary": summary,
            "deai": generation.get("deai") or {},
            "transition_contract": transition_contract,
            "extra_meta": {
                **self.generation_metadata,
                "audit_report": observation.get("audit_report") or {},
                "continuity": continuity,
                "generation_quality": generation.get("generation_quality") or {},
                "quality_profile": generation.get("quality_profile") or quality_profile_metadata(self.quality_profile),
                "payoff_contract": generation.get("payoff_contract") or {},
                "payoff_validation": generation.get("payoff_validation") or {},
                "payoff_evidence": observation.get("payoff_evidence") or [],
                "review_validation": observation.get("review_validation") or [],
            },
        }
        if not observation["passed_review"]:
            bridge_kwargs.update(
                {
                    "review_issues": observation.get("issues") or [],
                    "quality_gate": observation.get("quality_gate") or {},
                    "reader_experience": observation.get("reader_experience") or {},
                    "rework_count": observation.get("rework_count") or 0,
                }
            )
        v6_result = await asyncio.to_thread(bridge, **bridge_kwargs)

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
                "generation_quality": generation.get("generation_quality") or {},
                "quality_profile": generation.get("quality_profile") or quality_profile_metadata(self.quality_profile),
                "payoff_contract": generation.get("payoff_contract") or {},
                "quality_gate": observation.get("quality_gate") or {},
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
            "continuity": continuity,
            "rule_learning": rule_learning,
            "chapter_summary": summary,
            "states_applied": (memory_update.result or {}).get("states_applied", 0),
            "states_pending_review": (memory_update.result or {}).get("states_pending_review", 0),
            "states_discarded": (memory_update.result or {}).get("states_discarded", 0),
            "conflicts_found": (memory_update.result or {}).get("conflicts_found", 0),
            "memory_success": memory_update.success,
            "memory_deferred": bool((memory_update.result or {}).get("deferred")),
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
