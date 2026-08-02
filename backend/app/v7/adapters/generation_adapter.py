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

import hashlib
from typing import Any, Optional

from ...gateway import complete


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
        if not self.project_id:
            raise ValueError("V6 generation adapter requires project_id")
        # V6 owns prompt registration, model routing, budget checks and the
        # ai_calls ledger.  This adapter deliberately maps to a registered
        # editor task instead of inventing a second provider call surface.
        result = complete(
            run_id=None,
            node_key="v7_v6_generation_adapter",
            project_id=self.project_id,
            task_type="editor_polish",
            prompt_name="editor.polish",
            variables={"selection": prompt, "instruction": prompt, "text": prompt},
            client_mutation_id="v7-v6-adapter:" + hashlib.sha256(prompt.encode()).hexdigest(),
        )
        content = result.get("text", "") if isinstance(result, dict) else ""
        if response_format and isinstance(result, dict):
            content = result
        return {
            "content": content,
            "raw_content": result.get("text", "") if isinstance(result, dict) else "",
            "usage": result.get("usage", {}) if isinstance(result, dict) else {},
            "model": model,
            "finish_reason": "stop",
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
