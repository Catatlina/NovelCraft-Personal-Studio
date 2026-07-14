"""M3: Style imitation + batch fanout + scheduled briefing tasks."""
from __future__ import annotations

from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def run_imitation_workflow(self, reference_id: str, novel_id: str) -> dict:
    """TASK-036: Generate a chapter in the style of a reference work."""
    from app.db import connect, row_to_dict
    db = connect()
    ref = row_to_dict(db.execute("SELECT * FROM knowledge_items WHERE id = %s", (reference_id,)).fetchone())
    novel = row_to_dict(db.execute("SELECT * FROM contents WHERE id = %s", (novel_id,)).fetchone())
    db.close()

    if not ref or not novel:
        return {"status": "error", "message": "not found"}

    from app.gateway import complete
    output = complete(
        run_id=None, node_key=None, project_id=novel.get("project_id", ""),
        task_type="style_imitation", prompt_name="style.imitation",
        variables={
            "source_text": str(ref.get("body", ""))[:16000],
            "instruction": f"为《{novel.get('title', 'Untitled')}》生成原创仿写样稿；只学习节奏和语气，不复用原文设定。",
        },
    )
    return {"status": "generated", "title": output.get("title", ""), "has_text": bool(output.get("text"))}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def run_daily_briefing(self, project_id: str = "") -> dict:
    """TASK-038: Generate daily briefing from recent content."""
    from app.db import connect, encode
    from app.gateway import complete
    import datetime as dt

    db = connect()
    recent = db.execute(
        "SELECT title, type FROM contents WHERE project_id = %s ORDER BY updated_at DESC LIMIT 5",
        (project_id,),
    ).fetchall() if project_id else []
    db.close()

    titles = [r.get("title", "") for r in recent]

    if not titles:
        return {"status": "ok", "briefing": "今日无新内容"}

    from app.gateway import _request_api_key, _request_api_base_url, _request_model
    output = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="briefing", prompt_name="editor.rewrite",
        variables={
            "selection": "\n".join(titles),
            "instruction": f"Generate a daily briefing for {dt.date.today()}. Summarize key achievements and suggest next steps. Keep it under 200 words.",
        },
    )
    return {"status": "done", "briefing": output.get("text", "")}


@celery_app.task(bind=True, max_retries=1, default_retry_delay=5)
def run_batch_fanout(self, content_id: str, platforms: list[str]) -> dict:
    """TASK-039: Fan-out to multiple platforms in batch."""
    from app.gateway import complete
    from app.db import connect, encode, new_id
    import json

    db = connect()
    content = db.execute("SELECT * FROM contents WHERE id = %s", (content_id,)).fetchone()
    db.close()

    if not content:
        return {"status": "error", "message": "not found"}

    results = {}
    for platform in platforms:
        try:
            output = complete(
                run_id=None, node_key=None, project_id=content.get("project_id", ""),
                task_type="fanout", prompt_name="editor.rewrite",
                variables={
                    "selection": str(content.get("body", ""))[:3000],
                    "instruction": f"Rewrite for {platform}. Format: {platform}-optimized content.",
                },
            )
            db2 = connect()
            db2.execute(
                "INSERT INTO publish_records (id, content_id, platform, status, result) VALUES (%s,%s,%s,%s,%s)",
                (new_id(), content_id, platform, "draft", encode(output)),
            )
            db2.commit(); db2.close()
            results[platform] = "generated"
        except Exception as e:
            results[platform] = f"error: {str(e)[:60]}"
    return {"status": "done", "results": results}
