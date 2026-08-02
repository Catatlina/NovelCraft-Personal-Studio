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

import json
from typing import Any, Optional

from ...services.deai_pipeline import DeaiPipeline


class V6DeAIAdapter:
    """Adapter that wraps V6's deai_pipeline for V7 compatibility."""

    def __init__(
        self,
        style_profile: Optional[dict[str, Any]] = None,
        *,
        project_id: str | None = None,
        content_id: str | None = None,
        chapter_title: str = "",
    ):
        self.style_profile = style_profile or {}
        self.project_id = project_id or ""
        self.content_id = content_id or ""
        self.chapter_title = chapter_title

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
        if not self.project_id or not self.content_id:
            raise ValueError("V6 de-AI adapter requires project_id and content_id")
        # DeaiPipeline is provider-backed and raises on provider failure; this
        # adapter must not turn an unavailable rewrite into a heuristic success.
        effective_style = style_profile or self.style_profile
        result = DeaiPipeline(
            self.project_id, self.content_id, self.chapter_title
        ).run(text, style_profile=json.dumps(effective_style, ensure_ascii=False))

        return {
            "text": result.get("final_text", ""),
            "steps_applied": result.get("layers", []),
            "quality_score": result.get("final_score"),
            "original_length": len(text),
            "final_length": len(result.get("final_text", text)),
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
