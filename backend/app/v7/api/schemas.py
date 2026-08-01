"""V7 API schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Common ──────────────────────────────────────────────────────────────

class PaginationParams(BaseModel):
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=500)


class SuccessResponse(BaseModel):
    success: bool = True
    message: str | None = None


# ── Brain Overview ───────────────────────────────────────────────────────

class BrainOverviewResponse(BaseModel):
    novel_id: str
    states: dict[str, Any]
    goals: dict[str, Any]
    constraints: dict[str, Any]
    latest_version: dict[str, Any] | None = None
    recent_events: list[dict[str, Any]]


# ── Story States ─────────────────────────────────────────────────────────

class StateResponse(BaseModel):
    id: str
    key: str
    value: dict[str, Any]
    confidence: float
    version: int
    source: str
    is_pending_review: bool
    updated_at: str | None = None


class StateCreateRequest(BaseModel):
    state_type: str = Field(..., min_length=1, max_length=50)
    state_key: str = Field(..., min_length=1, max_length=200)
    state_value: dict[str, Any]
    confidence: float = Field(0.9, ge=0, le=1)
    source: str = "human"
    reason: str | None = None


class StateUpdateRequest(BaseModel):
    state_value: dict[str, Any] | None = None
    confidence: float | None = Field(None, ge=0, le=1)
    reason: str | None = None


class StateUpdateResponse(BaseModel):
    action: str
    state: dict[str, Any] | None = None
    confidence: float
    reason: str | None = None


class StateListResponse(BaseModel):
    items: list[StateResponse]
    total: int


# ── Goals ────────────────────────────────────────────────────────────────

class GoalResponse(BaseModel):
    id: str
    name: str
    type: str
    description: str | None = None
    parent_goal_id: str | None = None
    order: int
    status: str
    progress: float
    target_chapter: int | None = None
    completed_chapter: int | None = None
    priority: int
    confidence: float


class GoalCreateRequest(BaseModel):
    goal_type: str = Field(..., min_length=1, max_length=50)
    goal_name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    parent_goal_id: str | None = None
    goal_order: int = 0
    target_chapter: int | None = None
    priority: int = 50
    confidence: float = 0.8
    metadata: dict[str, Any] | None = None


class GoalUpdateRequest(BaseModel):
    goal_name: str | None = None
    description: str | None = None
    status: str | None = None
    progress: float | None = Field(None, ge=0, le=1)
    priority: int | None = None


class GoalTreeResponse(BaseModel):
    tree: list[dict[str, Any]]


# ── Constraints ──────────────────────────────────────────────────────────

class ConstraintResponse(BaseModel):
    id: str
    type: str
    name: str
    description: str | None = None
    value: dict[str, Any]
    severity: str
    check_method: str
    priority: int
    violation_count: int
    last_violation_at: str | None = None


class ConstraintCreateRequest(BaseModel):
    constraint_type: str = Field(..., min_length=1, max_length=50)
    constraint_name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    constraint_value: dict[str, Any]
    severity: str = "warning"
    check_method: str = "ai_review"
    priority: int = 50


class ConstraintUpdateRequest(BaseModel):
    constraint_name: str | None = None
    description: str | None = None
    constraint_value: dict[str, Any] | None = None
    severity: str | None = None
    priority: int | None = None
    is_active: bool | None = None


# ── Versions ─────────────────────────────────────────────────────────────

class VersionResponse(BaseModel):
    id: str
    version_number: int
    version_type: str
    description: str | None = None
    branch_name: str | None = None
    tag_name: str | None = None
    created_by: str
    created_at: str | None = None


class VersionCreateRequest(BaseModel):
    version_type: str = "manual"
    description: str | None = None
    branch_name: str = "main"
    tag_name: str | None = None


class SnapshotResponse(BaseModel):
    id: str
    snapshot_type: str
    description: str | None = None
    size_bytes: int | None = None
    created_at: str | None = None


class RollbackRequest(BaseModel):
    snapshot_id: str
    reason: str | None = None


class RollbackResponse(BaseModel):
    version_id: str
    version_number: int
    snapshot_id: str
    status: str
    note: str


# ── Decisions ────────────────────────────────────────────────────────────

class DecisionLogResponse(BaseModel):
    id: str
    decision_type: str
    decision: str
    reason: str | None = None
    confidence: float
    permission_level: str
    status: str
    decided_by: str
    created_at: str | None = None


# ── Events ───────────────────────────────────────────────────────────────

class EventResponse(BaseModel):
    id: str
    type: str
    name: str
    category: str
    severity: str
    description: str | None = None
    source: str
    time: str | None = None
    data: dict[str, Any]


# ── Trace ────────────────────────────────────────────────────────────────

class RunResponse(BaseModel):
    id: str
    run_type: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    total_tokens: int
    total_cost: float
    step_count: int
    chapter_number: int | None = None


class TraceStepResponse(BaseModel):
    id: str
    step_name: str
    step_type: str
    step_order: int
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    tokens_input: int
    tokens_output: int
    cost: float
    model: str | None = None
    confidence: float | None = None
