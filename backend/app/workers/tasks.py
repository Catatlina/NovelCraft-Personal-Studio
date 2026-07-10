"""Celery tasks — workflow execution and scheduled jobs."""
from __future__ import annotations

import time

from app.db import connect, encode, new_id
from app.gateway import BudgetExceeded, ProviderError, complete

from .celery_app import celery_app

BOOTSTRAP_NODES = [
    ("n1", "agent", "StoryArchitect", "生成书名候选", "gen_titles"),
    ("n2", "human", None, "选定书名", None),
    ("n3", "agent", "StoryArchitect", "生成简介卖点", "gen_synopsis"),
    ("n4", "agent", "StoryArchitect", "生成世界观", "gen_worldview"),
    ("n5", "agent", "Character", "生成人物卡", "gen_characters"),
    ("n6", "agent", "StoryArchitect", "生成总纲", "gen_outline"),
    ("n7", "agent", "Writer", "生成第一章", "gen_chapter1"),
    ("n8", "agent", "Reviewer", "七维审核", "review_7dim"),
]


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def execute_bootstrap(self, run_id: str, start_key: str = "n1") -> dict:
    """Execute bootstrap workflow from start_key to human node or completion."""
    start_index = next(i for i, node in enumerate(BOOTSTRAP_NODES) if node[0] == start_key)

    for node_key, kind, agent, title, task_type in BOOTSTRAP_NODES[start_index:]:
        conn = connect()
        node = conn.execute(
            "SELECT * FROM run_nodes WHERE run_id = %s AND node_key = %s",
            (run_id, node_key),
        ).fetchone()
        run = conn.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,)).fetchone()
        if node is None or run is None:
            conn.close()
            return {"status": "error", "detail": "run or node not found"}

        if node["status"] == "succeeded":
            conn.close()
            continue

        if kind == "human":
            conn.execute(
                "UPDATE run_nodes SET status = 'waiting_human', started_at = COALESCE(started_at, now()) WHERE run_id = %s AND node_key = %s",
                (run_id, node_key),
            )
            conn.execute(
                "UPDATE workflow_runs SET status = 'waiting_human', current_node_key = %s, updated_at = now() WHERE id = %s",
                (node_key, run_id),
            )
            conn.commit()
            conn.close()
            celery_app.backend.set(f"run:{run_id}:human", node_key)
            return {"status": "waiting_human", "node_key": node_key}

        conn.execute(
            "UPDATE run_nodes SET status = 'running', attempt = attempt + 1, started_at = now() WHERE run_id = %s AND node_key = %s",
            (run_id, node_key),
        )
        conn.execute(
            "UPDATE workflow_runs SET status = 'running', current_node_key = %s, updated_at = now() WHERE id = %s",
            (node_key, run_id),
        )
        conn.commit()
        conn.close()

        time.sleep(0.3)

        try:
            output = complete(
                run_id=run_id,
                node_key=node_key,
                project_id=run["project_id"],
                task_type=task_type or "",
                prompt_name=f"bootstrap.{task_type}",
                variables=run["context"] if isinstance(run["context"], dict) else {},
            )
        except BudgetExceeded:
            _mark_node(run_id, node_key, "pending_budget", "budget exceeded")
            return {"status": "pending_budget", "node_key": node_key}
        except ProviderError:
            _mark_node(run_id, node_key, "pending_provider", "provider error")
            return {"status": "pending_provider", "node_key": node_key}
        except Exception as exc:
            _mark_node(run_id, node_key, "failed", str(exc))
            try:
                self.retry(exc=exc)
            except Exception:
                pass
            return {"status": "failed", "node_key": node_key, "error": str(exc)}

        _persist_output(run_id, node_key, task_type or "", output)

    conn = connect()
    conn.execute(
        "UPDATE workflow_runs SET status = 'succeeded', current_node_key = NULL, updated_at = now() WHERE id = %s",
        (run_id,),
    )
    conn.commit()
    conn.close()
    celery_app.backend.set(f"run:{run_id}:status", "succeeded")
    return {"status": "succeeded"}


def create_run(project_id: str, novel_id: str) -> str:
    """Create a workflow run and its nodes in the database."""
    db = connect()
    novel = db.execute("SELECT * FROM contents WHERE id = %s", (novel_id,)).fetchone()
    if novel is None:
        db.close()
        raise ValueError("novel not found")
    meta = novel["meta"] if isinstance(novel["meta"], dict) else {}
    context = {"novel_id": novel_id, "idea": meta.get("idea", ""), **meta}
    run_id = new_id()
    db.execute(
        "INSERT INTO workflow_runs (id, project_id, novel_id, workflow_key, status, current_node_key, context) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (run_id, project_id, novel_id, "bootstrap", "pending", "n1", encode(context)),
    )
    for node_key, kind, agent, title, _task_type in BOOTSTRAP_NODES:
        db.execute(
            "INSERT INTO run_nodes (id, run_id, node_key, kind, agent, title) VALUES (%s, %s, %s, %s, %s, %s)",
            (new_id(), run_id, node_key, kind, agent, title),
        )
    db.commit()
    db.close()
    # Dispatch to Celery
    execute_bootstrap.delay(run_id, "n1")
    return run_id


def confirm_human(run_id: str, selected_title: str) -> None:
    """Confirm human node selection and continue workflow."""
    db = connect()
    run = db.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,)).fetchone()
    if run is None:
        db.close()
        raise ValueError("run not found")
    context = run["context"] if isinstance(run["context"], dict) else {}
    context["selected_title"] = selected_title
    db.execute("UPDATE contents SET title = %s, updated_at = now() WHERE id = %s", (selected_title, run["novel_id"]))
    db.execute(
        "UPDATE run_nodes SET status = 'succeeded', output = %s, finished_at = now() WHERE run_id = %s AND node_key = 'n2'",
        (encode({"selected_title": selected_title}), run_id),
    )
    db.execute(
        "UPDATE workflow_runs SET status = 'pending', current_node_key = 'n3', context = %s, updated_at = now() WHERE id = %s",
        (encode(context), run_id),
    )
    db.commit()
    db.close()
    execute_bootstrap.delay(run_id, "n3")


def _mark_node(run_id: str, node_key: str, status: str, error: str) -> None:
    db = connect()
    db.execute(
        "UPDATE run_nodes SET status = %s, error = %s, finished_at = now() WHERE run_id = %s AND node_key = %s",
        (status, error, run_id, node_key),
    )
    db.execute(
        "UPDATE workflow_runs SET status = %s, current_node_key = %s, updated_at = now() WHERE id = %s",
        (status, node_key, run_id),
    )
    db.commit()
    db.close()


def _persist_output(run_id: str, node_key: str, task_type: str, output: dict) -> None:
    db = connect()
    run = db.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,)).fetchone()
    if run is None:
        db.close()
        return
    context = run["context"] if isinstance(run["context"], dict) else {}
    context.update(output)
    novel_id = run["novel_id"]

    if task_type == "gen_titles":
        context["title_candidates"] = output.get("title_candidates", [])
    elif task_type == "gen_synopsis":
        meta = db.execute("SELECT meta FROM contents WHERE id = %s", (novel_id,)).fetchone()
        if meta:
            m = meta["meta"] if isinstance(meta["meta"], dict) else {}
            m.update({"synopsis": output.get("synopsis", ""), "selling_points": output.get("selling_points", [])})
            db.execute("UPDATE contents SET meta = %s, updated_at = now() WHERE id = %s", (encode(m), novel_id))
    elif task_type == "gen_worldview":
        wv = output.get("worldview", {})
        db.execute(
            "INSERT INTO knowledge_items (id, project_id, content_id, kind, title, body, meta) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (new_id(), run["project_id"], novel_id, "worldview", wv.get("name", ""), "\n".join(wv.get("rules", [])), encode(wv)),
        )
    elif task_type == "gen_characters":
        for c in output.get("characters", []):
            db.execute(
                "INSERT INTO knowledge_items (id, project_id, content_id, kind, title, body, meta) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (new_id(), run["project_id"], novel_id, "character", c.get("name", ""), c.get("arc", ""), encode(c)),
            )
    elif task_type == "gen_outline":
        meta = db.execute("SELECT meta FROM contents WHERE id = %s", (novel_id,)).fetchone()
        if meta:
            m = meta["meta"] if isinstance(meta["meta"], dict) else {}
            m["outline"] = output.get("outline", [])
            db.execute("UPDATE contents SET meta = %s, updated_at = now() WHERE id = %s", (encode(m), novel_id))
    elif task_type == "gen_chapter1":
        chapter = output.get("chapter", {})
        body = {"type": "doc", "content": [{"type": "paragraph", "text": t} for t in chapter.get("body", [])]}
        cid = new_id()
        db.execute(
            "INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (cid, run["project_id"], novel_id, "chapter", chapter.get("title", ""), encode(body), encode({"seq": 1}), "reviewed"),
        )
        context["chapter_id"] = cid
        db.execute(
            "INSERT INTO versions (id, entity_type, entity_id, label, snapshot) VALUES (%s, 'content', %s, 'ai_generate', %s)",
            (new_id(), cid, encode({"title": chapter.get("title", ""), "body": body, "meta": {"seq": 1}})),
        )
        # M2: auto-summarize chapter
        _summarize_and_store(db, cid, chapter.get("body", []))

    db.execute(
        "UPDATE run_nodes SET status = 'succeeded', output = %s, finished_at = now() WHERE run_id = %s AND node_key = %s",
        (encode(output), run_id, node_key),
    )
    db.execute(
        "UPDATE workflow_runs SET context = %s, updated_at = now() WHERE id = %s",
        (encode(context), run_id),
    )
    db.commit()
    db.close()


def _summarize_and_store(db, chapter_id: str, body: list) -> None:
    """M2: Generate and store chapter summary after generation."""
    try:
        from app.services.summarizer import summarize_chapter
        texts = []
        for p in body:
            if isinstance(p, dict):
                texts.append(p.get("text", ""))
            elif isinstance(p, str):
                texts.append(p)
        text = "\n".join(texts)
        if not text.strip():
            return
        result = summarize_chapter(chapter_id, text)
        summary = result.get("summary", "")
        if summary:
            db.execute(
                "UPDATE contents SET meta = meta || %s, updated_at = now() WHERE id = %s",
                (encode({"chapter_summary": summary}), chapter_id),
            )
    except Exception:
        pass  # Non-critical, don't block the workflow


@celery_app.task(bind=True, max_retries=2)
def gen_next_chapter_task(self, novel_id: str, project_id: str) -> dict:
    """M2: Generate the next chapter using context assembler."""
    from app.services.assembler import ContextAssembler
    from app.services.entity_tracker import extract_and_store

    db = connect()
    # Find last chapter seq
    last = db.execute(
        "SELECT COALESCE(MAX((meta->>'seq')::int), 0) as seq FROM contents WHERE parent_id = %s AND type='chapter'",
        (novel_id,),
    ).fetchone()
    next_seq = (last["seq"] if last else 0) + 1
    db.close()

    # Build context
    assembler = ContextAssembler(novel_id)
    context = assembler.build()

    # Generate
    output = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="gen_next_chapter", prompt_name="narrative.gen_next_chapter",
        variables={"context": context},
    )

    chapter = output.get("chapter", {})
    body = {"type": "doc", "content": [{"type": "paragraph", "text": t} for t in chapter.get("body", [])]}
    cid = new_id()

    db = connect()
    db.execute(
        "INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (cid, project_id, novel_id, "chapter", chapter.get("title", f"第{next_seq}章"), encode(body), encode({"seq": next_seq}), "draft"),
    )
    db.execute(
        "INSERT INTO versions (id, entity_type, entity_id, label, snapshot) VALUES (%s, 'content', %s, 'ai_generate', %s)",
        (new_id(), cid, encode({"title": chapter.get("title", ""), "body": body, "meta": {"seq": next_seq}})),
    )
    db.commit()

    # Extract entity states
    text = "\n".join(t if isinstance(t, str) else t.get("text", "") for t in chapter.get("body", []))
    extract_and_store(cid, novel_id, text)

    # Summarize
    _summarize_and_store(db, cid, chapter.get("body", []))

    db.close()
    return {"chapter_id": cid, "title": chapter.get("title", ""), "seq": next_seq}
