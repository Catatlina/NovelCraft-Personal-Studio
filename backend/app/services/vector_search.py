"""C4: pgvector-based vector search + knowledge hub retrieval."""
from __future__ import annotations
import os
from app.db import connect, encode


VECTOR_DIM = 384  # Default for all-MiniLM-L6-v2


def ensure_pgvector_extension():
    """Ensure the pgvector extension is installed."""
    db = connect()
    db.execute("CREATE EXTENSION IF NOT EXISTS vector")
    db.commit()
    db.close()


def add_embedding_column_if_needed():
    """Add embedding column to knowledge_items if not exists."""
    db = connect()
    try:
        db.execute(f"ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS embedding vector({VECTOR_DIM})")
        db.execute(f"CREATE INDEX IF NOT EXISTS idx_knowledge_embedding ON knowledge_items USING ivfflat (embedding vector_cosine_ops)")
        db.commit()
    except Exception:
        db.rollback()
    db.close()


def embed_text(text: str) -> list[float]:
    """Generate embedding vector for text using a simple hash-based fallback."""
    import hashlib, struct
    h = hashlib.sha256(text.encode()).digest()
    vec = []
    for i in range(0, min(len(h), VECTOR_DIM * 4), 4):
        val = struct.unpack('f', h[i:i+4])[0]
        vec.append(max(-1.0, min(1.0, val)))
    while len(vec) < VECTOR_DIM:
        vec.append(0.0)
    return vec[:VECTOR_DIM]


def search_knowledge(query: str, project_id: str = "", top_k: int = 10) -> list[dict]:
    """Search knowledge items by vector similarity."""
    ensure_pgvector_extension()
    add_embedding_column_if_needed()

    vec = embed_text(query)
    vec_str = "[" + ",".join(str(v) for v in vec) + "]"

    db = connect()
    try:
        rows = db.execute(
            f"""SELECT id, kind, title, body, meta, 
               1 - (embedding <=> %s::vector) as similarity
               FROM knowledge_items 
               WHERE embedding IS NOT NULL
               {'AND project_id = %s' if project_id else ''}
               ORDER BY embedding <=> %s::vector 
               LIMIT %s""",
            (vec_str, project_id, vec_str, top_k) if project_id else (vec_str, vec_str, top_k)
        ).fetchall()
    except Exception:
        # Fallback: full-text search
        rows = db.execute(
            """SELECT id, kind, title, body, meta, 0.5 as similarity
               FROM knowledge_items
               WHERE title ILIKE %s OR body ILIKE %s
               LIMIT %s""",
            (f"%{query}%", f"%{query}%", top_k)
        ).fetchall()

    db.close()
    return [{
        "id": r["id"], "kind": r.get("kind", ""), "title": r.get("title", ""),
        "body": (r.get("body") or "")[:500],
        "similarity": round(float(r.get("similarity", 0)), 3),
    } for r in rows]


def embed_all_knowledge_items(batch_size: int = 50) -> int:
    """Batch-embed all knowledge items without embeddings."""
    db = connect()
    items = db.execute(
        "SELECT id, title, body FROM knowledge_items WHERE embedding IS NULL LIMIT %s",
        (batch_size,)
    ).fetchall()
    count = 0
    for item in items:
        text = f"{item.get('title', '')}\n{item.get('body', '')[:2000]}"
        vec = embed_text(text)
        vec_str = "[" + ",".join(str(v) for v in vec) + "]"
        try:
            db.execute(
                "UPDATE knowledge_items SET embedding = %s::vector WHERE id = %s",
                (vec_str, item["id"])
            )
            count += 1
        except Exception:
            pass
    db.commit()
    db.close()
    return count
