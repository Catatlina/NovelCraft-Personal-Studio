"""Prompt version models."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class PromptVersion(BaseModel):
    """Prompt version record."""
    __tablename__ = "v7_prompt_versions"

    prompt_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    version_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 hash
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[str] = mapped_column(String(50), nullable=False, default="system")
    golden_cases: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class PromptExecution(BaseModel):
    """Prompt execution record."""
    __tablename__ = "v7_prompt_executions"

    prompt_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    prompt_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_variables: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    rendered_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    output_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_input: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost: Mapped[float] = mapped_column(nullable=False, default=0.0)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    # success / failed / timeout / validation_error
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    novel_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    validation_passed: Mapped[bool | None] = mapped_column(nullable=True)
    validation_errors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
