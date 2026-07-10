from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from .db import connect, decode, encode, new_id, row_to_dict
from .gateway import BudgetExceeded, ProviderError, complete

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

EVENT_LOGS: dict[str, list[dict[str, Any]]] = defaultdict(list)
RUN_TASKS: dict[str, asyncio.Task[None]] = {}


def emit(run_id: str, event: str, data: dict[str, Any]) -> None:
    item = {
        "id": len(EVENT_LOGS[run_id]) + 1,
        "event": event,
        "data": {"run_id": run_id, **data},
    }
    EVENT_LOGS[run_id].append(item)


def create_run(project_id: str, novel_id: str) -> str:
    run_id = new_id("run")
    conn = connect()
    novel = row_to_dict(conn.execute("SELECT * FROM contents WHERE id = %s", (novel_id,)).fetchone())
    if novel is None:
        raise ValueError("novel not found")
    context = {"novel_id": novel_id, "idea": decode(novel["meta"]).get("idea", ""), **decode(novel["meta"])}
    conn.execute(
        """
        INSERT INTO workflow_runs (id, project_id, novel_id, workflow_key, status, current_node_key, context)
        VALUES (%s, %s, %s, 'bootstrap', 'running', 'n1', %s)
        """,
        (run_id, project_id, novel_id, encode(context)),
    )
    for node_key, kind, agent, title, _task_type in BOOTSTRAP_NODES:
        conn.execute(
            "INSERT INTO run_nodes (id, run_id, node_key, kind, agent, title) VALUES (%s, %s, %s ,%s, %s, %s)",
            (new_id("node"), run_id, node_key, kind, agent, title),
        )
    conn.commit()
    conn.close()
    emit(run_id, "node_started", {"node_key": "n1", "agent": "StoryArchitect"})
    return run_id


def schedule_run(run_id: str, start_key: str = "n1") -> None:
    RUN_TASKS[run_id] = asyncio.create_task(run_until_human_or_done(run_id, start_key))


async def run_until_human_or_done(run_id: str, start_key: str) -> None:
    start_index = next(i for i, node in enumerate(BOOTSTRAP_NODES) if node[0] == start_key)
    for node_key, kind, agent, title, task_type in BOOTSTRAP_NODES[start_index:]:
        conn = connect()
        node = row_to_dict(
            conn.execute(
                "SELECT * FROM run_nodes WHERE run_id = %s AND node_key = %s",
                (run_id, node_key),
            ).fetchone()
        )
        run = row_to_dict(conn.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,)).fetchone())
        if node is None or run is None:
            conn.close()
            return
        if node["status"] == "succeeded":
            conn.close()
            continue
        if kind == "human":
            conn.execute(
                "UPDATE run_nodes SET status = 'waiting_human', started_at = COALESCE(started_at, CURRENT_TIMESTAMP) WHERE run_id = %s AND node_key = %s",
                (run_id, node_key),
            )
            conn.execute(
                "UPDATE workflow_runs SET status = 'waiting_human', current_node_key = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (node_key, run_id),
            )
            context = decode(run["context"])
            conn.commit()
            conn.close()
            emit(
                run_id,
                "node_waiting_human",
                {
                    "node_key": node_key,
                    "gate_type": "select_title",
                    "prompt": "请选定书名",
                    "options": context.get("title_candidates", []),
                },
            )
            return

        conn.execute(
            """
            UPDATE run_nodes
            SET status = 'running', attempt = attempt + 1, started_at = CURRENT_TIMESTAMP
            WHERE run_id = %s AND node_key = %s
            """,
            (run_id, node_key),
        )
        conn.execute(
            "UPDATE workflow_runs SET status = 'running', current_node_key = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (node_key, run_id),
        )
        conn.commit()
        context = decode(run["context"])
        conn.close()
        emit(run_id, "node_started", {"node_key": node_key, "agent": agent})
        await asyncio.sleep(0.55)
        try:
            output = complete(
                run_id=run_id,
                node_key=node_key,
                project_id=run["project_id"],
                task_type=task_type or "",
                prompt_name=f"bootstrap.{task_type}",
                variables=context,
            )
        except BudgetExceeded as exc:
            await mark_node_pending(run_id, node_key, "pending_budget", str(exc))
            emit(run_id, "node_failed", {"node_key": node_key, "status": "pending_budget", "error": str(exc)})
            return
        except ProviderError as exc:
            await mark_node_pending(run_id, node_key, "pending_provider", str(exc))
            emit(run_id, "node_failed", {"node_key": node_key, "status": "pending_provider", "error": str(exc)})
            return
        await persist_node_output(run_id, node_key, task_type or "", output)
        emit(run_id, "node_succeeded", {"node_key": node_key, "output": output})

    conn = connect()
    conn.execute(
        "UPDATE workflow_runs SET status = 'succeeded', current_node_key = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (run_id,),
    )
    conn.commit()
    conn.close()
    emit(run_id, "run_done", {"status": "succeeded", "summary": "第一章与七维审核已生成"})


async def mark_node_pending(run_id: str, node_key: str, status: str, error: str) -> None:
    conn = connect()
    conn.execute(
        "UPDATE run_nodes SET status = %s, error = %s, finished_at = CURRENT_TIMESTAMP WHERE run_id = %s AND node_key = %s",
        (status, error, run_id, node_key),
    )
    conn.execute(
        "UPDATE workflow_runs SET status = %s, current_node_key = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (status, node_key, run_id),
    )
    conn.commit()
    conn.close()


async def persist_node_output(run_id: str, node_key: str, task_type: str, output: dict[str, Any]) -> None:
    conn = connect()
    run = row_to_dict(conn.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,)).fetchone())
    if run is None:
        conn.close()
        return
    context = decode(run["context"])
    context.update(output)
    novel_id = run["novel_id"]

    if task_type == "gen_titles":
        context["title_candidates"] = output["title_candidates"]
    elif task_type == "gen_synopsis":
        meta = decode(conn.execute("SELECT meta FROM contents WHERE id = %s", (novel_id,)).fetchone()["meta"])
        meta.update({"synopsis": output["synopsis"], "selling_points": output["selling_points"]})
        conn.execute("UPDATE contents SET meta = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (encode(meta), novel_id))
    elif task_type == "gen_worldview":
        conn.execute(
            "INSERT INTO knowledge_items (id, project_id, content_id, kind, title, body, meta) VALUES (%s, %s, %s ,%s, %s ,%s, %s)",
            (
                new_id("knw"),
                run["project_id"],
                novel_id,
                "worldview",
                output["worldview"]["name"],
                "\n".join(output["worldview"]["rules"]),
                encode(output["worldview"]),
            ),
        )
    elif task_type == "gen_characters":
        for character in output["characters"]:
            conn.execute(
                "INSERT INTO knowledge_items (id, project_id, content_id, kind, title, body, meta) VALUES (%s, %s, %s ,%s, %s ,%s, %s)",
                (
                    new_id("knw"),
                    run["project_id"],
                    novel_id,
                    "character",
                    character["name"],
                    character["arc"],
                    encode(character),
                ),
            )
    elif task_type == "gen_outline":
        meta = decode(conn.execute("SELECT meta FROM contents WHERE id = %s", (novel_id,)).fetchone()["meta"])
        meta["outline"] = output["outline"]
        conn.execute("UPDATE contents SET meta = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (encode(meta), novel_id))
    elif task_type == "gen_chapter1":
        chapter = output["chapter"]
        body = {"type": "doc", "content": [{"type": "paragraph", "text": text} for text in chapter["body"]]}
        chapter_id = new_id("cnt")
        conn.execute(
            """
            INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status)
            VALUES (%s, %s, %s, 'chapter', %s ,%s, %s, 'reviewed')
            """,
            (chapter_id, run["project_id"], novel_id, chapter["title"], encode(body), encode({"seq": 1})),
        )
        context["chapter_id"] = chapter_id
        conn.execute(
            "INSERT INTO versions (id, entity_type, entity_id, label, snapshot) VALUES (%s, 'content', %s, 'ai_generate', %s)",
            (new_id("ver"), chapter_id, encode({"title": chapter["title"], "body": body, "meta": {"seq": 1}})),
        )

    conn.execute(
        "UPDATE run_nodes SET status = 'succeeded', output = %s, finished_at = CURRENT_TIMESTAMP WHERE run_id = %s AND node_key = %s",
        (encode(output), run_id, node_key),
    )
    conn.execute(
        "UPDATE workflow_runs SET context = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (encode(context), run_id),
    )
    conn.commit()
    conn.close()


def confirm_human(run_id: str, selected_title: str) -> None:
    conn = connect()
    run = row_to_dict(conn.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,)).fetchone())
    if run is None:
        conn.close()
        raise ValueError("run not found")
    context = decode(run["context"])
    context["selected_title"] = selected_title
    conn.execute("UPDATE contents SET title = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (selected_title, run["novel_id"]))
    conn.execute(
        """
        UPDATE run_nodes
        SET status = 'succeeded', output = %s, finished_at = CURRENT_TIMESTAMP
        WHERE run_id = %s AND node_key = 'n2'
        """,
        (encode({"selected_title": selected_title}), run_id),
    )
    conn.execute(
        "UPDATE workflow_runs SET status = 'running', current_node_key = 'n3', context = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (encode(context), run_id),
    )
    conn.commit()
    conn.close()
    emit(run_id, "node_succeeded", {"node_key": "n2", "output": {"selected_title": selected_title}})
