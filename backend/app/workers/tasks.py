"""Celery tasks — workflow execution and scheduled jobs."""
from __future__ import annotations

import time
from functools import wraps

from app.db import connect, encode, new_id, row_to_dict
from app.gateway import (BudgetExceeded, OutputValidationError, ProviderError, complete,
                         validate_task_output, _request_api_key, _request_api_base_url, _request_model)

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


def _isolated_request_context(fn):
    """Prevent BYOK credentials leaking between tasks in a reused worker process."""
    @wraps(fn)
    def wrapped(*args, **kwargs):
        _request_api_key.set(None)
        _request_api_base_url.set(None)
        _request_model.set(None)
        try:
            return fn(*args, **kwargs)
        finally:
            _request_api_key.set(None)
            _request_api_base_url.set(None)
            _request_model.set(None)
    return wrapped


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
@_isolated_request_context
def execute_bootstrap(self, run_id: str, start_key: str = "n1",
                       api_key: str = "", api_url: str = "", model: str = "") -> dict:
    """Execute bootstrap workflow from start_key to human node or completion."""
    # Set context vars for this worker process
    if api_key:
        _request_api_key.set(api_key)
    if api_url:
        _request_api_base_url.set(api_url)
    if model:
        _request_model.set(model)

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

        claim = conn.execute(
            """UPDATE run_nodes SET status='running',attempt=attempt+1,started_at=now(),error=NULL
               WHERE run_id=%s AND node_key=%s
                 AND status IN ('pending','failed','pending_provider','pending_budget')
               RETURNING id""", (run_id, node_key),
        )
        if hasattr(claim, "rowcount") and claim.rowcount != 1:
            conn.close()
            return {"status": "already_claimed", "node_key": node_key}
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
                client_mutation_id=f"bootstrap:{run_id}:{node_key}",
            )
            output = validate_task_output(task_type or "", output)
        except BudgetExceeded:
            _mark_node(run_id, node_key, "pending_budget", "budget exceeded")
            return {"status": "pending_budget", "node_key": node_key}
        except OutputValidationError as exc:
            _mark_node(run_id, node_key, "failed", str(exc))
            return {"status": "invalid_output", "node_key": node_key}
        except ProviderError:
            _mark_node(run_id, node_key, "pending_provider", "provider error")
            return {"status": "pending_provider", "node_key": node_key}
        except Exception as exc:
            _mark_node(run_id, node_key, "failed", str(exc))
            raise self.retry(exc=exc, countdown=5)

        _persist_output(run_id, node_key, task_type or "", output)

    conn = connect()
    completed_run = conn.execute("SELECT * FROM workflow_runs WHERE id=%s", (run_id,)).fetchone()
    completed_context = completed_run["context"] if completed_run and isinstance(completed_run["context"], dict) else {}
    chapter_id = completed_context.get("chapter_id")
    chapter = conn.execute("SELECT status FROM contents WHERE id=%s", (chapter_id,)).fetchone() if chapter_id else None
    needs_review = bool(chapter and chapter["status"] == "needs_rewrite")
    final_status = "needs_review" if needs_review else "succeeded"
    novel_status = "needs_review" if needs_review else "draft"
    topic_status = "needs_review" if needs_review else "generated"
    conn.execute(
        """UPDATE workflow_runs SET status=%s,current_node_key=NULL,finished_at=now(),updated_at=now()
           WHERE id=%s""", (final_status, run_id),
    )
    if completed_run and completed_run.get("novel_id"):
        conn.execute("UPDATE contents SET status=%s,updated_at=now() WHERE id=%s",
                     (novel_status, completed_run["novel_id"]))
        conn.execute("UPDATE topic_candidates SET status=%s WHERE novel_id=%s",
                     (topic_status, completed_run["novel_id"]))
    conn.commit()
    conn.close()
    celery_app.backend.set(f"run:{run_id}:status", final_status)
    return {"status": final_status}


def create_run(project_id: str, novel_id: str,
               api_key: str = "", api_url: str = "", model: str = "",
               selected_title: str = "", idempotency_key: str | None = None) -> str:
    """Create a workflow run and its nodes in the database."""
    db = connect()
    if idempotency_key:
        existing = db.execute(
            "SELECT * FROM workflow_runs WHERE project_id=%s AND idempotency_key=%s",
            (project_id, idempotency_key),
        ).fetchone()
        if existing:
            db.close()
            if existing["status"] == "dispatch_failed" or (
                existing["status"] == "pending" and not existing.get("last_dispatched_at")
            ):
                dispatch_bootstrap_run(existing["id"], existing.get("current_node_key") or "n1",
                                       api_key, api_url, model)
            return existing["id"]
    novel = db.execute("SELECT * FROM contents WHERE id = %s", (novel_id,)).fetchone()
    if novel is None:
        db.close()
        raise ValueError("novel not found")
    meta = novel["meta"] if isinstance(novel["meta"], dict) else {}
    context = {"novel_id": novel_id, "idea": meta.get("idea", ""), **meta}
    if selected_title:
        context["selected_title"] = selected_title
    run_id = new_id()
    db.execute(
        "INSERT INTO workflow_runs "
        "(id, project_id, novel_id, workflow_key, status, current_node_key, context, idempotency_key) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (run_id, project_id, novel_id, "bootstrap", "pending", "n1", encode(context), idempotency_key),
    )
    for node_key, kind, agent, title, _task_type in BOOTSTRAP_NODES:
        db.execute(
            "INSERT INTO run_nodes (id, run_id, node_key, kind, agent, title) VALUES (%s, %s, %s, %s, %s, %s)",
            (new_id(), run_id, node_key, kind, agent, title),
        )
    start_key = "n1"
    if selected_title:
        db.execute("""UPDATE run_nodes SET status='succeeded', output=%s, finished_at=now()
                      WHERE run_id=%s AND node_key IN ('n1','n2')""",
                   (encode({"selected_title": selected_title, "source": "ranking_topic"}), run_id))
        db.execute("UPDATE workflow_runs SET current_node_key='n3', context=%s WHERE id=%s", (encode(context), run_id))
        start_key = "n3"
    db.commit()
    db.close()
    dispatch_bootstrap_run(run_id, start_key, api_key, api_url, model)
    return run_id


def dispatch_bootstrap_run(run_id: str, start_key: str, api_key: str = "",
                           api_url: str = "", model: str = "") -> None:
    """Dispatch or redrive one committed run and persist broker failures."""
    try:
        execute_bootstrap.delay(run_id, start_key, api_key, api_url, model)
    except Exception as exc:
        db = connect()
        db.execute("""UPDATE workflow_runs SET status='dispatch_failed', dispatch_attempts=dispatch_attempts+1,
                      dispatch_error=%s, updated_at=now() WHERE id=%s""", (str(exc), run_id))
        db.commit(); db.close()
        raise
    db = connect()
    db.execute("""UPDATE workflow_runs SET status=CASE WHEN status='dispatch_failed' THEN 'pending' ELSE status END,
                  dispatch_attempts=dispatch_attempts+1,last_dispatched_at=now(),dispatch_error=NULL,updated_at=now()
                  WHERE id=%s""", (run_id,))
    db.commit(); db.close()


def confirm_human(run_id: str, selected_title: str,
                  api_key: str = "", api_url: str = "", model: str = "") -> None:
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
    db.close()
    execute_bootstrap.delay(run_id, "n3", api_key, api_url, model)


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
    knowledge_ids_to_reindex: list[str] = []
    run = db.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,)).fetchone()
    if run is None:
        db.close()
        return
    node = db.execute("SELECT * FROM run_nodes WHERE run_id=%s AND node_key=%s FOR UPDATE",
                      (run_id, node_key)).fetchone()
    if node and node["status"] == "succeeded":
        db.close()
        return
    context = run["context"] if isinstance(run["context"], dict) else {}
    context.update(output)
    novel_id = run["novel_id"]
    project_id = run["project_id"]

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
        knowledge_id = new_id()
        generation_key = f"run:{run_id}:node:{node_key}:worldview"
        stored = db.execute(
            """INSERT INTO knowledge_items
               (id,project_id,content_id,kind,title,body,meta,generation_key)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (content_id,generation_key) WHERE generation_key IS NOT NULL AND is_deleted=FALSE
               DO UPDATE SET title=EXCLUDED.title,body=EXCLUDED.body,meta=EXCLUDED.meta,updated_at=now()
               RETURNING id""",
            (knowledge_id, run["project_id"], novel_id, "worldview", wv.get("name", ""),
             "\n".join(wv.get("rules", [])), encode(wv), generation_key),
        ).fetchone()
        knowledge_ids_to_reindex.append(stored["id"] if stored else knowledge_id)
    elif task_type == "gen_characters":
        for index, c in enumerate(output.get("characters", [])):
            knowledge_id = new_id()
            generation_key = f"run:{run_id}:node:{node_key}:character:{index}"
            stored = db.execute(
                """INSERT INTO knowledge_items
                   (id,project_id,content_id,kind,title,body,meta,generation_key)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (content_id,generation_key) WHERE generation_key IS NOT NULL AND is_deleted=FALSE
                   DO UPDATE SET title=EXCLUDED.title,body=EXCLUDED.body,meta=EXCLUDED.meta,updated_at=now()
                   RETURNING id""",
                (knowledge_id, run["project_id"], novel_id, "character", c.get("name", ""),
                 c.get("arc", ""), encode(c), generation_key),
            ).fetchone()
            knowledge_ids_to_reindex.append(stored["id"] if stored else knowledge_id)
    elif task_type == "gen_outline":
        meta = db.execute("SELECT meta FROM contents WHERE id = %s", (novel_id,)).fetchone()
        if meta:
            m = meta["meta"] if isinstance(meta["meta"], dict) else {}
            m["outline"] = output.get("outline", [])
            db.execute("UPDATE contents SET meta = %s, updated_at = now() WHERE id = %s", (encode(m), novel_id))
    elif task_type == "gen_chapter1":
        from app.services.text_metrics import count_content_chars
        chapter = output.get("chapter", {})
        body = {"type": "doc", "content": [{"type": "paragraph", "text": t} for t in chapter.get("body", [])]}
        chapter_text = "\n".join(t if isinstance(t, str) else t.get("text", "") for t in chapter.get("body", []))
        chapter_meta = {"seq": 1, "word_count": count_content_chars(chapter_text)}
        cid = new_id()
        generation_key = f"run:{run_id}:node:{node_key}:chapter:1"
        stored = db.execute(
            """INSERT INTO contents (id,project_id,parent_id,type,title,body,meta,status,generation_key)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (project_id,generation_key) WHERE generation_key IS NOT NULL AND is_deleted=FALSE
               DO UPDATE SET title=EXCLUDED.title,body=EXCLUDED.body,meta=EXCLUDED.meta,updated_at=now()
               RETURNING id""",
            (cid, run["project_id"], novel_id, "chapter", chapter.get("title", ""),
             encode(body), encode(chapter_meta), "reviewed", generation_key),
        ).fetchone()
        cid = stored["id"] if stored else cid
        context["chapter_id"] = cid
        db.execute(
            """INSERT INTO versions (id,entity_type,entity_id,label,snapshot,client_mutation_id)
               VALUES (%s,'content',%s,'ai_generate',%s,%s)
               ON CONFLICT (client_mutation_id) WHERE client_mutation_id IS NOT NULL DO NOTHING""",
            (new_id(), cid, encode({"title": chapter.get("title", ""), "body": body, "meta": chapter_meta}),
             f"run:{run_id}:node:{node_key}:version"),
        )
        # M2: auto-summarize chapter
        _summarize_and_store(db, cid, chapter.get("body", []))

    if task_type == "review_7dim":
        score = output.get("score", 0)
        cid = context.get("chapter_id", "")
        if score < 80 and cid:
            review_issues = output.get("issues", [])
            rewrite_count = context.get("rewrite_count", 0)
            if rewrite_count < 2:
                # Local import: the gen_chapter1 branch's import doesn't run when this
                # node executes alone — mock reviews always scored 84 so this rework
                # path was never exercised until real-provider T3 (2026-07-12).
                from app.services.text_metrics import count_content_chars
                # Auto-rewrite: regenerate chapter with review feedback
                db.execute(
                    "UPDATE contents SET meta = meta || %s WHERE id = %s",
                    (encode({"review_score": score, "rewrite_count": rewrite_count + 1}), cid),
                )
                db.commit()
                # Re-run gen_chapter1 with review context
                gen_context = {**context, "rewrite_count": rewrite_count + 1,
                               "review_feedback": review_issues, "chapter_id": cid}
                output = complete(run_id=run_id, node_key=node_key, project_id=project_id,
                                 task_type="gen_chapter1", prompt_name="bootstrap.gen_chapter1",
                                 variables=gen_context)
                chapter = output.get("chapter", {})
                body = {"type": "doc", "content": [{"type": "paragraph", "text": t} for t in chapter.get("body", [])]}
                rewritten_text = "\n".join(t if isinstance(t, str) else t.get("text", "") for t in chapter.get("body", []))
                db.execute(
                    "UPDATE contents SET title = %s, body = %s, meta = meta || %s, status = 'draft', updated_at = now() WHERE id = %s",
                    (chapter.get("title", context.get("title", "")), encode(body),
                     encode({"review_score": score, "rewrite_count": rewrite_count + 1,
                             "review_issues": review_issues, "word_count": count_content_chars(rewritten_text)}), cid),
                )
            else:
                db.execute(
                    "UPDATE contents SET meta = meta || %s, status = 'needs_rewrite', updated_at = now() WHERE id = %s",
                    (encode({"review_score": score, "review_issues": review_issues, "rewrite_exhausted": True}), cid),
                )

        # M2: Extended review — OOC, consistency, rhythm
        if task_type in ("review_7dim", "gen_chapter1") and cid:
            chapter_body = context.get("body", "")
            if not chapter_body:
                chapter_body = db.execute("SELECT body FROM contents WHERE id = %s", (cid,)).fetchone()
                chapter_body = str(chapter_body["body"]) if chapter_body else ""
            if chapter_body:
                for dim, task_name in [("review.ooc", "review_ooc"),
                                       ("review.consistency", "review_consistency"),
                                       ("review.rhythm", "review_rhythm")]:
                    try:
                        dim_out = complete(run_id=run_id, node_key=None, project_id=project_id,
                                          task_type=task_name, prompt_name=dim,
                                          variables={"body": chapter_body[:3000]})
                        db.execute(
                            "UPDATE contents SET meta = meta || %s WHERE id = %s",
                            (encode({f"{task_name}_status": "succeeded",
                                     f"{task_name}_result": dim_out}), cid),
                        )
                    except Exception as exc:
                        # Keep the main review available, but persist the exact
                        # degraded dimension instead of silently claiming it ran.
                        db.execute(
                            "UPDATE contents SET meta = meta || %s WHERE id = %s",
                            (encode({f"{task_name}_status": "failed",
                                     f"{task_name}_error": str(exc)[:500]}), cid),
                        )

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
    if knowledge_ids_to_reindex:
        from app.services.knowledge_hub import rebuild_item_embeddings
        for knowledge_id in knowledge_ids_to_reindex:
            try:
                rebuild_item_embeddings(knowledge_id)
            except Exception as exc:
                from app.core.alerts import send_alert
                send_alert(f"知识向量重建失败 {knowledge_id}: {exc}", "warning")


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
@_isolated_request_context
def gen_next_chapter_task(self, novel_id: str, project_id: str,
                           api_key: str = "", api_url: str = "", model: str = "",
                           batch_id: str = "", batch_ordinal: int = 0) -> dict:
    """M2: Generate the next chapter using context assembler (with distributed lock)."""
    from app.gateway import _request_api_key, _request_api_base_url, _request_model
    from .lock import acquire_lock, release_lock

    if api_key:
        _request_api_key.set(api_key)
    if api_url:
        _request_api_base_url.set(api_url)
    if model:
        _request_model.set(model)

    lock_key = f"lock:novel:{novel_id}:gen_chapter"
    if not acquire_lock(lock_key):
        return {"status": "skipped", "reason": "another generation in progress"}
    try:
        return _generate_next_chapter_unlocked(novel_id, project_id, batch_id, batch_ordinal)
    finally:
        release_lock(lock_key)


def _batch_generation_key(batch_id: str, ordinal: int) -> str:
    return f"batch:{batch_id}:slot:{ordinal}:v1"


def _generate_next_chapter_unlocked(novel_id: str, project_id: str,
                                    batch_id: str = "", batch_ordinal: int = 0) -> dict:
    """Generate one chapter. The caller owns the per-novel distributed lock."""
    from app.services.assembler import ContextAssembler
    from app.services.entity_tracker import extract_and_store
    db = connect()
    slot_key = _batch_generation_key(batch_id, batch_ordinal) if batch_id and batch_ordinal else ""
    if slot_key:
        existing = db.execute("""SELECT * FROM contents WHERE project_id=%s AND parent_id=%s
                                  AND generation_key=%s AND type='chapter' AND is_deleted=FALSE""",
                              (project_id, novel_id, slot_key)).fetchone()
        if existing:
            db.close()
            meta = existing["meta"] if isinstance(existing.get("meta"), dict) else {}
            continuity = meta.get("continuity")
            if not isinstance(continuity, dict):
                continuity = _continuity_report(novel_id, int(meta.get("seq") or 0))
                repair_db = connect()
                repair_db.execute("UPDATE contents SET meta=meta || %s,updated_at=now() WHERE id=%s",
                                  (encode({"continuity": continuity}), existing["id"]))
                repair_db.commit(); repair_db.close()
            if existing["status"] in {"reviewed", "needs_rewrite"}:
                return {"chapter_id": existing["id"], "title": existing["title"], "seq": meta.get("seq"),
                        "continuity": continuity,
                        "accepted": existing["status"] == "reviewed",
                        "review_status": existing["status"], "final_score": meta.get("review_score"),
                        "rewrite_attempts": meta.get("rewrite_attempts", 0), "reused": True}
            from app.services.novel_export import extract_body_text
            paragraphs = [part for part in extract_body_text(existing.get("body", "")).splitlines() if part.strip()]
            review = _review_and_finalize_chapter(
                existing["id"], novel_id, project_id, int(meta.get("seq") or 0), slot_key,
                existing["title"], paragraphs, continuity,
            )
            return {"chapter_id": existing["id"], "title": review["title"], "seq": meta.get("seq"),
                    "continuity": meta.get("continuity", {"status": "unchecked"}),
                    "accepted": review["accepted"], "review_status": review["review_status"],
                    "final_score": review["final_score"], "rewrite_attempts": review["rewrite_attempts"],
                    "reused": True}
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

    # M2: Check for due foreshadows + inject into context
    from app.services.narrative_engine import check_foreshadow_due, inject_foreshadow_context
    due_foreshadows = check_foreshadow_due(novel_id, next_seq)
    if due_foreshadows:
        inject_str = inject_foreshadow_context(due_foreshadows)
        context = inject_str + "\n\n" + context

    # Generate — output is schema-validated by the gateway; the stable mutation id
    # lets a retry replay the succeeded ai_call instead of paying for a new one.
    generation_key = slot_key or f"novel:{novel_id}:chapter:{next_seq}:v1"
    output = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="gen_next_chapter", prompt_name="narrative.gen_next_chapter",
        variables={"context": context, "context_length": len(context), "assembled_layers": list(assembler.layers_built.keys())},
        client_mutation_id=generation_key,
    )

    chapter = output["chapter"]
    body = {"type": "doc", "content": [{"type": "paragraph", "text": t} for t in chapter["body"]]}
    cid = new_id()

    db = connect()
    from app.services.text_metrics import count_content_chars
    text = "\n".join(t if isinstance(t, str) else t.get("text", "") for t in chapter["body"])
    chapter_meta = {"seq": next_seq, "word_count": count_content_chars(text)}
    if batch_id and batch_ordinal:
        chapter_meta.update({"batch_id": batch_id, "batch_ordinal": batch_ordinal,
                             "ordinal": batch_ordinal, "quality_status": "draft_pending_review"})
    stored = db.execute(
        """INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status, generation_key)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (project_id, generation_key) WHERE generation_key IS NOT NULL AND is_deleted=FALSE
           DO UPDATE SET title=EXCLUDED.title, body=EXCLUDED.body, meta=EXCLUDED.meta, updated_at=now()
           RETURNING id""",
        (cid, project_id, novel_id, "chapter", chapter.get("title", f"第{next_seq}章"),
         encode(body), encode(chapter_meta), "pending_review", generation_key),
    ).fetchone()
    cid = stored["id"] if stored else cid
    db.execute(
        """INSERT INTO versions (id, entity_type, entity_id, label, snapshot, client_mutation_id)
           VALUES (%s, 'content', %s, 'ai_generate', %s, %s)
           ON CONFLICT (client_mutation_id) WHERE client_mutation_id IS NOT NULL DO NOTHING""",
        (new_id(), cid, encode({"title": chapter.get("title", ""), "body": body, "meta": chapter_meta}),
         generation_key),
    )
    db.commit()
    db.close()

    # Enrichments must never prevent the persisted draft from reaching the
    # continuity/review gates. Failures are recorded for later reconciliation.
    from app.services.foreshadowing import extract_and_store_foreshadowing
    from app.services.timeline import extract_timeline, update_arcs
    enrichment_errors = []
    for label, action in (
        ("entities", lambda: extract_and_store(cid, novel_id, text)),
        ("foreshadowing", lambda: extract_and_store_foreshadowing(cid, next_seq, text)),
        ("timeline", lambda: extract_timeline(cid, text)),
        ("arcs", lambda: update_arcs(novel_id, text)),
    ):
        try:
            action()
        except Exception as exc:
            enrichment_errors.append({"stage": label, "error": str(exc)[:300]})

    # Continuity check + risk report (DB comparison, no extra AI spend); a check
    # failure is recorded as unchecked, never silently dropped.
    continuity = _continuity_report(novel_id, next_seq)

    # Persist continuity evidence before the review gate so the reviewer can see it.
    db = connect()
    db.execute(
        "UPDATE contents SET meta = meta || %s, updated_at = now() WHERE id = %s",
        (encode({"continuity": continuity, "enrichment_errors": enrichment_errors}), cid),
    )
    db.commit()
    db.close()
    review = _review_and_finalize_chapter(
        cid, novel_id, project_id, next_seq, generation_key, chapter.get("title", ""),
        list(chapter["body"]), continuity,
    )
    db = connect()
    _summarize_and_store(db, cid, review["body"])
    db.commit(); db.close()
    return {"chapter_id": cid, "title": chapter.get("title", ""), "seq": next_seq,
            "continuity": continuity, "accepted": review["accepted"],
            "review_status": review["review_status"], "final_score": review["final_score"],
            "rewrite_attempts": review["rewrite_attempts"]}


def _review_and_finalize_chapter(chapter_id: str, novel_id: str, project_id: str, chapter_seq: int,
                                 generation_key: str, title: str, paragraphs: list[str],
                                 continuity: dict, threshold: float = 80, max_rewrites: int = 2) -> dict:
    """Review every generated chapter; rewrites must be reviewed again before acceptance."""
    current_title = title
    current_body = list(paragraphs)
    for attempt in range(max_rewrites + 1):
        current_text = "\n".join(current_body)
        review = complete(
            run_id=None, node_key=None, project_id=project_id,
            task_type="review_7dim", prompt_name="bootstrap.review_7dim",
            variables={"chapter_id": chapter_id, "chapter_seq": chapter_seq, "body": current_text,
                       "continuity": continuity, "threshold": threshold},
            client_mutation_id=f"{generation_key}:review:{attempt}:v1",
        )
        score = float(review["score"])
        issues = list(review.get("issues", []))
        review_key = f"{generation_key}:review-record:{attempt}:v1"
        db = connect()
        db.execute(
            """INSERT INTO reviews (id,content_id,score,dimensions,issues,generation_key)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT (content_id,generation_key) WHERE generation_key IS NOT NULL
               DO UPDATE SET score=EXCLUDED.score,dimensions=EXCLUDED.dimensions,issues=EXCLUDED.issues""",
            (new_id(), chapter_id, score, encode(review["dimensions"]), encode(issues), review_key),
        )
        status = "reviewed" if score >= threshold else "pending_review"
        db.execute("""UPDATE contents SET status=%s,meta=meta || %s,updated_at=now() WHERE id=%s""",
                   (status, encode({"review_score": score, "review_issues": issues,
                                    "review_attempts": attempt + 1,
                                    "quality_status": "accepted" if score >= threshold else "draft_pending_review"}), chapter_id))
        db.commit(); db.close()
        if score >= threshold:
            return {"accepted": True, "review_status": "reviewed", "final_score": score,
                    "rewrite_attempts": attempt, "title": current_title, "body": current_body}
        if attempt == max_rewrites:
            db = connect()
            db.execute("""UPDATE contents SET status='needs_rewrite',meta=meta || %s,updated_at=now()
                          WHERE id=%s""", (encode({"quality_status": "needs_review"}), chapter_id))
            db.commit(); db.close()
            return {"accepted": False, "review_status": "needs_rewrite", "final_score": score,
                    "rewrite_attempts": attempt, "title": current_title, "body": current_body}

        rewritten = complete(
            run_id=None, node_key=None, project_id=project_id,
            task_type="gen_next_chapter", prompt_name="narrative.gen_next_chapter",
            variables={"rewrite": True, "chapter_seq": chapter_seq, "current_title": current_title,
                       "current_body": current_text, "review_feedback": issues, "continuity": continuity},
            client_mutation_id=f"{generation_key}:rewrite:{attempt + 1}:v1",
        )["chapter"]
        current_title = rewritten["title"]
        current_body = list(rewritten["body"])
        rewritten_doc = {"type": "doc", "content": [{"type": "paragraph", "text": text}
                                                         for text in current_body]}
        from app.services.text_metrics import count_content_chars
        db = connect()
        db.execute("""UPDATE contents SET title=%s,body=%s,meta=meta || %s,status='pending_review',updated_at=now()
                      WHERE id=%s""",
                   (current_title, encode(rewritten_doc),
                    encode({"word_count": count_content_chars("\n".join(current_body)),
                            "rewrite_attempts": attempt + 1,
                            "quality_status": "draft_pending_review"}), chapter_id))
        db.commit(); db.close()


def _continuity_report(novel_id: str, chapter_seq: int) -> dict:
    """Cross-chapter conflicts + overdue foreshadows as a persisted risk report."""
    from datetime import datetime, timezone
    from app.services.narrative_engine import check_foreshadow_due, detect_cross_chapter_conflicts
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        conflicts = detect_cross_chapter_conflicts(novel_id)
        overdue = check_foreshadow_due(novel_id, chapter_seq)
    except Exception as exc:
        return {"status": "unchecked", "error": str(exc), "checked_at": checked_at}
    risks = ([{"type": "conflict", **c} for c in conflicts]
             + [{"type": "foreshadow_due", "content": f.get("content", ""), "foreshadow_id": f.get("id")}
                for f in overdue])
    return {"status": "flagged" if risks else "clean", "risks": risks, "checked_at": checked_at}


def _run_batch_slot(batch: dict, ordinal: int, api_key: str = "", api_url: str = "",
                    model: str = "") -> dict:
    """Run or resume one stable batch slot."""
    generation_key = _batch_generation_key(batch["id"], ordinal)
    db = connect()
    existing = db.execute("""SELECT * FROM contents WHERE project_id=%s AND parent_id=%s
                              AND generation_key=%s AND type='chapter' AND is_deleted=FALSE""",
                          (batch["project_id"], batch["novel_id"], generation_key)).fetchone()
    db.close()
    if existing:
        meta = existing["meta"] if isinstance(existing.get("meta"), dict) else {}
        continuity = meta.get("continuity")
        if not isinstance(continuity, dict):
            continuity = _continuity_report(batch["novel_id"], int(meta.get("seq") or 0))
            repair_db = connect()
            repair_db.execute("UPDATE contents SET meta=meta || %s,updated_at=now() WHERE id=%s",
                              (encode({"continuity": continuity}), existing["id"]))
            repair_db.commit(); repair_db.close()
        if existing.get("status") in {"reviewed", "needs_rewrite"}:
            accepted = existing["status"] == "reviewed"
            return {"chapter_id": existing["id"], "accepted": accepted,
                    "review_status": existing["status"], "reused": True}
        from app.services.novel_export import extract_body_text
        paragraphs = [line for line in extract_body_text(existing.get("body", "")).splitlines() if line.strip()]
        review = _review_and_finalize_chapter(
            existing["id"], batch["novel_id"], batch["project_id"], int(meta.get("seq") or 0),
            generation_key, existing["title"], paragraphs,
            continuity,
        )
        return {"chapter_id": existing["id"], **review, "reused": True}
    return gen_next_chapter_task.run(
        batch["novel_id"], batch["project_id"], api_key, api_url, model,
        batch["id"], ordinal,
    )


def _recount_batch_progress(db, batch_id: str) -> dict | None:
    """Rebuild counters from distinct persisted slots; never blindly trust increments."""
    cursor = db.execute("""SELECT status,meta FROM contents WHERE type='chapter'
                           AND meta->>'batch_id'=%s AND is_deleted=FALSE""", (batch_id,))
    if not hasattr(cursor, "fetchall"):
        return None  # Compatibility for lightweight adapters; production DB always supports it.
    rows = cursor.fetchall()
    by_ordinal = {}
    for row in rows:
        meta = row.get("meta", {}) if isinstance(row.get("meta"), dict) else {}
        if meta.get("batch_id") and meta.get("batch_id") != batch_id:
            continue
        ordinal = int(meta.get("batch_ordinal") or meta.get("ordinal") or 0)
        if ordinal > 0:
            by_ordinal[ordinal] = meta.get("quality_status") or row.get("status")
    generated = len(by_ordinal)
    accepted = sum(status in {"accepted", "reviewed"} for status in by_ordinal.values())
    needs_review = sum(status in {"needs_review", "needs_rewrite"} for status in by_ordinal.values())
    reviewed = accepted + needs_review
    terminal = reviewed
    db.execute("""UPDATE generation_batches SET generated_count=%s,reviewed_count=%s,
                  accepted_count=%s,needs_review_count=%s,completed_count=%s,updated_at=now() WHERE id=%s""",
               (generated, reviewed, accepted, needs_review, terminal, batch_id))
    return {"generated_count": generated, "reviewed_count": reviewed, "accepted_count": accepted,
            "needs_review_count": needs_review, "completed_count": terminal}


def _increment_batch_progress_legacy(db, batch_id: str, accepted: bool) -> None:
    """Only for non-production lightweight adapters without fetchall support."""
    db.execute("UPDATE generation_batches SET completed_count = completed_count + 1, updated_at=now() WHERE id=%s",
               (batch_id,))
    db.execute("""UPDATE generation_batches SET generated_count=generated_count+1,
                   reviewed_count=reviewed_count+1,accepted_count=accepted_count+%s,
                   needs_review_count=needs_review_count+%s,updated_at=now() WHERE id=%s""",
               (1 if accepted else 0, 0 if accepted else 1, batch_id))


@celery_app.task(bind=True, max_retries=1)
def batch_generate_chapters_task(
    self,
    batch_id: str,
    api_key: str = "",
    api_url: str = "",
    model: str = "",
) -> dict:
    """Generate a persisted batch, observing cancellation and resuming from completed_count."""
    db = connect()
    batch = db.execute("SELECT * FROM generation_batches WHERE id = %s", (batch_id,)).fetchone()
    if not batch:
        db.close()
        return {"status": "error", "message": "batch not found"}
    db.execute("UPDATE generation_batches SET status = 'running', error = NULL, updated_at = now() WHERE id = %s", (batch_id,))
    db.commit()
    db.close()

    start_ordinal = batch.get("completed_count", 0) + 1
    had_needs_review = False
    try:
        for ordinal in range(start_ordinal, batch["requested_count"] + 1):
            db = connect()
            db.execute("UPDATE generation_batches SET current_ordinal=%s,updated_at=now() WHERE id=%s",
                       (ordinal, batch_id))
            db.commit(); db.close()
            db = connect()
            state = db.execute("SELECT cancel_requested FROM generation_batches WHERE id = %s", (batch_id,)).fetchone()
            db.close()
            if not state or state["cancel_requested"]:
                return {"status": "cancelled", "batch_id": batch_id}
            result = _run_batch_slot(batch, ordinal, api_key, api_url, model)
            if result.get("status") == "skipped":
                raise RuntimeError(result.get("reason", "chapter generation skipped"))
            accepted = result.get("accepted", True)
            had_needs_review = had_needs_review or not accepted
            db = connect()
            counts = _recount_batch_progress(db, batch_id)
            if counts is None:
                _increment_batch_progress_legacy(db, batch_id, accepted)
            db.commit()
            db.close()
    except (ProviderError, BudgetExceeded) as exc:
        # Provider/budget waits are recoverable: keep progress and surface the cause.
        db = connect()
        db.execute(
            "UPDATE generation_batches SET status = 'pending_provider', error = %s, updated_at = now() WHERE id = %s",
            (str(exc), batch_id),
        )
        db.commit()
        db.close()
        from app.core.alerts import send_alert
        send_alert(f"批次 {batch_id} 进入 pending_provider：{exc}", "warning")
        return {"status": "pending_provider", "batch_id": batch_id, "reason": str(exc)}
    except Exception as exc:
        db = connect()
        db.execute(
            "UPDATE generation_batches SET status = 'failed', error = %s, updated_at = now() WHERE id = %s",
            (str(exc), batch_id),
        )
        db.commit()
        db.close()
        from app.core.alerts import send_alert
        send_alert(f"批次 {batch_id} 失败：{exc}", "error")
        raise

    db = connect()
    final_status = "needs_review" if had_needs_review else "succeeded"
    db.execute("""UPDATE generation_batches SET status=%s,quality_status=%s,current_ordinal=NULL,updated_at=now()
                  WHERE id=%s""",
               (final_status, "needs_review" if had_needs_review else "verified", batch_id))
    db.commit()
    db.close()
    return {"status": final_status, "batch_id": batch_id, "completed_count": batch["requested_count"]}


@celery_app.task
def expand_outline_task(novel_id: str, project_id: str) -> dict:
    """M2: Expand volume outline into chapter-level outlines."""
    db = connect()
    meta_row = db.execute("SELECT meta FROM contents WHERE id = %s", (novel_id,)).fetchone()
    db.close()
    if not meta_row:
        return {"error": "novel not found"}
    meta = meta_row["meta"] if isinstance(meta_row["meta"], dict) else {}
    outline = meta.get("outline", [])
    if not outline:
        return {"error": "no outline to expand"}

    chapters = []
    for vol_idx, vol_line in enumerate(outline):
        output = complete(
            run_id=None, node_key=None, project_id=project_id,
            task_type="expand_outline", prompt_name="narrative.expand_outline",
            variables={"volume": vol_line, "volume_num": vol_idx + 1, "chapters_per_volume": 10},
        )
        for ch in output.get("chapters", []):
            chapters.append({"volume": vol_idx + 1, "seq": len(chapters) + 1, "title": ch.get("title", ""), "outline": ch.get("outline", "")})

    db = connect()
    db.execute(
        "UPDATE contents SET meta = meta || %s, updated_at = now() WHERE id = %s",
        (encode({"chapter_outlines": chapters}), novel_id),
    )
    db.commit()
    db.close()
    return {"chapters": len(chapters), "sample": chapters[:3]}


@celery_app.task
def auto_serial_check() -> dict:
    """M2 beat: check for novels with auto-serial enabled and generate next chapter."""
    db = connect()
    novels = db.execute(
        "SELECT id, project_id FROM contents WHERE type='novel' AND meta->>'auto_serial' = 'true' AND is_deleted = FALSE"
    ).fetchall()
    db.close()
    results = []
    for novel in novels:
        try:
            gen_next_chapter_task.delay(novel["id"], novel["project_id"])
            results.append({"novel_id": novel["id"], "status": "dispatched"})
        except Exception as e:
            results.append({"novel_id": novel["id"], "status": f"error: {e}"})
    return {"checked": len(novels), "results": results}


@celery_app.task
def purge_stale_autosaves() -> dict:
    """C5-05: 7-day retention for routine save versions.

    Only manual_save/offline_save are purged, and the 10 most recent per
    entity are always kept; semantic branches (ai_edit/ai_generate/
    initial_idea/offline_conflict/before_restore) are never touched."""
    db = connect()
    db.execute(
        """DELETE FROM versions WHERE id IN (
             SELECT id FROM (
               SELECT id, ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY created_at DESC) AS rn
               FROM versions
               WHERE label IN ('manual_save', 'offline_save')
                 AND created_at < now() - interval '7 days'
             ) ranked WHERE ranked.rn > 10
           )"""
    )
    deleted = getattr(db._cur, "rowcount", 0)
    db.commit()
    db.close()
    return {"deleted": deleted}


@celery_app.task
def purge_stale_operational_data() -> dict:
    """Bound unbounded operational tables while retaining recent audit evidence."""
    import os

    ai_days = max(30, int(os.getenv("AI_CALL_RETENTION_DAYS", "365")))
    operation_days = max(30, int(os.getenv("OPERATION_LOG_RETENTION_DAYS", "180")))
    audit_days = max(30, int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "365")))
    db = connect()
    deleted = {}
    for table, days in (("ai_calls", ai_days), ("operation_logs", operation_days),
                        ("audit_logs", audit_days)):
        db.execute(
            f"DELETE FROM {table} WHERE created_at < now() - (%s * interval '1 day')", (days,),
        )
        deleted[table] = max(0, int(getattr(db._cur, "rowcount", 0)))
    db.commit()
    db.close()
    return {"deleted": deleted, "retention_days": {
        "ai_calls": ai_days, "operation_logs": operation_days, "audit_logs": audit_days,
    }}


def check_queue_backlog(threshold: int | None = None) -> str | None:
    """Alert when the celery queue piles up (e.g. stale dispatches burning
    provider credits — 404 messages were found queued on 2026-07-12)."""
    import os

    import redis as redis_lib

    limit = threshold if threshold is not None else int(os.getenv("QUEUE_BACKLOG_THRESHOLD", "50"))
    try:
        client = redis_lib.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        depth = int(client.llen("celery"))
    except Exception:
        return None  # Redis 不可达由 healthz 负责，不在这里重复告警
    if depth > limit:
        return f"celery queue backlog: {depth} messages (threshold {limit})"
    return None


@celery_app.task
def daily_cost_report() -> dict:
    """Beat: 昨日 AI 成本日报 — 个人部署最实用的一条监控。"""
    from app.core.alerts import send_alert

    db = connect()
    rows = db.execute(
        """SELECT task_type, COUNT(*) AS n, COALESCE(SUM(prompt_tokens),0) AS pt,
                  COALESCE(SUM(completion_tokens),0) AS ct, COALESCE(SUM(cost_cny),0) AS cost
           FROM ai_calls
           WHERE created_at >= now() - interval '24 hours' AND status = 'succeeded'
           GROUP BY task_type ORDER BY cost DESC"""
    ).fetchall()
    failed = db.execute(
        "SELECT COUNT(*) AS n FROM ai_calls WHERE created_at >= now() - interval '24 hours' AND status != 'succeeded'"
    ).fetchone()["n"]
    db.close()
    total_calls = sum(r["n"] for r in rows)
    total_tokens = sum(r["pt"] + r["ct"] for r in rows)
    total_cost = float(sum(r["cost"] for r in rows))
    if total_calls or failed:
        lines = [f"过去24h：{total_calls} 次调用 / {total_tokens} tokens / ¥{total_cost:.4f}，失败 {failed} 次"]
        lines += [f"• {r['task_type']}: {r['n']} 次, {r['pt'] + r['ct']} tokens" for r in rows[:6]]
        send_alert("AI 成本日报\n" + "\n".join(lines), "info")
    return {"calls": total_calls, "tokens": total_tokens, "cost_cny": round(total_cost, 4), "failed": failed}


@celery_app.task
def patrol_check() -> dict:
    """M2 beat: consistency patrol — check foreshadowing, chapter gaps, quality."""
    db = connect()
    # Check for overdue foreshadowing (planted but past planned chapter)
    overdue = db.execute(
        """SELECT f.id, f.content, f.planned_resolve_chapter, c.title as chapter_title
           FROM foreshadowings f
           JOIN contents c ON f.chapter_id = c.id
           WHERE f.status = 'planted'
             AND f.planned_resolve_chapter IS NOT NULL
             AND f.planned_resolve_chapter <= (
               SELECT COALESCE(MAX((latest.meta->>'seq')::int), 0)
               FROM contents latest
               WHERE latest.parent_id = c.parent_id AND latest.type = 'chapter'
                 AND latest.is_deleted = FALSE
             )"""
    ).fetchall()

    # Check for chapters needing rewrite
    needs_rewrite = db.execute(
        "SELECT id, title FROM contents WHERE status = 'needs_rewrite' AND is_deleted = FALSE"
    ).fetchall()

    # Check for orphan chapters (no parent novel)
    orphans = db.execute(
        "SELECT id, title FROM contents WHERE type='chapter' AND parent_id IS NULL AND is_deleted = FALSE"
    ).fetchall()

    db.close()

    issues = []
    if overdue:
        issues.append(f"{len(overdue)} unfulfilled foreshadowings")
    if needs_rewrite:
        issues.append(f"{len(needs_rewrite)} chapters need rewrite")
    if orphans:
        issues.append(f"{len(orphans)} orphan chapters")
    backlog = check_queue_backlog()
    if backlog:
        issues.append(backlog)

    # Send alerts for issues
    if issues:
        from app.core.alerts import send_alert
        send_alert("巡检发现问题:\n" + "\n".join(f"• {i}" for i in issues), "warning")

    return {
        "status": "ok" if not issues else "issues_found",
        "issues": issues,
        "foreshadowing_count": len(overdue),
        "needs_rewrite_count": len(needs_rewrite),
    }


@celery_app.task(bind=True, max_retries=2)
def bootstrap_short_story_task(self, project_id: str, short_id: str) -> dict:
    """M3: Generate short story from idea."""
    from app.services.short_story import SHORT_STORY_TEMPLATES

    db = connect()
    story = row_to_dict(db.execute("SELECT * FROM contents WHERE id = %s", (short_id,)).fetchone())
    if not story:
        db.close()
        return {"error": "story not found"}
    meta = story.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    template_key = meta.get("template", "viral")
    template = SHORT_STORY_TEMPLATES.get(template_key, SHORT_STORY_TEMPLATES["viral"])
    context = {"idea": meta.get("idea",""), "genre": meta.get("genre",""),
               "style": meta.get("style",""), "template": template["name"],
               "max_words": meta.get("max_words", template["max_words"])}
    db.close()

    output = complete(run_id=None, node_key="s1", project_id=project_id,
                     task_type="gen_short_titles", prompt_name="shortstory.gen_titles",
                     variables=context)
    titles = output.get("titles", [])
    context["title"] = titles[0] if titles else "未命名短篇"

    output = complete(run_id=None, node_key="s2", project_id=project_id,
                     task_type="gen_short_story", prompt_name="shortstory.gen_story",
                     variables=context)
    story_out = output.get("story", {})
    body = {"type":"doc","content":[{"type":"paragraph","text":t} for t in story_out.get("body",[])]}
    db = connect()
    db.execute("UPDATE contents SET title=%s, body=%s, meta=meta||%s, status=%s, updated_at=now() WHERE id=%s",
               (story_out.get("title", context["title"]), encode(body),
                encode({"short_score": 0, "template": template_key}), "completed", short_id))
    db.commit()
    db.close()
    return {"status": "completed", "title": story_out.get("title", "")}
