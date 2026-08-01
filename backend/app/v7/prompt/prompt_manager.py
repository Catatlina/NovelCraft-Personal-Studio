"""Prompt Version Manager - Sprint 3 Alpha.

Manages prompt versions, execution history, and golden cases.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.prompt import PromptVersionRepository, PromptExecutionRepository


class PromptVersionManager:
    """
    Prompt version manager.
    
    Sprint 3 Alpha: Basic version management and execution tracking.
    Full golden cases and A/B testing in V7.1.
    """

    def __init__(self, db: AsyncSession, novel_id: uuid.UUID):
        self.db = db
        self.novel_id = novel_id
        self.version_repo = PromptVersionRepository(db)
        self.execution_repo = PromptExecutionRepository(db)

    async def list_versions(
        self,
        prompt_name: str | None = None,
        *,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List prompt versions."""
        versions = await self.version_repo.list_by_novel(
            self.novel_id,
            prompt_name=prompt_name,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )
        return [self._version_to_dict(v) for v in versions]

    async def get_version(self, version_id: uuid.UUID) -> dict[str, Any] | None:
        """Get a specific prompt version."""
        version = await self.version_repo.get(version_id)
        if not version:
            return None
        return self._version_to_dict(version)

    async def create_version(
        self,
        prompt_name: str,
        template: str,
        *,
        model: str = "deepseek-chat",
        parameters: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        description: str = "",
        change_notes: str = "",
        is_default: bool = False,
    ) -> dict[str, Any]:
        """Create a new prompt version."""
        # Calculate hash
        prompt_hash = hashlib.sha256(template.encode()).hexdigest()[:16]

        # Get next version number
        existing = await self.version_repo.list_by_novel(
            self.novel_id,
            prompt_name=prompt_name,
            limit=1,
        )
        next_version = len(existing) + 1
        version_label = f"v{next_version}.0"

        version = await self.version_repo.create(
            novel_id=self.novel_id,
            prompt_name=prompt_name,
            version=next_version,
            version_label=version_label,
            template=template,
            model=model,
            parameters=parameters or {},
            output_schema=output_schema or {},
            prompt_hash=prompt_hash,
            description=description,
            change_notes=change_notes,
            is_active=True,
            is_default=is_default,
        )

        return self._version_to_dict(version)

    async def set_default(self, version_id: uuid.UUID) -> dict[str, Any] | None:
        """Set a version as the default."""
        version = await self.version_repo.get(version_id)
        if not version:
            return None

        # Unset current default
        await self.version_repo.update(
            version_id,
            {"is_default": False},
            # Note: actual implementation would filter by prompt_name
        )

        # Set new default
        updated = await self.version_repo.update(
            version_id,
            {"is_default": True},
        )

        return self._version_to_dict(updated) if updated else None

    async def record_execution(
        self,
        prompt_name: str,
        version: int,
        *,
        input_variables: dict[str, Any],
        rendered_prompt: str,
        output: str,
        output_raw: str | None = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost: float = 0.0,
        duration_seconds: float = 0.0,
        status: str = "success",
        error_message: str | None = None,
        run_id: uuid.UUID | None = None,
        step_id: uuid.UUID | None = None,
        validation_passed: bool = True,
        validation_errors: list[str] | None = None,
    ) -> dict[str, Any]:
        """Record a prompt execution."""
        execution = await self.execution_repo.record_execution(
            novel_id=self.novel_id,
            prompt_name=prompt_name,
            version=version,
            input_variables=input_variables,
            rendered_prompt=rendered_prompt,
            output=output,
            output_raw=output_raw,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost=cost,
            duration_seconds=duration_seconds,
            status=status,
            error_message=error_message,
            run_id=run_id,
            step_id=step_id,
            validation_passed=validation_passed,
            validation_errors=validation_errors or [],
        )

        return {
            "id": str(execution.id),
            "prompt_name": execution.prompt_name,
            "version": execution.version,
            "status": execution.status,
            "tokens_input": execution.tokens_input,
            "tokens_output": execution.tokens_output,
            "cost": execution.cost,
            "duration_seconds": execution.duration_seconds,
        }

    async def get_execution_history(
        self,
        prompt_name: str | None = None,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get prompt execution history."""
        executions = await self.execution_repo.list_by_novel(
            self.novel_id,
            prompt_name=prompt_name,
            status=status,
            limit=limit,
            offset=offset,
        )
        return [self._execution_to_dict(e) for e in executions]

    def _version_to_dict(self, version: Any) -> dict[str, Any]:
        return {
            "id": str(version.id),
            "prompt_name": version.prompt_name,
            "version": version.version,
            "version_label": version.version_label,
            "model": version.model,
            "parameters": version.parameters,
            "output_schema": version.output_schema,
            "prompt_hash": version.prompt_hash,
            "description": version.description,
            "change_notes": version.change_notes,
            "is_active": version.is_active,
            "is_default": version.is_default,
            "created_at": version.created_at.isoformat() if version.created_at else None,
        }

    def _execution_to_dict(self, execution: Any) -> dict[str, Any]:
        return {
            "id": str(execution.id),
            "prompt_name": execution.prompt_name,
            "version": execution.version,
            "status": execution.status,
            "tokens_input": execution.tokens_input,
            "tokens_output": execution.tokens_output,
            "cost": execution.cost,
            "duration_seconds": execution.duration_seconds,
            "validation_passed": execution.validation_passed,
            "created_at": execution.created_at.isoformat() if execution.created_at else None,
        }
