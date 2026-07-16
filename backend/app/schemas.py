from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int | str = 0
    message: str = "ok"
    data: Any = None


class NovelCreate(BaseModel):
    idea: str = Field(min_length=4, max_length=10000)
    genre: str = Field(default="东方玄幻", max_length=80)
    style: str = Field(default="克制、悬疑、强画面感", max_length=160)
    target_words: int = Field(default=1000000, ge=1000, le=3000000)


class ShortStoryCreate(BaseModel):
    idea: str = Field(min_length=4, max_length=10000)
    template: str = Field(default="viral", pattern="^(flash|emotional|suspense|viral|dialogue)$")
    genre: str = Field(default="都市", max_length=80)
    style: str = Field(default="现代", max_length=160)


class HumanConfirm(BaseModel):
    selected_title: str = Field(min_length=1, max_length=120)


class TitleRegenerateRequest(BaseModel):
    feedback: str = Field(default="", max_length=500)


class ContentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    body: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    label: str = Field(default="manual_save", max_length=80)
    base_updated_at: datetime | None = None
    client_mutation_id: str | None = Field(default=None, min_length=8, max_length=100)


class AiEditRequest(BaseModel):
    selection: str = Field(min_length=1, max_length=8000)
    instruction: str = Field(default="", max_length=1000)
    client_mutation_id: str | None = Field(default=None, min_length=8, max_length=100)


class VersionRestore(BaseModel):
    version_id: str


class BudgetUpdate(BaseModel):
    limit_cny: float = Field(ge=0.000001, le=10000)


class ModelRouteUpdate(BaseModel):
    provider: str = Field(pattern="^(deepseek|claude|openai|gemini)$")
    model: str = Field(min_length=1, max_length=120)
    params: dict[str, Any] = Field(default_factory=dict)


AiOperation = Literal["polish", "rewrite", "rewrite_chapter", "continue", "expand", "condense", "deai"]


class ContentMetaRegistry(BaseModel):
    """FR-C1-03: Content type meta schema registry."""
    type: str
    required_fields: list[str] = []
    optional_fields: list[str] = []


CONTENT_TYPE_REGISTRY: dict[str, ContentMetaRegistry] = {
    "novel": ContentMetaRegistry(type="novel", required_fields=["idea","genre","style"], optional_fields=["target_words","synopsis","selected_title"]),
    "chapter": ContentMetaRegistry(type="chapter", required_fields=["seq"], optional_fields=["needs_rewrite","quality_score"]),
    "volume": ContentMetaRegistry(type="volume", required_fields=["volume_number"], optional_fields=["summary"]),
    "short_story": ContentMetaRegistry(type="short_story", required_fields=["idea","template"], optional_fields=["genre","style","max_words","short_score"]),
    "wechat_article": ContentMetaRegistry(type="wechat_article", required_fields=["platform"], optional_fields=["tags","summary","cta","cover_text"]),
    "toutiao_article": ContentMetaRegistry(type="toutiao_article", required_fields=["platform"], optional_fields=["seo_title","keywords","summary"]),
    "xhs_note": ContentMetaRegistry(type="xhs_note", required_fields=["platform"], optional_fields=["tags","cover_text","cta"]),
    "zhihu_answer": ContentMetaRegistry(type="zhihu_answer", required_fields=["platform"], optional_fields=["question","tags"]),
    "xiaohongshu_video": ContentMetaRegistry(type="xiaohongshu_video", required_fields=["platform"], optional_fields=["hook_3s","scenes","cta"]),
    "douyin_video": ContentMetaRegistry(type="douyin_video", required_fields=["platform"], optional_fields=["hook_3s","scenes","cta"]),
    "bilibili_video": ContentMetaRegistry(type="bilibili_video", required_fields=["platform"], optional_fields=["hook_3s","scenes","cta"]),
    "medium_article": ContentMetaRegistry(type="medium_article", required_fields=["platform"], optional_fields=["seo_title","summary","tags"]),
}


def validate_content_meta(content_type: str, meta: dict) -> dict:
    """Validate meta against content type registry. Returns {valid: bool, missing: [...], extra: [...]}."""
    registry = CONTENT_TYPE_REGISTRY.get(content_type)
    if not registry:
        return {"valid": True, "warning": f"unregistered type: {content_type}"}
    missing = [f for f in registry.required_fields if f not in meta or not meta[f]]
    return {"valid": len(missing) == 0, "missing": missing, "type": content_type}
