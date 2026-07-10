"""M3: Knowledge Hub — vector search + ingest."""
from __future__ import annotations

import hashlib
import math
import re

from app.db import connect
from app.db import new_id

EMBEDDING_DIMENSION = 1536


def _local_embedding(text: str) -> list[float]:
    """Create a deterministic, normalized hashing embedding without an external service."""
    vector = [0.0] * EMBEDDING_DIMENSION
    normalized = re.sub(r"\s+", "", (text or "").lower())
    tokens = [normalized[i:i + 2] for i in range(max(0, len(normalized) - 1))]
    if len(normalized) == 1:
        tokens = [normalized]
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        vector[index] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


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
    """Atomically replace an item's chunks; embeddings can be filled by the configured model worker.

    Uses a deterministic local hashing embedding so indexing works offline and remains rebuildable.
    """
    db = connect()
    item = db.execute("SELECT body FROM knowledge_items WHERE id = %s AND is_deleted = FALSE", (item_id,)).fetchone()
    if not item:
        db.close()
        return 0
    chunks = _chunk_text(item.get("body", ""))
    db.execute("DELETE FROM knowledge_vectors WHERE item_id = %s", (item_id,))
    for chunk_no, chunk in enumerate(chunks):
        db.execute(
            "INSERT INTO knowledge_vectors (id, item_id, chunk_no, embedding, chunk_text) VALUES (%s, %s, %s, %s::vector, %s)",
            (new_id(), item_id, chunk_no, _vector_literal(_local_embedding(chunk)), chunk),
        )
    db.commit(); db.close()
    return len(chunks)


def search(query: str, project_id: str | None = None, kinds: list[str] | None = None, limit: int = 10) -> list[dict]:
    """Search indexed knowledge by vector distance, with lexical fallback."""
    db = connect()
    vector_sql = """
        SELECT ki.id, ki.kind, ki.title, ki.body, ki.meta, ki.source_url,
               MIN(kv.embedding <=> %s::vector) AS distance
        FROM knowledge_items ki
        JOIN knowledge_vectors kv ON kv.item_id = ki.id
        WHERE ki.is_deleted = FALSE AND kv.embedding IS NOT NULL
    """
    vector_params = [_vector_literal(_local_embedding(query))]
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
