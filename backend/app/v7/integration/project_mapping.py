"""Durable V7 novel -> V6 project mapping.

The V7 director receives a novel id while the V6 library is scoped by project.
This module makes that boundary explicit and validates an explicitly supplied
project instead of silently trusting a caller-provided pair.
"""
from __future__ import annotations

from typing import Any

from ...db import connect


def ensure_novel_project_link(
    novel_id: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Resolve and persist the project scope for one V7 novel.

    The mapping migration is required before the V7 director can write to V6.
    An explicit project must match the V6 novel row; an omitted project is
    resolved from the durable mapping and then backfilled from ``contents``
    only for older rows created before the mapping migration.
    """
    if not str(novel_id or "").strip():
        raise ValueError("novel_id is required")

    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT id, project_id
            FROM contents
            WHERE id=%s AND type='novel' AND is_deleted=FALSE
            """,
            (novel_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"novel {novel_id} does not exist in V6 contents")

        v6_project_id = str(row["project_id"])
        if project_id and str(project_id) != v6_project_id:
            raise ValueError(
                f"novel {novel_id} belongs to project {v6_project_id}, "
                f"not {project_id}"
            )

        mapped = conn.execute(
            """
            SELECT project_id, source
            FROM v7_novel_project_links
            WHERE novel_id=%s
            """,
            (novel_id,),
        ).fetchone()
        if mapped and str(mapped["project_id"]) != v6_project_id:
            raise ValueError(
                f"durable V7 mapping for novel {novel_id} conflicts with V6 contents"
            )

        conn.execute(
            """
            INSERT INTO v7_novel_project_links (novel_id, project_id, source)
            VALUES (%s, %s, %s)
            ON CONFLICT (novel_id) DO UPDATE SET
                project_id=EXCLUDED.project_id,
                source=EXCLUDED.source,
                updated_at=now()
            """,
            (novel_id, v6_project_id, "v7_director" if project_id else "v6_contents"),
        )
        conn.commit()
        return {
            "novel_id": str(novel_id),
            "project_id": v6_project_id,
            "source": "v7_director" if project_id else "v6_contents",
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
