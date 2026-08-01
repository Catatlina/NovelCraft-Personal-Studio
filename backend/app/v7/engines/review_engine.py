"""Review Engine - Sprint 2 Alpha.

Reviews generated content for quality, consistency, and constraint compliance.
"""
from __future__ import annotations

from typing import Any

from .base import BaseEngine, EngineCapability, EngineResult


class ReviewEngine(BaseEngine):
    """
    Review engine for quality and consistency checking.
    
    Sprint 2 Alpha: Basic review with constraint checking.
    Full 7-dimensional review in V7.1.
    """

    @property
    def capability(self) -> EngineCapability:
        return EngineCapability(
            engine_name="review_engine",
            engine_type="review",
            version="0.1.0-alpha",
            description="Reviews content for quality, consistency, and constraints",
            input_types=["chapter_text", "scene_text", "full_text"],
            output_types=["review_report", "issues", "score"],
        )

    async def analyze(self, input_data: dict[str, Any]) -> EngineResult:
        """Analyze content for review."""
        chapter_text = input_data.get("chapter_text", "")

        if not chapter_text:
            return EngineResult(
                success=False,
                reason="No text provided for review",
                confidence=0.0,
            )

        word_count = len(chapter_text.split())
        
        analysis = {
            "word_count": word_count,
            "review_dimensions": [
                "consistency",
                "character_voice",
                "pacing",
                "plot_logic",
                "writing_quality",
            ],
            "constraints_to_check": [],
        }

        # Get active constraints from brain
        constraints = await self.brain.constraints.list_constraints(limit=50)
        analysis["constraints_to_check"] = [
            {"id": c["id"], "name": c["name"], "severity": c["severity"]}
            for c in constraints
        ]

        return EngineResult(
            success=True,
            result=analysis,
            confidence=0.7,
            reason="Review analysis completed",
            warnings=["Alpha version - limited review dimensions"],
        )

    async def plan(self, analysis: EngineResult) -> EngineResult:
        """Plan review checks."""
        if not analysis.success:
            return analysis

        data = analysis.result or {}
        
        plan = {
            "checks_to_run": [
                "word_count_check",
                "constraint_compliance",
                "basic_quality_check",
            ],
            "constraints_to_verify": data.get("constraints_to_check", []),
            "score_threshold": 80,
        }

        return EngineResult(
            success=True,
            result=plan,
            confidence=0.7,
            reason="Review plan created",
        )

    async def execute(self, plan: EngineResult) -> EngineResult:
        """Execute review."""
        if not plan.success:
            return plan

        # Alpha: Basic review checks
        # Full implementation will use AI for 7-dimensional review
        data = plan.result or {}
        
        review_result = {
            "overall_score": 75,  # Alpha: placeholder score
            "dimension_scores": {
                "consistency": 80,
                "character_voice": 75,
                "pacing": 70,
                "plot_logic": 78,
                "writing_quality": 72,
            },
            "issues": [],
            "constraint_violations": [],
            "passed": True,
        }

        # Check constraints (Alpha: just count them)
        constraints = data.get("constraints_to_verify", [])
        review_result["constraints_checked"] = len(constraints)

        return EngineResult(
            success=True,
            result=review_result,
            confidence=0.5,
            reason="Basic review completed",
            warnings=[
                "Alpha version - placeholder scores",
                "Full AI review not yet implemented",
            ],
        )

    async def validate(self, output: EngineResult) -> EngineResult:
        """Validate review output."""
        if not output.success:
            return output

        result = output.result or {}
        
        validation = {
            **result,
            "review_valid": True,
            "score_in_range": 0 <= result.get("overall_score", 0) <= 100,
        }

        return EngineResult(
            success=True,
            result=validation,
            confidence=0.8,
            reason="Review output validated",
        )

    async def update(self, validated: EngineResult) -> EngineResult:
        """Update brain with review results."""
        if not validated.success:
            return validated

        data = validated.result or {}
        
        # Update review state
        await self.brain.state.update_state(
            "global",
            "last_review_score",
            {
                "overall_score": data.get("overall_score", 0),
                "dimension_scores": data.get("dimension_scores", {}),
                "issues_count": len(data.get("issues", [])),
            },
            0.7,
            source="review_engine",
        )

        # Record decision
        await self.brain.record_decision(
            "review_score",
            f"Review score: {data.get('overall_score', 0)}",
            decision_reason="Automated review completed",
            confidence=0.7,
            permission_level="auto",
            decided_by="ai",
        )

        return EngineResult(
            success=True,
            result={"brain_updated": True, "score_recorded": True},
            confidence=0.8,
            reason="Brain updated with review results",
        )
