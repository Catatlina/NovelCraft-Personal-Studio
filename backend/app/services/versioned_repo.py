"""Versioned repository — snapshot + restore with audit trail.

Tables supported: contents, knowledge_items, projects, model_routes, prompts.
Column whitelisting prevents SQL injection.

⚠️ DEPRECATED — This module has no active callers in the production codebase.
It is preserved for reference but not loaded by any endpoint or worker.
Consider removing after the next major release if still unused.
Audit: 2026-07-12 — confirmed dead code (grep: zero imports found).
"""
from __future__ import annotations

from datetime import datetime

from app.db import connect, encode, new_id

ENTITY_TABLE_MAP = {
    "content": "contents",
    "knowledge_item": "knowledge_items",
    "project": "projects",
    "model_route": "model_routes",
    "prompt": "prompts",
}

ALLOWED_COLUMNS = {
    "contents": {"title", "body", "meta", "status", "updated_at"},
    "knowledge_items": {"title", "body", "meta", "kind", "source_url", "updated_at"},
    "projects": {"name", "description", "updated_at"},
    "model_routes": {"provider", "model", "params", "fallback_json", "is_active", "updated_at"},
    "prompts": {"template", "version", "golden_cases", "updated_at"},
}


def save(entity_type: str, entity_id: str, data: dict, label: str = "auto_save") -> dict:
    """Versioned save: snapshot current state, then update."""
    table = ENTITY_TABLE_MAP.get(entity_type)
    if not table:
        raise ValueError(f"unsupported entity_type: {entity_type}")
    allowed = ALLOWED_COLUMNS.get(table, set())

    db = connect()
    row = db.execute(f"SELECT * FROM {table} WHERE id = %s", (entity_id,)).fetchone()
    if row:
        snapshot = {k: str(v) if isinstance(v, datetime) else v for k, v in dict(row).items()}
        latest = db.execute(
            "SELECT id FROM versions WHERE entity_type=%s AND entity_id=%s ORDER BY created_at DESC LIMIT 1",
            (entity_type, entity_id),
        ).fetchone()
        parent_id = latest["id"] if latest else None
        db.execute(
            "INSERT INTO versions (id, entity_type, entity_id, parent_version_id, label, snapshot) VALUES (%s,%s,%s,%s,%s,%s)",
            (new_id(), entity_type, entity_id, parent_id, label, encode(snapshot)),
        )
        # Update: only whitelisted columns
        safe_data = {k: v for k, v in data.items() if k in allowed}
        if safe_data:
            set_clauses = ", ".join(f"{k} = %s" for k in safe_data.keys())
            values = list(safe_data.values()) + [entity_id]
            db.execute(f"UPDATE {table} SET {set_clauses}, updated_at = now() WHERE id = %s", tuple(values))
        db.commit()
    db.close()
    return {"status": "saved"}


def restore(entity_type: str, entity_id: str, version_id: str) -> dict:
    """Restore entity to a specific version snapshot."""
    table = ENTITY_TABLE_MAP.get(entity_type)
    if not table:
        raise ValueError(f"unsupported entity_type: {entity_type}")
    db = connect()
    version = db.execute(
        "SELECT snapshot FROM versions WHERE id = %s AND entity_type = %s AND entity_id = %s",
        (version_id, entity_type, entity_id),
    ).fetchone()
    if not version:
        db.close()
        return {"error": "version not found"}
    snapshot = version["snapshot"]
    db.execute(f"UPDATE {table} SET body = %s, meta = %s, updated_at = now() WHERE id = %s",
               (snapshot.get("body"), snapshot.get("meta"), entity_id))
    db.commit()
    db.close()
    return {"status": "restored", "version_id": version_id}


def list_versions(entity_type: str, entity_id: str, limit: int = 20) -> list[dict]:
    """List versions for an entity (metadata only, no full snapshots)."""
    table = ENTITY_TABLE_MAP.get(entity_type)
    if not table:
        return []
    db = connect()
    rows = db.execute(
        "SELECT id, entity_type, entity_id, parent_version_id, label, created_at FROM versions WHERE entity_type=%s AND entity_id=%s ORDER BY created_at DESC LIMIT %s",
        (entity_type, entity_id, limit),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]
