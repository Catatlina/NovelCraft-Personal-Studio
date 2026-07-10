#!/usr/bin/env python3
"""Idempotent V1 → V2 migration with dry-run validation and rollback safety.

Run:
  python scripts/migrate_v1_to_v2.py --v1-db postgresql://... --v2-db postgresql://...
  python scripts/migrate_v1_to_v2.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg2
import psycopg2.extras

DEFAULT_V1_DB = os.getenv("V1_DATABASE_URL", "postgresql://novelcraft:novelcraft@localhost/novelcraft_v1")
DEFAULT_V2_DB = os.getenv("DATABASE_URL", "postgresql://novelcraft:novelcraft@localhost/novelcraft_dev")
REQUIRED_V1_TABLES = ("users", "projects", "novels", "chapters")


def connect(url: str) -> psycopg2.extensions.connection:
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


def table_exists(conn: psycopg2.extensions.connection, table: str) -> bool:
    with conn.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s) IS NOT NULL AS present", (f"public.{table}",))
        return bool(cursor.fetchone()["present"])


def table_columns(conn: psycopg2.extensions.connection, table: str) -> set[str]:
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
            (table,),
        )
        return {row["column_name"] for row in cursor.fetchall()}


def source_rows(conn: psycopg2.extensions.connection, table: str, order_by: str = "") -> list[dict[str, Any]]:
    columns = table_columns(conn, table)
    where = " WHERE is_deleted = FALSE" if "is_deleted" in columns else ""
    order = f" ORDER BY {order_by}" if order_by else ""
    with conn.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {table}{where}{order}")  # trusted internal table names only
        return [dict(row) for row in cursor.fetchall()]


def _stats() -> dict[str, int]:
    return {"source": 0, "inserted": 0, "existing": 0}


def _record(summary: dict[str, Any], key: str, cursor, source_increment: int = 1) -> None:
    summary[key]["source"] += source_increment
    if cursor.rowcount:
        summary[key]["inserted"] += cursor.rowcount
    else:
        summary[key]["existing"] += source_increment


def _stable_version_id(chapter_id: Any) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"novelcraft:v1:chapter-version:{chapter_id}"))


def migrate(v1_url: str, v2_url: str, dry_run: bool = False) -> dict[str, Any]:
    """Migrate supported entities; dry-run executes all SQL and rolls the V2 transaction back."""
    v1 = connect(v1_url)
    v2 = connect(v2_url)
    summary: dict[str, Any] = {
        "mode": "dry-run" if dry_run else "commit",
        "users": _stats(),
        "projects": _stats(),
        "memberships": _stats(),
        "novels": _stats(),
        "chapters": _stats(),
        "characters": _stats(),
        "validation": {},
    }
    try:
        if v1.dsn == v2.dsn:
            raise RuntimeError("V1 and V2 database connections must be different")
        missing = [table for table in REQUIRED_V1_TABLES if not table_exists(v1, table)]
        if missing:
            raise RuntimeError(f"V1 database is missing required tables: {', '.join(missing)}")

        users = source_rows(v1, "users")
        projects = source_rows(v1, "projects")
        novels = source_rows(v1, "novels")
        chapters = source_rows(v1, "chapters", "novel_id, chapter_number")
        characters = source_rows(v1, "characters") if table_exists(v1, "characters") else []
        novel_projects = {str(novel.get("id")): novel.get("project_id") for novel in novels}

        with v2.cursor() as cursor:
            for user in users:
                cursor.execute(
                    """
                    INSERT INTO users (id, email, password_hash, display_name, created_at)
                    VALUES (%s, %s, %s, %s, %s) ON CONFLICT(id) DO NOTHING
                    """,
                    (
                        user.get("id"), user.get("email", ""), user.get("password_hash", ""),
                        user.get("display_name", ""), user.get("created_at", datetime.now(timezone.utc)),
                    ),
                )
                _record(summary, "users", cursor)

            for project in projects:
                cursor.execute(
                    """
                    INSERT INTO projects (id, name, description, owner_id, created_at)
                    VALUES (%s, %s, %s, %s, %s) ON CONFLICT(id) DO NOTHING
                    """,
                    (
                        project.get("id"), project.get("name", ""), project.get("description", ""),
                        project.get("owner_id"), project.get("created_at", datetime.now(timezone.utc)),
                    ),
                )
                _record(summary, "projects", cursor)
                membership_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"novelcraft:v1:owner:{project.get('id')}"))
                cursor.execute(
                    """
                    INSERT INTO project_members (id, project_id, user_id, role)
                    VALUES (%s, %s, %s, 'owner') ON CONFLICT(project_id, user_id) DO NOTHING
                    """,
                    (membership_id, project.get("id"), project.get("owner_id")),
                )
                _record(summary, "memberships", cursor)

            for novel in novels:
                body = {"type": "doc", "content": []}
                meta = {
                    "idea": novel.get("idea", ""), "genre": novel.get("genre", ""),
                    "style": novel.get("style", ""), "target_words": novel.get("target_words", 0),
                    "synopsis": novel.get("synopsis", ""), "v1_id": str(novel.get("id")),
                }
                cursor.execute(
                    """
                    INSERT INTO contents (id, project_id, type, title, body, meta, status, created_at)
                    VALUES (%s, %s, 'novel', %s, %s, %s, 'draft', %s) ON CONFLICT(id) DO NOTHING
                    """,
                    (
                        novel.get("id"), novel.get("project_id"), novel.get("title", "未命名"),
                        json.dumps(body, ensure_ascii=False), json.dumps(meta, ensure_ascii=False),
                        novel.get("created_at", datetime.now(timezone.utc)),
                    ),
                )
                _record(summary, "novels", cursor)

            for chapter in chapters:
                raw_body = chapter.get("content", "")
                body = (
                    {"type": "doc", "content": [{"type": "paragraph", "text": raw_body}]}
                    if isinstance(raw_body, str) else raw_body
                )
                meta = {
                    "seq": chapter.get("chapter_number", 1),
                    "word_count": len("".join(str(raw_body).split())),
                    "v1_id": str(chapter.get("id")),
                }
                project_id = chapter.get("project_id") or chapter.get("novel_project_id") or novel_projects.get(str(chapter.get("novel_id")))
                cursor.execute(
                    """
                    INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status, created_at)
                    VALUES (%s, %s, %s, 'chapter', %s, %s, %s, 'draft', %s) ON CONFLICT(id) DO NOTHING
                    """,
                    (
                        chapter.get("id"), project_id, chapter.get("novel_id"), chapter.get("title", "未命名"),
                        json.dumps(body, ensure_ascii=False), json.dumps(meta, ensure_ascii=False),
                        chapter.get("created_at", datetime.now(timezone.utc)),
                    ),
                )
                _record(summary, "chapters", cursor)
                cursor.execute(
                    """
                    INSERT INTO versions (id, entity_type, entity_id, label, reason, snapshot, created_at)
                    VALUES (%s, 'content', %s, 'v1_migration', 'migration', %s, %s)
                    ON CONFLICT(id) DO NOTHING
                    """,
                    (
                        _stable_version_id(chapter.get("id")), chapter.get("id"),
                        json.dumps({"title": chapter.get("title", ""), "body": body, "meta": meta}, ensure_ascii=False),
                        datetime.now(timezone.utc),
                    ),
                )

            for character in characters:
                project_id = character.get("project_id") or novel_projects.get(str(character.get("novel_id")))
                cursor.execute(
                    """
                    INSERT INTO knowledge_items (id, project_id, content_id, kind, title, body, meta, created_at)
                    VALUES (%s, %s, %s, 'character', %s, %s, %s, %s) ON CONFLICT(id) DO NOTHING
                    """,
                    (
                        character.get("id"), project_id, character.get("novel_id"), character.get("name", ""),
                        character.get("description", ""),
                        json.dumps({"v1_id": str(character.get("id")), "role": character.get("role", "")}, ensure_ascii=False),
                        character.get("created_at", datetime.now(timezone.utc)),
                    ),
                )
                _record(summary, "characters", cursor)

            cursor.execute("SELECT COUNT(*) AS total FROM contents WHERE meta ? 'v1_id'")
            summary["validation"]["v2_migrated_contents"] = cursor.fetchone()["total"]
            cursor.execute("SELECT COUNT(*) AS total FROM knowledge_items WHERE meta ? 'v1_id'")
            summary["validation"]["v2_migrated_characters"] = cursor.fetchone()["total"]

        if dry_run:
            v2.rollback()
            summary["rolled_back"] = True
        else:
            v2.commit()
            summary["rolled_back"] = False
        return summary
    except Exception:
        v2.rollback()
        raise
    finally:
        v1.close()
        v2.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="V1→V2 data migration")
    parser.add_argument("--v1-db", default=DEFAULT_V1_DB)
    parser.add_argument("--v2-db", default=DEFAULT_V2_DB)
    parser.add_argument("--dry-run", action="store_true", help="Execute validation and roll back all V2 writes")
    args = parser.parse_args()
    try:
        result = migrate(args.v1_db, args.v2_db, dry_run=args.dry_run)
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
