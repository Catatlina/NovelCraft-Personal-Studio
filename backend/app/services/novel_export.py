"""NC-SC-004: Novel export — TXT, Markdown, EPUB + complete book status."""
from __future__ import annotations
import os, json
from datetime import datetime
from app.db import connect


def extract_body_text(body) -> str:
    """Extract plain text from a chapter body: plain string, {"text": ...},
    or the persisted doc format {"type":"doc","content":[{"type":"paragraph","text":...}]}
    (nodes may also carry standard Tiptap nested content with text leaves)."""
    if body is None:
        return ""
    if isinstance(body, str):
        try:
            parsed = json.loads(body)
        except (ValueError, TypeError):
            return body
        return body if not isinstance(parsed, (dict, list)) else extract_body_text(parsed)
    if isinstance(body, list):
        return "\n".join(filter(None, (extract_body_text(node) for node in body)))
    if isinstance(body, dict):
        parts = []
        if isinstance(body.get("text"), str):
            parts.append(body["text"])
        if isinstance(body.get("content"), list):
            parts.append(extract_body_text(body["content"]))
        return "\n".join(filter(None, parts))
    return str(body)


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
        lines.append(extract_body_text(ch.get("body", "")))
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
        lines.append(extract_body_text(ch.get("body", "")) + "\n")

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
            text = extract_body_text(ch.get("body", ""))
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
        len(extract_body_text(ch.get("body", ""))) for ch in chapters
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
    meta = novel.get("meta", {}) if novel and isinstance(novel.get("meta"), dict) else {}
    target_chapters = int(meta.get("target_chapters") or 0)
    target_words = int(meta.get("target_words") or 0)
    target_missing = target_chapters <= 0 and target_words <= 0
    if target_chapters > 0:
        generation_percent = min(100, round(len(chapters) / target_chapters * 100))
        progress_basis = "chapters"
    elif target_words > 0:
        generation_percent = min(100, round(word_count / target_words * 100))
        progress_basis = "words"
    else:
        generation_percent = None
        progress_basis = "missing"
    review_percent = round(reviewed / len(chapters) * 100) if chapters else 0
    continuity_flagged = 0
    continuity_unchecked = 0
    needs_rewrite = 0
    for chapter in chapters:
        chapter_meta = chapter.get("meta", {}) if isinstance(chapter.get("meta"), dict) else {}
        continuity_status = (chapter_meta.get("continuity") or {}).get("status")
        continuity_flagged += continuity_status == "flagged"
        continuity_unchecked += continuity_status == "unchecked"
        needs_rewrite += chapter.get("status") == "needs_rewrite"
    quality_warnings = []
    if reviewed < len(chapters):
        quality_warnings.append("存在未审核章节")
    if continuity_flagged:
        quality_warnings.append(f"{continuity_flagged}章存在连续性风险")
    if continuity_unchecked:
        quality_warnings.append(f"{continuity_unchecked}章连续性未检查")
    if needs_rewrite:
        quality_warnings.append(f"{needs_rewrite}章需要返工")
    ready_for_release = bool(chapters) and generation_percent == 100 and reviewed == len(chapters) \
        and continuity_flagged == 0 and continuity_unchecked == 0 and needs_rewrite == 0
    return {
        "novel_id": novel_id,
        "title": novel["title"] if novel else "",
        "total_chapters": len(chapters),
        "reviewed_chapters": reviewed,
        "total_words": word_count,
        "average_review_score": round(avg_score, 1),
        "completion_percent": generation_percent,
        "generation_percent": generation_percent,
        "review_percent": review_percent,
        "progress_basis": progress_basis,
        "target_chapters": target_chapters or None,
        "target_words": target_words or None,
        "target_missing": target_missing,
        "continuity_flagged": continuity_flagged,
        "continuity_unchecked": continuity_unchecked,
        "needs_rewrite_chapters": needs_rewrite,
        "quality_warnings": quality_warnings,
        "ready_for_release": ready_for_release,
        "status": novel.get("status", "unknown") if novel else "not_found",
        "exportable": len(chapters) > 0,
    }
