from __future__ import annotations

import asyncio
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .core.security import get_current_user
from .db import connect, decode, encode, init_db, new_id, row_to_dict
from .gateway import complete
from .config import settings
from .schemas import (
    AiEditRequest,
    AiOperation,
    ApiResponse,
    BudgetUpdate,
    ContentUpdate,
    HumanConfirm,
    ModelRouteUpdate,
    NovelCreate,
    VersionRestore,
)
from .workers.tasks import confirm_human, create_run
from .api.v1.auth import router as auth_router

app = FastAPI(title="NovelCraft Personal Studio API", version="0.1.0")
app.include_router(auth_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


def ok(data: Any = None) -> ApiResponse:
    return ApiResponse(data=data)


def parse_content(row: dict[str, Any]) -> dict[str, Any]:
    row["body"] = decode(row["body"], {})
    row["meta"] = decode(row["meta"], {})
    return row


@app.get("/api/v1/healthz")
def healthz() -> ApiResponse:
    checks = {"status": "ok", "ai_provider": settings.ai_provider}
    try:
        conn = connect()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, socket_connect_timeout=2)
        r.ping()
        r.close()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
    return ok(checks)


@app.get("/api/v1/projects")
def list_projects() -> ApiResponse:
    conn = connect()
    rows = [dict(row) for row in conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()]
    conn.close()
    return ok(rows)


@app.post("/api/v1/projects/{project_id}/novels")
def create_novel(project_id: str, payload: NovelCreate) -> ApiResponse:
    conn = connect()
    project = row_to_dict(conn.execute("SELECT * FROM projects WHERE id = %s", (project_id,)).fetchone())
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
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
def list_contents(project_id: str = Query(...), parent_id: str | None = None) -> ApiResponse:
    conn = connect()
    if parent_id is None:
        rows = conn.execute(
            "SELECT * FROM contents WHERE project_id = %s AND parent_id IS NULL ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM contents WHERE project_id = %s AND parent_id = %s ORDER BY created_at ASC",
            (project_id, parent_id),
        ).fetchall()
    items = [parse_content(dict(row)) for row in rows]
    conn.close()
    return ok(items)


@app.get("/api/v1/contents/{content_id}")
def get_content(content_id: str) -> ApiResponse:
    conn = connect()
    row = row_to_dict(conn.execute("SELECT * FROM contents WHERE id = %s", (content_id,)).fetchone())
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="content not found")
    return ok(parse_content(row))


@app.put("/api/v1/contents/{content_id}")
def update_content(content_id: str, payload: ContentUpdate) -> ApiResponse:
    conn = connect()
    row = row_to_dict(conn.execute("SELECT * FROM contents WHERE id = %s", (content_id,)).fetchone())
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="content not found")
    snapshot = {"title": row["title"], "body": decode(row["body"], {}), "meta": decode(row["meta"], {})}
    conn.execute(
        "INSERT INTO versions (id, entity_type, entity_id, label, snapshot) VALUES (%s, 'content', %s ,%s, %s)",
        (new_id("ver"), content_id, payload.label, encode(snapshot)),
    )
    title = payload.title if payload.title is not None else row["title"]
    body = payload.body if payload.body is not None else snapshot["body"]
    meta = payload.meta if payload.meta is not None else snapshot["meta"]
    conn.execute(
        "UPDATE contents SET title = %s, body = %s, meta = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (title, encode(body), encode(meta), content_id),
    )
    conn.commit()
    updated = parse_content(dict(conn.execute("SELECT * FROM contents WHERE id = %s", (content_id,)).fetchone()))
    conn.close()
    return ok(updated)


@app.post("/api/v1/novels/{novel_id}/bootstrap")
async def bootstrap_novel(novel_id: str) -> ApiResponse:
    conn = connect()
    novel = row_to_dict(conn.execute("SELECT * FROM contents WHERE id = %s", (novel_id,)).fetchone())
    conn.close()
    if novel is None:
        raise HTTPException(status_code=404, detail="novel not found")
    run_id = create_run(novel["project_id"], novel_id)
    return ok({"run_id": run_id})


@app.post("/api/v1/novels/{novel_id}/continue")
async def continue_novel(novel_id: str) -> ApiResponse:
    """M2: Generate next chapter for an existing novel."""
    conn = connect()
    novel = row_to_dict(conn.execute("SELECT * FROM contents WHERE id = %s AND type = 'novel'", (novel_id,)).fetchone())
    conn.close()
    if novel is None:
        raise HTTPException(status_code=404, detail="novel not found")
    from .workers.tasks import gen_next_chapter_task
    result = gen_next_chapter_task.delay(novel_id, novel["project_id"])
    return ok({"task_id": result.id, "novel_id": novel_id, "status": "dispatched"})


@app.post("/api/v1/novels/{novel_id}/expand-outline")
async def expand_outline(novel_id: str) -> ApiResponse:
    """M2: Expand volume outline into chapter-level outlines."""
    conn = connect()
    novel = row_to_dict(conn.execute("SELECT * FROM contents WHERE id = %s AND type = 'novel'", (novel_id,)).fetchone())
    conn.close()
    if novel is None:
        raise HTTPException(status_code=404, detail="novel not found")
    from .workers.tasks import expand_outline_task
    result = expand_outline_task.delay(novel_id, novel["project_id"])
    return ok({"task_id": result.id, "novel_id": novel_id, "status": "dispatched"})


@app.post("/api/v1/projects/{project_id}/short-stories")
async def create_short_story(project_id: str) -> ApiResponse:
    """M3: Create and bootstrap a short story."""
    conn = connect()
    project = row_to_dict(conn.execute("SELECT * FROM projects WHERE id = %s", (project_id,)).fetchone())
    if project is None:
        conn.close()
        raise HTTPException(status_code=404, detail="project not found")
    sid = new_id()
    conn.execute(
        "INSERT INTO contents (id, project_id, type, title, body, meta, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (sid, project_id, "short_story", "新短篇", encode({"type":"doc","content":[]}),
         encode({"idea": "请基于灵感创作", "template": "viral", "genre": "都市", "style": "现代"}), "draft"),
    )
    conn.commit(); conn.close()
    from .workers.tasks import bootstrap_short_story_task
    result = bootstrap_short_story_task.delay(project_id, sid)
    return ok({"short_id": sid, "task_id": result.id, "status": "dispatched"})


@app.post("/api/v1/contents/{content_id}/fanout")
async def fanout_content(content_id: str, platforms: str = "wechat,toutiao,xiaohongshu") -> ApiResponse:
    """M3: Fan-out source content to multiple social platforms."""
    from app.services.social_media import PLATFORMS
    conn = connect()
    source = row_to_dict(conn.execute("SELECT * FROM contents WHERE id = %s", (content_id,)).fetchone())
    if source is None:
        conn.close()
        raise HTTPException(status_code=404, detail="content not found")

    platform_list = [p.strip() for p in platforms.split(",") if p.strip() in PLATFORMS]
    results = []
    for pkey in platform_list:
        p = PLATFORMS[pkey]
        derived_id = new_id()
        conn.execute(
            "INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (derived_id, source["project_id"], content_id, p["type"],
             source["title"] + f" ({p['name']}版)", encode({"type":"doc","content":[]}),
             encode({"platform": pkey, "source_id": content_id}), "draft"),
        )
        conn.execute(
            "INSERT INTO derivations (id, source_content_id, derived_content_id) VALUES (%s,%s,%s)",
            (new_id(), content_id, derived_id),
        )
        results.append({"platform": pkey, "type": p["type"], "derived_id": derived_id})
    conn.commit(); conn.close()
    return ok({"fanout_count": len(results), "items": results})


@app.post("/api/v1/contents/{content_id}/video-script")
async def generate_video_script(content_id: str, platform: str = "douyin") -> ApiResponse:
    """M3: Generate short video script from content."""
    from app.services.social_media import VIDEO_PLATFORMS
    if platform not in VIDEO_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"unknown platform: {platform}")
    p = VIDEO_PLATFORMS[platform]
    conn = connect()
    source = row_to_dict(conn.execute("SELECT * FROM contents WHERE id = %s", (content_id,)).fetchone())
    conn.close()
    if source is None:
        raise HTTPException(status_code=404, detail="content not found")
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
def get_run(run_id: str) -> ApiResponse:
    conn = connect()
    run = row_to_dict(conn.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,)).fetchone())
    if run is None:
        conn.close()
        raise HTTPException(status_code=404, detail="run not found")
    nodes = [dict(row) for row in conn.execute("SELECT * FROM run_nodes WHERE run_id = %s ORDER BY node_key", (run_id,)).fetchall()]
    for node in nodes:
        node["output"] = decode(node["output"], {})
    run["context"] = decode(run["context"], {})
    run["nodes"] = nodes
    conn.close()
    return ok(run)


@app.get("/api/v1/runs/{run_id}/events")
async def run_events(run_id: str):
    async def event_stream():
        import asyncio
        while True:
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/v1/runs/{run_id}/nodes/n2/confirm")
async def confirm_title(run_id: str, payload: HumanConfirm) -> ApiResponse:
    confirm_human(run_id, payload.selected_title)
    return ok({"run_id": run_id, "selected_title": payload.selected_title})


@app.post("/api/v1/runs/{run_id}/nodes/{node_key}/retry")
async def retry_node(run_id: str, node_key: str) -> ApiResponse:
    conn = connect()
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


@app.get("/api/v1/contents/{content_id}/versions")
def list_versions(content_id: str) -> ApiResponse:
    conn = connect()
    rows = [dict(row) for row in conn.execute("SELECT * FROM versions WHERE entity_id = %s ORDER BY created_at DESC", (content_id,)).fetchall()]
    for row in rows:
        row["snapshot"] = decode(row["snapshot"], {})
    conn.close()
    return ok(rows)


@app.post("/api/v1/contents/{content_id}/versions/restore")
def restore_version(content_id: str, payload: VersionRestore) -> ApiResponse:
    conn = connect()
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
def ai_edit(content_id: str, op: AiOperation, payload: AiEditRequest) -> ApiResponse:
    conn = connect()
    content = row_to_dict(conn.execute("SELECT * FROM contents WHERE id = %s", (content_id,)).fetchone())
    conn.close()
    if content is None:
        raise HTTPException(status_code=404, detail="content not found")
    output = complete(
        run_id=None,
        node_key=None,
        project_id=content["project_id"],
        task_type=f"editor_{op}",
        prompt_name=f"editor.{op}",
        variables={"selection": payload.selection, "instruction": payload.instruction},
    )
    return ok(output)


@app.get("/api/v1/ai-calls")
def list_ai_calls(run_id: str | None = None) -> ApiResponse:
    conn = connect()
    if run_id:
        rows = conn.execute("SELECT * FROM ai_calls WHERE run_id = %s ORDER BY created_at DESC", (run_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM ai_calls ORDER BY created_at DESC LIMIT 100").fetchall()
    items = [dict(row) for row in rows]
    for item in items:
        item["input"] = decode(item["input"], {})
        item["output"] = decode(item["output"], {})
    conn.close()
    return ok(items)


@app.get("/api/v1/prompts")
def list_prompts() -> ApiResponse:
    conn = connect()
    rows = [dict(row) for row in conn.execute("SELECT * FROM prompts ORDER BY name, version").fetchall()]
    for row in rows:
        row["golden_cases"] = decode(row["golden_cases"], [])
    conn.close()
    return ok(rows)


@app.get("/api/v1/model-routes")
def list_model_routes() -> ApiResponse:
    conn = connect()
    rows = [dict(row) for row in conn.execute("SELECT * FROM model_routes ORDER BY task_type").fetchall()]
    for row in rows:
        row["params"] = decode(row["params"], {})
        row["fallback_json"] = decode(row["fallback_json"], [])
    conn.close()
    return ok(rows)


@app.put("/api/v1/model-routes/{task_type}")
def update_model_route(task_type: str, payload: ModelRouteUpdate) -> ApiResponse:
    conn = connect()
    conn.execute(
        """
        INSERT INTO model_routes (id, task_type, provider, model, params, fallback_json)
        VALUES (%s, %s, %s ,%s, %s, '[]')
        ON CONFLICT(task_type)
        DO UPDATE SET provider = excluded.provider, model = excluded.model, params = excluded.params, updated_at = CURRENT_TIMESTAMP
        """,
        (new_id("rte"), task_type, payload.provider, payload.model, encode(payload.params)),
    )
    conn.commit()
    row = dict(conn.execute("SELECT * FROM model_routes WHERE task_type = %s", (task_type,)).fetchone())
    row["params"] = decode(row["params"], {})
    row["fallback_json"] = decode(row["fallback_json"], [])
    conn.close()
    return ok(row)


@app.get("/api/v1/admin/budgets")
def list_budgets(project_id: str) -> ApiResponse:
    conn = connect()
    rows = [dict(row) for row in conn.execute("SELECT * FROM budgets WHERE project_id = %s ORDER BY scope", (project_id,)).fetchall()]
    conn.close()
    return ok(rows)


@app.put("/api/v1/admin/budgets/{project_id}/{scope}")
def update_budget(project_id: str, scope: str, payload: BudgetUpdate) -> ApiResponse:
    conn = connect()
    conn.execute(
        """
        INSERT INTO budgets (id, project_id, scope, limit_cny, spent_cny)
        VALUES (%s, %s, %s ,%s, 0)
        ON CONFLICT(project_id, scope)
        DO UPDATE SET limit_cny = excluded.limit_cny, updated_at = CURRENT_TIMESTAMP
        """,
        (new_id("bdg"), project_id, scope, payload.limit_cny),
    )
    conn.commit()
    row = dict(conn.execute("SELECT * FROM budgets WHERE project_id = %s AND scope = %s", (project_id, scope)).fetchone())
    conn.close()
    return ok(row)


@app.get("/api/v1/knowledge")
def list_knowledge(project_id: str, content_id: str | None = None) -> ApiResponse:
    conn = connect()
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


@app.post("/api/v1/knowledge/daily-briefing")
def daily_briefing(project_id: str) -> ApiResponse:
    """M3: Generate daily content briefing from hotspots."""
    from .services.hotspot import generate_daily_briefing
    return ok(generate_daily_briefing(project_id))
