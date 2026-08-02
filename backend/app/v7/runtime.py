"""Canonical V7 chapter runtime used by every product generation entrypoint.

The product keeps the V6 ``contents`` model because the editor, library and
export APIs already depend on it.  It no longer keeps V6 as a second prose
generation path: workers call this module, V7 owns context/quality/memory, and
the accepted result is bridged back into ``contents``.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from ..db import connect, decode
from ..services.novel_export import extract_body_text
from .brain.novel_brain import NovelBrain
from .db import AsyncSessionLocal, async_engine
from .director.story_director import StoryDirector
from .events.event_bus import EventBus
from .generation.generation_engine import chapter_state_key
from .trace.tracer import ExecutionTracer


def _v6_seed_snapshot(novel_id: str, before_chapter: int) -> dict[str, Any]:
    """Read the existing V6 story into a deterministic V7 import snapshot."""
    conn = connect()
    try:
        chapter_rows = conn.execute(
            """
            SELECT id, title, body, meta, status, seq
            FROM contents
            WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE
              AND COALESCE(seq, (meta->>'seq')::int, 0) < %s
            ORDER BY COALESCE(seq, (meta->>'seq')::int, 0) DESC
            LIMIT 200
            """,
            (novel_id, before_chapter),
        ).fetchall()
        novel_row = conn.execute(
            "SELECT title, meta FROM contents WHERE id=%s AND type='novel'",
            (novel_id,),
        ).fetchone()
        knowledge_rows = conn.execute(
            """
            SELECT kind, title, body, meta
            FROM knowledge_items
            WHERE content_id=%s AND is_deleted=FALSE
            ORDER BY updated_at DESC
            LIMIT 200
            """,
            (novel_id,),
        ).fetchall()
        return {
            "chapters": list(reversed(chapter_rows or [])),
            "novel": novel_row or {},
            "knowledge": knowledge_rows or [],
        }
    finally:
        conn.close()


def _chapter_value(row: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    meta = decode(row.get("meta"), {}) or {}
    try:
        seq = int(row.get("seq") or meta.get("seq") or 0)
    except (TypeError, ValueError):
        seq = 0
    if seq <= 0:
        return None
    text = extract_body_text(row.get("body", ""))
    transition = meta.get("transition_contract")
    if not isinstance(transition, dict):
        transition = {
            "schema_version": "v6-import",
            "chapter_number": seq,
            "end_state": {
                "title": row.get("title") or f"第{seq}章",
                "summary": meta.get("chapter_summary") or "",
                "last_tail": text[-1200:],
                "word_count": len(text.replace("\n", "")),
            },
            "next_chapter_bridge": text[-600:],
            "source": "v6_contents_import",
        }
    return chapter_state_key(seq), {
        "chapter_number": seq,
        "title": row.get("title") or f"第{seq}章",
        "text": text,
        "summary": str(meta.get("chapter_summary") or ""),
        "word_count": int(meta.get("word_count") or len(text.replace("\n", ""))),
        "review_score": meta.get("review_score"),
        "passed_review": row.get("status") == "reviewed",
        "rework_count": int(meta.get("rewrite_attempts") or 0),
        "run_id": meta.get("v7_run_id"),
        "transition_contract": transition,
        "v6_content_id": str(row.get("id") or ""),
    }


async def seed_v6_context(
    brain: NovelBrain,
    novel_id: str,
    before_chapter: int,
) -> dict[str, int]:
    """Import old V6 facts only when the V7 Brain does not have them yet."""
    snapshot = await asyncio.to_thread(_v6_seed_snapshot, novel_id, before_chapter)
    existing_chapters = {
        item.get("key")
        for item in await brain.state.list_states("chapter", limit=500)
    }
    imported_chapters = 0
    for row in snapshot["chapters"]:
        parsed = _chapter_value(row)
        if not parsed:
            continue
        key, value = parsed
        if key in existing_chapters:
            continue
        await brain.state.update_state(
            "chapter",
            key,
            value,
            0.95,
            source="v6_compat_import",
            reason="Seed canonical V7 context from existing V6 chapter fact source",
        )
        imported_chapters += 1

    imported_knowledge = 0
    existing_characters = {
        item.get("key")
        for item in await brain.state.list_states("character", limit=500)
    }
    existing_world = {
        item.get("key") for item in await brain.state.list_states("world", limit=500)
    }
    for row in snapshot["knowledge"]:
        kind = str(row.get("kind") or "")
        if kind not in {"character", "worldview", "world"}:
            continue
        state_type = "character" if kind == "character" else "world"
        key = f"v6:{kind}:{str(row.get('title') or 'untitled').strip()}"
        existing = existing_characters if state_type == "character" else existing_world
        if key in existing:
            continue
        meta = decode(row.get("meta"), {}) or {}
        body = str(row.get("body") or "").strip()
        value = {
            "title": row.get("title") or "",
            "summary": body[:2400],
            "detail": body[:8000],
            "source_meta": meta,
        }
        await brain.state.update_state(
            state_type,
            key,
            value,
            0.95,
            source="v6_compat_import",
            reason="Seed canonical V7 context from V6 knowledge items",
        )
        existing.add(key)
        imported_knowledge += 1

    return {
        "chapters": imported_chapters,
        "knowledge": imported_knowledge,
    }


def _resolve_chapter_number(
    novel_id: str,
    requested: int | None,
    *,
    batch_id: str = "",
    batch_ordinal: int = 0,
) -> int:
    if requested and requested > 0:
        return int(requested)
    conn = connect()
    try:
        if batch_id and batch_ordinal:
            batch = conn.execute(
                "SELECT start_seq FROM generation_batches WHERE id=%s",
                (batch_id,),
            ).fetchone()
            if batch and batch.get("start_seq"):
                return int(batch["start_seq"]) + int(batch_ordinal) - 1
        row = conn.execute(
            """
            SELECT COALESCE(MAX(seq), MAX((meta->>'seq')::int), 0) AS seq
            FROM contents
            WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE
            """,
            (novel_id,),
        ).fetchone()
        return int(row.get("seq") or 0) + 1 if row else 1
    finally:
        conn.close()


def _default_story_prompt(
    novel_id: str,
    chapter_number: int,
    outline: str | None,
) -> str:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT title, meta FROM contents WHERE id=%s AND type='novel'",
            (novel_id,),
        ).fetchone()
        if not row:
            return f"请直接创作第{chapter_number}章正文，推进冲突并在章末留下具体动作钩子。"
        meta = decode(row.get("meta"), {}) or {}
        outline_text = outline or ""
        if not outline_text:
            outlines = meta.get("chapter_outlines") or []
            for item in outlines:
                if isinstance(item, dict) and int(item.get("seq") or 0) == chapter_number:
                    outline_text = json.dumps(item, ensure_ascii=False)
                    break
        blocks = [
            f"小说：{row.get('title') or ''}",
            f"创作圣经：{str(meta.get('creative_bible') or '')[:9000]}",
            f"世界观：{json.dumps(meta.get('worldview') or {}, ensure_ascii=False)[:5000]}",
            f"人物系统：{str(meta.get('_characters_text') or '')[:5000]}",
            f"第{chapter_number}章细纲：{str(outline_text)[:5000]}",
            "只输出小说正文，不要解释、提纲、标题说明或 Markdown；必须承接上一章交接契约，推进本章冲突，并以具体动作/信息变化收束。",
        ]
        return "\n\n".join(block for block in blocks if block.split("：", 1)[-1].strip())
    finally:
        conn.close()


async def generate_v7_chapter(
    novel_id: str,
    project_id: str,
    *,
    chapter_number: int | None = None,
    prompt: str | None = None,
    outline: str | None = None,
    user_id: str | None = None,
    api_key: str = "",
    api_url: str = "",
    model: str = "",
    batch_id: str = "",
    batch_ordinal: int = 0,
) -> dict[str, Any]:
    """Run the only canonical prose generation path and return its evidence."""
    novel_uuid = uuid.UUID(str(novel_id))
    resolved_number = _resolve_chapter_number(
        novel_id,
        chapter_number,
        batch_id=batch_id,
        batch_ordinal=batch_ordinal,
    )
    effective_outline = outline
    effective_prompt = prompt or _default_story_prompt(novel_id, resolved_number, outline)
    provider_config = {
        key: value
        for key, value in {
            "api_key": api_key,
            "base_url": api_url,
            "model": model,
        }.items()
        if value
    }

    async with AsyncSessionLocal() as db:
        brain = NovelBrain(db, novel_uuid)
        seed = await seed_v6_context(brain, novel_id, resolved_number)
        tracer = ExecutionTracer(db, novel_uuid)
        event_bus = EventBus(db, novel_uuid)
        director = StoryDirector(
            db,
            novel_uuid,
            brain,
            tracer,
            event_bus,
            project_id=project_id,
            user_id=user_id,
            provider_config=provider_config,
            generation_metadata={
                key: value
                for key, value in {
                    "batch_id": batch_id,
                    "batch_ordinal": batch_ordinal,
                }.items()
                if value
            },
        )
        result = await director.generate_chapter(
            resolved_number,
            prompt=effective_prompt,
            outline=effective_outline,
        )
        result["canonical_engine"] = "v7"
        result["chapter_number"] = resolved_number
        result["v7_context_seed"] = seed
        if batch_id:
            result["batch_id"] = batch_id
            result["batch_ordinal"] = batch_ordinal
        await db.commit()
        return result


def generate_v7_chapter_sync(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Celery-safe synchronous bridge for the async V7 Director."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_generate_v7_chapter_worker(*args, **kwargs))
    raise RuntimeError("generate_v7_chapter_sync cannot run inside an active event loop")


async def _generate_v7_chapter_worker(*args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return await generate_v7_chapter(*args, **kwargs)
    finally:
        # Celery may execute multiple tasks in one process, each with its own
        # event loop.  Do not leak asyncpg connections across those loops.
        await async_engine.dispose()
