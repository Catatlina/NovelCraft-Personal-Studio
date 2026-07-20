from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from contextvars import ContextVar
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config import settings
from .core.circuit_breaker import circuit_breaker, record_failure, record_success
from .core.alerts import alert_budget, alert_provider_error
from .db import connect, decode, encode, new_id, row_to_dict
from .core.billing import get_active_subscription, monthly_window
from .prompt_registry import OUTPUT_CONTRACTS, render_prompt

# Context variable for per-request API key (set by middleware from X-Api-Key header)
_request_api_key: ContextVar[str | None] = ContextVar("request_api_key", default=None)
_request_api_base_url: ContextVar[str | None] = ContextVar("request_api_base_url", default=None)
_request_model: ContextVar[str | None] = ContextVar("request_model", default=None)
_request_user_id: ContextVar[str | None] = ContextVar("request_user_id", default=None)


# Default model when no route exists. Must be a model that actually exists on
# the DeepSeek API — a fictional name here fails every unrouted task at call time.
MODEL = "deepseek-v4-pro"
PROVIDER = "deepseek"

LONG_FORM_TASKS = {
    "gen_chapter1",
    "gen_next_chapter",
    "write_chapter_draft",
    "write_polish",
    "final_humanize",
    "editor_continue",
    "editor_rewrite",
    "editor_expand",
    "style_imitation",
}


class BudgetExceeded(RuntimeError):
    """Raised when a project budget would be exceeded by an AI call."""


class ProviderError(RuntimeError):
    """Raised when a configured provider cannot return a usable JSON result."""


class OutputValidationError(ProviderError):
    """Raised when a provider response is JSON but violates the task contract."""


class _StrictOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _SynopsisOutput(_StrictOutput):
    synopsis: str = Field(min_length=20)
    selling_points: list[str] = Field(min_length=2)


class _WorldviewBody(_StrictOutput):
    name: str = Field(min_length=2)
    rules: list[str] = Field(min_length=1)


class _WorldviewOutput(_StrictOutput):
    worldview: _WorldviewBody


class _CharacterBody(_StrictOutput):
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    arc: str = Field(min_length=5)


class _CharactersOutput(_StrictOutput):
    characters: list[_CharacterBody] = Field(min_length=2, max_length=8)


class _OutlineOutput(_StrictOutput):
    outline: list[str] = Field(min_length=3)


class _ChapterBody(_StrictOutput):
    title: str = Field(min_length=2)
    body: list[str] = Field(min_length=2)


class _ChapterOutput(_StrictOutput):
    chapter: _ChapterBody


class _ReviewDimensions(_StrictOutput):
    prose: float = Field(ge=0, le=100)
    plot: float = Field(ge=0, le=100)
    character_ooc: float = Field(ge=0, le=100)
    world_conflict: float = Field(ge=0, le=100)
    logic_consistency: float = Field(ge=0, le=100)
    pace: float = Field(ge=0, le=100)
    foreshadowing: float = Field(ge=0, le=100)


class _ReviewOutput(_StrictOutput):
    score: float = Field(ge=0, le=100)
    dimensions: _ReviewDimensions
    issues: list[str]


class _OocOutput(_StrictOutput):
    ooc_count: int = Field(ge=0)
    violations: list[dict[str, Any]]


class _ConsistencyOutput(_StrictOutput):
    contradictions: list[dict[str, Any]]


class _RhythmOutput(_StrictOutput):
    pacing_score: float = Field(ge=0, le=100)
    sections: list[dict[str, Any]]


# ── V2 four-stage bootstrap output models ──────────────────────────────────
# Real models are non-deterministic and often add extra fields; per the
# 2026-07-13 audit remediation these tolerate extras (ignore) while still
# requiring the fields downstream nodes consume.
class _LenientOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _PlanIdeaOutput(_LenientOutput):
    idea_expanded: str = Field(min_length=20)
    core_hook: str = Field(min_length=5)
    target_audience: str = Field(min_length=2)
    title_candidates: list[str] = Field(min_length=3, max_length=10)
    creative_bible: str = Field(min_length=300)
    source_facts: list[str] = Field(min_length=3, max_length=30)
    design_additions: list[str] = Field(default_factory=list, max_length=20)
    forbidden_changes: list[str] = Field(min_length=3, max_length=20)
    downstream_deliverables: list[str] = Field(min_length=1, max_length=20)


class _PlanFidelityAuditOutput(_LenientOutput):
    passed: bool
    score: float = Field(ge=0, le=100)
    matched_requirements: list[str] = Field(min_length=3)
    contradictions: list[str] = Field(default_factory=list)
    omissions: list[str] = Field(default_factory=list)


class _RegenerateTitlesOutput(_LenientOutput):
    title_candidates: list[str] = Field(min_length=3, max_length=10)


class _PlanMarketFitOutput(_LenientOutput):
    market_score: float = Field(ge=0, le=100)
    competitive_landscape: str = Field(min_length=5)
    market_gap: str = Field(min_length=5)


class _PlanStoryPatternOutput(_LenientOutput):
    story_model: str = Field(min_length=2)
    act_structure: list[str] = Field(min_length=1)
    turning_points: list[Any]


class _PlanCoreGameplayOutput(_LenientOutput):
    power_system: str = Field(min_length=5)
    progression_path: str = Field(min_length=5)
    pleasure_points: list[str] = Field(min_length=2)


class _LenientWorldviewBody(_LenientOutput):
    name: str = Field(min_length=2)
    rules: list[str] = Field(min_length=3)


class _PlanWorldArchitectureOutput(_LenientOutput):
    worldview: _LenientWorldviewBody


class _LenientCharacterBody(_LenientOutput):
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    arc: str = Field(min_length=2)


class _PlanCharacterSystemOutput(_LenientOutput):
    characters: list[_LenientCharacterBody] = Field(min_length=3, max_length=10)


class _PlanConflictMapOutput(_LenientOutput):
    conflicts: list[dict[str, Any]] = Field(min_length=1)


class _BlueprintVolumePlanOutput(_LenientOutput):
    volumes: list[dict[str, Any]] = Field(min_length=1)


class _BlueprintChapterOutlineOutput(_LenientOutput):
    chapter_outlines: list[dict[str, Any]] = Field(min_length=3)


class _BlueprintSceneBeatOutput(_LenientOutput):
    scene_beats: list[dict[str, Any]] = Field(min_length=3)


class _LenientChapterBody(_LenientOutput):
    title: str = Field(min_length=2)
    body: list[str] = Field(min_length=4)


class _WriteChapterDraftOutput(_LenientOutput):
    chapter: _LenientChapterBody


class _WriteSelfReviewOutput(_LenientOutput):
    self_score: float = Field(ge=0, le=100)
    strengths: list[str]
    weaknesses: list[str]


class _LenientPolishedBody(_LenientOutput):
    body: list[str] = Field(min_length=4)


class _WritePolishOutput(_LenientOutput):
    polished: _LenientPolishedBody
    changes_summary: str


class _WriteLengthCheckOutput(_LenientOutput):
    actual_chars: int = Field(ge=0)
    is_acceptable: bool
    advice: str = ""


class _WriteFactReconcileOutput(_LenientOutput):
    reconciliation: dict[str, Any]


class _ConsistencyDimension(_LenientOutput):
    status: str = Field(pattern=r"^(pass|warning|fail)$")
    issues: list[Any] = Field(default_factory=list)


class _FinalConsistencyDimensions(_LenientOutput):
    source_fidelity: _ConsistencyDimension
    characters: _ConsistencyDimension
    locations: _ConsistencyDimension
    timeline: _ConsistencyDimension
    objects: _ConsistencyDimension
    settings: _ConsistencyDimension
    foreshadowing: _ConsistencyDimension


class _FinalConsistencyCheckOutput(_LenientOutput):
    checks: _FinalConsistencyDimensions
    overall_status: str = Field(pattern=r"^(pass|warning|fail)$")
    warning_count: int = Field(ge=0)


class _ContinuityAuditBody(_LenientOutput):
    status: str = Field(pattern=r"^(continuous|warning|broken)$")
    gaps: list[Any] = Field(default_factory=list)
    narrative_flow: str = Field(min_length=2)


class _FinalContinuityAuditOutput(_LenientOutput):
    continuity: _ContinuityAuditBody


class _FinalHumanizeOutput(_LenientOutput):
    humanized_text: str = Field(min_length=50)
    changes: list[str]


class _BookAnalysisOutput(_LenientOutput):
    title: str = Field(min_length=1)
    total_paragraphs: int = Field(ge=0)
    opening_hook: str = ""
    detected_tropes: list[str] = Field(default_factory=list)
    rhythm: str = Field(min_length=1)
    avg_paragraph_length: int = Field(ge=0)
    structure_cards: dict[str, Any] = Field(default_factory=dict)
    style_profile: dict[str, Any] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class _HotspotContentOutput(_LenientOutput):
    title: str = Field(min_length=1)
    body: list[str] = Field(min_length=1)
    meta: dict[str, Any] = Field(default_factory=dict)


class _DailyBriefOutput(_LenientOutput):
    wechat_draft: str = Field(min_length=1)
    toutiao_draft: str = Field(min_length=1)
    xhs_draft: str = Field(min_length=1)


class _TitleVariantsOutput(_LenientOutput):
    titles: list[str] = Field(min_length=1, max_length=20)


class _VideoScriptOutput(_LenientOutput):
    title: str = Field(min_length=1)
    scenes: list[dict[str, Any]] = Field(min_length=1)
    narration_style: str = ""
    cover_text: str = ""


class _MaterialSuggestionsOutput(_LenientOutput):
    cover_image_prompt: str = ""
    suggested_charts: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    recommended_tags: list[str] = Field(default_factory=list)


class _TopicSuggestionItem(_LenientOutput):
    suggestion: str = Field(min_length=2)
    rationale: str = ""
    based_on: list[str] = Field(default_factory=list)


class _PerformanceFeedbackOutput(_LenientOutput):
    topic_suggestions: list[_TopicSuggestionItem] = Field(min_length=1)
    writing_advice: list[str] = Field(default_factory=list)


class _TranslateSegmentOutput(_LenientOutput):
    translated: str = Field(min_length=1)


class _CulturalLocalizeOutput(_LenientOutput):
    localized: str = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)


class _LocalizeNamesOutput(_LenientOutput):
    name_map: dict[str, str] = Field(default_factory=dict)


class _TextOutput(_StrictOutput):
    """Editor operations must never turn an empty provider payload into success."""

    text: str = Field(min_length=1)


class _DeaiLayerOutput(_LenientOutput):
    """De-AI pipeline layers: text + optional change log."""
    text: str = Field(min_length=1)
    changes: list[str] = Field(default_factory=list)


class _DeaiScoreOutput(_LenientOutput):
    """De-AI scoring result."""
    score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)


class _StyleImitationOutput(_LenientOutput):
    title: str = Field(min_length=2)
    style_profile: dict[str, Any]
    text: str = Field(min_length=800)


BOOTSTRAP_OUTPUT_MODELS: dict[str, type[BaseModel]] = {
    "gen_synopsis": _SynopsisOutput,
    "gen_worldview": _WorldviewOutput,
    "gen_characters": _CharactersOutput,
    "gen_outline": _OutlineOutput,
    "gen_chapter1": _ChapterOutput,
    "gen_next_chapter": _ChapterOutput,
    "review_7dim": _ReviewOutput,
    "review_ooc": _OocOutput,
    "review_consistency": _ConsistencyOutput,
    "review_rhythm": _RhythmOutput,
    # V2 four-stage bootstrap (18 agent nodes)
    "plan_idea": _PlanIdeaOutput,
    "audit_plan_fidelity": _PlanFidelityAuditOutput,
    "regenerate_titles": _RegenerateTitlesOutput,
    "plan_market_fit": _PlanMarketFitOutput,
    "plan_story_pattern": _PlanStoryPatternOutput,
    "plan_core_gameplay": _PlanCoreGameplayOutput,
    "plan_world_architecture": _PlanWorldArchitectureOutput,
    "plan_character_system": _PlanCharacterSystemOutput,
    "plan_conflict_map": _PlanConflictMapOutput,
    "blueprint_volume_plan": _BlueprintVolumePlanOutput,
    "blueprint_chapter_outline": _BlueprintChapterOutlineOutput,
    "blueprint_scene_beat": _BlueprintSceneBeatOutput,
    "write_chapter_draft": _WriteChapterDraftOutput,
    "write_self_review": _WriteSelfReviewOutput,
    "write_polish": _WritePolishOutput,
    "write_length_check": _WriteLengthCheckOutput,
    "write_fact_reconcile": _WriteFactReconcileOutput,
    "final_consistency_check": _FinalConsistencyCheckOutput,
    "final_continuity_audit": _FinalContinuityAuditOutput,
    "final_humanize": _FinalHumanizeOutput,
    "book_analysis": _BookAnalysisOutput,
    "gen_daily_brief": _HotspotContentOutput,
    "hm_daily_brief": _DailyBriefOutput,
    "hm_title_variants": _TitleVariantsOutput,
    "gen_video_script": _VideoScriptOutput,
    "hm_material_suggestions": _MaterialSuggestionsOutput,
    "performance_feedback": _PerformanceFeedbackOutput,
    "translate_segment": _TranslateSegmentOutput,
    "cultural_localize": _CulturalLocalizeOutput,
    "localize_names": _LocalizeNamesOutput,
    "editor_polish": _TextOutput,
    "editor_rewrite": _TextOutput,
    "editor_continue": _TextOutput,
    "editor_expand": _TextOutput,
    "editor_condense": _TextOutput,
    "editor_deai": _TextOutput,
    # ── De-AI 7-layer pipeline ──
    "deai_detect": _DeaiLayerOutput,
    "deai_colloquialize": _DeaiLayerOutput,
    "deai_rhythm": _DeaiLayerOutput,
    "deai_character": _DeaiLayerOutput,
    "deai_context": _DeaiLayerOutput,
    "deai_deduplicate": _DeaiLayerOutput,
    "deai_polish": _DeaiLayerOutput,
    "deai_score": _DeaiScoreOutput,
    "style_imitation": _StyleImitationOutput,
}


def validate_task_output(task_type: str, output: Any) -> dict[str, Any]:
    """Reject malformed creative output before it can be persisted as success."""
    if not isinstance(output, dict):
        raise OutputValidationError(f"provider returned non-object output for {task_type}")
    model = BOOTSTRAP_OUTPUT_MODELS.get(task_type)
    if not model:
        return output
    metadata = output.get("_meta")
    payload = {key: value for key, value in output.items() if key != "_meta"}
    try:
        validated = model.model_validate(payload).model_dump()
        if task_type.startswith("editor_") or task_type == "style_imitation":
            if not str(validated.get("text") or "").strip():
                raise OutputValidationError(f"provider returned empty text for {task_type}")
        if metadata is not None:
            validated["_meta"] = metadata
        return validated
    except ValidationError as exc:
        raise OutputValidationError(f"provider output schema mismatch for {task_type}: {exc}") from exc


def _complete_impl(
    *,
    run_id: str | None,
    node_key: str | None,
    project_id: str,
    user_id: str | None = None,
    task_type: str,
    prompt_name: str,
    variables: dict[str, Any],
    client_mutation_id: str | None = None,
) -> dict[str, Any]:
    if client_mutation_id:
        existing_db = connect()
        existing = existing_db.execute(
            "SELECT output FROM ai_calls WHERE project_id = %s AND client_mutation_id = %s AND status = 'succeeded'",
            (project_id, client_mutation_id),
        ).fetchone()
        existing_db.close()
        if existing:
            return decode(existing["output"], {})
    start = time.perf_counter()
    prompt_text, provider, model, params = _load_prompt_and_route(prompt_name, task_type, variables)
    estimated_cost = _estimate_cost(variables, {"prompt": prompt_text})
    _assert_budget(user_id, project_id, "bootstrap", estimated_cost)

    prompt_tokens, completion_tokens = 0, 0  # default
    provider_name = model_name = ""
    output: dict[str, Any] = {}

    # Route to a real provider, retrying schema-contract violations. Real models
    # are non-deterministic, so a malformed structured payload is retried
    # (FR-C3-07, <=2 retries) before it is surfaced as a failure.
    MAX_SCHEMA_ATTEMPTS = 3
    for schema_attempt in range(MAX_SCHEMA_ATTEMPTS):
        prompt_tokens, completion_tokens = 0, 0
        if provider == "deepseek":
            if not circuit_breaker("deepseek"):
                raise ProviderError("deepseek circuit breaker open — too many failures")
            try:
                model_ = _request_model.get() or model or settings.deepseek_model
                output, prompt_tokens, completion_tokens = _deepseek_complete(task_type, prompt_text, model_, params)
                record_success("deepseek")
                provider_name = "deepseek"
                model_name = model_
            except OutputValidationError:
                # Non-JSON and other structured-response violations are model
                # sample failures, not transport outages. Retry with a fresh
                # real completion under the same contract.
                if schema_attempt >= MAX_SCHEMA_ATTEMPTS - 1:
                    record_failure("deepseek")
                    raise
                continue
            except ProviderError:
                record_failure("deepseek")
                raise
        elif provider in ("claude", "openai", "gemini"):
            try:
                output, prompt_tokens, completion_tokens, provider_name, model_name = _call_real_provider(
                    provider, model or "", prompt_text, params
                )
            except Exception as exc:
                raise ProviderError(f"provider {provider} failed for {task_type}: {exc}") from exc
        else:
            raise ProviderError(f"unsupported real provider: {provider}")

        try:
            output = validate_task_output(task_type, output)
            break
        except OutputValidationError:
            # A real model may succeed on a fresh sample. Exhausted retries
            # re-raise for the caller.
            if schema_attempt >= MAX_SCHEMA_ATTEMPTS - 1:
                raise

    latency_ms = int((time.perf_counter() - start) * 1000)
    cost_cny = _calculate_cost(provider_name, model_name, prompt_tokens, completion_tokens)

    conn = connect()
    try:
        # ON CONFLICT lets a successful retry overwrite the failed-attempt ledger
        # row that shares this mutation id, instead of colliding on the unique
        # index and permanently breaking failed-state retry recovery.
        conn.execute(
            """
            INSERT INTO ai_calls (
                id, run_id, node_key, provider, model, prompt_name, task_type,
                input, output, prompt_tokens, completion_tokens, cost_cny, latency_ms, status,
                client_mutation_id, project_id, user_id
            ) VALUES (%s, %s, %s ,%s, %s ,%s, %s ,%s, %s ,%s, %s ,%s, %s, %s, %s, %s, %s)
            ON CONFLICT (project_id, client_mutation_id) WHERE client_mutation_id IS NOT NULL
            DO UPDATE SET provider = EXCLUDED.provider, model = EXCLUDED.model,
                prompt_name = EXCLUDED.prompt_name, task_type = EXCLUDED.task_type,
                input = EXCLUDED.input, output = EXCLUDED.output,
                prompt_tokens = EXCLUDED.prompt_tokens, completion_tokens = EXCLUDED.completion_tokens,
                cost_cny = EXCLUDED.cost_cny, latency_ms = EXCLUDED.latency_ms,
                status = 'succeeded', error = NULL
            """,
            (
                new_id("call"),
                run_id,
                node_key,
                provider_name,
                model_name,
                prompt_name,
                task_type,
                encode({"variables": variables, "prompt": prompt_text}),
                encode(output),
                prompt_tokens,
                completion_tokens,
                cost_cny,
                latency_ms,
                "succeeded",
                client_mutation_id,
                project_id,
                user_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return output


def complete(
    *,
    run_id: str | None,
    node_key: str | None,
    project_id: str,
    task_type: str,
    prompt_name: str,
    variables: dict[str, Any],
    user_id: str | None = None,
    client_mutation_id: str | None = None,
) -> dict[str, Any]:
    """Execute an AI call and keep both successful and failed attempts in the ledger."""
    user_id = user_id or _request_user_id.get()
    started = time.perf_counter()
    try:
        return _complete_impl(
            run_id=run_id, node_key=node_key, project_id=project_id,
            task_type=task_type, prompt_name=prompt_name, variables=variables,
            user_id=user_id, client_mutation_id=client_mutation_id,
        )
    except Exception as exc:
        _record_failed_call(
            run_id=run_id, node_key=node_key, project_id=project_id, task_type=task_type,
            prompt_name=prompt_name, variables=variables, user_id=user_id,
            client_mutation_id=client_mutation_id,
            started=started, error=exc,
        )
        raise


def _record_failed_call(*, run_id: str | None, node_key: str | None, project_id: str,
                        task_type: str, prompt_name: str, variables: dict[str, Any],
                        user_id: str | None = None, client_mutation_id: str | None,
                        started: float, error: Exception) -> None:
    conn = None
    try:
        route = _load_route(task_type) or {}
        provider = str(route.get("provider") or settings.ai_provider or "unknown")
        model = str(route.get("model") or settings.deepseek_model or "unknown")
        conn = connect()
        # DO NOTHING keeps the first attempt's row and never clobbers a prior
        # succeeded row; a later successful retry upgrades the row via complete()'s
        # own ON CONFLICT DO UPDATE.
        conn.execute(
            """INSERT INTO ai_calls (
                   id, run_id, node_key, provider, model, prompt_name, task_type,
                   input, output, prompt_tokens, completion_tokens, cost_cny,
                   latency_ms, status, error, client_mutation_id, project_id, user_id
               ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,0,0,%s,'failed',%s,%s,%s,%s)
               ON CONFLICT (project_id, client_mutation_id) WHERE client_mutation_id IS NOT NULL
               DO NOTHING""",
            (new_id("call"), run_id, node_key, provider, model, prompt_name, task_type,
             encode({"variables": variables}), encode({}),
             int((time.perf_counter() - started) * 1000), str(error)[:2000],
             client_mutation_id, project_id, user_id),
        )
        conn.commit()
    except Exception:
        pass  # Preserve the original provider/budget error if the ledger is unavailable.
    finally:
        if conn is not None:
            conn.close()


def _call_real_provider(provider: str, model: str, prompt_text: str, params: dict) -> tuple:
    """Call one configured real provider. No mock or fallback generation."""
    from .ai.providers import PROVIDERS

    fn = PROVIDERS.get(provider)
    if not fn:
        raise ProviderError(f"unknown provider: {provider}")
    output, pt, ct = fn(prompt_text, model, params)
    return output, pt, ct, provider, model


def _load_route(task_type: str) -> dict | None:
    conn = connect()
    route = row_to_dict(
        conn.execute(
            "SELECT * FROM model_routes WHERE task_type = %s AND is_active = TRUE",
            (task_type,),
        ).fetchone()
    )
    conn.close()
    if route:
        route["params"] = decode(route.get("params"), {})
        route["fallback_json"] = decode(route.get("fallback_json"), [])
    return route


def _load_prompt_and_route(
    prompt_name: str,
    task_type: str,
    variables: dict[str, Any],
    include_contract: bool = True,
) -> tuple[str, str, str, dict[str, Any]]:
    route = _load_route(task_type)
    provider = (route or {}).get("provider", "deepseek")
    model = (route or {}).get("model", MODEL)
    params = (route or {}).get("params", {})
    conn = connect()
    prompt = row_to_dict(
        conn.execute(
            """
            SELECT * FROM prompts
            WHERE name = %s AND is_active = TRUE
            ORDER BY string_to_array(version, '.')::int[] DESC, created_at DESC
            LIMIT 1
            """,
            (prompt_name,),
        ).fetchone()
    )
    conn.close()
    template = prompt["template"] if prompt else "请执行任务 $task_type，并输出 JSON。"
    enriched_variables = {"task_type": task_type, **variables}
    prompt_text = render_prompt(template, enriched_variables)
    contract = OUTPUT_CONTRACTS.get(task_type) or OUTPUT_CONTRACTS.get(task_type.replace("editor_", "editor_"))
    if contract and include_contract:
        prompt_text += "\n\n只输出合法 JSON（不得包含 JSON 以外的任何文本，不得增删字段），结构必须匹配：\n" + contract
    return prompt_text, provider, model, params


def _assert_budget(user_id: str | None, project_id: str, scope: str, estimated_cost: float) -> None:
    """Enforce the user's plan-derived monthly cost budget.

    The limit is sourced from the user's active plan (plans.monthly_budget_cny)
    instead of the previously hardcoded 2.0 CNY per-project 'bootstrap' budget.
    When no user context is available (e.g. background workers), fall back to the
    configured default and aggregate spend by project_id. Spend is the sum of
    ai_calls.cost_cny for the current natural month.
    """
    limit = float(settings.default_monthly_budget_cny)
    if user_id:
        try:
            sub = get_active_subscription(user_id)
            limit = float(sub.get("monthly_budget_cny") or settings.default_monthly_budget_cny)
        except Exception:
            limit = float(settings.default_monthly_budget_cny)
    start, end = monthly_window()
    conn = connect()
    try:
        agg = row_to_dict(conn.execute(
            """
            SELECT COALESCE(SUM(cost_cny), 0)::float AS spent
            FROM ai_calls
            WHERE created_at >= %s AND created_at < %s
              AND (user_id = %s OR (user_id IS NULL AND project_id = %s))
            """,
            (start, end, user_id, project_id),
        ).fetchone())
    finally:
        conn.close()
    spent = float(agg.get("spent") or 0)
    if spent + estimated_cost > limit:
        alert_budget(project_id, scope, spent, limit)
        raise BudgetExceeded(
            f"{scope} monthly budget exceeded: {spent:.4f}/{limit:.2f} CNY"
        )


def _estimate_cost(variables: dict[str, Any], output_hint: dict[str, Any]) -> float:
    prompt_tokens = max(80, len(encode(variables)) // 3)
    completion_tokens = max(120, len(encode(output_hint)) // 3)
    return round((prompt_tokens + completion_tokens) * 0.000002, 4)


def _calculate_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Provider-aware CNY pricing; deployments may override the full table as JSON."""
    default_rates = {
        "deepseek": {"input": 2.0, "output": 3.0},
        "openai": {"input": 18.0, "output": 72.0},
        "anthropic": {"input": 21.0, "output": 105.0},
        "claude": {"input": 21.0, "output": 105.0},
        "gemini": {"input": 0.75, "output": 3.0},
    }
    try:
        overrides = json.loads(os.getenv("AI_PRICE_CNY_PER_MILLION", "{}"))
        if isinstance(overrides, dict):
            default_rates.update(overrides)
    except json.JSONDecodeError:
        pass
    rate = default_rates.get(provider, default_rates.get(model, {"input": 0.0, "output": 0.0}))
    return round(
        (prompt_tokens * float(rate.get("input", 0)) + completion_tokens * float(rate.get("output", 0))) / 1_000_000,
        6,
    )


def _deepseek_complete(task_type: str, prompt: str, model: str, params: dict[str, Any]) -> dict[str, Any]:
    api_key = _request_api_key.get() or settings.deepseek_api_key
    if not api_key:
        raise ProviderError("DEEPSEEK_API_KEY is not configured")
    max_tokens = params.get("max_tokens")
    if max_tokens is None and task_type in LONG_FORM_TASKS:
        # Long-form fiction nodes must be able to return 3000+ Chinese
        # characters inside a JSON payload. Relying on provider defaults makes
        # the prompt say "write long" while the API may still truncate output.
        max_tokens = 8192
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是 NovelCraft 的职业网文创作 Agent。只输出合法 JSON；正文必须是可直接连载发布的小说叙事，不写说明文、计划书或创作建议。"},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": params.get("temperature", 0.7),
    }
    if max_tokens is not None:
        try:
            body["max_tokens"] = max(1024, min(int(max_tokens), 8192))
        except (TypeError, ValueError):
            body["max_tokens"] = 8192
    from .core.url_security import validate_ai_base_url
    base_url = validate_ai_base_url(_request_api_base_url.get() or settings.deepseek_base_url)
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.request_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:
        alert_provider_error(task_type, str(exc))
        raise ProviderError(f"deepseek request failed: {exc}") from exc
    msg = payload["choices"][0]["message"]
    content = msg.get("content") or msg.get("reasoning_content", "")
    usage = payload.get("usage", {})
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise OutputValidationError(f"deepseek returned non-json for {task_type}") from exc
    return parsed, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


# ===== Streaming (pure-text tasks only) =====
# Structured tasks (gen_chapter1 etc.) must be validated as a whole JSON object
# before persisting, so streaming is limited to plain-text editor operations.

TEXT_STREAM_TASKS = {
    "editor_polish", "editor_rewrite", "editor_continue",
    "editor_expand", "editor_condense", "editor_deai",
}


def _deepseek_stream(prompt: str, model: str, params: dict[str, Any], usage_out: dict[str, int]):
    """Yield content deltas from an OpenAI-compatible streaming endpoint."""
    api_key = _request_api_key.get() or settings.deepseek_api_key
    if not api_key:
        raise ProviderError("DEEPSEEK_API_KEY is not configured")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是 NovelCraft 的创作助手。直接输出正文文本，不要任何解释、标题或格式包裹。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": params.get("temperature", 0.7),
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    from .core.url_security import validate_ai_base_url
    base_url = validate_ai_base_url(_request_api_base_url.get() or settings.deepseek_base_url)
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                 "Accept": "text/event-stream"},
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.request_timeout_seconds) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if payload.get("usage"):
                    usage_out.update(payload["usage"])
                choices = payload.get("choices") or []
                if choices:
                    delta = (choices[0].get("delta") or {}).get("content")
                    if delta:
                        yield delta
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError(f"deepseek stream failed: {exc}") from exc


def _complete_stream_impl(
    *,
    project_id: str,
    user_id: str | None = None,
    task_type: str,
    prompt_name: str,
    variables: dict[str, Any],
    client_mutation_id: str | None = None,
):
    """Stream text deltas for a pure-text task, then write the ai_calls ledger.

    Same semantics as complete(): budget assert up front, mutation replay from
    the ledger (yielded as one delta), circuit breaker + failure recording, and
    a succeeded ai_calls row with usage once the stream finishes."""
    if task_type not in TEXT_STREAM_TASKS:
        raise ProviderError(f"streaming is not supported for {task_type}")
    if client_mutation_id:
        conn = connect()
        existing = conn.execute(
            "SELECT output FROM ai_calls WHERE project_id = %s AND client_mutation_id = %s AND status = 'succeeded'",
            (project_id, client_mutation_id),
        ).fetchone()
        conn.close()
        if existing:
            yield decode(existing["output"], {}).get("text", "")
            return

    start = time.perf_counter()
    prompt_text, provider, model, params = _load_prompt_and_route(
        prompt_name, task_type, variables, include_contract=False
    )
    _assert_budget(user_id, project_id, "bootstrap", _estimate_cost(variables, {"prompt": prompt_text}))

    chunks: list[str] = []
    usage: dict[str, int] = {}
    if provider == "deepseek":
        if not circuit_breaker("deepseek"):
            raise ProviderError("deepseek circuit breaker open — too many failures")
        model_name = _request_model.get() or model or settings.deepseek_model
        provider_name = "deepseek"
        try:
            for delta in _deepseek_stream(prompt_text, model_name, params, usage):
                chunks.append(delta)
                yield delta
            record_success("deepseek")
        except ProviderError:
            record_failure("deepseek")
            raise
    else:
        # Other providers use different auth/protocol implementations in the
        # non-streaming gateway. Until matching stream adapters exist, fail
        # explicitly.
        raise ProviderError(f"streaming is not supported for provider: {provider}")

    full_text = "".join(chunks)
    if not full_text.strip():
        raise OutputValidationError(f"provider returned empty streamed text for {task_type}")
    prompt_tokens = int(usage.get("prompt_tokens", 0)) or max(1, len(prompt_text) // 4)
    completion_tokens = int(usage.get("completion_tokens", 0)) or max(1, len(full_text) // 4)
    latency_ms = int((time.perf_counter() - start) * 1000)
    conn = connect()
    try:
        # Same replay-safety as complete(): a successful stream upgrades any prior
        # failed-attempt row sharing this mutation id instead of colliding.
        conn.execute(
            """INSERT INTO ai_calls (
                   id, run_id, node_key, provider, model, prompt_name, task_type,
                   input, output, prompt_tokens, completion_tokens, cost_cny, latency_ms, status,
                   client_mutation_id, project_id, user_id
               ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (project_id, client_mutation_id) WHERE client_mutation_id IS NOT NULL
               DO UPDATE SET provider = EXCLUDED.provider, model = EXCLUDED.model,
                   prompt_name = EXCLUDED.prompt_name, task_type = EXCLUDED.task_type,
                   input = EXCLUDED.input, output = EXCLUDED.output,
                   prompt_tokens = EXCLUDED.prompt_tokens, completion_tokens = EXCLUDED.completion_tokens,
                   cost_cny = EXCLUDED.cost_cny, latency_ms = EXCLUDED.latency_ms,
                   status = 'succeeded', error = NULL""",
            (new_id("call"), None, None, provider_name, model_name, prompt_name, task_type,
             encode({"variables": variables, "prompt": prompt_text, "stream": True}),
             encode({"text": full_text}),
             prompt_tokens, completion_tokens,
             _calculate_cost(provider_name, model_name, prompt_tokens, completion_tokens), latency_ms,
             "succeeded", client_mutation_id, project_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def complete_stream(
    *, project_id: str, task_type: str, prompt_name: str,
    variables: dict[str, Any], user_id: str | None = None,
    client_mutation_id: str | None = None,
):
    """Public streaming wrapper with the same failed-call ledger contract as complete()."""
    user_id = user_id or _request_user_id.get()
    started = time.perf_counter()
    try:
        yield from _complete_stream_impl(
            project_id=project_id, user_id=user_id, task_type=task_type, prompt_name=prompt_name,
            variables=variables, client_mutation_id=client_mutation_id,
        )
    except Exception as exc:
        _record_failed_call(
            run_id=None, node_key=None, project_id=project_id, task_type=task_type,
            prompt_name=prompt_name, variables={**variables, "stream": True},
            user_id=user_id, client_mutation_id=client_mutation_id, started=started, error=exc,
        )
        raise
