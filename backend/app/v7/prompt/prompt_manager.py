"""Prompt Version Manager.

Closed loop over ``v7_prompt_versions`` / ``v7_prompt_executions``:
deterministic prompt hashing -> change detection -> version registration ->
per-execution records carrying ``prompt_version_id``.

``v7_prompt_versions`` is a global table (prompt templates are shared across
novels); ``novel_id`` only scopes the execution records.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.prompt import PromptVersion, PromptExecution
from ..repositories.prompt import PromptVersionRepository, PromptExecutionRepository


def compute_prompt_hash(
    template: str,
    *,
    model: str = "",
    parameters: dict[str, Any] | None = None,
    output_schema: dict[str, Any] | None = None,
) -> str:
    """Deterministic SHA256 over everything that changes prompt behaviour."""
    payload = json.dumps(
        {
            "template": template,
            "model": model,
            "parameters": parameters or {},
            "output_schema": output_schema or {},
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PromptVersionManager:
    """Prompt version and execution manager."""

    def __init__(self, db: AsyncSession, novel_id: uuid.UUID | None = None):
        self.db = db
        self.novel_id = novel_id
        self.version_repo = PromptVersionRepository(db)
        self.execution_repo = PromptExecutionRepository(db)

    # ── Versions ─────────────────────────────────────────────────────────

    async def list_prompt_names(self) -> list[str]:
        """List every registered prompt name."""
        return await self.version_repo.list_prompt_names()

    async def list_versions(
        self,
        *,
        prompt_name: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List prompt versions."""
        versions = await self.version_repo.list_versions(
            prompt_name=prompt_name,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )
        return [self._version_to_dict(v) for v in versions]

    async def count_versions(
        self,
        *,
        prompt_name: str | None = None,
        is_active: bool | None = None,
    ) -> int:
        """Count prompt versions."""
        return await self.version_repo.count_versions(
            prompt_name=prompt_name, is_active=is_active
        )

    async def get_version(self, version_id: uuid.UUID) -> dict[str, Any] | None:
        """Get one prompt version, including its template."""
        version = await self.version_repo.get(version_id)
        if not version:
            return None
        return self._version_to_dict(version, include_template=True)

    async def get_active_version(self, prompt_name: str) -> dict[str, Any] | None:
        """Get the version currently in use for a prompt name."""
        version = await self.version_repo.get_default(prompt_name)
        if not version:
            return None
        return self._version_to_dict(version, include_template=True)

    async def detect_change(
        self,
        prompt_name: str,
        template: str,
        *,
        model: str = "deepseek-chat",
        parameters: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compare a candidate template against the registered versions."""
        new_hash = compute_prompt_hash(
            template,
            model=model,
            parameters=parameters,
            output_schema=output_schema,
        )

        current = await self.version_repo.get_default(prompt_name)
        identical = await self.version_repo.get_by_hash(prompt_name, new_hash)

        return {
            "prompt_name": prompt_name,
            "new_hash": new_hash,
            "changed": current is None or current.prompt_hash != new_hash,
            "is_new_prompt": current is None,
            "current_version": current.version if current else None,
            "current_hash": current.prompt_hash if current else None,
            "existing_version_with_same_hash": (
                identical.version if identical else None
            ),
            "next_version": await self.version_repo.get_next_version_number(
                prompt_name
            ),
        }

    async def register_version(
        self,
        prompt_name: str,
        template: str,
        *,
        model: str = "deepseek-chat",
        parameters: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        version_label: str | None = None,
        description: str | None = None,
        change_notes: str | None = None,
        created_by: str = "system",
        make_default: bool = True,
        force_new: bool = False,
    ) -> dict[str, Any]:
        """Register a prompt version, creating one only when content changed.

        Returns ``{"created": bool, "changed": bool, "version": {...}}``.
        """
        if not template.strip():
            raise ValueError("template must not be empty")

        new_hash = compute_prompt_hash(
            template,
            model=model,
            parameters=parameters,
            output_schema=output_schema,
        )

        if not force_new:
            existing = await self.version_repo.get_by_hash(prompt_name, new_hash)
            if existing:
                if make_default and not existing.is_default:
                    await self.version_repo.clear_default(prompt_name)
                    existing = await self.version_repo.update(
                        existing.id, {"is_default": True, "is_active": True}
                    )
                return {
                    "created": False,
                    "changed": False,
                    "version": self._version_to_dict(existing, include_template=True),
                }

        previous = await self.version_repo.get_default(prompt_name)
        version = await self.version_repo.create_version(
            prompt_name,
            template,
            new_hash,
            model=model,
            parameters=parameters,
            output_schema=output_schema,
            version_label=version_label,
            description=description,
            change_notes=change_notes,
            is_default=make_default,
            created_by=created_by,
        )

        return {
            "created": True,
            "changed": True,
            "previous_version": previous.version if previous else None,
            "previous_hash": previous.prompt_hash if previous else None,
            "version": self._version_to_dict(version, include_template=True),
        }

    async def ensure_runtime_version(
        self,
        prompt_name: str,
        version_label: str | int | None,
        *,
        model: str = "deepseek-chat",
    ) -> dict[str, Any]:
        """Seed the concrete runtime label before its first execution.

        V7 prompt builders render context inline, so the full rendered prompt
        is recorded on ``PromptExecution`` rather than pretending that every
        context change is a new template version.  The registered template is
        a stable runtime identity; the execution carries the exact rendered
        hash and text used by the provider.
        """
        label = str(version_label or "runtime-1").strip() or "runtime-1"
        template = f"runtime-managed:{prompt_name}:{label}"
        parameters = {
            "runtime_managed": True,
            "runtime_version_label": label,
        }
        result = await self.register_version(
            prompt_name,
            template,
            model=model,
            parameters=parameters,
            version_label=label,
            description="Runtime-seeded provenance identity; exact rendered prompt is stored per execution.",
            change_notes="Created or reconciled by the shared V6/V7 execution gateway.",
            created_by="runtime",
            make_default=True,
        )
        return result["version"]

    async def set_default(self, version_id: uuid.UUID) -> dict[str, Any] | None:
        """Make a version the default for its prompt name."""
        version = await self.version_repo.get(version_id)
        if not version:
            return None

        await self.version_repo.clear_default(version.prompt_name)
        updated = await self.version_repo.update(
            version_id, {"is_default": True, "is_active": True}
        )
        return self._version_to_dict(updated, include_template=True)

    async def deactivate_version(self, version_id: uuid.UUID) -> dict[str, Any] | None:
        """Deactivate a version without deleting it."""
        version = await self.version_repo.get(version_id)
        if not version:
            return None
        updated = await self.version_repo.update(
            version_id, {"is_active": False, "is_default": False}
        )
        return self._version_to_dict(updated)

    # ── Executions ───────────────────────────────────────────────────────

    async def record_execution(
        self,
        prompt_name: str,
        *,
        prompt_version_id: uuid.UUID | None = None,
        version: int | None = None,
        input_variables: dict[str, Any] | None = None,
        rendered_prompt: str | None = None,
        output: dict[str, Any] | None = None,
        output_raw: str | None = None,
        model: str | None = None,
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
    ) -> dict[str, Any]:
        """Record one prompt execution against a concrete prompt version.

        The prompt version must already exist — resolved by ``prompt_version_id``,
        then by ``(prompt_name, version)``, then by the prompt's default version.
        """
        prompt_version = await self._resolve_version(
            prompt_name, prompt_version_id, version
        )

        execution = await self.execution_repo.record_execution(
            prompt_version.id,
            prompt_version.prompt_name,
            prompt_version.version,
            model or prompt_version.model,
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
            novel_id=novel_id or self.novel_id,
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            extra_metadata=extra_metadata,
        )
        return self._execution_to_dict(execution)

    async def record_runtime_execution(
        self,
        prompt_name: str,
        *,
        version_label: str | int | None,
        rendered_prompt: str,
        model: str,
        input_variables: dict[str, Any] | None = None,
        output_raw: str | None = None,
        output: dict[str, Any] | None = None,
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
    ) -> dict[str, Any]:
        """Register a runtime prompt identity and record its exact execution."""
        version = await self.ensure_runtime_version(
            prompt_name,
            version_label,
            model=model,
        )
        return await self.record_execution(
            prompt_name,
            prompt_version_id=uuid.UUID(version["id"]),
            input_variables=input_variables,
            rendered_prompt=rendered_prompt,
            output=output,
            output_raw=output_raw,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost=cost,
            duration_seconds=duration_seconds,
            status=status,
            error_message=error_message,
            run_id=run_id,
            step_id=step_id,
            novel_id=novel_id,
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            extra_metadata=extra_metadata,
        )

    async def get_execution_history(
        self,
        *,
        prompt_name: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        status: str | None = None,
        run_id: uuid.UUID | None = None,
        novel_scoped: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List prompt execution records."""
        executions = await self.execution_repo.list_executions(
            novel_id=self.novel_id if novel_scoped else None,
            prompt_name=prompt_name,
            prompt_version_id=prompt_version_id,
            status=status,
            run_id=run_id,
            skip=skip,
            limit=limit,
        )
        return [self._execution_to_dict(e) for e in executions]

    async def get_execution_stats(
        self,
        prompt_name: str,
        *,
        novel_scoped: bool = True,
    ) -> dict[str, Any]:
        """Per-version execution statistics for a prompt."""
        rows = await self.execution_repo.stats_by_version(
            prompt_name,
            novel_id=self.novel_id if novel_scoped else None,
        )
        return {
            "prompt_name": prompt_name,
            "novel_id": str(self.novel_id) if (novel_scoped and self.novel_id) else None,
            "total_executions": sum(r["execution_count"] for r in rows),
            "total_cost": round(sum(r["total_cost"] for r in rows), 6),
            "total_tokens": sum(
                r["tokens_input"] + r["tokens_output"] for r in rows
            ),
            "by_version": rows,
        }

    # ── Internals ────────────────────────────────────────────────────────

    async def _resolve_version(
        self,
        prompt_name: str,
        prompt_version_id: uuid.UUID | None,
        version: int | None,
    ) -> PromptVersion:
        if prompt_version_id:
            found = await self.version_repo.get(prompt_version_id)
            if not found:
                raise ValueError(f"Prompt version not found: {prompt_version_id}")
            return found

        if version is not None:
            found = await self.version_repo.get_by_name_version(prompt_name, version)
            if not found:
                raise ValueError(
                    f"Prompt version not found: {prompt_name} v{version}"
                )
            return found

        found = await self.version_repo.get_default(prompt_name)
        if not found:
            raise ValueError(
                f"No registered prompt version for '{prompt_name}'. "
                f"Call register_version() before recording executions."
            )
        return found

    @staticmethod
    def _version_to_dict(
        version: PromptVersion,
        *,
        include_template: bool = False,
    ) -> dict[str, Any]:
        data = {
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
            "created_by": version.created_by,
            "extra_metadata": version.extra_metadata,
            "created_at": version.created_at.isoformat() if version.created_at else None,
        }
        if include_template:
            data["template"] = version.template
            data["golden_cases"] = version.golden_cases
        return data

    @staticmethod
    def _execution_to_dict(execution: PromptExecution) -> dict[str, Any]:
        return {
            "id": str(execution.id),
            "prompt_version_id": str(execution.prompt_version_id),
            "prompt_name": execution.prompt_name,
            "version": execution.version,
            "model": execution.model,
            "status": execution.status,
            "input_variables": execution.input_variables,
            "output": execution.output,
            "output_raw": execution.output_raw,
            "rendered_prompt": execution.rendered_prompt,
            "tokens_input": execution.tokens_input,
            "tokens_output": execution.tokens_output,
            "cost": execution.cost,
            "duration_seconds": execution.duration_seconds,
            "error_message": execution.error_message,
            "run_id": str(execution.run_id) if execution.run_id else None,
            "step_id": str(execution.step_id) if execution.step_id else None,
            "novel_id": str(execution.novel_id) if execution.novel_id else None,
            "validation_passed": execution.validation_passed,
            "validation_errors": execution.validation_errors,
            "extra_metadata": execution.extra_metadata,
            "created_at": execution.created_at.isoformat() if execution.created_at else None,
        }
