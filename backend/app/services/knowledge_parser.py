"""TASK-035: Knowledge hub — PDF/Word/Markdown/Link parsing."""
from __future__ import annotations

from app.db import connect, new_id, encode


def parse_text_file(text: str, filename: str = "") -> list[dict]:
    """Parse uploaded text/JSON/Markdown into knowledge items."""
    items = []
    # Split on YAML frontmatter or markdown headings
    import re
    sections = re.split(r'\n(?=#{1,3}\s)', text)
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        title = sec.split('\n')[0].lstrip('#').strip()[:120]
        body = sec[:10000]
        kind = "reference"
        if len(sec) < 500:
            kind = "note"
        items.append({"title": title or filename, "body": body, "kind": kind})
    return items


def store_parsed_items(items: list[dict]) -> int:
    """Store parsed items into knowledge_items table."""
    db = connect()
    count = 0
    for item in items:
        try:
            db.execute(
                "INSERT INTO knowledge_items (id, kind, title, body, meta) VALUES (%s,%s,%s,%s,%s)",
                (new_id(), item.get("kind", "note"), item.get("title", "unknown"),
                 item.get("body", ""), encode(item.get("meta", {}))),
            )
            count += 1
        except Exception:
            pass
    db.commit(); db.close()
    return count


def check_imitation_similarity(original: str, imitation: str) -> dict:
    """TASK-036: N-gram similarity with redline check."""
    def ngrams(s: str, n: int = 5):
        return set(tuple(s[i:i+n]) for i in range(len(s) - n + 1))

    orig_ngrams = ngrams(original)
    imit_ngrams = ngrams(imitation)
    if not orig_ngrams or not imit_ngrams:
        return {"similarity": 0, "redline_breach": False, "warning": None}

    sim = len(orig_ngrams & imit_ngrams) / max(len(orig_ngrams), 1)
    breaching = sim > 0.6
    return {
        "similarity": round(sim, 3),
        "redline_breach": breaching,
        "warning": "⚠️ 相似度超过60%红线" if breaching else None,
    }
