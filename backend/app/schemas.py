from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int | str = 0
    message: str = "ok"
    data: Any = None


class NovelCreate(BaseModel):
    idea: str = Field(min_length=4, max_length=1200)
    genre: str = Field(default="东方玄幻", max_length=80)
    style: str = Field(default="克制、悬疑、强画面感", max_length=160)
    target_words: int = Field(default=1000000, ge=1000, le=3000000)


class HumanConfirm(BaseModel):
    selected_title: str = Field(min_length=1, max_length=120)


class ContentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    body: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    label: str = Field(default="manual_save", max_length=80)


class AiEditRequest(BaseModel):
    selection: str = Field(min_length=1, max_length=8000)
    instruction: str = Field(default="", max_length=1000)


class VersionRestore(BaseModel):
    version_id: str


class BudgetUpdate(BaseModel):
    limit_cny: float = Field(ge=0.000001, le=10000)


class ModelRouteUpdate(BaseModel):
    provider: str = Field(pattern="^(mock|deepseek)$")
    model: str = Field(min_length=1, max_length=120)
    params: dict[str, Any] = Field(default_factory=dict)


AiOperation = Literal["polish", "rewrite", "continue", "expand", "condense", "deai"]
