from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from .config import settings
from .db import connect, decode, encode, new_id, row_to_dict
from .prompt_registry import OUTPUT_CONTRACTS, render_prompt


MODEL = "mock-deepseek-chat"
PROVIDER = "local-mock"


class BudgetExceeded(RuntimeError):
    """Raised when a project budget would be exceeded by an AI call."""


class ProviderError(RuntimeError):
    """Raised when a configured provider cannot return a usable JSON result."""


def complete(
    *,
    run_id: str | None,
    node_key: str | None,
    project_id: str,
    task_type: str,
    prompt_name: str,
    variables: dict[str, Any],
) -> dict[str, Any]:
    start = time.perf_counter()
    prompt_text, provider, model, params = _load_prompt_and_route(prompt_name, task_type, variables)
    estimated_cost = _estimate_cost(variables, {"prompt": prompt_text})
    _assert_budget(project_id, "bootstrap", estimated_cost)

    if provider == "deepseek" or (settings.ai_provider == "deepseek" and settings.deepseek_api_key):
        output = _deepseek_complete(task_type, prompt_text, model or settings.deepseek_model, params)
        provider_name = "deepseek"
        model_name = model or settings.deepseek_model
    else:
        output = _mock_output(task_type, variables)
        provider_name = PROVIDER
        model_name = MODEL

    latency_ms = int((time.perf_counter() - start) * 1000) + 60
    prompt_tokens = max(80, len(prompt_text) // 3)
    completion_tokens = max(120, len(encode(output)) // 3)
    cost_cny = round((prompt_tokens + completion_tokens) * 0.000002, 4)

    conn = connect()
    conn.execute(
        """
        INSERT INTO ai_calls (
            id, run_id, node_key, provider, model, prompt_name, task_type,
            input, output, prompt_tokens, completion_tokens, cost_cny, latency_ms, status
        ) VALUES (%s, %s, %s ,%s, %s ,%s, %s ,%s, %s ,%s, %s ,%s, %s, %s)
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


def _load_prompt_and_route(
    prompt_name: str,
    task_type: str,
    variables: dict[str, Any],
) -> tuple[str, str, str, dict[str, Any]]:
    conn = connect()
    route = row_to_dict(
        conn.execute(
            "SELECT * FROM model_routes WHERE task_type = %s AND is_active = TRUE",
            (task_type,),
        ).fetchone()
    )
    provider = (route or {}).get("provider", "mock")
    model = (route or {}).get("model", MODEL)
    params = decode((route or {}).get("params"), {})
    prompt = row_to_dict(
        conn.execute(
            """
            SELECT * FROM prompts
            WHERE name = %s AND is_active = TRUE
            ORDER BY created_at DESC
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
    if contract:
        prompt_text += "\n\n只输出合法 JSON，结构必须匹配：\n" + contract
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
        raise BudgetExceeded(f"{scope} budget exceeded")


def _estimate_cost(variables: dict[str, Any], output_hint: dict[str, Any]) -> float:
    prompt_tokens = max(80, len(encode(variables)) // 3)
    completion_tokens = max(120, len(encode(output_hint)) // 3)
    return round((prompt_tokens + completion_tokens) * 0.000002, 4)


def _deepseek_complete(task_type: str, prompt: str, model: str, params: dict[str, Any]) -> dict[str, Any]:
    if not settings.deepseek_api_key:
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
    request = urllib.request.Request(
        f"{settings.deepseek_base_url.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.request_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError(f"deepseek request failed: {exc}") from exc
    content = payload["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"deepseek returned non-json for {task_type}") from exc
    return parsed


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
    if task_type == "review_7dim":
        return {
            "score": 84,
            "dimensions": {
                "hook": 88,
                "character": 82,
                "world": 86,
                "pace": 80,
                "emotion": 78,
                "clarity": 90,
                "serial_potential": 85,
            },
            "issues": [
                "第一章悬念成立，可以在结尾补一个更明确的行动目标。",
                "主角职业和日常压力还可以再落地一些。",
            ],
        }
    if task_type.startswith("editor_"):
        selection = variables.get("selection", "")
        instruction = variables.get("instruction", "")
        if task_type == "editor_continue":
            text = selection + "\n\n他把墨晶握在掌心，忽然听见城市深处传来潮水般的翻页声。"
        elif task_type == "editor_rewrite":
            text = f"改写版：{selection.strip()}（更强调冲突与画面，{instruction or '保持原意'}。）"
        else:
            text = f"润色版：{selection.strip()}（语言更顺，节奏更稳。）"
        return {"text": text}
    return {"text": f"{style}：围绕“{idea}”生成的内容。"}


def _keyword(text: str) -> str:
    cleaned = "".join(ch for ch in text if ch.isalnum())
    return (cleaned[:4] or "星河")
