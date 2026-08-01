"""
V6 DeAI Adapter
================

Wraps V6's deai_pipeline.py to provide V7-compatible de-AI pipeline.

V7's DeAIPipeline interface:
    process(text, style_profile, intensity)
    -> {text, steps_applied, quality_score}

V6's deai_pipeline interface:
    deai_pipeline(text, style_profile, ...)
    -> {text, steps, ...}
"""
from __future__ import annotations

from typing import Any, Optional

from ...services.deai_pipeline import deai_pipeline


class V6DeAIAdapter:
    """Adapter that wraps V6's deai_pipeline for V7 compatibility."""

    def __init__(self, style_profile: Optional[dict[str, Any]] = None):
        self.style_profile = style_profile or {}

    def process(
        self,
        text: str,
        style_profile: Optional[dict[str, Any]] = None,
        intensity: str = "medium",
    ) -> dict[str, Any]:
        """Run de-AI pipeline on text.

        Args:
            text: Input text to process
            style_profile: Optional style profile to use
            intensity: Processing intensity (light/medium/heavy)

        Returns:
            Dict with: text, steps_applied, quality_score, raw_result
        """
        profile = style_profile or self.style_profile

        result = deai_pipeline(
            text=text,
            style_profile=profile,
            intensity=intensity,
        )

        return {
            "text": result.get("text", text),
            "steps_applied": result.get("steps_applied", []),
            "quality_score": result.get("quality_score", 0),
            "original_length": len(text),
            "final_length": len(result.get("text", text)),
            "raw_result": result,
        }

    def light_process(self, text: str, style_profile: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Light de-AI processing."""
        return self.process(text, style_profile, intensity="light")

    def medium_process(self, text: str, style_profile: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Medium de-AI processing."""
        return self.process(text, style_profile, intensity="medium")

    def heavy_process(self, text: str, style_profile: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Heavy de-AI processing."""
        return self.process(text, style_profile, intensity="heavy")
