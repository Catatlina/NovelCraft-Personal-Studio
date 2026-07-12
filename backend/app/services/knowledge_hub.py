"""M3: Knowledge Hub — vector search + ingest.

Embeddings come from app.core.embeddings (remote API / local ONNX bge /
hash fallback); vectors are padded to the 1536-dim pgvector column."""
from __future__ import annotations

from app.core.embeddings import embed_query_with_backend, embed_texts
from app.db import connect
from app.db import new_id

EMBEDDING_DIMENSION = 1536


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def _chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    """Split text deterministically so rebuilding produces the same chunk set."""
    clean = (text or "").strip()
    if not clean:
        return []
    chunks = []
    start = 0
    while start < len(clean):
        chunks.append(clean[start:start + size])
        if start + size >= len(clean):
            break
        start += size - overlap
    return chunks


def rebuild_item_embeddings(item_id: str) -> int:
    """Atomically replace an item's chunks with embeddings from the configured backend."""
    db = connect()
    item = db.execute("SELECT body FROM knowledge_items WHERE id = %s AND is_deleted = FALSE", (item_id,)).fetchone()
    if not item:
        db.close()
        return 0
    chunks = _chunk_text(item.get("body", ""))
    vectors, backend = embed_texts(chunks)
    db.execute("DELETE FROM knowledge_vectors WHERE item_id = %s", (item_id,))
    for chunk_no, (chunk, vector) in enumerate(zip(chunks, vectors)):
        db.execute(
            "INSERT INTO knowledge_vectors (id, item_id, chunk_no, embedding, chunk_text) VALUES (%s, %s, %s, %s::vector, %s)",
            (new_id(), item_id, chunk_no, _vector_literal(vector), chunk),
        )
    # provenance: which backend produced this item's vectors (for reindex audits)
    db.execute(
        "UPDATE knowledge_items SET meta = COALESCE(meta,'{}'::jsonb) || jsonb_build_object('embedding_backend', %s::text) WHERE id = %s",
        (backend, item_id),
    )
    db.commit()
    db.close()
    return len(chunks)


def reindex_project_embeddings(project_id: str) -> dict:
    """Re-embed every item in a project — run after switching EMBEDDING_BACKEND."""
    db = connect()
    ids = [r["id"] for r in db.execute(
        "SELECT id FROM knowledge_items WHERE project_id = %s AND is_deleted = FALSE", (project_id,)
    ).fetchall()]
    db.close()
    chunks_total = sum(rebuild_item_embeddings(item_id) for item_id in ids)
    from app.core.embeddings import resolve_backend
    return {"items": len(ids), "chunks": chunks_total, "backend": resolve_backend()}


def search(query: str, project_id: str | None = None, kinds: list[str] | None = None, limit: int = 10) -> list[dict]:
    """Search indexed knowledge by vector distance, with lexical fallback."""
    db = connect()
    query_vector, query_backend = embed_query_with_backend(query)
    vector_sql = """
        SELECT ki.id, ki.kind, ki.title, ki.body, ki.meta, ki.source_url,
               MIN(kv.embedding <=> %s::vector) AS distance
        FROM knowledge_items ki
        JOIN knowledge_vectors kv ON kv.item_id = ki.id
        WHERE ki.is_deleted = FALSE AND kv.embedding IS NOT NULL
          AND COALESCE(ki.meta->>'embedding_backend', 'hash') = %s
    """
    vector_params = [_vector_literal(query_vector), query_backend]
    if project_id:
        vector_sql += " AND ki.project_id = %s"
        vector_params.append(project_id)
    if kinds:
        vector_sql += " AND ki.kind = ANY(%s)"
        vector_params.append(kinds)
    vector_sql += " GROUP BY ki.id, ki.kind, ki.title, ki.body, ki.meta, ki.source_url ORDER BY distance LIMIT %s"
    vector_params.append(limit)
    try:
        rows = db.execute(vector_sql, tuple(vector_params)).fetchall()
        db.close()
        if rows:
            return [dict(row) for row in rows]
    except Exception:
        db.rollback()
        db.close()

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
    rebuild_item_embeddings(str(kid))
    return str(kid)


def list_by_kind(project_id: str, kind: str) -> list[dict]:
    db = connect()
    rows = db.execute(
        "SELECT id, kind, title, body, source_url, created_at FROM knowledge_items WHERE project_id=%s AND kind=%s AND is_deleted=FALSE ORDER BY created_at DESC LIMIT 50",
        (project_id, kind),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]
