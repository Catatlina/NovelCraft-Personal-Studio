"""
星禾AI工作台 · 小说创作 App Router

小说是星禾AI工作台的第一个AI应用插件。
本 router 提供小说专属的 API 入口，实际逻辑委托给现有 services。
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/novel-app", tags=["Novel App"])


@router.get("/status")
def novel_app_status():
    """小说 App 状态检查"""
    return {
        "code": "SUCCESS",
        "data": {
            "app": "novel",
            "version": "1.0.0",
            "capabilities": [
                "ranking_scan", "market_analysis", "auto_books",
                "deai_pipeline", "foreshadowing", "timeline",
                "multi_platform_publish", "style_learning"
            ]
        }
    }
