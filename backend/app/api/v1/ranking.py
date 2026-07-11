"""Ranking-driven novel creation: scan, snapshot, analyze, propose, create book."""
from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.db import connect, encode, new_id
from app.services.ranking_adapter import RANKING_FETCHERS, normalize_ranking_items

router = APIRouter(prefix="/api/v1/ranking", tags=["ranking"])

SOURCE_NAMES = {"fanqie": "番茄小说", "qidian": "起点中文网", "zongheng": "纵横中文网"}


def ok(data: Any):
    return {"code": 0, "message": "ok", "data": data}


def require_member(db, project_id: str, user: dict, write: bool = False) -> None:
    row = db.execute(
        "SELECT role FROM project_members WHERE project_id = %s AND user_id = %s",
        (project_id, user["id"]),
    ).fetchone()
    if not row:
        raise HTTPException(403, "not a project member")
    if write and row["role"] not in {"owner", "editor"}:
        raise HTTPException(403, "insufficient permissions")


def rows(db, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(row) for row in db.execute(sql, params).fetchall()]


class CreateBookRequest(BaseModel):
    auto_start: bool = True
    target_words: int = Field(default=800_000, ge=10_000, le=5_000_000)
    style: str = "商业网文、节奏紧凑、人物驱动"


@router.get("/sources")
def list_sources(project_id: str, user: dict = Depends(get_current_user)):
    db = connect()
    require_member(db, project_id, user)
    existing = {r["source_key"]: r for r in rows(db, "SELECT * FROM ranking_sources WHERE project_id = %s", (project_id,))}
    result = []
    for key, name in SOURCE_NAMES.items():
        row = existing.get(key, {})
        result.append({"source_key": key, "display_name": name, "enabled": row.get("enabled", True),
                       "last_success_at": row.get("last_success_at"), "last_attempt_at": row.get("last_attempt_at"),
                       "consecutive_failures": row.get("consecutive_failures", 0), "last_error": row.get("last_error")})
    db.close()
    return ok(result)


@router.post("/sources/{source_key}/scan")
def scan_source(source_key: str, project_id: str, user: dict = Depends(get_current_user)):
    return _scan_source(source_key, project_id, user)


def _scan_source(source_key: str, project_id: str, user: dict, retry_of_snapshot_id: str | None = None):
    fetcher = RANKING_FETCHERS.get(source_key)
    if not fetcher:
        raise HTTPException(404, "unknown ranking source")
    db = connect()
    require_member(db, project_id, user, write=True)
    source_id = new_id()
    db.execute(
        """INSERT INTO ranking_sources (id, project_id, source_key, display_name)
           VALUES (%s,%s,%s,%s) ON CONFLICT(project_id, source_key) DO UPDATE SET updated_at=now()
           RETURNING id""",
        (source_id, project_id, source_key, SOURCE_NAMES[source_key]),
    )
    source_id = db.fetchone()["id"]
    db.execute("UPDATE ranking_sources SET last_attempt_at=now(), updated_at=now() WHERE id=%s", (source_id,))
    try:
        result = fetcher()
    except Exception as exc:
        result = [{"source": source_key, "error": str(exc), "degraded": True}]
    error_item = next((item for item in result if item.get("error")), None)
    normalized = normalize_ranking_items(source_key, result)
    snapshot_id = new_id()
    if error_item or not normalized:
        error = (error_item or {}).get("error", "source returned no ranking items")
        db.execute("""INSERT INTO ranking_snapshots (id,project_id,source_id,status,error,retry_of_snapshot_id)
                      VALUES (%s,%s,%s,'failed',%s,%s)""",
                   (snapshot_id, project_id, source_id, error, retry_of_snapshot_id))
        db.execute("""UPDATE ranking_sources SET last_error=%s, consecutive_failures=consecutive_failures+1,
                      updated_at=now() WHERE id=%s""", (error, source_id))
        db.commit(); db.close()
        raise HTTPException(502, {"code": "RANKING_SOURCE_FAILED", "source": source_key,
                                  "snapshot_id": snapshot_id, "reason": error})
    db.execute("""INSERT INTO ranking_snapshots (id,project_id,source_id,status,item_count,retry_of_snapshot_id)
                  VALUES (%s,%s,%s,'succeeded',%s,%s)""",
               (snapshot_id, project_id, source_id, len(normalized), retry_of_snapshot_id))
    for item in normalized:
        db.execute(
            """INSERT INTO ranking_items
               (id,snapshot_id,rank_no,title,author,category,source_url,metrics,fetched_at,external_id,dedupe_key)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (new_id(), snapshot_id, item["rank_no"], item["title"], item["author"], item["category"],
             item["source_url"], encode(item["metrics"]), item["fetched_at"], item["external_id"], item["dedupe_key"]),
        )
    db.execute("""UPDATE ranking_sources SET last_success_at=now(), last_error=NULL, consecutive_failures=0,
                  updated_at=now() WHERE id=%s""", (source_id,))
    db.commit(); db.close()
    return ok({"snapshot_id": snapshot_id, "source": source_key, "item_count": len(normalized),
               "raw_count": len(result), "dropped_count": len(result) - len(normalized), "status": "succeeded"})


@router.get("/snapshots")
def list_snapshots(project_id: str, user: dict = Depends(get_current_user)):
    db = connect(); require_member(db, project_id, user)
    data = rows(db, """SELECT rs.*, src.source_key, src.display_name FROM ranking_snapshots rs
                         JOIN ranking_sources src ON src.id=rs.source_id
                         WHERE rs.project_id=%s ORDER BY rs.captured_at DESC LIMIT 50""", (project_id,))
    db.close(); return ok(data)


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str, user: dict = Depends(get_current_user)):
    db = connect()
    snapshot = db.execute("SELECT * FROM ranking_snapshots WHERE id=%s", (snapshot_id,)).fetchone()
    if not snapshot: db.close(); raise HTTPException(404, "snapshot not found")
    require_member(db, snapshot["project_id"], user)
    items = rows(db, "SELECT * FROM ranking_items WHERE snapshot_id=%s ORDER BY rank_no", (snapshot_id,))
    data = {**dict(snapshot), "items": items}; db.close(); return ok(data)


@router.post("/snapshots/{snapshot_id}/retry")
def retry_snapshot(snapshot_id: str, user: dict = Depends(get_current_user)):
    db = connect()
    snapshot = db.execute("""SELECT rs.*, src.source_key FROM ranking_snapshots rs
                             JOIN ranking_sources src ON src.id=rs.source_id WHERE rs.id=%s""", (snapshot_id,)).fetchone()
    if not snapshot:
        db.close(); raise HTTPException(404, "snapshot not found")
    require_member(db, snapshot["project_id"], user, write=True)
    if snapshot["status"] != "failed":
        db.close(); raise HTTPException(409, "only failed snapshots can be retried")
    project_id, source_key = snapshot["project_id"], snapshot["source_key"]
    db.close()
    return _scan_source(source_key, project_id, user, retry_of_snapshot_id=snapshot_id)


@router.post("/snapshots/{snapshot_id}/analyze")
def analyze_snapshot(snapshot_id: str, user: dict = Depends(get_current_user)):
    db = connect()
    snapshot = db.execute("SELECT * FROM ranking_snapshots WHERE id=%s", (snapshot_id,)).fetchone()
    if not snapshot: db.close(); raise HTTPException(404, "snapshot not found")
    require_member(db, snapshot["project_id"], user, write=True)
    existing = db.execute("SELECT * FROM market_analyses WHERE snapshot_id=%s ORDER BY created_at DESC LIMIT 1", (snapshot_id,)).fetchone()
    if existing:
        candidates = rows(db, "SELECT * FROM topic_candidates WHERE analysis_id=%s ORDER BY market_score DESC", (existing["id"],))
        data = {"analysis_id": existing["id"], "summary": existing["summary"], "signals": existing["signals"],
                "candidates": candidates, "status": "already_analyzed"}
        db.close(); return ok(data)
    items = rows(db, "SELECT * FROM ranking_items WHERE snapshot_id=%s ORDER BY rank_no", (snapshot_id,))
    if not items: db.close(); raise HTTPException(409, "snapshot has no items")
    categories = Counter(item.get("category") or "未分类" for item in items)
    authors = Counter(item.get("author") or "未知" for item in items)
    signals = {"top_categories": categories.most_common(5), "repeat_authors": authors.most_common(5),
               "sample_size": len(items), "title_lengths": [len(item["title"]) for item in items]}
    summary = f"样本 {len(items)} 本；主要题材：" + "、".join(k for k, _ in categories.most_common(3))
    analysis_id = new_id()
    db.execute("INSERT INTO market_analyses (id,project_id,snapshot_id,summary,signals) VALUES (%s,%s,%s,%s,%s)",
               (analysis_id, snapshot["project_id"], snapshot_id, summary, encode(signals)))
    seed_titles = [item["title"] for item in items[:3]]
    candidates = []
    for index, angle in enumerate(("身份反差与成长", "规则危机与逆袭", "群像竞争与长期悬念"), 1):
        candidate_id = new_id()
        genre = categories.most_common(1)[0][0]
        title = f"{genre}原创选题 {index}"
        premise = f"从榜单共性中提取“{angle}”市场信号，重新构造人物、世界和冲突；不复用样本《{'》《'.join(seed_titles)}》的表达与情节。"
        score = 86 - index * 3
        db.execute("""INSERT INTO topic_candidates (id,project_id,analysis_id,title,premise,genre,market_score)
                      VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                   (candidate_id, snapshot["project_id"], analysis_id, title, premise, genre, score))
        candidates.append({"id": candidate_id, "title": title, "premise": premise, "genre": genre, "market_score": score})
    db.commit(); db.close()
    return ok({"analysis_id": analysis_id, "summary": summary, "signals": signals, "candidates": candidates})


@router.get("/topics")
def list_topics(project_id: str, user: dict = Depends(get_current_user)):
    db = connect(); require_member(db, project_id, user)
    data = rows(db, "SELECT * FROM topic_candidates WHERE project_id=%s ORDER BY created_at DESC", (project_id,))
    db.close(); return ok(data)


@router.get("/library/books")
def list_books(project_id: str, limit: int = 100, offset: int = 0,
               user: dict = Depends(get_current_user)):
    db = connect(); require_member(db, project_id, user)
    data = rows(db, """SELECT id,project_id,type,title,meta,status,updated_at FROM contents
                         WHERE project_id=%s AND type='novel' AND is_deleted=FALSE
                         ORDER BY updated_at DESC LIMIT %s OFFSET %s""", (project_id, min(limit, 200), max(offset, 0)))
    db.close(); return ok(data)


@router.post("/topics/{topic_id}/generate-book")
def generate_book(topic_id: str, payload: CreateBookRequest, request: Request,
                  user: dict = Depends(get_current_user)):
    db = connect()
    topic = db.execute("SELECT * FROM topic_candidates WHERE id=%s", (topic_id,)).fetchone()
    if not topic: db.close(); raise HTTPException(404, "topic not found")
    require_member(db, topic["project_id"], user, write=True)
    if topic.get("novel_id"):
        novel_id = topic["novel_id"]
        existing_run = db.execute("SELECT id FROM workflow_runs WHERE novel_id=%s ORDER BY created_at DESC LIMIT 1", (novel_id,)).fetchone()
        db.close()
        if existing_run:
            return ok({"novel_id": novel_id, "run_id": existing_run["id"], "status": "already_created"})
        if not payload.auto_start:
            return ok({"novel_id": novel_id, "run_id": None, "status": "planning"})
        from app.workers.tasks import create_run
        try:
            run_id = create_run(topic["project_id"], novel_id, request.headers.get("X-Api-Key", ""),
                                request.headers.get("X-Api-Base-Url", ""), request.headers.get("X-Model", ""),
                                selected_title=topic["title"])
            return ok({"novel_id": novel_id, "run_id": run_id, "status": "generating"})
        except Exception as exc:
            return ok({"novel_id": novel_id, "run_id": None, "status": "planning", "warning": f"book created but workflow unavailable: {exc}"})
    novel_id = new_id(); meta = {"idea": topic["premise"], "genre": topic["genre"], "style": payload.style,
        "target_words": payload.target_words, "selected_title": topic["title"], "source_type": "ranking_topic",
        "source_ref_id": topic_id}
    db.execute("""INSERT INTO contents (id,project_id,type,title,body,meta,status,owner_id)
                  VALUES (%s,%s,'novel',%s,%s,%s,'planning',%s)""",
               (novel_id, topic["project_id"], topic["title"], encode({"type":"doc","content":[]}), encode(meta), user["id"]))
    db.execute("UPDATE topic_candidates SET status='generating', novel_id=%s WHERE id=%s", (novel_id, topic_id))
    db.commit(); db.close()
    run_id = None
    if payload.auto_start:
        from app.workers.tasks import create_run
        try:
            run_id = create_run(topic["project_id"], novel_id, request.headers.get("X-Api-Key", ""),
                                request.headers.get("X-Api-Base-Url", ""), request.headers.get("X-Model", ""),
                                selected_title=topic["title"])
        except Exception as exc:
            return ok({"novel_id": novel_id, "run_id": None, "status": "planning",
                       "warning": f"book created but workflow unavailable: {exc}"})
    return ok({"novel_id": novel_id, "run_id": run_id, "status": "generating" if run_id else "planning"})
