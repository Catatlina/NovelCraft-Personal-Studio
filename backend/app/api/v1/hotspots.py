"""TASK-037: Hotspot API with web adapter."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.db import connect, encode, new_id
from app.gateway import BudgetExceeded, ProviderError, complete
from app.services.hotspot_collector import fetch_hotspots, store_hotspots, analyze_hotspots, get_hotspot_trend_report
from app.services.social_media import PLATFORMS, VIDEO_PLATFORMS

router = APIRouter(prefix="/api/v1", tags=["hotspots"])


class HotspotGenerateRequest(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=200)
    source: str = Field(default="", max_length=40)
    url: str = Field(default="", max_length=1000)
    platforms: list[str] = Field(default_factory=lambda: ["wechat", "toutiao", "baijia", "dayu", "xiaohongshu", "douyin"],
                                 min_length=1, max_length=12)


@router.get("/hotspots")
def get_hotspots(user: dict = Depends(get_current_user)):
    """TASK-037: Fetch current hotspots. Source failures are explicit, never an empty 200."""
    try:
        items, source_status = fetch_hotspots(user_id=user["id"])
    except TypeError as exc:
        if "user_id" not in str(exc):
            raise
        items, source_status = fetch_hotspots()
    if items:
        store_hotspots(items)
    if not items and source_status and all(status.startswith("error") for status in source_status.values()):
        raise HTTPException(status_code=502, detail={
            "code": "HOTSPOT_SOURCES_FAILED", "sources": source_status,
        })
    angles = analyze_hotspots(items)
    return {"code": 0, "message": "ok",
            "data": {"hotspots": items, "creative_angles": angles, "sources": source_status}}


@router.get("/hotspots/trend-report")
def hotspot_trend_report(user: dict = Depends(get_current_user)):
    return {"code": 0, "message": "ok", "data": get_hotspot_trend_report()}


@router.post("/hotspots/generate")
def generate_from_hotspot(payload: HotspotGenerateRequest, user: dict = Depends(get_current_user)):
    """Generate platform-specific content from one hotspot via real AI only."""
    db = connect()
    member = db.execute("SELECT role FROM project_members WHERE project_id=%s AND user_id=%s",
                        (payload.project_id, user["id"])).fetchone()
    if not member or member["role"] not in {"owner", "editor"}:
        db.close()
        raise HTTPException(403, "insufficient permissions")
    generated = []
    try:
        for platform in payload.platforms:
            cfg = PLATFORMS.get(platform) or VIDEO_PLATFORMS.get(platform)
            if not cfg:
                raise HTTPException(422, f"unsupported platform: {platform}")
            output = complete(
                run_id=None, node_key=None, project_id=payload.project_id,
                task_type="gen_daily_brief", prompt_name="social.gen_hotspot_content",
                variables={
                    "hotspot_title": payload.title,
                    "hotspot_source": payload.source,
                    "hotspot_url": payload.url,
                    "platform": cfg["name"],
                    "style": cfg["style"],
                },
                client_mutation_id=f"hotspot:{payload.project_id}:{platform}:{payload.source}:{payload.title}"[:100],
            )
            body_parts = output.get("body") or output.get("paragraphs") or output.get("script") or output.get("text") or []
            if isinstance(body_parts, str):
                body_parts = [body_parts]
            title = output.get("title") or f"{payload.title} - {cfg['name']}"
            content_id = new_id()
            db.execute("""INSERT INTO contents (id,project_id,type,title,body,meta,status,owner_id)
                          VALUES (%s,%s,%s,%s,%s,%s,'draft',%s)""",
                       (content_id, payload.project_id, cfg.get("type", "social_post"), title[:200],
                        encode({"type": "doc", "content": [{"type": "paragraph", "text": str(p)} for p in body_parts]}),
                        encode({"platform": platform, "hotspot_title": payload.title, "hotspot_source": payload.source,
                                "hotspot_url": payload.url, "ai_generated": True, "meta": output.get("meta", {})}),
                        user["id"]))
            generated.append({"platform": platform, "content_id": content_id, "title": title, "status": "succeeded"})
        db.commit()
    except (ProviderError, BudgetExceeded) as exc:
        db.rollback()
        raise HTTPException(502, {"code": "AI_PROVIDER_FAILED", "detail": str(exc)}) from exc
    finally:
        db.close()
    return {"code": 0, "message": "ok", "data": {"items": generated}}
