"""Layered summarizer — chapter → volume → book summaries for context assembly."""
from __future__ import annotations

from app.db import connect, encode


def summarize_chapter(chapter_id: str, chapter_body: str, extra_context: str = "") -> dict:
    """Generate or update chapter-level summary (~200 tokens)."""
    summary = _call_ai("summarize_chapter", {
        "body": chapter_body[:8000],
        "instructions": "提取本章关键事件、人物变化、新伏笔和设定变更。≤200字。" + extra_context,
    })
    return {"level": "chapter", "entity_id": chapter_id, "summary": summary}


def summarize_volume(novel_id: str, volume_num: int, chapter_summaries: list[str]) -> dict:
    """Aggregate chapter summaries into a volume summary (~500 tokens)."""
    combined = "\n".join(f"第{i+1}章: {s}" for i, s in enumerate(chapter_summaries))
    summary = _call_ai("summarize_volume", {
        "body": combined,
        "instructions": f"汇总第{volume_num}卷的核心冲突、人物弧线进展和回收的伏笔。≤500字。",
    })
    return {"level": "volume", "entity_id": novel_id, "volume": volume_num, "summary": summary}


def summarize_book(novel_id: str, volume_summaries: list[str]) -> dict:
    """Aggregate volume summaries into a book-level overview (~800 tokens)."""
    combined = "\n".join(f"第{i+1}卷: {s}" for i, s in enumerate(volume_summaries))
    summary = _call_ai("summarize_book", {
        "body": combined,
        "instructions": "总结全书当前状态：主要人物位置/关系、未回收伏笔、主线进展。≤800字。",
    })
    return {"level": "book", "entity_id": novel_id, "summary": summary}


def _call_ai(task_type: str, variables: dict) -> str:
    """Call AI for summarization. Falls back gracefully."""
    try:
        from app.gateway import complete
        result = complete(
            run_id=None, node_key=None, project_id=_get_project_id(),
            task_type=task_type, prompt_name=f"narrative.{task_type}", variables=variables,
        )
        return result.get("summary", result.get("text", str(result)))
    except Exception:
        return f"[摘要生成失败] {variables.get('instructions', '')}"


def _get_project_id() -> str:
    db = connect()
    row = db.execute("SELECT id FROM projects LIMIT 1").fetchone()
    db.close()
    return row["id"] if row else ""
