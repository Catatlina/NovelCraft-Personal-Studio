"""Generation Engine - Sprint 2 Alpha.

Handles text generation with context assembly, scene direction, and de-AI pipeline.
Alpha: Adapter pattern to reuse V6 generation code.
"""
from __future__ import annotations
import os

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..brain.novel_brain import NovelBrain
from ..trace.tracer import ExecutionTracer
from ..events.event_bus import EventBus


class ContextAssembler:
    """
    Context assembler for generation.
    
    Alpha: Adapter that will use V6's assembler.py.
    Full V7 implementation will use Novel Brain state directly.
    """

    def __init__(self, brain: NovelBrain):
        self.brain = brain

    async def assemble_context(
        self,
        chapter_number: int,
        *,
        scene_type: str = "normal",
        token_budget: int = 5400,
    ) -> dict[str, Any]:
        """
        Assemble context for generation.
        
        Alpha: Basic context from brain state.
        Full: 10-layer context with priority-based token allocation.
        """
        # Get brain overview
        overview = await self.brain.get_overview()

        # Alpha: Simple context assembly
        context = {
            "chapter_number": chapter_number,
            "scene_type": scene_type,
            "token_budget": token_budget,
            "context_layers": {
                "story_state": overview.states.total,
                "active_goals": overview.goals.in_progress,
                "active_constraints": overview.constraints.active,
            },
            "notes": "Alpha: Basic context assembly only",
        }

        return context


class SceneDirector:
    """
    Scene director for generation planning.
    
    Alpha: Basic scene planning.
    Full: Beat-by-beat scene direction with emotional arcs.
    """

    def __init__(self, brain: NovelBrain):
        self.brain = brain

    async def plan_scene(
        self,
        chapter_number: int,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Plan a scene for generation.
        
        Alpha: Basic scene plan.
        Full: Detailed beat sheet with emotional beats, pacing, etc.
        """
        scene_plan = {
            "chapter_number": chapter_number,
            "scene_type": context.get("scene_type", "normal"),
            "beats": [
                "opening",
                "development",
                "climax",
                "resolution",
            ],
            "target_word_count": 3000,
            "pacing": "medium",
            "notes": "Alpha: Basic scene plan only",
        }

        return scene_plan


class DeAIPipeline:
    """
    De-AI pipeline for removing AI-generated feel.
    
    Alpha: Placeholder that will use V6's deai_pipeline.py.
    Full: 7-layer de-AI pipeline.
    """

    def __init__(self):
        pass

    async def process(self, text: str) -> dict[str, Any]:
        """
        Process text through de-AI pipeline.
        
        Alpha: Pass-through (no actual processing).
        Full: 7-layer pipeline.
        """
        return {
            "original_text": text,
            "processed_text": text,
            "layers_applied": [],
            "notes": "Alpha: De-AI pipeline not yet implemented",
        }


class AIGateway:
    """
    AI Gateway for calling LLM APIs.
    
    Alpha: Real DeepSeek API calls.
    Full: Model routing, cost tracking, prompt versioning.
    """

    def __init__(self, tracer: ExecutionTracer):
        self.tracer = tracer
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str = "你是一个专业的小说创作助手。",
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate text using AI.
        
        Alpha: Real DeepSeek API calls.
        Full: Model routing, cost tracking, structured output validation.
        """
        import requests
        
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # Add structured output if schema is provided
        if output_schema:
            data["response_format"] = {
                "type": "json_object",
            }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            content = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})
            
            # Calculate cost (approximate)
            # DeepSeek: input ¥1/M tokens, output ¥2/M tokens
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            cost = (input_tokens / 1_000_000 * 1.0) + (output_tokens / 1_000_000 * 2.0)
            
            return {
                "text": content,
                "model": model,
                "tokens_input": input_tokens,
                "tokens_output": output_tokens,
                "cost": cost,
                "finish_reason": result["choices"][0].get("finish_reason", "stop"),
                "raw_response": result,
            }
        except Exception as e:
            # Fallback: return error info
            return {
                "text": f"[Error] AI generation failed: {str(e)}",
                "model": model,
                "tokens_input": 0,
                "tokens_output": 0,
                "cost": 0.0,
                "finish_reason": "error",
                "error": str(e),
            }


class GenerationEngine:
    """
    Generation Engine - main generation orchestrator.
    
    Coordinates context assembly, scene planning, AI generation, and de-AI processing.
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

        self.context_assembler = ContextAssembler(brain)
        self.scene_director = SceneDirector(brain)
        self.deai_pipeline = DeAIPipeline()
        self.ai_gateway = AIGateway(tracer)

    async def generate_chapter(
        self,
        chapter_number: int,
        *,
        prompt: str | None = None,
        outline: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a complete chapter.
        
        Pipeline:
        1. Assemble context
        2. Plan scene
        3. Generate text
        4. De-AI processing
        5. Review
        """
        # Step 1: Assemble context
        async with self.tracer.trace_step(
            "generation.assemble_context",
            "context_assembly",
            input_summary=f"Assemble context for chapter {chapter_number}",
        ):
            context = await self.context_assembler.assemble_context(chapter_number)

        # Step 2: Plan scene
        async with self.tracer.trace_step(
            "generation.plan_scene",
            "scene_planning",
            input_summary="Plan scene structure",
        ):
            scene_plan = await self.scene_director.plan_scene(chapter_number, context)

        # Step 3: Generate text
        async with self.tracer.trace_step(
            "generation.ai_generate",
            "ai_generation",
            input_summary="Generate text with AI",
        ):
            generation_prompt = prompt or outline or f"Write chapter {chapter_number}"
            generation_result = await self.ai_gateway.generate(
                generation_prompt,
                max_tokens=3000,
            )

        # Step 4: De-AI processing
        async with self.tracer.trace_step(
            "generation.deai_process",
            "deai_processing",
            input_summary="Process through de-AI pipeline",
        ):
            deai_result = await self.deai_pipeline.process(generation_result["text"])

        # Publish event
        await self.event_bus.publish(
            "generation_completed",
            f"Chapter {chapter_number} generation completed",
            "generation",
            event_data={
                "chapter_number": chapter_number,
                "word_count": len(deai_result["processed_text"].split()),
            },
        )

        return {
            "chapter_number": chapter_number,
            "text": deai_result["processed_text"],
            "word_count": len(deai_result["processed_text"].split()),
            "context": context,
            "scene_plan": scene_plan,
            "generation": generation_result,
            "deai": deai_result,
        }
