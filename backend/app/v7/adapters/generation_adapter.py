"""
V6 Generation Adapter
=====================

Wraps V6's gateway.py AI gateway to provide V7-compatible generation interface.

V7's AIGateway interface:
    generate(prompt, system_prompt, model, temperature, max_tokens, response_format)
    -> {content, usage, model, finish_reason}

V6's gateway interface:
    generate_text(prompt, system_prompt, model, temperature, max_tokens, ...)
    -> {text, usage, ...}
"""
from __future__ import annotations

import json
from typing import Any, Optional

from ...gateway import generate_text, generate_structured


class V6GenerationAdapter:
    """Adapter that wraps V6's gateway to provide V7-compatible AI generation."""

    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        response_format: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Generate text using V6's gateway.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            model: Model name (default: deepseek-chat)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: Optional response format specification

        Returns:
            Dict with: content, usage, model, finish_reason, raw_response
        """
        if response_format:
            # Structured output
            result = generate_structured(
                prompt=prompt,
                system_prompt=system_prompt or "",
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                project_id=self.project_id,
            )
            return {
                "content": result.get("parsed", result.get("text", "")),
                "raw_content": result.get("text", ""),
                "usage": result.get("usage", {}),
                "model": result.get("model", model),
                "finish_reason": result.get("finish_reason", "stop"),
                "raw_response": result,
            }
        else:
            # Plain text generation
            result = generate_text(
                prompt=prompt,
                system_prompt=system_prompt or "",
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                project_id=self.project_id,
            )
            return {
                "content": result.get("text", ""),
                "usage": result.get("usage", {}),
                "model": result.get("model", model),
                "finish_reason": result.get("finish_reason", "stop"),
                "raw_response": result,
            }

    def generate_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        max_retries: int = 3,
        response_format: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Generate with automatic retry on failure.

        Note: V6's gateway already has retry logic built in.
        This is just a pass-through for V7 compatibility.
        """
        return self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

    def count_tokens(self, text: str, model: str = "deepseek-chat") -> int:
        """Count tokens in text.

        Note: V6 doesn't have a dedicated token counting function.
        This is a rough estimate.
        """
        # Rough estimate: 1 token ≈ 1.5 Chinese characters or 0.75 English words
        char_count = len(text)
        return int(char_count / 1.5)
