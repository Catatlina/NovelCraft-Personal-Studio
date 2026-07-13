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
from .prompt_registry import OUTPUT_CONTRACTS, render_prompt

# Context variable for per-request API key (set by middleware from X-Api-Key header)
_request_api_key: ContextVar[str | None] = ContextVar("request_api_key", default=None)
_request_api_base_url: ContextVar[str | None] = ContextVar("request_api_base_url", default=None)
_request_model: ContextVar[str | None] = ContextVar("request_model", default=None)


# Default model when no route exists. Must be a model that actually exists on
# the DeepSeek API — a fictional name here fails every unrouted task at call time.
MODEL = "deepseek-chat"
PROVIDER = "deepseek"


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
    title_candidates: list[str] = Field(min_length=3, max_length=8)


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


class _FinalConsistencyCheckOutput(_LenientOutput):
    checks: dict[str, Any]
    overall_status: str = Field(min_length=2)


class _FinalContinuityAuditOutput(_LenientOutput):
    continuity: dict[str, Any]


class _FinalHumanizeOutput(_LenientOutput):
    humanized_text: str = Field(min_length=50)
    changes: list[str]


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
    _assert_budget(project_id, "bootstrap", estimated_cost)

    prompt_tokens, completion_tokens = 0, 0  # default
    provider_name = model_name = ""
    output: dict[str, Any] = {}

    # Route to provider, retrying schema-contract violations. Real models are
    # non-deterministic, so a malformed structured payload is retried (FR-C3-07,
    # ≤2 retries) before it is surfaced as a failure. Mock output is always valid,
    # so it never loops.
    MAX_SCHEMA_ATTEMPTS = 3
    for schema_attempt in range(MAX_SCHEMA_ATTEMPTS):
        prompt_tokens, completion_tokens = 0, 0
        if provider == "mock":
            environment = os.getenv("NOVELCRAFT_ENV", "development").lower()
            allow_mock = (os.getenv("NOVELCRAFT_ALLOW_MOCK") or os.getenv("ALLOW_MOCK", "false")).lower() == "true"
            if environment not in {"test", "testing"} or not allow_mock:
                raise ProviderError("mock provider requires NOVELCRAFT_ENV=test and NOVELCRAFT_ALLOW_MOCK=true")
            output = _mock_output(task_type, variables)
            provider_name = "mock"
            model_name = "mock"
        elif provider == "deepseek":
            if not circuit_breaker("deepseek"):
                raise ProviderError("deepseek circuit breaker open — too many failures")
            try:
                model_ = _request_model.get() or model or settings.deepseek_model
                output, prompt_tokens, completion_tokens = _deepseek_complete(task_type, prompt_text, model_, params)
                record_success("deepseek")
                # Dynamic provider name based on model prefix
                provider_name = "openai" if model_.startswith("gpt") else ("anthropic" if model_.startswith("claude") else "deepseek")
                model_name = model_
            except ProviderError:
                record_failure("deepseek")
                # Try fallback chain
                route = _load_route(task_type)
                fallbacks = route.get("fallback_json", []) if route else []
                if isinstance(fallbacks, str):
                    fallbacks = json.loads(fallbacks)
                for fb in fallbacks:
                    try:
                        output, prompt_tokens, completion_tokens, provider_name, model_name = _try_fallback(fb, task_type, prompt_text, variables, params)
                        break
                    except Exception:
                        continue
                else:
                    raise ProviderError(f"deepseek failed and all fallbacks exhausted for {task_type}")
        elif provider in ("claude", "openai", "gemini"):
            try:
                output, prompt_tokens, completion_tokens, provider_name, model_name = _try_fallback(
                    {"provider": provider, "model": model or ""}, task_type, prompt_text, variables, params
                )
            except Exception:
                route = _load_route(task_type)
                fallbacks = route.get("fallback_json", []) if route else []
                for fb in fallbacks:
                    try:
                        output, prompt_tokens, completion_tokens, provider_name, model_name = _try_fallback(fb, task_type, prompt_text, variables, params)
                        break
                    except Exception:
                        continue
                else:
                    raise ProviderError(f"provider {provider} failed and all fallbacks exhausted for {task_type}")
        else:
            raise ProviderError(f"unsupported provider: {provider}")

        try:
            output = validate_task_output(task_type, output)
            break
        except OutputValidationError:
            # Deterministic providers (mock) can't self-correct; a real model may
            # succeed on a fresh sample. Exhausted retries re-raise for the caller.
            if provider_name == "mock" or schema_attempt >= MAX_SCHEMA_ATTEMPTS - 1:
                raise

    if provider_name == "mock":
        output["_meta"] = {"provider": "mock", "synthetic": True}

    latency_ms = int((time.perf_counter() - start) * 1000)
    cost_cny = _calculate_cost(provider_name, model_name, prompt_tokens, completion_tokens)

    conn = connect()
    try:
        # ON CONFLICT lets a successful retry overwrite the failed-attempt ledger
        # row that shares this mutation id, instead of colliding on the unique
        # index and permanently breaking pending_provider/resume recovery.
        conn.execute(
            """
            INSERT INTO ai_calls (
                id, run_id, node_key, provider, model, prompt_name, task_type,
                input, output, prompt_tokens, completion_tokens, cost_cny, latency_ms, status,
                client_mutation_id, project_id
            ) VALUES (%s, %s, %s ,%s, %s ,%s, %s ,%s, %s ,%s, %s ,%s, %s, %s, %s, %s)
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
            ),
        )
        conn.execute(
            """
            INSERT INTO budgets (id, project_id, scope, limit_cny, spent_cny)
            VALUES (%s, %s, 'bootstrap', 2.0, %s)
            ON CONFLICT(project_id, scope)
            DO UPDATE SET spent_cny = budgets.spent_cny + excluded.spent_cny, updated_at = CURRENT_TIMESTAMP
            """,
            (new_id("bdg"), project_id, cost_cny),
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
    client_mutation_id: str | None = None,
) -> dict[str, Any]:
    """Execute an AI call and keep both successful and failed attempts in the ledger."""
    started = time.perf_counter()
    try:
        return _complete_impl(
            run_id=run_id, node_key=node_key, project_id=project_id,
            task_type=task_type, prompt_name=prompt_name, variables=variables,
            client_mutation_id=client_mutation_id,
        )
    except Exception as exc:
        _record_failed_call(
            run_id=run_id, node_key=node_key, project_id=project_id, task_type=task_type,
            prompt_name=prompt_name, variables=variables, client_mutation_id=client_mutation_id,
            started=started, error=exc,
        )
        raise


def _record_failed_call(*, run_id: str | None, node_key: str | None, project_id: str,
                        task_type: str, prompt_name: str, variables: dict[str, Any],
                        client_mutation_id: str | None, started: float, error: Exception) -> None:
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
                   latency_ms, status, error, client_mutation_id, project_id
               ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,0,0,%s,'failed',%s,%s,%s)
               ON CONFLICT (project_id, client_mutation_id) WHERE client_mutation_id IS NOT NULL
               DO NOTHING""",
            (new_id("call"), run_id, node_key, provider, model, prompt_name, task_type,
             encode({"variables": variables}), encode({}),
             int((time.perf_counter() - started) * 1000), str(error)[:2000],
             client_mutation_id, project_id),
        )
        conn.commit()
    except Exception:
        pass  # Preserve the original provider/budget error if the ledger is unavailable.
    finally:
        if conn is not None:
            conn.close()


def _try_fallback(fb: dict, task_type: str, prompt_text: str, variables: dict, params: dict) -> tuple:
    """Try a fallback provider. Returns (output, prompt_tokens, completion_tokens, provider_name, model_name)."""
    fb_provider = fb.get("provider", "deepseek")
    fb_model = fb.get("model", "deepseek-chat")
    if fb_provider == "deepseek":
        output, pt, ct = _deepseek_complete(task_type, prompt_text, fb_model, params)
    elif fb_provider in ("claude", "openai", "gemini"):
        from .ai.providers import PROVIDERS
        fn = PROVIDERS.get(fb_provider)
        if fn:
            output, pt, ct = fn(prompt_text, fb_model, params)
        else:
            raise ProviderError(f"unknown provider: {fb_provider}")
    else:
        output = _mock_output(task_type, variables)
        pt = max(80, len(prompt_text) // 3)
        ct = max(120, len(encode(output)) // 3)
    return output, pt, ct, fb_provider, fb_model


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


def _assert_budget(project_id: str, scope: str, estimated_cost: float) -> None:
    conn = connect()
    budget = row_to_dict(
        conn.execute(
            "SELECT * FROM budgets WHERE project_id = %s AND scope = %s",
            (project_id, scope),
        ).fetchone()
    )
    conn.close()
    if budget and float(budget["spent_cny"]) + estimated_cost > float(budget["limit_cny"]):
        alert_budget(project_id, "bootstrap", float(budget["spent_cny"]), float(budget["limit_cny"]))
        raise BudgetExceeded(f"{scope} budget exceeded")


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
        "mock": {"input": 0.0, "output": 0.0},
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
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是 NovelCraft 的结构化创作 Agent。只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": params.get("temperature", 0.7),
    }
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
        raise ProviderError(f"deepseek returned non-json for {task_type}") from exc
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
    _assert_budget(project_id, "bootstrap", _estimate_cost(variables, {"prompt": prompt_text}))

    chunks: list[str] = []
    usage: dict[str, int] = {}
    if provider == "mock":
        environment = os.getenv("NOVELCRAFT_ENV", "development").lower()
        allow_mock = (os.getenv("NOVELCRAFT_ALLOW_MOCK") or os.getenv("ALLOW_MOCK", "false")).lower() == "true"
        if environment not in {"test", "testing"} or not allow_mock:
            raise ProviderError("mock provider requires NOVELCRAFT_ENV=test and NOVELCRAFT_ALLOW_MOCK=true")
        mock_text = str(_mock_output(task_type, variables).get("text", ""))
        midpoint = max(1, len(mock_text) // 2)
        for piece in (mock_text[:midpoint], mock_text[midpoint:]):
            if piece:
                chunks.append(piece)
                yield piece
        provider_name = model_name = "mock"
    elif provider == "deepseek":
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
        # explicitly so the client can safely fall back to complete().
        raise ProviderError(f"streaming is not supported for provider: {provider}")

    full_text = "".join(chunks)
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
                   client_mutation_id, project_id
               ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
             "succeeded", client_mutation_id, project_id),
        )
        conn.commit()
    finally:
        conn.close()


def complete_stream(
    *, project_id: str, task_type: str, prompt_name: str,
    variables: dict[str, Any], client_mutation_id: str | None = None,
):
    """Public streaming wrapper with the same failed-call ledger contract as complete()."""
    started = time.perf_counter()
    try:
        yield from _complete_stream_impl(
            project_id=project_id, task_type=task_type, prompt_name=prompt_name,
            variables=variables, client_mutation_id=client_mutation_id,
        )
    except Exception as exc:
        _record_failed_call(
            run_id=None, node_key=None, project_id=project_id, task_type=task_type,
            prompt_name=prompt_name, variables={**variables, "stream": True},
            client_mutation_id=client_mutation_id, started=started, error=exc,
        )
        raise


def _mock_output(task_type: str, variables: dict[str, Any]) -> dict[str, Any]:
    idea = variables.get("idea", "一个人在迷雾中寻找真相")
    genre = variables.get("genre", "幻想")
    style = variables.get("style", "克制、悬疑")
    title = variables.get("selected_title") or variables.get("title") or "雾灯纪元"

    if task_type == "gen_titles":
        return {
            "title_candidates": [
                f"《{_keyword(idea)}之门》",
                "《雾灯纪元》",
                "《第七封回信》",
            ]
        }
    if task_type == "gen_synopsis":
        return {
            "synopsis": f"{title}讲述一位普通创作者被卷入{genre}谜局后，必须用记忆、文字和选择重写命运的故事。",
            "selling_points": ["强钩子开局", "主角成长清晰", "世界观可持续扩展", "适合长篇连载"],
        }
    if task_type == "gen_worldview":
        return {
            "worldview": {
                "name": "回声城邦",
                "rules": [
                    "重要记忆会凝结成可交易的墨晶",
                    "每一次改写历史都会留下不可擦除的旁证",
                    "夜航者负责修补城市中的叙事裂缝",
                ],
            }
        }
    if task_type == "gen_characters":
        return {
            "characters": [
                {"name": "林序", "role": "主角", "arc": "从逃避表达走向主动书写"},
                {"name": "沈微澜", "role": "盟友", "arc": "在秩序与真相之间重新选择"},
                {"name": "闻烬", "role": "对手", "arc": "相信牺牲少数即可拯救多数"},
            ]
        }
    if task_type == "gen_outline":
        return {
            "outline": [
                "第一卷：主角发现自己的小说正在现实中逐字发生。",
                "第二卷：团队进入回声城邦，寻找第一枚墨晶。",
                "第三卷：真相揭开，主角必须决定是否保留被改写的人生。",
            ]
        }
    if task_type == "gen_chapter1":
        paragraphs = [
            f"{title}的第一章开始于一场不合时宜的停电。林序盯着屏幕上最后一行字，发现它并不是自己刚刚写下的。",
            "窗外的雨声像无数细小的指节敲在玻璃上。楼下便利店的灯牌忽明忽暗，而他文档里的城市名，正好也叫回声城邦。",
            "手机弹出一条陌生短信：不要删掉下一段。林序笑了一下，以为是谁的恶作剧。直到门外响起三下敲门声，节奏和他草稿里的描写完全一致。",
            "他打开门，门外没有人，只有一枚黑色墨晶躺在脚垫中央。墨晶内部像困着一盏灯，照亮了他从未告诉过任何人的一句话：如果故事能救人，我愿意先被故事审判。",
        ]
        return {"chapter": {"title": "第一章 墨晶来信", "body": paragraphs}}
    if task_type == "gen_next_chapter":
        paragraphs = [
            "夜色沉下来的时候，林序把墨晶放进外套内袋，沿着环河路往修档馆走。",
            "沈微澜在馆门口等他，手里捏着一页被雨水泡皱的档案，纸角的编号正在缓慢褪色。",
            "两人对视一眼，都没有说话。城市在他们身后轻轻震了一下，像一本被人翻动的书。",
        ]
        return {"chapter": {"title": "下一章 修档馆的震动", "body": paragraphs}}
    if task_type == "review_7dim":
        return {
            "score": 84,
            "dimensions": {
                "prose": 88, "plot": 82, "character_ooc": 80,
                "world_conflict": 86, "logic_consistency": 84,
                "pace": 80, "foreshadowing": 78,
            },
            "issues": [
                "第一章悬念成立，可在结尾补更明确的行动目标。",
                "主角职业和日常压力可以再落地一些。",
            ],
        }
    if task_type == "review_ooc":
        return {"ooc_count": 0, "violations": []}
    if task_type == "review_consistency":
        return {"contradictions": []}
    if task_type == "review_rhythm":
        return {"pacing_score": 82, "sections": []}
    if task_type.startswith("editor_"):
        selection = variables.get("selection", "")
        instruction = variables.get("instruction", "")
        if task_type == "editor_continue":
            text = selection + "\n\n他把墨晶握在掌心，忽然听见城市深处传来潮水般的翻页声。"
        elif task_type == "editor_rewrite":
            text = f"改写版：{selection.strip()}（更强调冲突与画面，{instruction or '保持原意'}。）"
        elif task_type == "editor_expand":
            text = f"{selection.strip()}\n\n（扩写）周围的一切都在诉说着不为人知的秘密。空气里弥漫着墨晶的微光，每一次呼吸都像在吸入远古的记忆。他感到自己的心跳与城市的脉搏渐渐同步。"
        elif task_type == "editor_condense":
            sentences = selection.strip().split("。")
            text = "。".join(sentences[:max(1, len(sentences)//2)]) + "。"
        elif task_type == "editor_deai":
            text = selection.strip().replace("值得注意的是", "").replace("综上所述", "").replace("首先", "").replace("其次", "").replace("最后", "")
        else:
            text = f"润色版：{selection.strip()}（语言更顺，节奏更稳。）"
        return {"text": text}
    # ── V2 four-stage bootstrap mocks (schema-conformant so the mock T2
    # pipeline exercises the same validation the real provider faces) ──
    if task_type == "plan_idea":
        return {
            "idea_expanded": f"基于灵感「{idea}」展开：一位普通创作者发现自己写下的{genre}故事正在现实中逐字发生，"
                             "他必须在故事完结前找出幕后执笔者，否则自己的人生将被彻底改写。",
            "core_hook": "你写的每一个字都在杀人，而你停不下笔。",
            "target_audience": "18-35 岁悬疑/脑洞向读者",
            "title_candidates": ["《墨晶来信》", "《回声城邦》", "《第七封回信》", "《执笔者》", "《雾灯纪元》"],
        }
    if task_type == "plan_market_fit":
        return {"market_score": 78.0,
                "competitive_landscape": "同类元叙事悬疑作品头部集中在无限流框架，普遍弱化现实锚点。",
                "market_gap": "现实系元叙事+创作者身份代入，现有作品未覆盖。"}
    if task_type == "plan_story_pattern":
        return {"story_model": "悬疑解谜+成长",
                "act_structure": ["第一幕：发现故事成真", "第二幕：追查执笔者", "第三幕：自我审判与改写"],
                "turning_points": [{"point": "墨晶第一次出现", "chapter_hint": "第1章"},
                                    {"point": "盟友身份反转", "chapter_hint": "第15章"}],
                "emotional_arc": "好奇→惊惧→掌控→释然"}
    if task_type == "plan_core_gameplay":
        return {"power_system": "墨晶记忆体系：重要记忆凝结为墨晶，可读取、交易、改写",
                "progression_path": "读者→执笔者→修档人→叙事仲裁者，四级",
                "pleasure_points": ["信息差反杀", "伏笔跨章回收", "以文字改写现实的代价抉择"],
                "power_ceiling": "每次改写都留下不可擦除的旁证，滥用即暴露"}
    if task_type == "plan_world_architecture":
        return {"worldview": {"name": "回声城邦",
                               "rules": ["重要记忆凝结成可交易的墨晶", "改写历史留下不可擦除的旁证",
                                          "夜航者修补叙事裂缝", "城邦每夜按已出版文本自我校对"],
                               "forces": ["修档馆：维护正史", "执笔会：垄断改写权"],
                               "geography": "环河七区，修档馆居中",
                               "history": "百年前的大改写抹去了城邦第一任执笔者"}}
    if task_type == "plan_character_system":
        return {"characters": [
            {"name": "林序", "role": "主角", "arc": "从逃避表达走向主动书写", "motivation": "夺回人生的著作权",
             "flaw": "习惯性自我怀疑", "relationships": [{"with": "沈微澜", "type": "互信盟友"}]},
            {"name": "沈微澜", "role": "盟友", "arc": "在秩序与真相间重新选择", "motivation": "修正家族档案",
             "flaw": "过度守序", "relationships": [{"with": "闻烬", "type": "旧识决裂"}]},
            {"name": "闻烬", "role": "反派", "arc": "相信牺牲少数即可拯救多数", "motivation": "阻止第二次大改写",
             "flaw": "目的正义化手段", "relationships": [{"with": "林序", "type": "镜像对照"}]},
        ]}
    if task_type == "plan_conflict_map":
        return {"conflicts": [
            {"type": "external", "between": ["林序", "执笔会"], "stakes": "人生著作权",
             "escalation": "从躲避追踪到正面夺权"},
            {"type": "internal", "between": ["林序", "林序"], "stakes": "表达的勇气",
             "escalation": "每次改写都在考验他是否敢署名"},
        ]}
    if task_type == "blueprint_volume_plan":
        return {"volumes": [{"number": 1, "title": "墨晶来信", "arc": "发现与卷入",
                              "start_chapter": 1, "end_chapter": 50,
                              "climax": "修档馆之夜", "hook": "第一枚墨晶里是主角自己的记忆"}],
                "chapter_tree": [{"volume": 1, "start_chapter": 1, "end_chapter": 50}]}
    if task_type == "blueprint_chapter_outline":
        return {"chapter_outlines": [
            {"volume": 1, "seq": i, "title": f"第{i}章", "outline": f"第{i}章：目标受阻后的转折与代价。",
             "beats": ["建立目标", "遭遇阻碍", "付出代价", "转折钩子"],
             "foreshadow_plant": ["墨晶微光" if i == 1 else ""], "foreshadow_reap": []}
            for i in range(1, 11)
        ]}
    if task_type == "blueprint_scene_beat":
        return {"scene_beats": [
            {"scene": 1, "pov": "林序", "location": "出租屋", "goal": "赶稿", "conflict": "文档自行改写",
             "outcome": "意外", "emotional_shift": "烦躁→惊惧"},
            {"scene": 2, "pov": "林序", "location": "楼道", "goal": "查敲门声", "conflict": "无人却有墨晶",
             "outcome": "失败", "emotional_shift": "惊惧→好奇"},
            {"scene": 3, "pov": "林序", "location": "便利店", "goal": "求证现实", "conflict": "店员说出他草稿台词",
             "outcome": "成功", "emotional_shift": "好奇→下定决心"},
        ]}
    if task_type == "write_chapter_draft":
        return {"chapter": {"title": "第一章 墨晶来信", "body": [
            f"{title}的第一章开始于一场不合时宜的停电。林序盯着屏幕上最后一行字，发现它并不是自己刚刚写下的。",
            "窗外的雨声像无数细小的指节敲在玻璃上。楼下便利店的灯牌忽明忽暗，而他文档里的城市名，正好也叫回声城邦。",
            "手机弹出一条陌生短信：不要删掉下一段。林序以为是谁的恶作剧，直到门外响起三下敲门声，节奏和他草稿里的描写完全一致。",
            "他打开门，门外没有人，只有一枚黑色墨晶躺在脚垫中央。",
            "墨晶内部像困着一盏灯，照亮了他从未告诉过任何人的一句话：如果故事能救人，我愿意先被故事审判。",
            "林序握紧墨晶，转身回屋。屏幕上，光标正停在一行新出现的字后面——「现在，轮到你写了。」",
        ]}}
    if task_type == "write_self_review":
        return {"overall": "开篇钩子成立，节奏可控", "strengths": ["悬念递进清晰", "现实锚点扎实"],
                "weaknesses": ["主角职业压力可再落地"], "suggestions": ["结尾补一个明确的行动目标"],
                "self_score": 84.0}
    if task_type == "write_polish":
        return {"polished": {"title": "第一章 墨晶来信", "body": [
            "停电来得不合时宜。林序盯着屏幕上最后一行字——那不是他写的。",
            "雨点敲着玻璃，楼下便利店的灯牌忽明忽暗。他文档里的城市，也叫回声城邦。",
            "陌生短信弹出来：不要删掉下一段。门外接着响起三下敲门声，和他草稿里写的一模一样。",
            "门外没有人。只有一枚黑色墨晶，躺在脚垫中央。",
            "墨晶里像困着一盏灯，照亮他从未说出口的那句话：如果故事能救人，我愿意先被故事审判。",
            "他握紧墨晶回屋。光标停在一行新字后面——「现在，轮到你写了。」",
        ]}, "changes_summary": "打散雷同句式，收紧开篇三段，强化结尾钩子。"}
    if task_type == "write_length_check":
        return {"actual_chars": 3200, "is_acceptable": True, "advice": "无需调整"}
    if task_type == "write_fact_reconcile":
        return {"reconciliation": {"conflicts_found": 0, "issues": [], "passed": True}}
    if task_type == "final_consistency_check":
        return {"checks": {dim: {"status": "pass", "issues": []} for dim in
                            ("characters", "locations", "timeline", "objects", "settings", "foreshadowing")},
                "overall_status": "pass", "warning_count": 0}
    if task_type == "final_continuity_audit":
        return {"continuity": {"status": "continuous", "gaps": [], "narrative_flow": "场景因果链完整，情绪曲线连续"}}
    if task_type == "final_humanize":
        return {"humanized_text": "停电来得不合时宜。林序盯着屏幕上最后一行字——那不是他写的。"
                                   "雨点敲着玻璃，楼下便利店的灯牌忽明忽暗。他文档里的城市，也叫回声城邦。"
                                   "门外没有人，只有一枚黑色墨晶躺在脚垫中央。他握紧墨晶回屋，光标停在一行新字后面——「现在，轮到你写了。」",
                "changes": ["删去两处总结式收尾", "长短句交替"], "ai_patterns_removed": ["章末总结体"]}
    return {"text": f"{style}：围绕“{idea}”生成的内容。"}


def _keyword(text: str) -> str:
    cleaned = "".join(ch for ch in text if ch.isalnum())
    return (cleaned[:4] or "星河")
