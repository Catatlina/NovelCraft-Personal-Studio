"""M3: Knowledge Hub — vector search + ingest."""
from __future__ import annotations

from app.db import connect


def search(query: str, project_id: str | None = None, kinds: list[str] | None = None, limit: int = 10) -> list[dict]:
    """Search knowledge_items by text match (fallback when pgvector unavailable)."""
    db = connect()
    sql = "SELECT id, kind, title, body, meta, source_url FROM knowledge_items WHERE is_deleted = FALSE"
    params = []

    if project_id:
        sql += " AND project_id = %s"
        params.append(project_id)
    if kinds:
        placeholders = ",".join(["%s"] * len(kinds))
        sql += f" AND kind IN ({placeholders})"
        params.extend(kinds)

    # Simple ILIKE search
    sql += " AND (title ILIKE %s OR body ILIKE %s) ORDER BY created_at DESC LIMIT %s"
    params.extend([f"%{query}%", f"%{query}%", limit])

    rows = db.execute(sql, tuple(params)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def ingest_text(project_id: str, title: str, body: str, kind: str = "article", source_url: str = "") -> str:
    """Ingest text content into knowledge_items."""
    db = connect()
    kid = __import__("uuid").uuid4()
    db.execute(
        "INSERT INTO knowledge_items (id, project_id, kind, title, body, source_url, meta) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (str(kid), project_id, kind, title, body[:50000], source_url, "{}"),
    )
    db.commit()
    db.close()
    return str(kid)


def list_by_kind(project_id: str, kind: str) -> list[dict]:
    db = connect()
    rows = db.execute(
        "SELECT id, kind, title, body, source_url, created_at FROM knowledge_items WHERE project_id=%s AND kind=%s AND is_deleted=FALSE ORDER BY created_at DESC LIMIT 50",
        (project_id, kind),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]
