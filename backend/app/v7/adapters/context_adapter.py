"""
V6 Context Adapter
===================

Wraps V6's assembler.py to provide V7-compatible context assembly.

V7's ContextAssembler interface:
    assemble(novel_id, chapter_id, scene_id, purpose, token_budget)
    -> {context, token_count, layers_used}

V6's assembler interface:
    assemble_context(novel_id, chapter_id, ...)
    -> {context, token_count, ...}
"""
from __future__ import annotations

from typing import Any, Optional

from ...services.assembler import ContextAssembler


class V6ContextAdapter:
    """Adapter that wraps V6's context assembler for V7 compatibility."""

    def __init__(self, default_token_budget: int = 5400):
        self.default_token_budget = default_token_budget

    def assemble(
        self,
        novel_id: str,
        chapter_id: Optional[str] = None,
        scene_id: Optional[str] = None,
        purpose: str = "chapter_generation",
        token_budget: Optional[int] = None,
    ) -> dict[str, Any]:
        """Assemble context for generation.

        Args:
            novel_id: Novel ID
            chapter_id: Optional chapter ID
            scene_id: Optional scene ID
            purpose: Purpose of context assembly
            token_budget: Token budget (default: 5400)

        Returns:
            Dict with: context, token_count, layers_used, raw_result
        """
        budget = token_budget or self.default_token_budget

        assembler = ContextAssembler(novel_id, chapter_id=chapter_id)
        context = assembler.build()

        return {
            "context": context,
            "token_count": max(0, len(context) // 2),
            "token_budget": budget,
            "layers_used": [name for name, value in assembler.layers_built.items() if value],
            "raw_result": {"context": context, "discarded": assembler.discarded},
        }

    def assemble_for_chapter(
        self,
        novel_id: str,
        chapter_id: str,
        token_budget: Optional[int] = None,
    ) -> dict[str, Any]:
        """Assemble context for chapter generation."""
        return self.assemble(
            novel_id=novel_id,
            chapter_id=chapter_id,
            purpose="chapter_generation",
            token_budget=token_budget,
        )

    def assemble_for_review(
        self,
        novel_id: str,
        chapter_id: str,
        token_budget: Optional[int] = None,
    ) -> dict[str, Any]:
        """Assemble context for review."""
        return self.assemble(
            novel_id=novel_id,
            chapter_id=chapter_id,
            purpose="review",
            token_budget=token_budget,
        )

    def assemble_for_continuation(
        self,
        novel_id: str,
        chapter_id: str,
        token_budget: Optional[int] = None,
    ) -> dict[str, Any]:
        """Assemble context for continuation."""
        return self.assemble(
            novel_id=novel_id,
            chapter_id=chapter_id,
            purpose="continuation",
            token_budget=token_budget,
        )
