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
    safety_snapshot_id: str
    status: str
    restored_states: int
    recreated_states: int
    deactivated_states: int
    unchanged_states: int
    restored: list[dict[str, Any]] = Field(default_factory=list)
    recreated: list[dict[str, Any]] = Field(default_factory=list)
    deactivated: list[dict[str, Any]] = Field(default_factory=list)


class SnapshotCompareRequest(BaseModel):
    snapshot_a_id: str
    snapshot_b_id: str


class SnapshotCompareResponse(BaseModel):
    snapshot_a: dict[str, Any]
    snapshot_b: dict[str, Any]
    added: list[dict[str, Any]]
    removed: list[dict[str, Any]]
    modified: list[dict[str, Any]]
    unchanged_count: int
    summary: dict[str, Any]


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


# ── Human interventions ──────────────────────────────────────────────────

class HumanInterventionResponse(BaseModel):
    id: str
    novel_id: str
    intervention_type: str
    target_type: str
    target_id: str | None = None
    action: str
    description: str | None = None
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    reason: str | None = None
    user_id: str | None = None
    run_id: str | None = None
    result: str
    extra_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class HumanInterventionListResponse(BaseModel):
    items: list[HumanInterventionResponse]
    total: int
    stats: dict[str, Any]


class ReviewRequest(BaseModel):
    """Payload for human approve/reject actions."""
    reason: str | None = None
    user_id: str | None = None


class InstructionRequest(BaseModel):
    instruction: str = Field(..., min_length=1)
    scope: str = Field("next_chapter", max_length=50)
    target_chapter: int | None = None
    priority: int = Field(50, ge=0, le=100)
    reason: str | None = None
    user_id: str | None = None


class InstructionResponse(BaseModel):
    intervention: HumanInterventionResponse
    instruction: dict[str, Any]
    state_id: str
    pending_count: int


# ── Decisions (human review) ─────────────────────────────────────────────

class DecisionReviewResponse(BaseModel):
    decision_id: str
    decision_type: str
    decision: str
    status: str
    previous_status: str
    decided_by: str
    decided_at: str | None = None
    decision_reason: str | None = None
    intervention_id: str


# ── Cost ─────────────────────────────────────────────────────────────────

class BudgetCreateRequest(BaseModel):
    budget_type: str = Field(..., min_length=1, max_length=50)
    budget_scope: str = Field("novel", min_length=1, max_length=50)
    limit_cny: float = Field(..., gt=0)
    limit_tokens: int | None = Field(None, gt=0)
    period_days: int | None = Field(None, gt=0)
    action_on_exceed: str = Field("warn", max_length=20)
    description: str | None = None
    cost_policy: dict[str, Any] | None = None


class BudgetUpdateRequest(BaseModel):
    limit_cny: float | None = Field(None, gt=0)
    limit_tokens: int | None = Field(None, gt=0)
    action_on_exceed: str | None = None
    is_active: bool | None = None
    description: str | None = None
    cost_policy: dict[str, Any] | None = None


class CostRecordRequest(BaseModel):
    cost_cny: float = Field(0.0, ge=0)
    tokens: int = Field(0, ge=0)
    budget_type: str | None = None
    run_id: str | None = None
    source: str = "system"
    description: str | None = None


# ── Prompt ───────────────────────────────────────────────────────────────

class PromptVersionCreateRequest(BaseModel):
    prompt_name: str = Field(..., min_length=1, max_length=200)
    template: str = Field(..., min_length=1)
    model: str = Field("deepseek-chat", max_length=100)
    parameters: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    version_label: str | None = Field(None, max_length=100)
    description: str | None = None
    change_notes: str | None = None
    created_by: str = "human"
    make_default: bool = True
    force_new: bool = False


class PromptChangeDetectRequest(BaseModel):
    prompt_name: str = Field(..., min_length=1, max_length=200)
    template: str = Field(..., min_length=1)
    model: str = Field("deepseek-chat", max_length=100)
    parameters: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None


class PromptExecutionCreateRequest(BaseModel):
    prompt_name: str = Field(..., min_length=1, max_length=200)
    prompt_version_id: str | None = None
    version: int | None = None
    novel_id: str | None = None
    input_variables: dict[str, Any] | None = None
    rendered_prompt: str | None = None
    output: dict[str, Any] | None = None
    output_raw: str | None = None
    model: str | None = None
    tokens_input: int = Field(0, ge=0)
    tokens_output: int = Field(0, ge=0)
    cost: float = Field(0.0, ge=0)
    duration_seconds: float | None = None
    status: str = "success"
    error_message: str | None = None
    run_id: str | None = None
    step_id: str | None = None
    validation_passed: bool | None = None
    validation_errors: list[str] | None = None
