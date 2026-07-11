"""Complete API endpoints: providers, adapters, multi-review, cross-model, matrix, book analysis, V1 migration."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from app.core.security import get_current_user

router = APIRouter(prefix="/api/v1", tags=["complete"])

def ok(data): return {"code": 0, "message": "ok", "data": data}


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
def migrate_v1(project_id: str = "", user: dict = Depends(get_current_user)):
    from app.services.v1_migration import create_v1_test_db, migrate_v1_to_v2
    v1_path = create_v1_test_db()
    stats = migrate_v1_to_v2(v1_path, project_id)
    return ok({"v1_source": v1_path, "stats": stats})


# --- NC-SC-004: Novel export ---

@router.get("/novels/{novel_id}/export/txt")
def export_novel_txt_endpoint(novel_id: str, user: dict = Depends(get_current_user)):
    from app.services.novel_export import export_novel_txt
    result = export_novel_txt(novel_id)
    return ok(result)


@router.get("/novels/{novel_id}/export/markdown")
def export_novel_markdown_endpoint(novel_id: str, user: dict = Depends(get_current_user)):
    from app.services.novel_export import export_novel_markdown
    return ok(export_novel_markdown(novel_id))


@router.get("/novels/{novel_id}/export/epub")
def export_novel_epub_endpoint(novel_id: str, user: dict = Depends(get_current_user)):
    from app.services.novel_export import export_novel_epub
    return ok(export_novel_epub(novel_id))


@router.get("/novels/{novel_id}/completion")
def get_novel_completion_endpoint(novel_id: str, user: dict = Depends(get_current_user)):
    from app.services.novel_export import get_novel_completion_status
    return ok(get_novel_completion_status(novel_id))


# --- NC-FUS: BrowserAct + insprira fusion ---

@router.post("/scrape/browseract")
def scrape_with_browseract(url: str, selector: str = "", user: dict = Depends(get_current_user)):
    from app.services.fusion_browseract_insprira import scrape_ranking_with_browseract
    return ok(scrape_ranking_with_browseract(url, selector))


@router.post("/accounts/track")
def track_account_endpoint(platform: str, account_id: str, project_id: str = "", user: dict = Depends(get_current_user)):
    from app.services.fusion_browseract_insprira import track_account
    return ok(track_account(platform, account_id, project_id))


@router.get("/accounts/{platform}/{account_id}/diagnostics")
def account_diagnostics(platform: str, account_id: str, user: dict = Depends(get_current_user)):
    from app.services.fusion_browseract_insprira import get_account_diagnostics
    return ok(get_account_diagnostics(platform, account_id))


@router.post("/content/check-compliance")
def check_content_compliance(text: str, user: dict = Depends(get_current_user)):
    from app.services.fusion_browseract_insprira import check_compliance
    return ok(check_compliance(text))


@router.get("/skills/community")
def fetch_community_skills_endpoint(user: dict = Depends(get_current_user)):
    from app.services.fusion_browseract_insprira import fetch_community_skills
    return ok(fetch_community_skills())
