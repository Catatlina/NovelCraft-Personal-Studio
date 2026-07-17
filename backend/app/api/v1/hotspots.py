"""TASK-037: Hotspot API with web adapter."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.db import connect, encode, new_id
from app.gateway import BudgetExceeded, ProviderError, complete
from app.services.hotspot_collector import (
    backfill_hotspot_history,
    fetch_hotspots,
    get_hotspot_history_report,
    get_hotspot_trend_report,
    get_hotspot_overview,
    get_hotspots_paginated,
    store_hotspots,
)
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
    return {"code": 0, "message": "ok",
            "data": {"hotspots": items, "sources": source_status}}


@router.get("/hotspots/trend-report")
def hotspot_trend_report(user: dict = Depends(get_current_user)):
    return {"code": 0, "message": "ok", "data": get_hotspot_trend_report()}


@router.post("/hotspots/history/backfill")
def hotspot_history_backfill(days: int = 7, user: dict = Depends(get_current_user)):
    """Backfill stored hotspot snapshots from configured real archive URLs.

    Sources without a historical endpoint are reported as unsupported; this
    endpoint never synthesizes past trends from today's list.
    """
    try:
        result = backfill_hotspot_history(days=days, user_id=user["id"])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if result["status"] == "unsupported":
        raise HTTPException(status_code=502, detail={
            "code": "HOTSPOT_HISTORY_UNSUPPORTED",
            "message": "No configured historical hotspot source returned data.",
            "data": result,
        })
    return {"code": 0, "message": "ok", "data": result}


@router.get("/hotspots/history")
def hotspot_history_report(days: int = 7, user: dict = Depends(get_current_user)):
    try:
        report = get_hotspot_history_report(days=days)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"code": 0, "message": "ok", "data": report}


def _require_editor(db, project_id: str, user: dict) -> None:
    member = db.execute("SELECT role FROM project_members WHERE project_id=%s AND user_id=%s",
                        (project_id, user["id"])).fetchone()
    if not member or member["role"] not in {"owner", "editor"}:
        raise HTTPException(403, "insufficient permissions")


@router.get("/hotspots/platform-match")
def hotspot_platform_match(topic: str, category: str = "", user: dict = Depends(get_current_user)):
    """NC-HM-002: score platform suitability + audience + compliance risks for a topic."""
    from app.services.hm_content import match_platforms_for_topic
    if not topic.strip():
        raise HTTPException(422, "topic is required")
    return {"code": 0, "message": "ok", "data": {"matches": match_platforms_for_topic(topic.strip(), category.strip())}}


class HmTopicRequest(BaseModel):
    project_id: str
    topic: str = Field(min_length=1, max_length=200)
    count: int = Field(default=5, ge=1, le=20)
    platform: str = Field(default="douyin", max_length=40)
    content: str = Field(default="", max_length=8000)


@router.post("/hotspots/title-variants")
def hotspot_title_variants(payload: HmTopicRequest, user: dict = Depends(get_current_user)):
    """NC-HM-003: real-AI title variants for A/B testing. Provider failure is a 502, never a template."""
    from app.services.hm_content import generate_title_variants
    db = connect()
    try:
        _require_editor(db, payload.project_id, user)
    finally:
        db.close()
    try:
        titles = generate_title_variants(payload.topic, payload.count, project_id=payload.project_id)
    except (ProviderError, BudgetExceeded) as exc:
        raise HTTPException(502, {"code": "AI_PROVIDER_FAILED", "detail": str(exc)}) from exc
    return {"code": 0, "message": "ok", "data": {"titles": titles}}


@router.post("/hotspots/video-script")
def hotspot_video_script(payload: HmTopicRequest, user: dict = Depends(get_current_user)):
    """NC-HM-003: real-AI short-video script from a hot topic (no source content required)."""
    from app.services.hm_content import generate_video_script
    db = connect()
    try:
        _require_editor(db, payload.project_id, user)
    finally:
        db.close()
    try:
        result = generate_video_script(payload.topic, payload.platform, project_id=payload.project_id)
    except (ProviderError, BudgetExceeded) as exc:
        raise HTTPException(502, {"code": "AI_PROVIDER_FAILED", "detail": str(exc)}) from exc
    if result.get("status") == "error":
        raise HTTPException(422, result.get("message", "unknown platform"))
    return {"code": 0, "message": "ok", "data": result}


@router.post("/hotspots/material-suggestions")
def hotspot_material_suggestions(payload: HmTopicRequest, user: dict = Depends(get_current_user)):
    """NC-HM-003: real-AI cover/chart/data-source suggestions for a drafted article."""
    from app.services.hm_content import generate_material_suggestions
    db = connect()
    try:
        _require_editor(db, payload.project_id, user)
    finally:
        db.close()
    try:
        result = generate_material_suggestions(payload.topic, payload.content, project_id=payload.project_id)
    except (ProviderError, BudgetExceeded) as exc:
        raise HTTPException(502, {"code": "AI_PROVIDER_FAILED", "detail": str(exc)}) from exc
    return {"code": 0, "message": "ok", "data": result}


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


# ── Hotspot Overview ────────────────────────────────────────────────


class HotspotOverviewQuery(BaseModel):
    platforms: list[str] = Field(default_factory=list, max_length=20)
    project_id: str = Field(default="")


@router.get("/hotspots/overview")
def hotspot_overview(
    platforms: str = "",
    project_id: str = "",
    user: dict = Depends(get_current_user),
):
    """Return today's hotspot overview with AI-generated summary."""
    platform_list = [p.strip() for p in platforms.split(",") if p.strip()] if platforms else None
    overview = get_hotspot_overview(
        user_id=user["id"],
        project_id=project_id or "",
        platforms=platform_list,
    )
    return {"code": 0, "message": "ok", "data": overview}


@router.get("/hotspots/paginated")
def hotspots_paginated(
    platforms: str = "",
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(get_current_user),
):
    """Get hotspots with pagination, platform filtering, and unified scoring."""
    platform_list = [p.strip() for p in platforms.split(",") if p.strip()] if platforms else None
    result = get_hotspots_paginated(
        user_id=user["id"],
        platforms=platform_list,
        page=page,
        page_size=min(page_size, 50),
    )
    return {"code": 0, "message": "ok", "data": result}


# ── Article Library (文库) ──────────────────────────────────────────


class ArticleEditRequest(BaseModel):
    title: str = Field(default="", max_length=200)
    body: str = Field(default="")  # JSON string or text


@router.get("/articles")
def list_articles(
    project_id: str = "",
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(get_current_user),
):
    """List all generated articles with pagination."""
    db = connect()
    try:
        where = "WHERE c.type = 'social_post' AND c.is_deleted = FALSE"
        params: list = []
        if project_id:
            where += " AND c.project_id = %s"
            params.append(project_id)

        total_row = db.execute(
            f"SELECT COUNT(*) as cnt FROM contents c {where}",
            tuple(params),
        ).fetchone()
        total = total_row["cnt"] if total_row else 0

        offset = (page - 1) * page_size
        rows = db.execute(
            f"""SELECT c.id, c.title, c.body, c.meta, c.status, c.created_at, c.updated_at,
                       c.project_id
                FROM contents c {where}
                ORDER BY c.created_at DESC
                LIMIT %s OFFSET %s""",
            tuple(params) + (page_size, offset),
        ).fetchall()

        articles = []
        for row in rows:
            meta = row.get("meta") or {}
            body = row.get("body") or {}
            # Extract summary from body
            content_items = body.get("content", []) if isinstance(body, dict) else []
            summary = ""
            if content_items and isinstance(content_items, list):
                first_text = ""
                for item in content_items[:2]:
                    if isinstance(item, dict):
                        first_text += str(item.get("text", ""))
                    elif isinstance(item, str):
                        first_text += item
                summary = first_text[:150]

            articles.append({
                "id": row["id"],
                "title": row["title"],
                "summary": summary,
                "platform": meta.get("platform", "unknown"),
                "hotspot_title": meta.get("hotspot_title", ""),
                "hotspot_source": meta.get("hotspot_source", ""),
                "status": row["status"],
                "created_at": str(row["created_at"]) if row["created_at"] else "",
                "updated_at": str(row["updated_at"]) if row["updated_at"] else "",
                "project_id": row["project_id"],
            })

        return {"code": 0, "message": "ok", "data": {
            "articles": articles,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }}
    finally:
        db.close()


@router.get("/articles/{article_id}")
def get_article_detail(article_id: str, user: dict = Depends(get_current_user)):
    """Get full article detail."""
    db = connect()
    try:
        row = db.execute(
            """SELECT c.id, c.title, c.body, c.meta, c.status, c.created_at,
                      c.updated_at, c.project_id
               FROM contents c
               WHERE c.id = %s AND c.type = 'social_post' AND c.is_deleted = FALSE""",
            (article_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "article not found")

        meta = row.get("meta") or {}
        body = row.get("body") or {}
        content_items = body.get("content", []) if isinstance(body, dict) else []
        full_text = ""
        if content_items and isinstance(content_items, list):
            for item in content_items:
                if isinstance(item, dict):
                    full_text += str(item.get("text", "")) + "\n"
                elif isinstance(item, str):
                    full_text += item + "\n"

        return {"code": 0, "message": "ok", "data": {
            "id": row["id"],
            "title": row["title"],
            "body": body,
            "full_text": full_text.strip(),
            "platform": meta.get("platform", "unknown"),
            "hotspot_title": meta.get("hotspot_title", ""),
            "hotspot_source": meta.get("hotspot_source", ""),
            "hotspot_url": meta.get("hotspot_url", ""),
            "ai_generated": meta.get("ai_generated", False),
            "status": row["status"],
            "created_at": str(row["created_at"]) if row["created_at"] else "",
            "updated_at": str(row["updated_at"]) if row["updated_at"] else "",
            "project_id": row["project_id"],
        }}
    finally:
        db.close()


@router.delete("/articles/{article_id}")
def delete_article(article_id: str, user: dict = Depends(get_current_user)):
    """Soft-delete an article."""
    db = connect()
    try:
        row = db.execute(
            "SELECT project_id FROM contents WHERE id = %s AND type = 'social_post' AND is_deleted = FALSE",
            (article_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "article not found")
        _require_editor(db, row["project_id"], user)
        db.execute(
            "UPDATE contents SET is_deleted = TRUE, updated_at = now() WHERE id = %s",
            (article_id,),
        )
        db.commit()
        return {"code": 0, "message": "ok", "data": {"id": article_id, "deleted": True}}
    finally:
        db.close()


@router.put("/articles/{article_id}")
def edit_article(article_id: str, payload: ArticleEditRequest, user: dict = Depends(get_current_user)):
    """Edit an article's title and body."""
    db = connect()
    try:
        row = db.execute(
            "SELECT project_id, body FROM contents WHERE id = %s AND type = 'social_post' AND is_deleted = FALSE",
            (article_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "article not found")
        _require_editor(db, row["project_id"], user)

        updates = []
        params: list = []
        if payload.title:
            updates.append("title = %s")
            params.append(payload.title[:200])
        if payload.body:
            import json as _json
            try:
                new_body = _json.loads(payload.body)
            except (_json.JSONDecodeError, ValueError):
                new_body = {"type": "doc", "content": [{"type": "paragraph", "text": payload.body}]}
            updates.append("body = %s")
            params.append(encode(new_body))
        if updates:
            updates.append("updated_at = now()")
            params.append(article_id)
            db.execute(
                f"UPDATE contents SET {', '.join(updates)} WHERE id = %s",
                tuple(params),
            )
            db.commit()
        return {"code": 0, "message": "ok", "data": {"id": article_id, "updated": True}}
    finally:
        db.close()
