"""Typed event payloads for the V7 event bus.

Every event type that drives state changes has a Pydantic payload model so the
contract between publisher and subscriber is enforced instead of implied.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaseEventPayload(BaseModel):
    """Base payload; extra keys are kept so publishers can add detail."""

    model_config = ConfigDict(extra="allow")


class ChapterGeneratedPayload(BaseEventPayload):
    chapter_number: int = Field(ge=1)
    word_count: int = Field(ge=0)
    review_score: float = Field(default=0.0, ge=0, le=100)
    passed_review: bool = False
    run_id: str | None = None
    title: str | None = None


class GenerationCompletedPayload(BaseEventPayload):
    chapter_number: int = Field(ge=1)
    word_count: int = Field(ge=0)
    tokens: int = Field(default=0, ge=0)
    cost: float = Field(default=0.0, ge=0)
    deai_changes: int = Field(default=0, ge=0)


class ReviewCompletedPayload(BaseEventPayload):
    chapter_number: int | None = None
    overall_score: float = Field(ge=0, le=100)
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    blocking_violations: int = Field(default=0, ge=0)


class ConstraintViolatedPayload(BaseEventPayload):
    chapter_number: int | None = None
    constraint: str | None = None
    description: str | None = None
    severity: str = "medium"


class MemoryConflictPayload(BaseEventPayload):
    chapter_number: int | None = None
    key: str | None = None
    description: str | None = None
    severity: str = "medium"


class HumanInterventionPayload(BaseEventPayload):
    intervention_type: str
    target_type: str | None = None
    target_id: str | None = None
    action: str | None = None


EVENT_PAYLOAD_MODELS: dict[str, type[BaseEventPayload]] = {
    "chapter_generated": ChapterGeneratedPayload,
    "generation_completed": GenerationCompletedPayload,
    "review_completed": ReviewCompletedPayload,
    "constraint_violated": ConstraintViolatedPayload,
    "memory_conflict_detected": MemoryConflictPayload,
    "human_intervention": HumanInterventionPayload,
}


def validate_event_data(
    event_type: str, event_data: dict[str, Any] | None
) -> dict[str, Any]:
    """Validate + normalise the payload of a registered event type."""
    model = EVENT_PAYLOAD_MODELS.get(event_type)
    if model is None:
        return event_data or {}
    payload = model.model_validate(event_data or {})
    return payload.model_dump(mode="json")
