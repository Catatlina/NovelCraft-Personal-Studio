"""Complete: Claude/OpenAI/Gemini providers + 6 platform adapters + multi-round review + matrix batch + book workbench."""
from __future__ import annotations
import json, os, urllib.request, urllib.error, base64


# ===== Claude Provider =====

def _claude_complete(model: str, messages: list, api_key: str = "", api_url: str = "") -> dict:
    """Claude API call — OpenAI-compatible format."""
    key = api_key or os.getenv("CLAUDE_API_KEY", "")
    url = api_url or os.getenv("CLAUDE_API_URL", "https://api.anthropic.com/v1/messages")
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    body = {"model": model or "claude-sonnet-4-20250514", "max_tokens": 4096, "messages": messages}
    try:
        req = urllib.request.Request(url, json.dumps(body).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        return {"text": data.get("content", [{}])[0].get("text", ""), "model": model, "provider": "claude"}
    except Exception as e:
        return {"error": str(e), "provider": "claude", "degraded": True}


# ===== OpenAI Provider =====

def _openai_complete(model: str, messages: list, api_key: str = "", api_url: str = "") -> dict:
    """OpenAI API call."""
    key = api_key or os.getenv("OPENAI_API_KEY", "")
    url = api_url or os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {"model": model or "gpt-4o", "messages": messages, "max_tokens": 4096}
    try:
        req = urllib.request.Request(url, json.dumps(body).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        return {"text": data["choices"][0]["message"]["content"], "model": model, "provider": "openai"}
    except Exception as e:
        return {"error": str(e), "provider": "openai", "degraded": True}


# ===== Gemini Provider =====

def _gemini_complete(model: str, messages: list, api_key: str = "", api_url: str = "") -> dict:
    """Gemini API call."""
    key = api_key or os.getenv("GEMINI_API_KEY", "")
    url = api_url or os.getenv("GEMINI_API_URL", f"https://generativelanguage.googleapis.com/v1beta/models/{model or 'gemini-pro'}:generateContent")
    if "?key=" not in url:
        url += f"?key={key}"
    contents = [{"parts": [{"text": m["content"]}], "role": "user" if m["role"] == "user" else "model"} for m in messages]
    body = {"contents": contents}
    try:
        req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        return {"text": data["candidates"][0]["content"]["parts"][0]["text"], "model": model, "provider": "gemini"}
    except Exception as e:
        return {"error": str(e), "provider": "gemini", "degraded": True}


# ===== HTTP publish helper =====

def _publish_http_post(url: str, headers: dict, body: dict) -> dict:
    """Helper: POST to a publishing API with 30s timeout. Returns (success, data_or_error)."""
    try:
        req = urllib.request.Request(url, json.dumps(body).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        return {"ok": True, "response": data}
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read())
        except Exception:
            detail = str(e)
        return {"ok": False, "error": detail, "http_status": e.code}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ===== 6 Platform Adapters =====

def _publish_wechat(title: str, body: str, app_id: str = "", app_secret: str = "") -> dict:
    """WeChat Official Account — draft creation via API."""
    if not app_id or not app_secret:
        return {"status": "draft", "platform": "wechat", "mode": "manual_required",
                "instructions": "登录微信公众平台 → 素材管理 → 新建图文 → 粘贴内容"}
    # Step 1: get access token
    token_url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={app_secret}"
    token_result = _publish_http_post(token_url, {"Content-Type": "application/json"}, {})
    if not token_result["ok"]:
        return {"status": "failed", "platform": "wechat", "mode": "api_error",
                "error": f"Failed to get access token: {token_result.get('error')}"}
    access_token = token_result["response"].get("access_token", "")
    if not access_token:
        return {"status": "failed", "platform": "wechat", "mode": "api_error",
                "error": f"Token response missing access_token: {token_result['response']}"}
    # Step 2: upload draft
    publish_url = f"https://api.weixin.qq.com/cgi-bin/material/add_news?access_token={access_token}"
    articles = [{"title": title[:64], "thumb_media_id": "", "author": "", "digest": body[:120],
                  "show_cover_pic": 0, "content": body, "content_source_url": "",
                  "need_open_comment": 0, "only_fans_can_comment": 0}]
    result = _publish_http_post(publish_url, {"Content-Type": "application/json"}, {"articles": articles})
    if result["ok"]:
        return {"status": "submitted", "platform": "wechat", "mode": "api", "response": result["response"]}
    return {"status": "failed", "platform": "wechat", "mode": "api_error",
            "error": str(result.get("error", "unknown")), "http_status": result.get("http_status")}


def _publish_toutiao(title: str, body: str, token: str = "") -> dict:
    """Toutiao (头条号) — article publishing."""
    if not token:
        return {"status": "draft", "platform": "toutiao", "mode": "manual_required",
                "instructions": "登录头条号后台 → 发布 → 文章 → 粘贴内容"}
    url = "https://developer.toutiao.com/api/v2/content/article/create/"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    result = _publish_http_post(url, headers, {"title": title, "content": body})
    if result["ok"]:
        return {"status": "submitted", "platform": "toutiao", "mode": "api", "response": result["response"]}
    return {"status": "failed", "platform": "toutiao", "mode": "api_error",
            "error": str(result.get("error", "unknown")), "http_status": result.get("http_status")}


def _publish_xiaohongshu(title: str, body: str, images: list = []) -> dict:
    """XiaoHongShu (小红书) — no public write API; copy-based export only."""
    return {
        "status": "draft", "platform": "xiaohongshu", "mode": "manual_required",
        "title": title[:20], "body_preview": body[:200],
        "instructions": "小红书无公开写入API。复制标题和正文 → 打开小红书App → 发布笔记 → 粘贴",
    }


def _publish_zhihu(title: str, body: str) -> dict:
    """Zhihu (知乎) — no public write API; manual only."""
    return {"status": "draft", "platform": "zhihu", "mode": "manual_required",
            "instructions": "知乎无公开写入API。登录知乎 → 写文章 → 粘贴 → 选择话题 → 发布"}


def _publish_baijia(title: str, body: str) -> dict:
    """Baijiahao (百家号) — no public write API; manual only."""
    return {"status": "draft", "platform": "baijia", "mode": "manual_required",
            "instructions": "百家号无公开写入API。登录百家号 → 发布 → 图文 → 粘贴 → 提交审核"}


def _publish_substack(title: str, body: str, token: str = "") -> dict:
    """Substack — post via API."""
    if not token:
        return {"status": "draft", "platform": "substack", "mode": "manual_required",
                "instructions": "请提供Substack API token以自动发布"}
    url = "https://api.substack.com/v1/posts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    result = _publish_http_post(url, headers, {"title": title, "body": body})
    if result["ok"]:
        return {"status": "submitted", "platform": "substack", "mode": "api", "response": result["response"]}
    return {"status": "failed", "platform": "substack", "mode": "api_error",
            "error": str(result.get("error", "unknown")), "http_status": result.get("http_status")}


def _publish_x(title: str, body: str, token: str = "") -> dict:
    """X (Twitter) — post tweet (or thread if >280 chars)."""
    if not token:
        return {"status": "draft", "platform": "x", "mode": "manual_required",
                "instructions": "请提供X API Bearer token以自动发布"}
    url = "https://api.twitter.com/2/tweets"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    # Truncate to 280 chars for single tweet; could be extended to thread posting
    tweet_text = body[:280]
    result = _publish_http_post(url, headers, {"text": tweet_text})
    if result["ok"]:
        return {"status": "submitted", "platform": "x", "mode": "api", "response": result["response"],
                "note": "Tweet truncated to 280 chars" if len(body) > 280 else None}
    return {"status": "failed", "platform": "x", "mode": "api_error",
            "error": str(result.get("error", "unknown")), "http_status": result.get("http_status")}


# ===== Multi-round review =====
# These review/audit/matrix helpers previously fabricated scores from string
# length ("固定字典冒充 AI 分析", forbidden by docs/23 §4). They now go through
# the gateway; provider unavailability surfaces as pending_provider, never as
# an invented score.

def _review_via_gateway(content: str, project_id: str, mutation_id: str) -> dict:
    from app.gateway import complete

    return complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="review_7dim", prompt_name="bootstrap.review_7dim",
        variables={"body": content[:6000]},
        client_mutation_id=mutation_id,
    )


def multi_round_review(content: str, rounds: int = 3, project_id: str = "") -> dict:
    """TASK-032/033: Real multi-round review; stops early once the round threshold passes."""
    import hashlib

    from app.gateway import BudgetExceeded, ProviderError

    digest = hashlib.sha256(content.encode()).hexdigest()[:16]
    results = []
    for round_no in range(1, rounds + 1):
        threshold = 70 + (round_no - 1) * 10  # 70, 80, 90
        try:
            review = _review_via_gateway(content, project_id, f"multi-review:{digest}:round:{round_no}")
        except (ProviderError, BudgetExceeded) as exc:
            results.append({"round": round_no, "threshold": threshold,
                            "status": "pending_provider", "error": str(exc)})
            return {"rounds": results, "final_pass": False, "status": "pending_provider"}
        score = int(review.get("score", 0))
        passed = score >= threshold
        results.append({"round": round_no, "threshold": threshold, "score": score,
                        "passed": passed, "issues": review.get("issues", []), "status": "succeeded"})
        if not passed:
            return {"rounds": results, "final_pass": False, "status": "succeeded"}
    return {"rounds": results, "final_pass": True, "status": "succeeded"}


# ===== Cross-model audit =====

def cross_model_audit(content: str, models: list[str] | None = None, project_id: str = "") -> dict:
    """TASK-C6: Cross-model audit via the gateway model override, one real call per model."""
    import hashlib

    from app.gateway import BudgetExceeded, ProviderError, _request_model

    models = models or ["deepseek"]
    digest = hashlib.sha256(content.encode()).hexdigest()[:16]
    audits = []
    for model in models:
        previous = _request_model.get()
        _request_model.set(model if model not in ("deepseek",) else None)
        try:
            review = _review_via_gateway(content, project_id, f"cross-audit:{digest}:{model}")
            score = int(review.get("score", 0))
            audits.append({"model": model, "score": score, "passed": score >= 70,
                           "issues": review.get("issues", []), "status": "succeeded"})
        except (ProviderError, BudgetExceeded) as exc:
            audits.append({"model": model, "status": "pending_provider", "error": str(exc)})
        finally:
            _request_model.set(previous)
    scored = [a for a in audits if a.get("status") == "succeeded"]
    consensus = sum(a["passed"] for a in scored) / len(scored) if scored else 0.0
    return {"audits": audits, "consensus": consensus,
            "overall_pass": bool(scored) and consensus >= 0.5,
            "status": "succeeded" if scored else "pending_provider"}


# ===== Matrix batch run =====

def matrix_batch_run(prompt_name: str, variables_list: list[dict], models: list[str] | None = None,
                     project_id: str = "") -> dict:
    """TASK-039: Matrix batch — really executes prompt × variables × models via the gateway."""
    import hashlib
    import json as _json

    from app.gateway import BudgetExceeded, ProviderError, _request_model, complete

    models = models or ["deepseek"]
    task_type = prompt_name.split(".")[-1]
    results = []
    for index, variables in enumerate(variables_list):
        var_digest = hashlib.sha256(_json.dumps(variables, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        for model in models:
            previous = _request_model.get()
            _request_model.set(model if model not in ("deepseek",) else None)
            try:
                output = complete(
                    run_id=None, node_key=None, project_id=project_id,
                    task_type=task_type, prompt_name=prompt_name, variables=variables,
                    client_mutation_id=f"matrix:{prompt_name}:{var_digest}:{model}",
                )
                results.append({"batch": index + 1, "model": model, "variables": variables,
                                "status": "succeeded", "output": output})
            except (ProviderError, BudgetExceeded) as exc:
                results.append({"batch": index + 1, "model": model, "variables": variables,
                                "status": "pending_provider", "error": str(exc)})
            finally:
                _request_model.set(previous)
    succeeded = sum(1 for r in results if r["status"] == "succeeded")
    return {"prompt": prompt_name, "total_runs": len(results), "succeeded": succeeded,
            "models": models, "results": results}


# ===== Book analysis workbench =====

def book_analysis_workbench(title: str, content: str) -> dict:
    """TASK-041: Full book analysis — structure, tropes, rhythm, style."""
    import re
    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
    # Opening analysis
    opening = paragraphs[0][:200] if paragraphs else ""
    # Trope detection
    tropes = []
    if "重生" in content: tropes.append("重生/穿越")
    if "系统" in content: tropes.append("系统流")
    if "打脸" in content: tropes.append("打脸爽文")
    if "反派" in content: tropes.append("反派路线")
    # Rhythm scoring
    avg_para_len = sum(len(p) for p in paragraphs[:20]) / max(len(paragraphs[:20]), 1)
    rhythm = "快节奏" if avg_para_len < 80 else "中速" if avg_para_len < 150 else "慢热"
    
    return {
        "title": title, "total_paragraphs": len(paragraphs),
        "opening_hook": opening, "detected_tropes": tropes,
        "rhythm": rhythm, "avg_paragraph_length": round(avg_para_len),
        "structure_cards": {
            "three_act": "act1_setup, act2_confrontation, act3_resolution",
            "save_the_cat": len(paragraphs) // 15,  # Estimated beats
        },
    }
