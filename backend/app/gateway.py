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


MODEL = "mock-deepseek-chat"
PROVIDER = "local-mock"


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
    rules: list[str] = Field(min_length=3)


class _WorldviewOutput(_StrictOutput):
    worldview: _WorldviewBody


class _CharacterBody(_StrictOutput):
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    arc: str = Field(min_length=5)


class _CharactersOutput(_StrictOutput):
    characters: list[_CharacterBody] = Field(min_length=3, max_length=8)


class _OutlineOutput(_StrictOutput):
    outline: list[str] = Field(min_length=3)


class _ChapterBody(_StrictOutput):
    title: str = Field(min_length=2)
    body: list[str] = Field(min_length=3)


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


BOOTSTRAP_OUTPUT_MODELS: dict[str, type[BaseModel]] = {
    "gen_synopsis": _SynopsisOutput,
    "gen_worldview": _WorldviewOutput,
    "gen_characters": _CharactersOutput,
    "gen_outline": _OutlineOutput,
    "gen_chapter1": _ChapterOutput,
    "gen_next_chapter": _ChapterOutput,
    "review_7dim": _ReviewOutput,
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

    # Route to provider
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

    output = validate_task_output(task_type, output)
    if provider_name == "mock":
        output["_meta"] = {"provider": "mock", "synthetic": True}

    latency_ms = int((time.perf_counter() - start) * 1000)
    cost_cny = _calculate_cost(provider_name, model_name, prompt_tokens, completion_tokens)

    conn = connect()
    conn.execute(
        """
        INSERT INTO ai_calls (
            id, run_id, node_key, provider, model, prompt_name, task_type,
            input, output, prompt_tokens, completion_tokens, cost_cny, latency_ms, status,
            client_mutation_id, project_id
        ) VALUES (%s, %s, %s ,%s, %s ,%s, %s ,%s, %s ,%s, %s ,%s, %s, %s, %s, %s)
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
    try:
        route = _load_route(task_type) or {}
        provider = str(route.get("provider") or settings.ai_provider or "unknown")
        model = str(route.get("model") or settings.deepseek_model or "unknown")
        conn = connect()
        conn.execute(
            """INSERT INTO ai_calls (
                   id, run_id, node_key, provider, model, prompt_name, task_type,
                   input, output, prompt_tokens, completion_tokens, cost_cny,
                   latency_ms, status, error, client_mutation_id, project_id
               ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,0,0,%s,'failed',%s,%s,%s)""",
            (new_id("call"), run_id, node_key, provider, model, prompt_name, task_type,
             encode({"variables": variables}), encode({}),
             int((time.perf_counter() - started) * 1000), str(error)[:2000],
             client_mutation_id, project_id),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Preserve the original provider/budget error if the ledger is unavailable.


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
    provider = (route or {}).get("provider", "mock")
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
    base_url = (_request_api_base_url.get() or settings.deepseek_base_url).rstrip("/")
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
    content = payload["choices"][0]["message"]["content"]
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
    base_url = (_request_api_base_url.get() or settings.deepseek_base_url).rstrip("/")
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
    conn.execute(
        """INSERT INTO ai_calls (
               id, run_id, node_key, provider, model, prompt_name, task_type,
               input, output, prompt_tokens, completion_tokens, cost_cny, latency_ms, status,
               client_mutation_id, project_id
           ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (new_id("call"), None, None, provider_name, model_name, prompt_name, task_type,
         encode({"variables": variables, "prompt": prompt_text, "stream": True}),
         encode({"text": full_text}),
         prompt_tokens, completion_tokens,
         _calculate_cost(provider_name, model_name, prompt_tokens, completion_tokens), latency_ms,
         "succeeded", client_mutation_id, project_id),
    )
    conn.commit()
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
    return {"text": f"{style}：围绕“{idea}”生成的内容。"}


def _keyword(text: str) -> str:
    cleaned = "".join(ch for ch in text if ch.isalnum())
    return (cleaned[:4] or "星河")
