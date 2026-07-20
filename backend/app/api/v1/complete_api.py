"""Complete API endpoints: providers, adapters, multi-review, cross-model, matrix, book analysis, V1 migration."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask
from starlette.responses import FileResponse
import os
import re
import logging
logger = logging.getLogger(__name__)
from app.core.security import get_current_user
from app.db import connect

router = APIRouter(prefix="/api/v1", tags=["complete"])

def ok(data): return {"code": 0, "message": "ok", "data": data}


def require_member(db, project_id: str, user: dict, write: bool = False) -> None:
    row = db.execute(
        "SELECT role FROM project_members WHERE project_id = %s AND user_id = %s",
        (project_id, user["id"]),
    ).fetchone()
    if not row:
        raise HTTPException(403, "not a project member")
    if write and row["role"] not in {"owner", "editor"}:
        raise HTTPException(403, "insufficient permissions")


def require_novel_member(novel_id: str, user: dict, write: bool = False) -> None:
    """Resolve a novel to its project and enforce membership before any access."""
    db = connect()
    try:
        novel = db.execute(
            "SELECT project_id FROM contents WHERE id = %s AND type = 'novel'", (novel_id,)
        ).fetchone()
        if not novel:
            raise HTTPException(404, "novel not found")
        require_member(db, novel["project_id"], user, write=write)
    finally:
        db.close()


def require_project_member(project_id: str, user: dict, write: bool = False) -> None:
    if not project_id or not project_id.strip():
        raise HTTPException(422, "project_id is required")
    db = connect()
    try:
        require_member(db, project_id, user, write=write)
    finally:
        db.close()


def require_content_member(content_id: str, user: dict, write: bool = False) -> str:
    db = connect()
    try:
        content = db.execute(
            "SELECT project_id FROM contents WHERE id=%s AND is_deleted=FALSE", (content_id,)
        ).fetchone()
        if not content:
            raise HTTPException(404, "content not found")
        require_member(db, content["project_id"], user, write=write)
        return str(content["project_id"])
    finally:
        db.close()


def user_project_ids(user: dict) -> list[str]:
    db = connect()
    rows = db.execute(
        "SELECT project_id FROM project_members WHERE user_id=%s", (user["id"],)
    ).fetchall()
    db.close()
    return [str(row["project_id"]) for row in rows]


@router.get("/providers/test/{provider}")
def test_provider(provider: str, project_id: str, model: str = "",
                  api_key: str = Header("", alias="X-Api-Key"),
                  user: dict = Depends(get_current_user)):
    from app.services.providers_and_adapters import _claude_complete, _openai_complete, _gemini_complete
    providers = {"claude": _claude_complete, "openai": _openai_complete, "gemini": _gemini_complete}
    fn = providers.get(provider)
    if not fn:
        raise HTTPException(404, f"unknown provider: {provider}")
    require_project_member(project_id, user, write=True)
    if not api_key:
        raise HTTPException(422, "X-Api-Key is required for provider tests")
    result = fn(model, [{"role": "user", "content": "Hello"}], api_key=api_key)
    if result.get("degraded") or result.get("error"):
        raise HTTPException(502, {"code": "PROVIDER_TEST_FAILED", "provider": provider, "detail": result.get("error", "provider test failed")})
    return ok({"status": "succeeded", **result})


@router.post("/publish/{platform}")
def publish_to_platform(platform: str, title: str, body: str, credentials: dict = {}, user: dict = Depends(get_current_user)):
    from app.services.providers_and_adapters import (_publish_wechat, _publish_toutiao, _publish_xiaohongshu,
                                                     _publish_zhihu, _publish_baijia, _publish_substack, _publish_x)
    adapters = {
        "wechat": _publish_wechat, "toutiao": _publish_toutiao, "xiaohongshu": _publish_xiaohongshu,
        "zhihu": _publish_zhihu, "baijia": _publish_baijia, "substack": _publish_substack, "x": _publish_x,
    }
    fn = adapters.get(platform)
    if not fn: raise HTTPException(404, f"unknown platform: {platform}")
    from app.services.publish_hub import get_platform_credentials
    stored_credentials = get_platform_credentials(user["id"], platform) or {}
    merged = {**stored_credentials, **(credentials or {})}
    if platform == "wechat":
        result = fn(title, body, app_id=merged.get("app_id", ""), app_secret=merged.get("app_secret", ""))
    elif platform == "toutiao":
        result = fn(title, body, token=merged.get("token") or merged.get("access_token", ""))
    elif platform == "substack":
        result = fn(title, body, token=merged.get("token") or merged.get("api_key", ""))
    elif platform == "x":
        result = fn(title, body, token=merged.get("token") or merged.get("bearer_token") or merged.get("access_token", ""))
    elif platform == "xiaohongshu":
        result = fn(title, body, images=merged.get("images", []))
    else:
        result = fn(title, body)
    # Reflect the adapter's honest status in the response message
    adapter_status = result.get("status", "unknown")
    adapter_mode = result.get("mode", "")
    if adapter_status == "draft" and adapter_mode == "manual_required":
        msg = f"manual_required — {result.get('instructions', result.get('message', 'manual publish required'))}"
    elif adapter_status in ("exported", "submitted"):
        msg = f"exported — {result.get('instructions', result.get('message', 'content exported for copy-paste'))}"
    elif adapter_status == "draft":
        msg = "draft — content saved as draft, manual review required"
    else:
        msg = adapter_status
    return {"code": 0, "message": msg, "data": result}


@router.post("/review/multi-round")
def multi_round_review_endpoint(content: str, project_id: str, rounds: int = 3,
                                user: dict = Depends(get_current_user)):
    from app.services.providers_and_adapters import multi_round_review
    require_project_member(project_id, user)
    return ok(multi_round_review(content, rounds, project_id=project_id))


@router.post("/review/cross-model")
def cross_model_review(content: str, project_id: str, models: list[str] | None = None,
                       user: dict = Depends(get_current_user)):
    from app.services.providers_and_adapters import cross_model_audit
    require_project_member(project_id, user)
    return ok(cross_model_audit(content, models, project_id=project_id))


@router.post("/prompts/matrix-run")
def matrix_run(prompt_name: str, variables_list: list[dict], project_id: str,
               models: list[str] | None = None, user: dict = Depends(get_current_user)):
    from app.services.providers_and_adapters import matrix_batch_run
    require_project_member(project_id, user)
    return ok(matrix_batch_run(prompt_name, variables_list, models, project_id=project_id))


@router.post("/books/analyze")
def analyze_book(title: str, content: str, project_id: str,
                 user: dict = Depends(get_current_user)):
    from app.services.providers_and_adapters import book_analysis_workbench
    require_project_member(project_id, user, write=True)
    return ok(book_analysis_workbench(title, content, project_id=project_id))


@router.post("/v1/migrate")
def migrate_v1(project_id: str, user: dict = Depends(get_current_user)):
    from app.services.v1_migration import create_v1_test_db, migrate_v1_to_v2
    require_project_member(project_id, user, write=True)
    v1_path = create_v1_test_db()
    stats = migrate_v1_to_v2(v1_path, project_id)
    return ok({"v1_source": v1_path, "stats": stats})


# --- NC-SC-004: Novel export ---

@router.get("/novels/{novel_id}/export/txt")
def export_novel_txt_endpoint(novel_id: str, user: dict = Depends(get_current_user)):
    from app.services.novel_export import export_novel_txt
    require_novel_member(novel_id, user)
    return ok(export_novel_txt(novel_id))


@router.get("/novels/{novel_id}/export/markdown")
def export_novel_markdown_endpoint(novel_id: str, user: dict = Depends(get_current_user)):
    from app.services.novel_export import export_novel_markdown
    require_novel_member(novel_id, user)
    return ok(export_novel_markdown(novel_id))


@router.get("/novels/{novel_id}/export/epub")
def export_novel_epub_endpoint(novel_id: str, user: dict = Depends(get_current_user)):
    from app.services.novel_export import export_novel_epub, get_novel_completion_status
    require_novel_member(novel_id, user)
    result = export_novel_epub(novel_id)
    if result.get("status") == "empty":
        raise HTTPException(409, "novel has no chapters")
    if result.get("status") != "ok" or not result.get("path"):
        raise HTTPException(503, {"code": "EPUB_EXPORT_UNAVAILABLE", "reason": result.get("message")})
    completion = get_novel_completion_status(novel_id)
    safe_title = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", completion.get("title") or "novel")[:80]
    path = result["path"]
    return FileResponse(path, media_type="application/epub+zip", filename=f"{safe_title}.epub",
                        headers={"X-NovelCraft-Ready-For-Release": str(bool(completion.get("ready_for_release"))).lower()},
                        background=BackgroundTask(lambda: os.path.exists(path) and os.unlink(path)))


@router.get("/novels/{novel_id}/completion")
def get_novel_completion_endpoint(novel_id: str, user: dict = Depends(get_current_user)):
    from app.services.novel_export import get_novel_completion_status
    require_novel_member(novel_id, user)
    return ok(get_novel_completion_status(novel_id))


@router.post("/novels/{novel_id}/completion")
def generate_novel_continuation(novel_id: str, user: dict = Depends(get_current_user), payload: dict | None = None):
    """Generate continuation (mode=continue) or polish (mode=polish) text for a novel's latest chapter."""
    require_novel_member(novel_id, user)
    db = connect()
    try:
        row = db.execute(
            "SELECT project_id, body FROM contents WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE ORDER BY created_at DESC LIMIT 1",
            (novel_id,),
        ).fetchone()
    finally:
        db.close()
    if not row:
        return ok({"text": "", "warning": "no chapter found"})
    project_id = row["project_id"]
    body = row["body"]
    if isinstance(body, dict):
        paragraphs = body.get("content", [])
        text = "\n\n".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in paragraphs)
    elif isinstance(body, list):
        text = "\n\n".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in body)
    else:
        text = str(body or "")
    mode = (payload or {}).get("mode", "continue")
    prompt_name = "novel.continuation" if mode == "continue" else "novel.polish"
    try:
        from app.gateway import complete
        out = complete(run_id=None, node_key=None, project_id=project_id,
                       task_type="novel_continuation", prompt_name=prompt_name,
                       variables={"text": text[:4000]})
        gen = str(out.get("text") or out.get("sample") or "")
    except Exception as exc:
        logger.warning("novel continuation failed: %s", exc)
        return ok({"text": "", "warning": f"generation failed: {exc}"})
    return ok({"text": gen})


# --- NC-FUS: BrowserAct + insprira fusion ---
# NOTE: the former POST /scrape/browseract endpoint (stealth-extract anti-bot scraping)
# was removed: docs/25 forbids bypassing anti-bot measures. Ranking capture goes through
# the user-controlled browser artifacts in ranking_capture.py instead.

@router.post("/accounts/track")
def track_account_endpoint(platform: str, account_id: str, project_id: str, user: dict = Depends(get_current_user)):
    from app.services.fusion_browseract_insprira import track_account
    require_project_member(project_id, user, write=True)
    return ok(track_account(platform, account_id, project_id))


@router.get("/accounts/{platform}/{account_id}/diagnostics")
def account_diagnostics(platform: str, account_id: str, project_id: str, user: dict = Depends(get_current_user)):
    from app.services.fusion_browseract_insprira import get_account_diagnostics
    require_project_member(project_id, user)
    return ok(get_account_diagnostics(platform, account_id, project_id))


class ComplianceCheckRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)


@router.post("/content/check-compliance")
def check_content_compliance(payload: ComplianceCheckRequest, user: dict = Depends(get_current_user)):
    """insprira 融合：违禁词检测。正文走请求体，不进 URL/查询串。"""
    from app.services.fusion_browseract_insprira import check_compliance
    return ok(check_compliance(payload.text))


@router.get("/skills/community")
def fetch_community_skills_endpoint(user: dict = Depends(get_current_user)):
    from app.services.fusion_browseract_insprira import fetch_community_skills
    return ok(fetch_community_skills())


# --- NC-FUS-001~004: Fusion governance ---

@router.get("/fusion/report")
def get_fusion_report_endpoint(user: dict = Depends(get_current_user)):
    from app.services.fusion_governance import get_fusion_report
    return ok(get_fusion_report())


@router.get("/fusion/contracts")
def validate_contracts_endpoint(user: dict = Depends(get_current_user)):
    from app.services.fusion_governance import validate_fusion_contracts
    return ok(validate_fusion_contracts())


@router.get("/fusion/integration")
def get_integration_status(user: dict = Depends(get_current_user)):
    from app.services.fusion_governance import get_fusion_integration_status
    return ok(get_fusion_integration_status())


@router.get("/fusion/integrity")
def validate_integrity_endpoint(user: dict = Depends(get_current_user)):
    from app.services.fusion_governance import validate_fusion_data_integrity
    return ok(validate_fusion_data_integrity())


# --- NC-PUB-001~003: Publish state machine + data collection + ROI ---

@router.post("/publish/account/register")
def register_publish_account(platform: str, account_name: str, credentials: dict | None = None,
                             user: dict = Depends(get_current_user)):
    from app.services.publish_hub import register_platform_account
    return ok(register_platform_account(platform, account_name, credentials, user_id=user["id"]))


@router.get("/publish/accounts")
def list_publish_accounts(user: dict = Depends(get_current_user)):
    from app.services.publish_hub import list_platform_accounts
    return ok(list_platform_accounts(user["id"]))


@router.post("/publish/state")
def update_publish_state(content_id: str, platform: str, target_state: str, user: dict = Depends(get_current_user)):
    from app.services.publish_hub import publish_state_machine
    require_content_member(content_id, user, write=True)
    return ok(publish_state_machine(content_id, platform, target_state))


@router.get("/publish/history")
def get_publish_history(content_id: str = "", platform: str = "", user: dict = Depends(get_current_user)):
    from app.services.publish_hub import get_publishing_history
    if content_id:
        require_content_member(content_id, user)
    return ok(get_publishing_history(content_id, platform, project_ids=user_project_ids(user)))


@router.post("/publish/data/collect")
def collect_engagement_data(platform: str, content_id: str, data: dict, user: dict = Depends(get_current_user)):
    from app.services.publish_hub import collect_platform_data
    project_id = require_content_member(content_id, user, write=True)
    return ok(collect_platform_data(platform, content_id, {**data, "project_id": project_id}))


@router.get("/publish/stats")
def get_platform_stats(platform: str = "", user: dict = Depends(get_current_user)):
    from app.services.publish_hub import aggregate_platform_stats
    return ok(aggregate_platform_stats(platform, project_ids=user_project_ids(user)))


@router.get("/publish/roi")
def get_roi_report(user: dict = Depends(get_current_user)):
    from app.services.publish_hub import generate_roi_report
    return ok(generate_roi_report(project_ids=user_project_ids(user)))


@router.get("/publish/topic-suggestions")
def get_topic_suggestions_from_performance(user: dict = Depends(get_current_user)):
    from app.services.publish_hub import generate_topic_suggestions_from_data
    return ok(generate_topic_suggestions_from_data(project_ids=user_project_ids(user)))


@router.get("/analytics/dashboard")
def get_performance_dashboard(user: dict = Depends(get_current_user)):
    """NC-PUB-003: 效果看板 — 指标口径 + 汇总 + 平台 ROI + Top 内容 + 可追溯选题建议。"""
    from app.services.publish_hub import build_performance_dashboard
    return ok(build_performance_dashboard(project_ids=user_project_ids(user)))


@router.get("/analytics/usage")
def get_usage(scope: str = "user", project_id: str = "", user: dict = Depends(get_current_user)):
    """P0-T4: AI cost / token usage.

    - ``scope=user``    -> current-month usage for the authenticated user
                           (projects owned, words generated, cost, calls).
    - ``scope=project``  -> cumulative AI usage for a project the user belongs to.
    """
    from app.core.billing import get_subscription_usage
    from app.db import row_to_dict

    if scope == "project":
        if not project_id or not project_id.strip():
            raise HTTPException(422, "project_id is required when scope=project")
        require_project_member(project_id, user)
        db = connect()
        try:
            agg = row_to_dict(db.execute(
                """
                SELECT COALESCE(SUM(prompt_tokens), 0)::bigint AS prompt_tokens,
                       COALESCE(SUM(completion_tokens), 0)::bigint AS completion_tokens,
                       COALESCE(SUM(cost_cny), 0)::float AS cost_cny,
                       COUNT(*) AS calls
                FROM ai_calls WHERE project_id = %s
                """,
                (project_id,),
            ).fetchone())
        finally:
            db.close()
        return ok({
            "scope": "project",
            "project_id": project_id,
            "prompt_tokens": int(agg["prompt_tokens"] or 0),
            "completion_tokens": int(agg["completion_tokens"] or 0),
            "words_used": int(agg["completion_tokens"] or 0),
            "cost_used": float(agg["cost_cny"] or 0),
            "calls": int(agg["calls"] or 0),
        })
    usage = get_subscription_usage(user["id"])
    return ok({"scope": "user", **usage})


class PerformanceFeedbackRequest(BaseModel):
    project_id: str


@router.post("/analytics/feedback")
def get_performance_feedback(payload: PerformanceFeedbackRequest, user: dict = Depends(get_current_user)):
    """NC-PUB-003: 真实 AI 反哺建议，绑定源数据 post_id 可追溯；Provider 失败显式 502。"""
    from app.gateway import BudgetExceeded, ProviderError
    from app.services.publish_hub import performance_feedback
    db = connect()
    try:
        require_member(db, payload.project_id, user, write=True)
    finally:
        db.close()
    try:
        return ok(performance_feedback(payload.project_id, project_ids=user_project_ids(user)))
    except (ProviderError, BudgetExceeded) as exc:
        raise HTTPException(502, {"code": "AI_PROVIDER_FAILED", "detail": str(exc)}) from exc


# --- NC-SEA-001~003: Overseas markets, translation, publishing ---

@router.get("/markets")
def get_market_config_endpoint(market: str = "", user: dict = Depends(get_current_user)):
    from app.services.overseas_complete import get_market_config
    return ok(get_market_config(market))


@router.post("/markets/{market}/compliance")
def check_market_compliance_endpoint(market: str, content: str, user: dict = Depends(get_current_user)):
    from app.services.overseas_complete import check_market_compliance
    return ok(check_market_compliance(market, content))


@router.post("/translate")
def translate_text_endpoint(text: str, project_id: str, source_lang: str = "zh", target_lang: str = "en",
                            novel_id: str = "", user: dict = Depends(get_current_user)):
    from app.services.overseas_complete import translate_text
    from app.gateway import BudgetExceeded, ProviderError
    require_project_member(project_id, user, write=True)
    if novel_id:
        require_novel_member(novel_id, user)
    try:
        return ok(translate_text(text, source_lang, target_lang, project_id=project_id, novel_id=novel_id))
    except (ProviderError, BudgetExceeded) as exc:
        raise HTTPException(502, {"code": "AI_PROVIDER_FAILED", "detail": str(exc)}) from exc


@router.post("/translate/localize")
def localize_names_endpoint(chinese_name: str, target_market: str, novel_id: str = "",
                            user: dict = Depends(get_current_user)):
    from app.services.overseas_complete import localize_names
    if novel_id:
        require_novel_member(novel_id, user)
    return ok(localize_names(chinese_name, target_market, novel_id=novel_id))


@router.post("/revenue/convert")
def convert_revenue_endpoint(amount: float, from_currency: str, to_currency: str = "CNY", user: dict = Depends(get_current_user)):
    from app.services.overseas_complete import convert_revenue
    return ok(convert_revenue(amount, from_currency, to_currency))


@router.post("/overseas/publish")
def publish_overseas_endpoint(content_id: str, market: str, platform: str, user: dict = Depends(get_current_user)):
    from app.services.overseas_complete import publish_overseas
    project_id = require_content_member(content_id, user, write=True)
    return ok(publish_overseas(content_id, market, platform, project_id=project_id))
