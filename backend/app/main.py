import json
import os
import secrets
from typing import Any

from contextlib import asynccontextmanager

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .core.security import get_current_user
from .db import connect, decode, encode, init_db, new_id, row_to_dict
from .gateway import BudgetExceeded, ProviderError, complete
from .config import settings
from .schemas import (
    AiEditRequest,
    AiOperation,
    ApiResponse,
    ContentUpdate,
    HumanConfirm,
    NovelCreate,
    ShortStoryCreate,
    VersionRestore,
)
from .workers.tasks import confirm_human, create_run
from .api.v1.auth import router as auth_router
from .api.v1.config import router as config_router
from .api.v1.short_story import router as short_story_router
from .api.v1.dag_exec import router as dag_exec_router
from .api.v1.knowledge import router as knowledge_router
from .api.v1.hotspots import router as hotspots_router
from .api.v1.publish_schedule import router as publish_schedule_router
from .api.v1.overseas import router as overseas_router
from .api.v1.batch_endpoints import router as batch_router
from .api.v1.complete_api import router as complete_router
from .api.v1.ranking import router as ranking_router
from .api.v1.fusion import router as fusion_router
from .core.logging_config import setup_logging, get_logger
from .core.rate_limit import install_rate_limiter, limiter

setup_logging()
logger = get_logger(__name__)

from .core.observability import init_metrics, init_sentry  # noqa: E402

init_sentry("fastapi")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="NovelCraft Personal Studio API", version="2.2.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(short_story_router)
app.include_router(dag_exec_router)
app.include_router(knowledge_router)
app.include_router(hotspots_router)
app.include_router(publish_schedule_router)
app.include_router(overseas_router)
app.include_router(batch_router)
app.include_router(complete_router)
app.include_router(ranking_router)
app.include_router(fusion_router, prefix="/api/v1")
init_metrics(app)
install_rate_limiter(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def csrf_guard(request: Request, call_next):
    """Protect unsafe requests authenticated by the refresh cookie."""
    public_auth_paths = {"/api/v1/auth/login", "/api/v1/auth/register"}
    if (
        request.method not in {"GET", "HEAD", "OPTIONS"}
        and request.url.path not in public_auth_paths
        and request.cookies.get("refresh_token")
    ):
        cookie_token = request.cookies.get("csrf_token")
        header_token = request.headers.get("X-CSRF-Token")
        if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
            return JSONResponse({"code": "CSRF_FAILED", "message": "CSRF 校验失败", "data": None}, status_code=403)
    return await call_next(request)


@app.middleware("http")
async def metrics_guard(request: Request, call_next):
    """Keep operational metrics private even when explicitly enabled."""
    if request.url.path == "/metrics":
        expected = os.getenv("METRICS_TOKEN", "").strip()
        supplied = request.headers.get("Authorization", "")
        if not expected or not secrets.compare_digest(supplied, f"Bearer {expected}"):
            return JSONResponse({"detail": "not found"}, status_code=404)
    return await call_next(request)

# Middleware: capture X-Api-* headers for this request
@app.middleware("http")
async def capture_api_key(request: Request, call_next):
    from app.gateway import _request_api_key, _request_api_base_url, _request_model
    from app.core.url_security import validate_ai_base_url
    tokens = []
    key = request.headers.get("X-Api-Key")
    if key:
        tokens.append((_request_api_key, _request_api_key.set(key)))
    base_url = request.headers.get("X-Api-Base-Url")
    if base_url:
        if not key:
            return JSONResponse({"detail": "X-Api-Base-Url requires request-scoped X-Api-Key"}, status_code=400)
        try:
            base_url = validate_ai_base_url(base_url)
        except ValueError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        tokens.append((_request_api_base_url, _request_api_base_url.set(base_url)))
    model = request.headers.get("X-Model")
    if model:
        tokens.append((_request_model, _request_model.set(model)))
    try:
        return await call_next(request)
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)


def ok(data: Any = None) -> ApiResponse:
    return ApiResponse(data=data)


def parse_content(row: dict[str, Any]) -> dict[str, Any]:
    row["body"] = decode(row["body"], {})
    row["meta"] = decode(row["meta"], {})
    return row


class BatchChapterRequest(BaseModel):
    chapter_count: int = Field(default=10, ge=1, le=50)


class ProjectCreate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str = Field(default="", max_length=2000)


class AgentExecuteRequest(BaseModel):
    project_id: str
    variables: dict[str, Any] = Field(default_factory=dict)
    client_mutation_id: str | None = Field(default=None, max_length=100)


def ensure_project_member(conn, project_id: str, user: dict, roles: set[str] | None = None) -> dict:
    member = conn.execute(
        "SELECT role FROM project_members WHERE project_id = %s AND user_id = %s",
        (project_id, user["id"]),
    ).fetchone()
    if not member:
        raise HTTPException(status_code=403, detail="not a project member")
    if roles and member["role"] not in roles:
        raise HTTPException(status_code=403, detail="insufficient permissions")
    return dict(member)


def load_content_for_user(content_id: str, user: dict, roles: set[str] | None = None) -> tuple[Any, dict]:
    conn = connect()
    content = row_to_dict(conn.execute("SELECT * FROM contents WHERE id = %s", (content_id,)).fetchone())
    if content is None:
        conn.close()
        raise HTTPException(status_code=404, detail="content not found")
    try:
        ensure_project_member(conn, content["project_id"], user, roles)
    except Exception:
        conn.close()
        raise
    return conn, content


def load_run_for_user(run_id: str, user: dict, roles: set[str] | None = None) -> tuple[Any, dict]:
    conn = connect()
    run = row_to_dict(conn.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,)).fetchone())
    if run is None:
        conn.close()
        raise HTTPException(status_code=404, detail="run not found")
    try:
        ensure_project_member(conn, run["project_id"], user, roles)
    except Exception:
        conn.close()
        raise
    return conn, run


@app.get("/api/v1/healthz")
def healthz() -> ApiResponse:
    checks = {"status": "ok", "ai_provider": settings.ai_provider,
              # BUG-07: lets the UI warn before a keyless bootstrap fails.
              # Boolean only — never the key material.
              "ai_key_configured": bool(settings.deepseek_api_key)}
    try:
        conn = connect()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
    try:
        import redis
        r = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            socket_connect_timeout=2,
        )
        r.ping()
        checks["redis"] = "ok"
        # QA-001 follow-up: a dead Celery worker previously looked healthy here
        # while every async run sat pending forever. Surface worker liveness
        # (heartbeat keys kept by celery's redis transport) and queue depth.
        try:
            queue_depth = int(r.llen("celery"))
            checks["queue_depth"] = queue_depth
            worker_keys = r.keys("_kombu.binding.celery*")
            from .workers.celery_app import celery_app as _celery
            replies = _celery.control.inspect(timeout=1.0).ping() or {}
            if replies:
                checks["worker"] = f"ok: {len(replies)} online"
            elif queue_depth > 0 or worker_keys:
                checks["worker"] = "error: no worker responding (queue exists but nothing consumes it)"
            else:
                checks["worker"] = "error: no worker responding"
        except Exception as worker_exc:  # inspection is best-effort, never 500s healthz
            checks["worker"] = f"error: {worker_exc}"
        r.close()
    except Exception as e:
        checks["redis"] = f"error: {e}"
    return ok(checks)


@app.get("/api/v1/projects")
def list_projects(user: dict = Depends(get_current_user)) -> ApiResponse:
    conn = connect()
    rows = [dict(row) for row in conn.execute(
        "SELECT p.* FROM projects p JOIN project_members pm ON p.id = pm.project_id WHERE pm.user_id = %s ORDER BY p.created_at DESC",
        (user["id"],),
    ).fetchall()]
    conn.close()
    return ok(rows)


@app.post("/api/v1/projects")
def create_project(payload: ProjectCreate | None = Body(default=None), name: str = "新项目",
                   user: dict = Depends(get_current_user)) -> ApiResponse:
    # Prefer the request body's name; fall back to the ?name= query param so older
    # callers keep working. Ignoring a provided name was BUG-006.
    body_name = payload.name.strip() if payload and payload.name and payload.name.strip() else ""
    project_name = body_name or name
    description = payload.description if payload else ""
    conn = connect()
    pid = new_id()
    conn.execute(
        "INSERT INTO projects (id, name, description, owner_id) VALUES (%s, %s, %s, %s)",
        (pid, project_name, description, user["id"]),
    )
    conn.execute(
        "INSERT INTO project_members (id, project_id, user_id, role) VALUES (%s, %s, %s, 'owner') ON CONFLICT DO NOTHING",
        (new_id(), pid, user["id"]),
    )
    conn.commit()
    row = dict(conn.execute("SELECT * FROM projects WHERE id = %s", (pid,)).fetchone())
    conn.close()
    return ok(row)


@app.post("/api/v1/projects/{project_id}/novels")
def create_novel(project_id: str, payload: NovelCreate, user: dict = Depends(get_current_user)) -> ApiResponse:
    conn = connect()
    project = row_to_dict(conn.execute("SELECT * FROM projects WHERE id = %s", (project_id,)).fetchone())
    if project is None:
        conn.close()
        raise HTTPException(status_code=404, detail="project not found")
    ensure_project_member(conn, project_id, user, {"owner", "editor"})
    novel_id = new_id("cnt")
    title = payload.idea[:26] + ("..." if len(payload.idea) > 26 else "")
    body = {"type": "doc", "content": []}
    meta = payload.model_dump()
    conn.execute(
        """
        INSERT INTO contents (id, project_id, type, title, body, meta, status)
        VALUES (%s, %s, 'novel', %s ,%s, %s, 'draft')
        """,
        (novel_id, project_id, title, encode(body), encode(meta)),
    )
    conn.execute(
        "INSERT INTO versions (id, entity_type, entity_id, label, snapshot) VALUES (%s, 'content', %s, 'initial_idea', %s)",
        (new_id("ver"), novel_id, encode({"title": title, "body": body, "meta": meta})),
    )
    conn.commit()
    novel = parse_content(dict(conn.execute("SELECT * FROM contents WHERE id = %s", (novel_id,)).fetchone()))
    conn.close()
    return ok(novel)


@app.get("/api/v1/contents")
def list_contents(project_id: str = Query(...), parent_id: str | None = None,
                  limit: int = Query(50, le=200), offset: int = Query(0, ge=0),
                  user: dict = Depends(get_current_user)) -> ApiResponse:
    conn = connect()
    # Verify project membership
    member = conn.execute(
        "SELECT 1 FROM project_members WHERE project_id = %s AND user_id = %s",
        (project_id, user["id"]),
    ).fetchone()
    if not member:
        conn.close()
        raise HTTPException(status_code=403, detail="not a project member")
    if parent_id is None:
        rows = conn.execute(
            "SELECT * FROM contents WHERE project_id = %s AND parent_id IS NULL ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (project_id, limit, offset),
    ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM contents WHERE project_id = %s AND parent_id = %s ORDER BY created_at ASC LIMIT %s OFFSET %s",
            (project_id, parent_id, limit, offset),
        ).fetchall()
    items = [parse_content(dict(row)) for row in rows]
    conn.close()
    return ok(items)


@app.get("/api/v1/contents/{content_id}")
def get_content(content_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    conn, row = load_content_for_user(content_id, user)
    conn.close()
    return ok(parse_content(row))


@app.put("/api/v1/contents/{content_id}")
def update_content(content_id: str, payload: ContentUpdate, user: dict = Depends(get_current_user)) -> ApiResponse:
    conn, row = load_content_for_user(content_id, user, {"owner", "editor"})
    row = conn.execute("SELECT * FROM contents WHERE id = %s FOR UPDATE", (content_id,)).fetchone()
    snapshot = {"title": row["title"], "body": decode(row["body"], {}), "meta": decode(row["meta"], {})}
    if payload.client_mutation_id:
        existing = conn.execute(
            "SELECT id, reason FROM versions WHERE client_mutation_id = %s",
            (payload.client_mutation_id,),
        ).fetchone()
        if existing:
            current = parse_content(dict(row))
            current["sync_status"] = "conflict" if existing["reason"] == "offline_conflict" else "applied"
            current["mutation_replayed"] = True
            current["conflict_version_id"] = existing["id"] if existing["reason"] == "offline_conflict" else None
            conn.close()
            return ok(current)

    latest = conn.execute(
        "SELECT id, reason FROM versions WHERE entity_type = 'content' AND entity_id = %s ORDER BY created_at DESC LIMIT 1",
        (content_id,),
    ).fetchone()
    parent_version_id = latest["id"] if latest else None
    if payload.base_updated_at and payload.base_updated_at != row["updated_at"]:
        conflict_version_id = new_id("ver")
        incoming = {
            "title": payload.title if payload.title is not None else snapshot["title"],
            "body": payload.body if payload.body is not None else snapshot["body"],
            "meta": payload.meta if payload.meta is not None else snapshot["meta"],
        }
        conn.execute(
            """
            INSERT INTO versions (
                id, entity_type, entity_id, parent_version_id, label, snapshot,
                reason, author_id, client_mutation_id
            ) VALUES (%s, 'content', %s, %s, 'offline_conflict', %s, 'offline_conflict', %s, %s)
            """,
            (conflict_version_id, content_id, parent_version_id, encode(incoming), user["id"], payload.client_mutation_id),
        )
        conn.commit()
        current = parse_content(dict(row))
        current["sync_status"] = "conflict"
        current["conflict_version_id"] = conflict_version_id
        conn.close()
        return ok(current)

    conn.execute(
        """
        INSERT INTO versions (
            id, entity_type, entity_id, parent_version_id, label, snapshot,
            reason, author_id, client_mutation_id
        ) VALUES (%s, 'content', %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            new_id("ver"), content_id, parent_version_id, payload.label, encode(snapshot),
            "offline_sync" if payload.client_mutation_id else "manual", user["id"], payload.client_mutation_id,
        ),
    )
    if latest and latest.get("reason") == "offline_conflict":
        conn.execute("UPDATE versions SET reason = 'offline_conflict_resolved' WHERE id = %s", (latest["id"],))
    title = payload.title if payload.title is not None else row["title"]
    body = payload.body if payload.body is not None else snapshot["body"]
    meta = payload.meta if payload.meta is not None else snapshot["meta"]
    conn.execute(
        "UPDATE contents SET title = %s, body = %s, meta = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (title, encode(body), encode(meta), content_id),
    )
    conn.commit()
    updated = parse_content(dict(conn.execute("SELECT * FROM contents WHERE id = %s", (content_id,)).fetchone()))
    if payload.client_mutation_id:
        updated["sync_status"] = "applied"
    conn.close()
    return ok(updated)


@app.post("/api/v1/novels/{novel_id}/bootstrap")
@limiter.limit("10/minute")
async def bootstrap_novel(request: Request, novel_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    conn, novel = load_content_for_user(novel_id, user, {"owner", "editor"})
    conn.close()
    if novel["type"] != "novel":
        raise HTTPException(status_code=400, detail="content is not a novel")
    run_id = create_run(novel["project_id"], novel_id,
                        api_key=request.headers.get("X-Api-Key", ""),
                        api_url=request.headers.get("X-Api-Base-Url", ""),
                        model=request.headers.get("X-Model", ""))
    return ok({"run_id": run_id})


@app.post("/api/v1/novels/{novel_id}/continue")
@limiter.limit("10/minute")
async def continue_novel(request: Request, novel_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    """M2: Generate next chapter for an existing novel."""
    conn, novel = load_content_for_user(novel_id, user, {"owner", "editor"})
    conn.close()
    if novel["type"] != "novel":
        raise HTTPException(status_code=400, detail="content is not a novel")
    from .workers.tasks import gen_next_chapter_task
    result = gen_next_chapter_task.delay(novel_id, novel["project_id"],
                                         api_key=request.headers.get("X-Api-Key", ""),
                                         api_url=request.headers.get("X-Api-Base-Url", ""),
                                         model=request.headers.get("X-Model", ""))
    return ok({"task_id": result.id, "novel_id": novel_id, "status": "dispatched"})


@app.post("/api/v1/novels/{novel_id}/expand-outline")
@limiter.limit("10/minute")
async def expand_outline(request: Request, novel_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    """M2: Expand volume outline into chapter-level outlines."""
    conn, novel = load_content_for_user(novel_id, user, {"owner", "editor"})
    conn.close()
    if novel["type"] != "novel":
        raise HTTPException(status_code=400, detail="content is not a novel")
    from .workers.tasks import expand_outline_task
    result = expand_outline_task.delay(novel_id, novel["project_id"])
    return ok({"task_id": result.id, "novel_id": novel_id, "status": "dispatched"})


@app.post("/api/v1/novels/{novel_id}/chapters/batch")
@limiter.limit("5/minute")
async def batch_generate_chapters(
    request: Request,
    novel_id: str,
    payload: BatchChapterRequest,
    user: dict = Depends(get_current_user),
) -> ApiResponse:
    """Queue 1-50 chapters and persist cancellation/progress state."""
    conn, novel = load_content_for_user(novel_id, user, {"owner", "editor"})
    if novel["type"] != "novel":
        conn.close()
        raise HTTPException(status_code=400, detail="content is not a novel")
    batch_id = new_id()
    start_row = conn.execute("""SELECT COALESCE(MAX((meta->>'seq')::int),0)+1 AS start_seq FROM contents
                                WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE""",
                             (novel_id,)).fetchone()
    start_seq = int((start_row or {}).get("start_seq") or 1)
    conn.execute(
        """INSERT INTO generation_batches
           (id,project_id,novel_id,requested_count,start_seq,quality_status)
           VALUES (%s,%s,%s,%s,%s,'in_progress')""",
        (batch_id, novel["project_id"], novel_id, payload.chapter_count, start_seq),
    )
    conn.commit()
    conn.close()
    from .workers.tasks import batch_generate_chapters_task
    try:
        task = batch_generate_chapters_task.delay(
            batch_id,
            api_key=request.headers.get("X-Api-Key", ""),
            api_url=request.headers.get("X-Api-Base-Url", ""),
            model=request.headers.get("X-Model", ""),
        )
    except Exception as exc:
        conn = connect()
        conn.execute(
            "UPDATE generation_batches SET status = 'failed', updated_at = now() WHERE id = %s",
            (batch_id,),
        )
        conn.commit()
        conn.close()
        raise HTTPException(status_code=503, detail="generation queue unavailable") from exc
    conn = connect()
    conn.execute("UPDATE generation_batches SET celery_task_id = %s WHERE id = %s", (task.id, batch_id))
    conn.commit()
    conn.close()
    return ok({"batch_id": batch_id, "task_id": task.id, "status": "pending"})


@app.get("/api/v1/novels/{novel_id}/generation-batches")
def list_novel_generation_batches(novel_id: str, limit: int = 20, offset: int = 0,
                                  user: dict = Depends(get_current_user)) -> ApiResponse:
    conn, novel = load_content_for_user(novel_id, user)
    batches = conn.execute("""SELECT * FROM generation_batches WHERE novel_id=%s
                              ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                           (novel_id, min(max(limit, 1), 100), max(offset, 0))).fetchall()
    conn.close()
    items = []
    for batch in batches:
        requested = max(int(batch.get("requested_count") or 0), 1)
        generated = int(batch.get("generated_count") or 0)
        reviewed = int(batch.get("reviewed_count") or 0)
        accepted = int(batch.get("accepted_count") or 0)
        needs_review = int(batch.get("needs_review_count") or 0)
        legacy = batch.get("status") == "succeeded" and generated == 0 and reviewed == 0 \
            and int(batch.get("completed_count") or 0) > 0
        quality_status = "legacy_unverified" if legacy else (batch.get("quality_status") or "in_progress")
        items.append({**dict(batch), "terminal_count": accepted + needs_review,
                      "generation_percent": round(generated / requested * 100),
                      "review_percent": round(reviewed / generated * 100) if generated else 0,
                      "acceptance_percent": round(accepted / requested * 100),
                      "recoverable": batch.get("status") in {"failed", "pending_provider", "dispatch_failed"},
                      "quality_status": quality_status})
    return ok({"items": items, "count": len(items)})


@app.get("/api/v1/generation-batches/{batch_id}")
def get_generation_batch(batch_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    conn = connect()
    batch = row_to_dict(conn.execute("SELECT * FROM generation_batches WHERE id = %s", (batch_id,)).fetchone())
    if not batch:
        conn.close()
        raise HTTPException(status_code=404, detail="batch not found")
    ensure_project_member(conn, batch["project_id"], user)
    conn.close()
    return ok(batch)


@app.post("/api/v1/generation-batches/{batch_id}/cancel")
def cancel_generation_batch(batch_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    conn = connect()
    batch = row_to_dict(conn.execute("SELECT * FROM generation_batches WHERE id = %s", (batch_id,)).fetchone())
    if not batch:
        conn.close()
        raise HTTPException(status_code=404, detail="batch not found")
    ensure_project_member(conn, batch["project_id"], user, {"owner", "editor"})
    if batch["status"] in {"succeeded", "failed", "cancelled"}:
        conn.close()
        return ok({"batch_id": batch_id, "status": batch["status"]})
    conn.execute(
        "UPDATE generation_batches SET cancel_requested = TRUE, status = 'cancelled', updated_at = now() WHERE id = %s",
        (batch_id,),
    )
    conn.commit()
    conn.close()
    current_ordinal = batch.get("current_ordinal")
    return ok({"batch_id": batch_id, "status": "cancelled", "in_flight": current_ordinal is not None,
               "current_ordinal": current_ordinal,
               "message": "已停止后续槽位；当前正在执行的章节可能完成后才停止" if current_ordinal is not None
                          else "已取消，尚无正在执行的槽位"})


@app.post("/api/v1/generation-batches/{batch_id}/resume")
def resume_generation_batch(request: Request, batch_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    """Re-dispatch an interrupted batch; it continues from completed_count."""
    conn = connect()
    batch = row_to_dict(conn.execute("SELECT * FROM generation_batches WHERE id = %s", (batch_id,)).fetchone())
    if not batch:
        conn.close()
        raise HTTPException(status_code=404, detail="batch not found")
    ensure_project_member(conn, batch["project_id"], user, {"owner", "editor"})
    if batch["status"] not in {"failed", "pending_provider"}:
        conn.close()
        raise HTTPException(status_code=409, detail=f"batch is {batch['status']}, only failed/pending_provider can resume")
    conn.execute(
        "UPDATE generation_batches SET status = 'pending', cancel_requested = FALSE, updated_at = now() WHERE id = %s",
        (batch_id,),
    )
    conn.commit()
    conn.close()
    from .workers.tasks import batch_generate_chapters_task
    try:
        task = batch_generate_chapters_task.delay(
            batch_id,
            api_key=request.headers.get("X-Api-Key", ""),
            api_url=request.headers.get("X-Api-Base-Url", ""),
            model=request.headers.get("X-Model", ""),
        )
    except Exception as exc:
        conn = connect()
        conn.execute(
            "UPDATE generation_batches SET status = %s, error = %s, updated_at = now() WHERE id = %s",
            (batch["status"], f"resume dispatch failed: {exc}", batch_id),
        )
        conn.commit()
        conn.close()
        raise HTTPException(status_code=503, detail="generation queue unavailable") from exc
    conn = connect()
    conn.execute("UPDATE generation_batches SET celery_task_id = %s WHERE id = %s", (task.id, batch_id))
    conn.commit()
    conn.close()
    return ok({"batch_id": batch_id, "task_id": task.id, "status": "pending",
               "completed_count": batch["completed_count"], "requested_count": batch["requested_count"]})


@app.post("/api/v1/projects/{project_id}/short-stories")
@limiter.limit("10/minute")
async def create_short_story(request: Request, project_id: str, payload: ShortStoryCreate,
                             user: dict = Depends(get_current_user)) -> ApiResponse:
    """M3: Create and bootstrap a short story."""
    conn = connect()
    project = row_to_dict(conn.execute("SELECT * FROM projects WHERE id = %s", (project_id,)).fetchone())
    if project is None:
        conn.close()
        raise HTTPException(status_code=404, detail="project not found")
    ensure_project_member(conn, project_id, user, {"owner", "editor"})
    sid = new_id()
    conn.execute(
        "INSERT INTO contents (id, project_id, type, title, body, meta, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (sid, project_id, "short_story", payload.idea[:26], encode({"type":"doc","content":[]}),
         encode(payload.model_dump()), "draft"),
    )
    conn.commit()
    conn.close()
    from .workers.tasks import bootstrap_short_story_task
    result = bootstrap_short_story_task.delay(project_id, sid)
    return ok({"short_id": sid, "task_id": result.id, "status": "dispatched"})


@app.post("/api/v1/contents/{content_id}/fanout")
async def fanout_content(
    content_id: str,
    platforms: str = "wechat,toutiao,xiaohongshu",
    user: dict = Depends(get_current_user),
) -> ApiResponse:
    """M3: Fan-out source content to multiple social platforms."""
    from app.services.social_media import PLATFORMS
    conn, source = load_content_for_user(content_id, user, {"owner", "editor"})

    # Extract source text
    src_body = source.get("body", {})
    src_text = ""
    if isinstance(src_body, dict) and src_body.get("content"):
        src_text = "\n".join(c.get("text", "") for c in src_body["content"] if isinstance(c, dict))

    platform_list = [p.strip() for p in platforms.split(",") if p.strip() in PLATFORMS]
    results = []
    for pkey in platform_list:
        p = PLATFORMS[pkey]
        derived_id = new_id()
        # Generate platform-specific content via AI
        try:
            output = complete(
                run_id=None, node_key=None, project_id=source["project_id"],
                task_type=f"fanout_{pkey}", prompt_name="editor.rewrite",
                variables={"selection": src_text[:3000], "instruction": f"改写为{p['name']}格式: {p['style']}"},
            )
            body = {"type": "doc", "content": [{"type": "paragraph", "text": output.get("text", src_text[:500])}]}
        except (ProviderError, BudgetExceeded) as exc:
            results.append({"platform": pkey, "status": "pending_provider", "error": str(exc)})
            continue

        conn.execute(
            "INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (derived_id, source["project_id"], content_id, p["type"],
             source["title"] + f" ({p['name']}版)", encode(body),
             encode({"platform": pkey, "source_id": content_id, "style": p["style"]}), "draft"),
        )
        conn.execute(
            "INSERT INTO derivations (id, source_content_id, derived_content_id) VALUES (%s,%s,%s)",
            (new_id(), content_id, derived_id),
        )
        results.append({"platform": pkey, "type": p["type"], "derived_id": derived_id,
                        "status": "succeeded"})
    conn.commit()
    conn.close()
    return ok({"fanout_count": len(results), "items": results})


@app.post("/api/v1/contents/{content_id}/video-script")
@limiter.limit("20/minute")
async def generate_video_script(
    request: Request,
    content_id: str,
    platform: str = "douyin",
    user: dict = Depends(get_current_user),
) -> ApiResponse:
    """M3: Generate short video script from content."""
    from app.services.social_media import VIDEO_PLATFORMS
    if platform not in VIDEO_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"unknown platform: {platform}")
    p = VIDEO_PLATFORMS[platform]
    conn, source = load_content_for_user(content_id, user, {"owner", "editor"})
    conn.close()
    # Generate via AI
    from .gateway import complete
    body_text = ""
    if isinstance(source.get("body"), dict):
        body_text = "\n".join(c.get("text","") for c in source["body"].get("content",[]))
    output = complete(run_id=None, node_key=None, project_id=source["project_id"],
                      task_type="gen_video_script", prompt_name="social.gen_video",
                      variables={"body": body_text[:3000], "platform": p["name"], "style": p["style"], "max_duration": p["max_duration"]})
    return ok({"platform": platform, "script": output})


@app.get("/api/v1/runs/{run_id}")
def get_run(run_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    conn, run = load_run_for_user(run_id, user)
    nodes = [dict(row) for row in conn.execute("SELECT * FROM run_nodes WHERE run_id = %s ORDER BY node_key", (run_id,)).fetchall()]
    for node in nodes:
        node["output"] = decode(node["output"], {})
    run["context"] = decode(run["context"], {})
    run["nodes"] = nodes
    conn.close()
    return ok(run)


@app.get("/api/v1/runs/{run_id}/events")
async def run_events(run_id: str, user: dict = Depends(get_current_user)):
    conn, _run = load_run_for_user(run_id, user)
    conn.close()

    async def event_stream():
        import asyncio
        # Cap the long-poll so an abandoned or stuck run can never hold a
        # connection/worker forever; the client reconnects with EventSource.
        MAX_TICKS = int(os.getenv("SSE_RUN_EVENTS_MAX_TICKS", "600"))  # ~10 min at 1s
        seq = 0
        for _tick in range(MAX_TICKS):
            seq += 1
            yield f"id: {seq}\n\n"
            await asyncio.sleep(1)
            conn = connect()
            row = conn.execute("SELECT status FROM workflow_runs WHERE id = %s", (run_id,)).fetchone()
            nodes = conn.execute(
                "SELECT node_key, status, output, error, updated_at FROM run_nodes "
                "WHERE run_id = %s ORDER BY node_key", (run_id,),
            ).fetchall()
            conn.close()
            if row and row["status"] in ("succeeded", "failed", "cancelled"):
                for n in nodes:
                    seq += 1
                    event = dict(n)
                    event["output"] = decode(event.get("output"), {})
                    event["updated_at"] = str(event.get("updated_at") or "")
                    yield f"id: {seq}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                yield f"id: {seq+1}\ndata: {json.dumps({'status': row['status']})}\n\n"
                return
        # Timed out without a terminal state: tell the client to reconnect.
        yield f"id: {seq+1}\ndata: {json.dumps({'status': 'timeout', 'reconnect': True})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/v1/runs/{run_id}/nodes/n2/confirm")
async def confirm_title(request: Request, run_id: str, payload: HumanConfirm, user: dict = Depends(get_current_user)) -> ApiResponse:
    conn, _run = load_run_for_user(run_id, user, {"owner", "editor"})
    conn.close()
    confirm_human(run_id, payload.selected_title,
                  api_key=request.headers.get("X-Api-Key", ""),
                  api_url=request.headers.get("X-Api-Base-Url", ""),
                  model=request.headers.get("X-Model", ""))
    return ok({"run_id": run_id, "selected_title": payload.selected_title})


@app.post("/api/v1/runs/{run_id}/nodes/{node_key}/retry")
async def retry_node(run_id: str, node_key: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    conn, _run = load_run_for_user(run_id, user, {"owner", "editor"})
    conn.execute(
        "UPDATE run_nodes SET status = 'pending', output = '{}', error = NULL WHERE run_id = %s AND node_key = %s",
        (run_id, node_key),
    )
    conn.execute(
        "UPDATE workflow_runs SET status = 'running', current_node_key = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (node_key, run_id),
    )
    conn.commit()
    conn.close()
    from .workers.tasks import execute_bootstrap
    execute_bootstrap.delay(run_id, node_key)
    return ok({"run_id": run_id, "node_key": node_key})


@app.delete("/api/v1/contents/{content_id}")
def delete_content(content_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    """QA-004: soft-delete a content row; deleting a novel cascades to its
    chapters and knowledge items. Versions are retained for recovery."""
    conn, content = load_content_for_user(content_id, user, {"owner", "editor"})
    deleted_children = 0
    if content["type"] == "novel":
        cur = conn.execute(
            "UPDATE contents SET is_deleted = TRUE, updated_at = now() WHERE parent_id = %s AND is_deleted = FALSE",
            (content_id,),
        )
        deleted_children = getattr(cur, "rowcount", 0) or 0
        conn.execute(
            "UPDATE knowledge_items SET is_deleted = TRUE, updated_at = now() WHERE content_id = %s AND is_deleted = FALSE",
            (content_id,),
        )
    conn.execute(
        "UPDATE contents SET is_deleted = TRUE, updated_at = now() WHERE id = %s",
        (content_id,),
    )
    conn.commit()
    conn.close()
    return ok({"deleted": content_id, "type": content["type"], "children_deleted": deleted_children})


@app.delete("/api/v1/novels/{novel_id}")
def delete_novel(novel_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    """QA-004 alias: novels are contents of type 'novel'."""
    conn, content = load_content_for_user(novel_id, user, {"owner", "editor"})
    conn.close()
    if content["type"] != "novel":
        raise HTTPException(status_code=404, detail="novel not found")
    return delete_content(novel_id, user)


@app.get("/api/v1/contents/{content_id}/versions")
def list_versions(content_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    conn, _content = load_content_for_user(content_id, user)
    rows = [dict(row) for row in conn.execute("SELECT * FROM versions WHERE entity_id = %s ORDER BY created_at DESC", (content_id,)).fetchall()]
    for row in rows:
        row["snapshot"] = decode(row["snapshot"], {})
    conn.close()
    return ok(rows)


@app.post("/api/v1/contents/{content_id}/versions/restore")
def restore_version(content_id: str, payload: VersionRestore, user: dict = Depends(get_current_user)) -> ApiResponse:
    conn, _content = load_content_for_user(content_id, user, {"owner", "editor"})
    version = row_to_dict(
        conn.execute("SELECT * FROM versions WHERE id = %s AND entity_id = %s", (payload.version_id, content_id)).fetchone()
    )
    if version is None:
        conn.close()
        raise HTTPException(status_code=404, detail="version not found")
    current = row_to_dict(conn.execute("SELECT * FROM contents WHERE id = %s", (content_id,)).fetchone())
    if current is not None:
        snapshot = {"title": current["title"], "body": decode(current["body"], {}), "meta": decode(current["meta"], {})}
        conn.execute(
            "INSERT INTO versions (id, entity_type, entity_id, label, snapshot) VALUES (%s, 'content', %s, 'before_restore', %s)",
            (new_id("ver"), content_id, encode(snapshot)),
        )
    restored = decode(version["snapshot"], {})
    conn.execute(
        "UPDATE contents SET title = %s, body = %s, meta = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (restored.get("title", "未命名"), encode(restored.get("body", {})), encode(restored.get("meta", {})), content_id),
    )
    conn.commit()
    row = parse_content(dict(conn.execute("SELECT * FROM contents WHERE id = %s", (content_id,)).fetchone()))
    conn.close()
    return ok(row)


@app.post("/api/v1/contents/{content_id}/ai/{op}")
@limiter.limit("30/minute")
def ai_edit(
    request: Request,
    content_id: str,
    op: AiOperation,
    payload: AiEditRequest,
    user: dict = Depends(get_current_user),
) -> ApiResponse:
    conn, content = load_content_for_user(content_id, user, {"owner", "editor"})
    conn.close()
    output = complete(
        run_id=None,
        node_key=None,
        project_id=content["project_id"],
        task_type=f"editor_{op}",
        prompt_name=f"editor.{op}",
        variables={"selection": payload.selection, "instruction": payload.instruction},
        client_mutation_id=payload.client_mutation_id,
    )
    # C5-03: every AI edit leaves a version branch so the tree stays auditable.
    conn = connect()
    conn.execute(
        """INSERT INTO versions (id, entity_type, entity_id, label, snapshot, reason, author_id, client_mutation_id)
           VALUES (%s, 'content', %s, 'ai_edit', %s, %s, %s, %s)
           ON CONFLICT (client_mutation_id) WHERE client_mutation_id IS NOT NULL DO NOTHING""",
        (new_id("ver"), content_id,
         encode({"op": str(op), "selection": payload.selection[:2000],
                 "instruction": payload.instruction[:500], "output": output}),
         f"editor_{op}", user["id"], payload.client_mutation_id),
    )
    conn.commit()
    conn.close()
    return ok(output)


@app.post("/api/v1/contents/{content_id}/ai/{op}/stream")
@limiter.limit("20/minute")
def ai_edit_stream(
    request: Request,
    content_id: str,
    op: AiOperation,
    payload: AiEditRequest,
    user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """SSE streaming variant of ai_edit for pure-text operations.

    Frames: {"delta": str}* then {"done": true, "text": full}; provider/budget
    failures emit a single {"error", "code"} frame instead of an HTTP error so
    the client can fall back to the non-streaming path."""
    from .gateway import BudgetExceeded, ProviderError, complete_stream

    conn, content = load_content_for_user(content_id, user, {"owner", "editor"})
    conn.close()
    project_id = content["project_id"]

    def event_source():
        chunks: list[str] = []
        try:
            for delta in complete_stream(
                project_id=project_id,
                task_type=f"editor_{op}",
                prompt_name=f"editor.{op}",
                variables={"selection": payload.selection, "instruction": payload.instruction},
                client_mutation_id=payload.client_mutation_id,
            ):
                chunks.append(delta)
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
        except (ProviderError, BudgetExceeded) as exc:
            code = "PENDING_BUDGET" if isinstance(exc, BudgetExceeded) else "PROVIDER_FAILED"
            yield f"data: {json.dumps({'error': str(exc), 'code': code}, ensure_ascii=False)}\n\n"
            return
        full_text = "".join(chunks)
        version_conn = connect()
        version_conn.execute(
            """INSERT INTO versions (id, entity_type, entity_id, label, snapshot, reason, author_id, client_mutation_id)
               VALUES (%s, 'content', %s, 'ai_edit', %s, %s, %s, %s)
               ON CONFLICT (client_mutation_id) WHERE client_mutation_id IS NOT NULL DO NOTHING""",
            (new_id("ver"), content_id,
             encode({"op": str(op), "selection": payload.selection[:2000],
                     "instruction": payload.instruction[:500], "output": {"text": full_text}}),
             f"editor_{op}", user["id"], payload.client_mutation_id),
        )
        version_conn.commit()
        version_conn.close()
        yield f"data: {json.dumps({'done': True, 'text': full_text}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/v1/agents/status")
def agents_status(user: dict = Depends(get_current_user)) -> ApiResponse:
    """Real per-agent stats from run_nodes, scoped to the user's projects."""
    conn = connect()
    rows = [dict(r) for r in conn.execute(
        """SELECT rn.agent AS name,
                  COUNT(*) AS task_count,
                  COUNT(*) FILTER (WHERE rn.status = 'running') AS running_count,
                  MAX(COALESCE(rn.finished_at, rn.started_at)) AS last_run
           FROM run_nodes rn
           JOIN workflow_runs wr ON wr.id = rn.run_id
           JOIN project_members pm ON pm.project_id = wr.project_id
           WHERE pm.user_id = %s AND rn.agent IS NOT NULL AND rn.agent != ''
           GROUP BY rn.agent ORDER BY rn.agent""",
        (user["id"],),
    ).fetchall()]
    conn.close()
    return ok([{"name": r["name"],
                "status": "running" if r["running_count"] else "idle",
                "task_count": int(r["task_count"]),
                "last_run": str(r["last_run"]) if r["last_run"] else "--"} for r in rows])


@app.get("/api/v1/ai-calls")
def list_ai_calls(run_id: str | None = None, user: dict = Depends(get_current_user)) -> ApiResponse:
    conn = connect()
    if run_id:
        run = row_to_dict(conn.execute("SELECT project_id FROM workflow_runs WHERE id = %s", (run_id,)).fetchone())
        if run is None:
            conn.close()
            raise HTTPException(status_code=404, detail="run not found")
        ensure_project_member(conn, run["project_id"], user)
        rows = conn.execute("SELECT * FROM ai_calls WHERE run_id = %s ORDER BY created_at DESC", (run_id,)).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT ac.* FROM ai_calls ac
            LEFT JOIN workflow_runs wr ON ac.run_id = wr.id
            JOIN project_members pm ON wr.project_id = pm.project_id
            WHERE pm.user_id = %s
            ORDER BY ac.created_at DESC LIMIT 100
            """,
            (user["id"],),
        ).fetchall()
    items = [dict(row) for row in rows]
    for item in items:
        item["input"] = decode(item["input"], {})
        item["output"] = decode(item["output"], {})
    conn.close()
    return ok(items)


@app.get("/api/v1/prompts")
def list_prompts(user: dict = Depends(get_current_user)) -> ApiResponse:
    conn = connect()
    rows = [dict(row) for row in conn.execute("SELECT * FROM prompts ORDER BY name, version").fetchall()]
    for row in rows:
        row["golden_cases"] = decode(row["golden_cases"], [])
    conn.close()
    return ok(rows)


@app.get("/api/v1/knowledge")
def list_knowledge(
    project_id: str,
    content_id: str | None = None,
    user: dict = Depends(get_current_user),
) -> ApiResponse:
    conn = connect()
    ensure_project_member(conn, project_id, user)
    if content_id:
        rows = conn.execute(
            "SELECT * FROM knowledge_items WHERE project_id = %s AND content_id = %s ORDER BY created_at",
            (project_id, content_id),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM knowledge_items WHERE project_id = %s ORDER BY created_at", (project_id,)).fetchall()
    items = [dict(row) for row in rows]
    for item in items:
        item["meta"] = decode(item["meta"], {})
    conn.close()
    return ok(items)


@app.post("/api/v1/knowledge/search")
def search_knowledge(
    project_id: str,
    query: str = "",
    kind: str = "",
    user: dict = Depends(get_current_user),
) -> ApiResponse:
    """M3: Search knowledge hub."""
    conn = connect()
    ensure_project_member(conn, project_id, user)
    conn.close()
    from .services.knowledge_hub import search
    kinds = [kind] if kind else None
    return ok(search(query, project_id, kinds))


@app.post("/api/v1/knowledge/daily-briefing")
@limiter.limit("10/minute")
def daily_briefing(request: Request, project_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    """M3: Generate daily content briefing from hotspots."""
    conn = connect()
    ensure_project_member(conn, project_id, user, {"owner", "editor"})
    conn.close()
    from .services.hotspot import generate_daily_briefing
    return ok(generate_daily_briefing(project_id))


@app.post("/api/v1/knowledge/style-learn")
async def style_learn(request: Request, user: dict = Depends(get_current_user)) -> ApiResponse:
    """M3: Learn style from sample texts."""
    from .services.style_learn import learn_style
    body = await request.json()
    project_id = body.get("project_id") if isinstance(body, dict) else None
    if project_id:
        conn = connect()
        ensure_project_member(conn, project_id, user, {"owner", "editor"})
        conn.close()
    return ok(learn_style(body.get("samples", body if isinstance(body, list) else [])))


@app.post("/api/v1/knowledge/check-similarity")
async def check_similarity(request: Request, user: dict = Depends(get_current_user)) -> ApiResponse:
    """M3: Check similarity between original and generated text."""
    from .services.style_learn import check_similarity
    body = await request.json()
    project_id = body.get("project_id") if isinstance(body, dict) else None
    if project_id:
        conn = connect()
        ensure_project_member(conn, project_id, user)
        conn.close()
    return ok(check_similarity(body.get("original",""), body.get("generated","")))


@app.post("/api/v1/prompts/lab")
@limiter.limit("20/minute")
def prompt_lab(
    request: Request,
    prompt_name: str,
    input_text: str,
    project_id: str,
    models: str = "deepseek-chat",
    user: dict = Depends(get_current_user),
) -> ApiResponse:
    """M3: Prompt lab — run same input against multiple models and compare."""
    from .gateway import complete
    conn = connect()
    ensure_project_member(conn, project_id, user, {"owner", "editor"})
    conn.close()
    model_list = [m.strip() for m in models.split(",")]
    results = []
    for model in model_list:
        try:
            output = complete(run_id=None, node_key=None, project_id=project_id,
                            task_type="prompt_lab", prompt_name=prompt_name,
                            variables={"input": input_text, "model": model})
            results.append({"model": model, "output": output, "status": "ok"})
        except Exception as e:
            results.append({"model": model, "error": str(e), "status": "error"})
    return ok({"prompt": prompt_name, "models": len(results), "results": results})


@app.post("/api/v1/publish")
@limiter.limit("20/minute")
def publish(
    request: Request,
    content_id: str,
    platform: str,
    mode: str | None = None,
    user: dict = Depends(get_current_user),
) -> ApiResponse:
    """M4: Publish content to a platform."""
    from .services.publish_gateway import publish_content, check_sensitive
    conn, content = load_content_for_user(content_id, user, {"owner", "editor"})
    row = conn.execute("SELECT body FROM contents WHERE id = %s", (content_id,)).fetchone()
    conn.close()
    if row:
        body_text = ""
        if isinstance(row.get("body"), dict):
            body_text = "\n".join(c.get("text","") for c in row["body"].get("content",[]))
        if body_text:
            safety = check_sensitive(body_text[:5000])
            if not safety["passed"]:
                return ok({"blocked": True, "words": safety["blocked_words"]})
    result = publish_content(content_id, platform, mode, user_id=user["id"])
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return ok(result)


@app.post("/api/v1/contents/{content_id}/check-sensitive")
def check_content_sensitive(content_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    """Standalone sensitive-word check so the UI can validate before publishing."""
    from .services.publish_gateway import check_sensitive
    conn, content = load_content_for_user(content_id, user)
    conn.close()
    body = content.get("body")
    body = decode(body, {}) if isinstance(body, str) else (body or {})
    text = "\n".join(c.get("text", "") for c in body.get("content", [])) if isinstance(body, dict) else str(body)
    result = check_sensitive(text[:5000])
    return ok({"passed": result["passed"], "blocked_words": result["blocked_words"], "checked_chars": len(text[:5000])})


@app.get("/api/v1/novels/{novel_id}/narrative")
def get_novel_narrative(novel_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    """Timeline events and character arcs for the review panel — real tables, no fallbacks."""
    conn, novel = load_content_for_user(novel_id, user)
    timeline = [dict(r) for r in conn.execute(
        """SELECT te.event_text AS event, (c.meta->>'seq')::int AS chapter_seq
           FROM timeline_events te JOIN contents c ON c.id = te.chapter_id
           WHERE c.parent_id = %s ORDER BY chapter_seq, te.event_order LIMIT 200""",
        (novel_id,),
    ).fetchall()]
    arcs = [dict(r) for r in conn.execute(
        """SELECT character_name AS character, stage, goal, status
           FROM arcs WHERE novel_id = %s ORDER BY character_name""",
        (novel_id,),
    ).fetchall()]
    conn.close()
    return ok({"timeline": timeline, "arcs": arcs})


@app.get("/api/v1/stats/overview")
def stats_overview(user: dict = Depends(get_current_user)) -> ApiResponse:
    """Real workspace statistics for the settings page (scoped to the user's projects)."""
    conn = connect()
    row = conn.execute(
        """SELECT
             (SELECT COUNT(*) FROM ai_calls a JOIN project_members pm ON pm.project_id = a.project_id
              WHERE pm.user_id = %s) AS ai_calls,
             (SELECT COUNT(*) FROM contents c JOIN project_members pm ON pm.project_id = c.project_id
              WHERE pm.user_id = %s AND c.is_deleted = FALSE) AS contents,
             pg_size_pretty(pg_database_size(current_database())) AS db_size""",
        (user["id"], user["id"]),
    ).fetchone()
    conn.close()
    return ok({"ai_calls": int(row["ai_calls"] or 0), "contents": int(row["contents"] or 0),
               "db_size": row["db_size"]})


@app.post("/api/v1/overseas/translate")
@limiter.limit("20/minute")
def overseas_translate(
    request: Request,
    content_id: str,
    target_lang: str = "en",
    user: dict = Depends(get_current_user),
) -> ApiResponse:
    """M4: Translate content for overseas publishing."""
    from .services.overseas import translate_chapter
    conn, _content = load_content_for_user(content_id, user, {"owner", "editor"})
    row = conn.execute("SELECT body FROM contents WHERE id = %s", (content_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="content not found")
    body_text = ""
    if isinstance(row.get("body"), dict):
        body_text = "\n".join(c.get("text","") for c in row["body"].get("content",[]))
    return ok(translate_chapter(body_text[:8000], target_lang))


@app.get("/api/v1/publish/records")
def publish_records(content_id: str | None = None, user: dict = Depends(get_current_user)) -> ApiResponse:
    """M4: List publish records."""
    from .services.publish_gateway import list_publish_records
    if content_id:
        conn, _content = load_content_for_user(content_id, user)
        conn.close()
        return ok(list_publish_records(content_id))
    conn = connect()
    project_ids = [
        row["project_id"]
        for row in conn.execute("SELECT project_id FROM project_members WHERE user_id = %s", (user["id"],)).fetchall()
    ]
    conn.close()
    return ok(list_publish_records(project_ids=project_ids))


@app.post("/api/v1/collaboration/invite")
def invite_member(
    project_id: str,
    email: str,
    role: str = "editor",
    user: dict = Depends(get_current_user),
) -> ApiResponse:
    """M5: Invite a user to collaborate on a project."""
    from .services.collaboration import invite_user
    conn = connect()
    ensure_project_member(conn, project_id, user, {"owner"})
    conn.close()
    return ok(invite_user(project_id, email, role, invited_by=user["id"]))


@app.get("/api/v1/collaboration/members")
def collaboration_members(project_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    """M5: List project members."""
    from .services.collaboration import list_members
    conn = connect()
    ensure_project_member(conn, project_id, user)
    conn.close()
    return ok(list_members(project_id))


@app.get("/api/v1/collaboration/logs")
def collaboration_logs(project_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    """M5: Get operation logs."""
    from .services.collaboration import get_operation_logs
    conn = connect()
    ensure_project_member(conn, project_id, user)
    conn.close()
    return ok(get_operation_logs(project_id))


@app.get("/api/v1/novels/{novel_id}/foreshadowings")
def list_foreshadowings(novel_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    """TASK-018: List foreshadowings for a novel."""
    conn, _ = load_content_for_user(novel_id, user)
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM foreshadowings WHERE chapter_id IN (SELECT id FROM contents WHERE parent_id = %s) ORDER BY created_at DESC",
        (novel_id,)
    ).fetchall()]
    conn.close()
    return ok(rows)


# --- C3: Agent registry ---

@app.get("/api/v1/agents")
def list_agents_endpoint(user: dict = Depends(get_current_user)) -> ApiResponse:
    """List all registered AI agents with their contracts."""
    from app.services.agent_registry import list_agents
    agents = list_agents()
    return ok({"agents": agents, "count": len(agents)})


@app.get("/api/v1/agents/{agent_id}")
def get_agent_endpoint(agent_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    """Get agent definition by ID."""
    from app.services.agent_registry import get_agent
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")
    return ok({"id": agent_id, **agent})


@app.post("/api/v1/agents/{agent_id}/execute")
@limiter.limit("20/minute")
def execute_agent_endpoint(request: Request, agent_id: str, payload: AgentExecuteRequest,
                           user: dict = Depends(get_current_user)) -> ApiResponse:
    """Execute an Agent contract through the real gateway with project isolation."""
    conn = connect()
    ensure_project_member(conn, payload.project_id, user, {"owner", "editor"})
    conn.close()
    from app.services.agent_registry import execute_agent
    try:
        result = execute_agent(agent_id, payload.project_id, payload.variables,
                               payload.client_mutation_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")
    return ok(result)
