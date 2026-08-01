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
    ):
        self.db = db
        self.novel_id = novel_id
        self.brain = brain
        self.tracer = tracer
        self.event_bus = event_bus

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
        """
        engine_name = self.capability.engine_name

        # Step 1: Analyze
        async with self.tracer.trace_step(
            f"{engine_name}.analyze",
            "analyze",
            input_summary=f"Analyze input for {engine_name}",
        ):
            analysis = await self.analyze(input_data)
            if not analysis.success:
                return analysis

        # Step 2: Plan
        async with self.tracer.trace_step(
            f"{engine_name}.plan",
            "plan",
            input_summary=f"Plan based on analysis",
        ):
            plan = await self.plan(analysis)
            if not plan.success:
                return plan

        # Step 3: Execute
        async with self.tracer.trace_step(
            f"{engine_name}.execute",
            "execute",
            input_summary=f"Execute plan for {engine_name}",
        ):
            output = await self.execute(plan)
            if not output.success:
                return output

        # Step 4: Validate
        async with self.tracer.trace_step(
            f"{engine_name}.validate",
            "validate",
            input_summary=f"Validate output",
        ):
            validated = await self.validate(output)
            if not validated.success:
                return validated

        # Step 5: Update
        async with self.tracer.trace_step(
            f"{engine_name}.update",
            "update",
            input_summary=f"Update brain state",
        ):
            updated = await self.update(validated)

        # Publish event
        await self.event_bus.publish(
            f"engine_{engine_name}_completed",
            f"{engine_name} engine completed",
            "engine",
            source="engine",
            event_data={"engine": engine_name, "success": updated.success},
        )

        return updated
