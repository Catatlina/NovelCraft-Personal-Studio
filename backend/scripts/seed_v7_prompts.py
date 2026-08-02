"""Idempotently seed the V7 runtime PromptVersion identities.

Usage from the repository root:

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/seed_v7_prompts.py

This does not call a model.  It creates the concrete PromptVersion rows used by
the runtime gateway; each later execution still stores the exact rendered
prompt and hash in ``v7_prompt_executions`` and ``ai_execution_ledger``.
"""
from __future__ import annotations

import asyncio

from app.v7.db import AsyncSessionLocal
from app.v7.prompt.prompt_manager import PromptVersionManager


RUNTIME_PROMPTS: tuple[tuple[str, str], ...] = (
    ("v7.plot.assess", "1.1.0"),
    ("v7.memory.extract", "1.0.0"),
    ("v7.review.seven_dimension", "1.1.0"),
    ("v7.generation.scene_plan", "1.1.0"),
    ("v7.generation.chapter", "1.1.0"),
    ("v7.generation.continuation", "1.1.0"),
    ("bootstrap.final_humanize", "1.0.4"),
    ("editor.polish", "runtime-1"),
)


async def seed() -> list[dict[str, object]]:
    async with AsyncSessionLocal() as db:
        manager = PromptVersionManager(db)
        rows = []
        for prompt_name, version_label in RUNTIME_PROMPTS:
            rows.append(
                await manager.ensure_runtime_version(
                    prompt_name,
                    version_label,
                    model="deepseek-chat",
                )
            )
        await db.commit()
        return rows


if __name__ == "__main__":
    seeded = asyncio.run(seed())
    for row in seeded:
        print(
            f"{row['prompt_name']} {row['version_label']} "
            f"id={row['id']} created_by={row['created_by']}"
        )
