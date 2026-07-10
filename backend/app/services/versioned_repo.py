"""VersionedRepository — ensures save() snapshots before write."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.db import connect, encode, new_id


def save(entity_type: str, entity_id: str, data: dict, label: str = "auto_save") -> dict:
    """Versioned save: snapshot current state, then update."""
    db = connect()
    # Snapshot current state
    row = db.execute(f"SELECT * FROM {entity_type}s WHERE id = %s", (entity_id,)).fetchone()
    if row:
        snapshot = {k: str(v) if isinstance(v, (datetime,)) else v for k, v in dict(row).items()}
        # Find latest version for parent_version_id chain
        latest = db.execute(
            "SELECT id FROM versions WHERE entity_type=%s AND entity_id=%s ORDER BY created_at DESC LIMIT 1",
            (entity_type, entity_id),
        ).fetchone()
        parent_id = latest["id"] if latest else None
        db.execute(
            "INSERT INTO versions (id, entity_type, entity_id, parent_version_id, label, snapshot) VALUES (%s,%s,%s,%s,%s,%s)",
            (new_id(), entity_type, entity_id, parent_id, label, encode(snapshot)),
        )
        # Update with new data
        set_clauses = ", ".join(f"{k} = %s" for k in data.keys())
        values = list(data.values()) + [entity_id]
        db.execute(f"UPDATE {entity_type}s SET {set_clauses}, updated_at = now() WHERE id = %s", tuple(values))
    db.commit()
    db.close()
    return {"status": "saved", "entity_type": entity_type, "entity_id": entity_id, "label": label}


def restore(entity_type: str, entity_id: str, version_id: str) -> dict:
    """Restore entity to a specific version."""
    db = connect()
    ver = db.execute("SELECT * FROM versions WHERE id = %s", (version_id,)).fetchone()
    if not ver:
        db.close()
        return {"error": "version not found"}
    snapshot = ver["snapshot"]
    if isinstance(snapshot, str):
        snapshot = json.loads(snapshot)
    # Save current state as a version first, then restore
    current = db.execute(f"SELECT * FROM {entity_type}s WHERE id = %s", (entity_id,)).fetchone()
    if current:
        current_snap = {k: str(v) if isinstance(v, (datetime,)) else v for k, v in dict(current).items()}
        db.execute(
            "INSERT INTO versions (id, entity_type, entity_id, parent_version_id, label, snapshot) VALUES (%s,%s,%s,%s,%s,%s)",
            (new_id(), entity_type, entity_id, version_id, "pre_restore", encode(current_snap)),
        )
    # Restore fields from snapshot
    updatable = {k: v for k, v in snapshot.items() if k not in ("id", "created_at", "updated_at")}
    set_clauses = ", ".join(f"{k} = %s" for k in updatable.keys())
    values = list(updatable.values()) + [entity_id]
    if set_clauses:
        db.execute(f"UPDATE {entity_type}s SET {set_clauses}, updated_at = now() WHERE id = %s", tuple(values))
    db.commit()
    db.close()
    return {"status": "restored", "entity_type": entity_type, "entity_id": entity_id, "version": version_id}
