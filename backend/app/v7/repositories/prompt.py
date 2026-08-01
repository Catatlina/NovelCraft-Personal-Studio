"""Prompt version and execution repositories."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.prompt import PromptVersion, PromptExecution


class PromptVersionRepository(BaseRepository[PromptVersion]):
    """Prompt version repository.

    Note: ``v7_prompt_versions`` is a global (non novel-scoped) table —
    prompt templates are shared across novels.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(PromptVersion, db)

    async def list_versions(
        self,
        *,
        prompt_name: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[PromptVersion]:
        """List prompt versions."""
        query = select(PromptVersion)

        if prompt_name:
            query = query.where(PromptVersion.prompt_name == prompt_name)
        if is_active is not None:
            query = query.where(PromptVersion.is_active == is_active)

        query = (
            query.order_by(
                PromptVersion.prompt_name.asc(), PromptVersion.version.desc()
            )
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_versions(
        self,
        *,
        prompt_name: str | None = None,
        is_active: bool | None = None,
    ) -> int:
        """Count prompt versions."""
        query = select(func.count()).select_from(PromptVersion)

        if prompt_name:
            query = query.where(PromptVersion.prompt_name == prompt_name)
        if is_active is not None:
            query = query.where(PromptVersion.is_active == is_active)

        result = await self.db.execute(query)
        return result.scalar_one()

    async def get_by_name_version(
        self,
        prompt_name: str,
        version: int,
    ) -> PromptVersion | None:
        """Get a specific version of a prompt."""
        result = await self.db.execute(
            select(PromptVersion).where(
                PromptVersion.prompt_name == prompt_name,
                PromptVersion.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_hash(
        self,
        prompt_name: str,
        prompt_hash: str,
    ) -> PromptVersion | None:
        """Get a version by its content hash."""
        result = await self.db.execute(
            select(PromptVersion)
            .where(
                PromptVersion.prompt_name == prompt_name,
                PromptVersion.prompt_hash == prompt_hash,
            )
            .order_by(PromptVersion.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest(self, prompt_name: str) -> PromptVersion | None:
        """Get the highest-numbered version of a prompt."""
        result = await self.db.execute(
            select(PromptVersion)
            .where(PromptVersion.prompt_name == prompt_name)
            .order_by(PromptVersion.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_default(self, prompt_name: str) -> PromptVersion | None:
        """Get the default (currently used) version of a prompt.

        Falls back to the latest active version when no default is flagged.
        """
        result = await self.db.execute(
            select(PromptVersion)
            .where(
                PromptVersion.prompt_name == prompt_name,
                PromptVersion.is_default == True,
                PromptVersion.is_active == True,
            )
            .order_by(PromptVersion.version.desc())
            .limit(1)
        )
        default = result.scalar_one_or_none()
        if default:
            return default

        fallback = await self.db.execute(
            select(PromptVersion)
            .where(
                PromptVersion.prompt_name == prompt_name,
                PromptVersion.is_active == True,
            )
            .order_by(PromptVersion.version.desc())
            .limit(1)
        )
        return fallback.scalar_one_or_none()

    async def get_next_version_number(self, prompt_name: str) -> int:
        """Get the next version number for a prompt name."""
        result = await self.db.execute(
            select(func.max(PromptVersion.version)).where(
                PromptVersion.prompt_name == prompt_name
            )
        )
        return (result.scalar_one_or_none() or 0) + 1

    async def list_prompt_names(self) -> list[str]:
        """List all distinct prompt names."""
        result = await self.db.execute(
            select(PromptVersion.prompt_name)
            .distinct()
            .order_by(PromptVersion.prompt_name)
        )
        return [row[0] for row in result.all()]

    async def create_version(
        self,
        prompt_name: str,
        template: str,
        prompt_hash: str,
        *,
        model: str = "deepseek-chat",
        parameters: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        version_label: str | None = None,
        description: str | None = None,
        change_notes: str | None = None,
        is_default: bool = False,
        created_by: str = "system",
        golden_cases: list[dict[str, Any]] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> PromptVersion:
        """Create a new prompt version."""
        version_number = await self.get_next_version_number(prompt_name)

        if is_default:
            await self.clear_default(prompt_name)

        return await self.create({
            "prompt_name": prompt_name,
            "version": version_number,
            "version_label": version_label or f"v{version_number}",
            "template": template,
            "model": model,
            "parameters": parameters or {},
            "output_schema": output_schema,
            "prompt_hash": prompt_hash,
            "description": description,
            "change_notes": change_notes,
            "is_active": True,
            "is_default": is_default,
            "created_by": created_by,
            "golden_cases": golden_cases or [],
            "extra_metadata": extra_metadata or {},
        })

    async def clear_default(self, prompt_name: str) -> None:
        """Unset is_default on every version of a prompt."""
        await self.db.execute(
            update(PromptVersion)
            .where(
                PromptVersion.prompt_name == prompt_name,
                PromptVersion.is_default == True,
            )
            .values(is_default=False)
        )
        await self.db.flush()


class PromptExecutionRepository(BaseRepository[PromptExecution]):
    """Prompt execution repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(PromptExecution, db)

    async def list_executions(
        self,
        *,
        novel_id: uuid.UUID | None = None,
        prompt_name: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        status: str | None = None,
        run_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[PromptExecution]:
        """List prompt executions."""
        query = select(PromptExecution)

        if novel_id:
            query = query.where(PromptExecution.novel_id == novel_id)
        if prompt_name:
            query = query.where(PromptExecution.prompt_name == prompt_name)
        if prompt_version_id:
            query = query.where(
                PromptExecution.prompt_version_id == prompt_version_id
            )
        if status:
            query = query.where(PromptExecution.status == status)
        if run_id:
            query = query.where(PromptExecution.run_id == run_id)

        query = (
            query.order_by(PromptExecution.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_executions(
        self,
        *,
        novel_id: uuid.UUID | None = None,
        prompt_name: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> int:
        """Count prompt executions."""
        query = select(func.count()).select_from(PromptExecution)

        if novel_id:
            query = query.where(PromptExecution.novel_id == novel_id)
        if prompt_name:
            query = query.where(PromptExecution.prompt_name == prompt_name)
        if prompt_version_id:
            query = query.where(
                PromptExecution.prompt_version_id == prompt_version_id
            )
        if status:
            query = query.where(PromptExecution.status == status)

        result = await self.db.execute(query)
        return result.scalar_one()

    async def stats_by_version(
        self,
        prompt_name: str,
        *,
        novel_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregate execution stats grouped by prompt version."""
        query = (
            select(
                PromptExecution.prompt_version_id,
                PromptExecution.version,
                func.count(),
                func.coalesce(func.sum(PromptExecution.tokens_input), 0),
                func.coalesce(func.sum(PromptExecution.tokens_output), 0),
                func.coalesce(func.sum(PromptExecution.cost), 0.0),
                func.coalesce(func.avg(PromptExecution.duration_seconds), 0.0),
                func.count().filter(PromptExecution.status == "success"),
            )
            .where(PromptExecution.prompt_name == prompt_name)
        )

        if novel_id:
            query = query.where(PromptExecution.novel_id == novel_id)

        query = query.group_by(
            PromptExecution.prompt_version_id, PromptExecution.version
        ).order_by(PromptExecution.version.desc())

        result = await self.db.execute(query)
        rows = []
        for row in result.all():
            total = int(row[2] or 0)
            success = int(row[7] or 0)
            rows.append({
                "prompt_version_id": str(row[0]) if row[0] else None,
                "version": row[1],
                "execution_count": total,
                "tokens_input": int(row[3] or 0),
                "tokens_output": int(row[4] or 0),
                "total_cost": float(row[5] or 0.0),
                "avg_duration_seconds": round(float(row[6] or 0.0), 4),
                "success_count": success,
                "success_rate": round(success / total, 4) if total else 0.0,
            })
        return rows

    async def record_execution(
        self,
        prompt_version_id: uuid.UUID,
        prompt_name: str,
        version: int,
        model: str,
        *,
        input_variables: dict[str, Any] | None = None,
        rendered_prompt: str | None = None,
        output: dict[str, Any] | None = None,
        output_raw: str | None = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost: float = 0.0,
        duration_seconds: float | None = None,
        status: str = "success",
        error_message: str | None = None,
        run_id: uuid.UUID | None = None,
        step_id: uuid.UUID | None = None,
        novel_id: uuid.UUID | None = None,
        validation_passed: bool | None = None,
        validation_errors: list[str] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> PromptExecution:
        """Record a prompt execution."""
        return await self.create({
            "prompt_version_id": prompt_version_id,
            "prompt_name": prompt_name,
            "version": version,
            "model": model,
            "input_variables": input_variables or {},
            "rendered_prompt": rendered_prompt,
            "output": output,
            "output_raw": output_raw,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "cost": cost,
            "duration_seconds": duration_seconds,
            "status": status,
            "error_message": error_message,
            "run_id": run_id,
            "step_id": step_id,
            "novel_id": novel_id,
            "validation_passed": validation_passed,
            "validation_errors": validation_errors or [],
            "extra_metadata": extra_metadata or {},
        })
