"""Base engine class.

All engines must implement the 5 unified methods:
- analyze: Analyze input and return findings
- plan: Create a plan of action
- execute: Execute the plan
- validate: Validate the output
- update: Update brain state

Every engine must declare its EngineCapability.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..brain.novel_brain import NovelBrain
from ..trace.tracer import ExecutionTracer
from ..events.event_bus import EventBus


@dataclass
class EngineCapability:
    """Engine capability declaration."""
    engine_name: str
    engine_type: str  # plot / memory / character / world / causal / reader / review / market
    version: str = "1.0.0"
    supports_analyze: bool = True
    supports_plan: bool = True
    supports_execute: bool = True
    supports_validate: bool = True
    supports_update: bool = True
    requires_ai: bool = True
    input_types: list[str] = field(default_factory=list)
    output_types: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class EngineResult:
    """Standard engine result."""
    success: bool
    result: Any = None
    confidence: float = 0.9
    reason: str = ""
    warnings: list[str] = field(default_factory=list)
    schema_version: str = "1.0"
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseEngine(ABC):
    """
    Base class for all V7 engines.
    
    All engines must implement the 5 unified methods.
    """

    def __init__(
        self,
        db: AsyncSession,
        novel_id: uuid.UUID,
        brain: NovelBrain,
        tracer: ExecutionTracer,
        event_bus: EventBus,
        project_id: str | None = None,
        provider_config: dict[str, str] | None = None,
    ):
        self.db = db
        self.novel_id = novel_id
        self.brain = brain
        self.tracer = tracer
        self.event_bus = event_bus
        self.project_id = project_id
        # The canonical V7 runtime may receive a short-lived BYOK override
        # from a V6-compatible HTTP entrypoint.  Empty values intentionally
        # fall back to the worker environment in AIGateway.
        self.provider_config = provider_config or {}
        # Set by run() so phase implementations can report token usage / cost
        # onto the trace step that is currently open.
        self._step_ctx: Any = None
        self.total_usage: dict[str, Any] = {
            "tokens_input": 0,
            "tokens_output": 0,
            "cost": 0.0,
            "model": None,
        }

    def record_usage(self, usage: dict[str, Any] | None) -> None:
        """Attach LLM token usage / cost to the currently open trace step."""
        if not usage:
            return
        tokens_input = int(usage.get("tokens_input", 0) or 0)
        tokens_output = int(usage.get("tokens_output", 0) or 0)
        cost = float(usage.get("cost", 0.0) or 0.0)
        model = usage.get("model")

        self.total_usage["tokens_input"] += tokens_input
        self.total_usage["tokens_output"] += tokens_output
        self.total_usage["cost"] += cost
        if model:
            self.total_usage["model"] = model

        if self._step_ctx is not None:
            self._step_ctx.set_output(
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                cost=cost,
                model=model,
            )

    def _finish_step(self, result: "EngineResult", summary: str) -> None:
        """Write phase outcome onto the open trace step."""
        if self._step_ctx is None:
            return
        self._step_ctx.set_output(summary, confidence=result.confidence)

    @property
    @abstractmethod
    def capability(self) -> EngineCapability:
        """Engine capability declaration."""
        ...

    @abstractmethod
    async def analyze(self, input_data: dict[str, Any]) -> EngineResult:
        """
        Analyze input and return findings.
        
        Phase 1: Understand the input, identify issues, extract information.
        """
        ...

    @abstractmethod
    async def plan(self, analysis: EngineResult) -> EngineResult:
        """
        Create a plan of action based on analysis.
        
        Phase 2: Decide what to do, create steps/strategy.
        """
        ...

    @abstractmethod
    async def execute(self, plan: EngineResult) -> EngineResult:
        """
        Execute the plan.
        
        Phase 3: Do the actual work (generation, modification, etc.).
        """
        ...

    @abstractmethod
    async def validate(self, output: EngineResult) -> EngineResult:
        """
        Validate the output.
        
        Phase 4: Check quality, consistency, constraints.
        """
        ...

    @abstractmethod
    async def update(self, validated: EngineResult) -> EngineResult:
        """
        Update brain state.
        
        Phase 5: Persist changes to Novel Brain.
        """
        ...

    async def run(self, input_data: dict[str, Any]) -> EngineResult:
        """
        Run the full engine pipeline: analyze → plan → execute → validate → update.
        
        This is the main entry point for using an engine.

        Every phase result is captured into ``metadata["phases"]`` so callers
        can inspect intermediate output (e.g. the analysis) without re-running
        the engine, including on the early-return failure paths.
        """
        engine_name = self.capability.engine_name
        phases: dict[str, Any] = {}

        def _capture(name: str, res: EngineResult) -> EngineResult:
            phases[name] = {
                "success": res.success,
                "confidence": res.confidence,
                "reason": res.reason,
                "result": res.result,
                "warnings": list(res.warnings or []),
            }
            res.metadata.setdefault("phases", phases)
            res.metadata.setdefault("engine", engine_name)
            res.metadata["usage"] = dict(self.total_usage)
            return res

        # Step 1: Analyze
        async with self.tracer.trace_step(
            f"{engine_name}.analyze",
            "analyze",
            input_summary=f"Analyze input for {engine_name}",
        ) as step:
            self._step_ctx = step
            analysis = await self.analyze(input_data)
            _capture("analyze", analysis)
            self._finish_step(analysis, analysis.reason or "analyze done")
            self._step_ctx = None
            if not analysis.success:
                return analysis

        # Step 2: Plan
        async with self.tracer.trace_step(
            f"{engine_name}.plan",
            "plan",
            input_summary="Plan based on analysis",
        ) as step:
            self._step_ctx = step
            plan = await self.plan(analysis)
            _capture("plan", plan)
            self._finish_step(plan, plan.reason or "plan done")
            self._step_ctx = None
            if not plan.success:
                return plan

        # Step 3: Execute
        async with self.tracer.trace_step(
            f"{engine_name}.execute",
            "execute",
            input_summary=f"Execute plan for {engine_name}",
        ) as step:
            self._step_ctx = step
            output = await self.execute(plan)
            _capture("execute", output)
            self._finish_step(output, output.reason or "execute done")
            self._step_ctx = None
            if not output.success:
                return output

        # Step 4: Validate
        async with self.tracer.trace_step(
            f"{engine_name}.validate",
            "validate",
            input_summary="Validate output",
        ) as step:
            self._step_ctx = step
            validated = await self.validate(output)
            _capture("validate", validated)
            self._finish_step(validated, validated.reason or "validate done")
            self._step_ctx = None
            if not validated.success:
                return validated

        # Step 5: Update
        async with self.tracer.trace_step(
            f"{engine_name}.update",
            "update",
            input_summary="Update brain state",
        ) as step:
            self._step_ctx = step
            updated = await self.update(validated)
            _capture("update", updated)
            self._finish_step(updated, updated.reason or "update done")
            self._step_ctx = None

        updated.metadata["usage"] = dict(self.total_usage)

        # Publish event
        await self.event_bus.publish(
            f"engine_{engine_name}_completed",
            f"{engine_name} engine completed",
            "engine",
            source="engine",
            event_data={
                "engine": engine_name,
                "success": updated.success,
                "confidence": updated.confidence,
                "usage": dict(self.total_usage),
            },
        )

        return updated
