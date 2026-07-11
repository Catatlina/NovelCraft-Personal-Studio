"""Complete API endpoints: providers, adapters, multi-review, cross-model, matrix, book analysis, V1 migration."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from starlette.background import BackgroundTask
from starlette.responses import FileResponse
import os
import re
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


@router.get("/providers/test/{provider}")
def test_provider(provider: str, model: str = "", user: dict = Depends(get_current_user)):
    from app.services.providers_and_adapters import _claude_complete, _openai_complete, _gemini_complete
    providers = {"claude": _claude_complete, "openai": _openai_complete, "gemini": _gemini_complete}
    fn = providers.get(provider)
    if not fn: raise HTTPException(404, f"unknown provider: {provider}")
    return ok(fn(model, [{"role": "user", "content": "Hello"}]))


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
    return ok(fn(title, body, **credentials) if credentials else fn(title, body))


@router.post("/review/multi-round")
def multi_round_review_endpoint(content: str, rounds: int = 3, user: dict = Depends(get_current_user)):
    from app.services.providers_and_adapters import multi_round_review
    return ok(multi_round_review(content, rounds))


@router.post("/review/cross-model")
def cross_model_review(content: str, models: list = ["deepseek", "claude", "openai"], user: dict = Depends(get_current_user)):
    from app.services.providers_and_adapters import cross_model_audit
    return ok(cross_model_audit(content, models))


@router.post("/prompts/matrix-run")
def matrix_run(prompt_name: str, variables_list: list[dict], models: list = ["deepseek"], user: dict = Depends(get_current_user)):
    from app.services.providers_and_adapters import matrix_batch_run
    return ok(matrix_batch_run(prompt_name, variables_list, models))


@router.post("/books/analyze")
def analyze_book(title: str, content: str, user: dict = Depends(get_current_user)):
    from app.services.providers_and_adapters import book_analysis_workbench
    return ok(book_analysis_workbench(title, content))


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


@router.post("/content/check-compliance")
def check_content_compliance(text: str, user: dict = Depends(get_current_user)):
    from app.services.fusion_browseract_insprira import check_compliance
    return ok(check_compliance(text))


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
    return ok(publish_state_machine(content_id, platform, target_state))


@router.get("/publish/history")
def get_publish_history(content_id: str = "", platform: str = "", user: dict = Depends(get_current_user)):
    from app.services.publish_hub import get_publishing_history
    return ok(get_publishing_history(content_id, platform))


@router.post("/publish/data/collect")
def collect_engagement_data(platform: str, content_id: str, data: dict, user: dict = Depends(get_current_user)):
    from app.services.publish_hub import collect_platform_data
    return ok(collect_platform_data(platform, content_id, data))


@router.get("/publish/stats")
def get_platform_stats(platform: str = "", user: dict = Depends(get_current_user)):
    from app.services.publish_hub import aggregate_platform_stats
    return ok(aggregate_platform_stats(platform))


@router.get("/publish/roi")
def get_roi_report(user: dict = Depends(get_current_user)):
    from app.services.publish_hub import generate_roi_report
    return ok(generate_roi_report())


@router.get("/publish/topic-suggestions")
def get_topic_suggestions_from_performance(user: dict = Depends(get_current_user)):
    from app.services.publish_hub import generate_topic_suggestions_from_data
    return ok(generate_topic_suggestions_from_data())


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
def translate_text_endpoint(text: str, source_lang: str = "zh", target_lang: str = "en", user: dict = Depends(get_current_user)):
    from app.services.overseas_complete import translate_text
    return ok(translate_text(text, source_lang, target_lang))


@router.post("/translate/localize")
def localize_names_endpoint(chinese_name: str, target_market: str, user: dict = Depends(get_current_user)):
    from app.services.overseas_complete import localize_names
    return ok(localize_names(chinese_name, target_market))


@router.post("/revenue/convert")
def convert_revenue_endpoint(amount: float, from_currency: str, to_currency: str = "CNY", user: dict = Depends(get_current_user)):
    from app.services.overseas_complete import convert_revenue
    return ok(convert_revenue(amount, from_currency, to_currency))


@router.post("/overseas/publish")
def publish_overseas_endpoint(content_id: str, market: str, platform: str, user: dict = Depends(get_current_user)):
    from app.services.overseas_complete import publish_overseas
    return ok(publish_overseas(content_id, market, platform))
