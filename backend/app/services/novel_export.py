"""NC-SC-004: Novel export — TXT, Markdown, EPUB + complete book status."""
from __future__ import annotations
import os, json
from datetime import datetime
from app.db import connect


def export_novel_txt(novel_id: str) -> dict:
    """Export novel as plain text with chapter markers."""
    db = connect()
    novel = db.execute("SELECT * FROM contents WHERE id = %s AND type = 'novel'", (novel_id,)).fetchone()
    chapters = db.execute(
        "SELECT * FROM contents WHERE parent_id = %s AND type = 'chapter' ORDER BY (meta->>'seq')::int",
        (novel_id,)
    ).fetchall()
    db.close()

    if not novel: return {"status": "error", "message": "novel not found"}

    lines = [f"{novel['title']}\n{'=' * 40}\n"]
    lines.append(f"作者: {novel.get('meta', {}).get('author', '') if isinstance(novel.get('meta'), dict) else ''}")
    lines.append(f"导出时间: {datetime.utcnow().isoformat()}\n")

    for ch in chapters:
        lines.append(f"\n--- 第{ch.get('meta', {}).get('seq', '?')}章 {ch['title']} ---\n")
        body = ch.get("body", "")
        if isinstance(body, str):
            lines.append(body)
        elif isinstance(body, dict):
            lines.append(str(body.get("text", "")))
    return {"status": "ok", "format": "txt", "content": "\n".join(lines), "chapter_count": len(chapters)}


def export_novel_markdown(novel_id: str) -> dict:
    """Export novel as Markdown with chapter headings."""
    db = connect()
    novel = db.execute("SELECT * FROM contents WHERE id = %s AND type = 'novel'", (novel_id,)).fetchone()
    chapters = db.execute(
        "SELECT * FROM contents WHERE parent_id = %s AND type = 'chapter' ORDER BY (meta->>'seq')::int",
        (novel_id,)
    ).fetchall()
    db.close()

    if not novel: return {"status": "error", "message": "novel not found"}

    lines = [f"# {novel['title']}\n"]
    lines.append(f"> 自动生成于 {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}\n")

    for ch in chapters:
        seq = ch.get('meta', {}).get('seq', '?') if isinstance(ch.get('meta'), dict) else '?'
        lines.append(f"## 第{seq}章 {ch['title']}\n")
        body = ch.get("body", "")
        if isinstance(body, str):
            lines.append(body + "\n")
        elif isinstance(body, dict):
            lines.append(str(body.get("text", "")) + "\n")

    return {"status": "ok", "format": "markdown", "content": "\n".join(lines), "chapter_count": len(chapters)}


def export_novel_epub(novel_id: str, output_path: str = "") -> dict:
    """Export novel as EPUB file. Falls back to TXT if ebooklib not installed."""
    try:
        from ebooklib import epub
        db = connect()
        novel = db.execute("SELECT * FROM contents WHERE id = %s AND type = 'novel'", (novel_id,)).fetchone()
        chapters = db.execute(
            "SELECT * FROM contents WHERE parent_id = %s AND type = 'chapter' ORDER BY (meta->>'seq')::int",
            (novel_id,)
        ).fetchall()
        db.close()

        book = epub.EpubBook()
        book.set_identifier(novel_id)
        book.set_title(novel['title'])
        book.set_language('zh')
        book.add_author('NovelCraft')

        spine = ['nav']
        for ch in chapters:
            seq = ch.get('meta', {}).get('seq', '?') if isinstance(ch.get('meta'), dict) else ch.get('seq', '?')
            c = epub.EpubHtml(title=ch['title'], file_name=f'ch{seq}.xhtml', lang='zh')
            body = ch.get("body", "")
            text = body if isinstance(body, str) else str(body.get("text", ""))
            c.content = f'<h1>第{seq}章 {ch["title"]}</h1>\n{text.replace(chr(10), "<br/>")}'
            book.add_item(c)
            spine.append(c)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = spine

        path = output_path or f"/tmp/novelcraft_export_{novel_id[:8]}.epub"
        epub.write_epub(path, book)
        return {"status": "ok", "format": "epub", "path": path, "chapter_count": len(chapters)}
    except ImportError:
        return {"status": "fallback", "format": "txt", "message": "Install ebooklib for EPUB", **export_novel_txt(novel_id)}


def get_novel_completion_status(novel_id: str) -> dict:
    """NC-SC-004: Return complete book status with chapter stats and quality metrics."""
    db = connect()
    novel = db.execute("SELECT * FROM contents WHERE id = %s AND type = 'novel'", (novel_id,)).fetchone()
    chapters = db.execute(
        "SELECT * FROM contents WHERE parent_id = %s AND type = 'chapter' ORDER BY (meta->>'seq')::int",
        (novel_id,)
    ).fetchall()
    word_count = sum(
        len(str(ch.get("body", ""))) for ch in chapters
    )
    reviewed = sum(1 for ch in chapters if ch.get("status") == "reviewed")
    avg_score = 0
    scores = []
    for ch in chapters:
        meta = ch.get("meta", {})
        if isinstance(meta, dict):
            s = meta.get("review_score", 0)
            if s: scores.append(s)
    if scores: avg_score = sum(scores) / len(scores)

    db.close()
    return {
        "novel_id": novel_id,
        "title": novel["title"] if novel else "",
        "total_chapters": len(chapters),
        "reviewed_chapters": reviewed,
        "total_words": word_count,
        "average_review_score": round(avg_score, 1),
        "completion_percent": round(len(chapters) / max(novel.get("meta", {}).get("target_chapters", len(chapters) or 1), 1) * 100 if novel else 0),
        "status": novel.get("status", "unknown") if novel else "not_found",
        "exportable": len(chapters) > 0,
    }
