#!/usr/bin/env python3
"""TASK-004: V1 → V2 data migration script.

Maps V1 novels/chapters/characters to V2 unified content + knowledge model.
Run: python scripts/migrate_v1_to_v2.py [--v1-db postgresql://...] [--v2-db postgresql://...]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

V1_DB = os.getenv("V1_DATABASE_URL", "postgresql://novelcraft:novelcraft@localhost/novelcraft_v1")
V2_DB = os.getenv("DATABASE_URL", "postgresql://novelcraft:novelcraft@localhost/novelcraft_dev")


def connect(url: str) -> psycopg2.extensions.connection:
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


def migrate() -> dict:
    """Execute V1→V2 migration. Returns summary dict."""
    v1 = connect(V1_DB)
    v2 = connect(V2_DB)
    summary: dict[str, int] = {"users": 0, "projects": 0, "novels": 0, "chapters": 0, "characters": 0, "errors": 0}

    try:
        # ── Users ──
        v1_users = v1.cursor()
        v1_users.execute("SELECT * FROM users WHERE is_deleted = FALSE")
        for u in v1_users.fetchall():
            v2.cursor().execute(
                "INSERT INTO users (id, email, password_hash, display_name, created_at) VALUES (%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING",
                (u.get("id"), u.get("email", ""), u.get("password_hash", ""), u.get("display_name", ""), u.get("created_at", datetime.now(timezone.utc))),
            )
            summary["users"] += 1

        # ── Projects ──
        v1_projects = v1.cursor()
        v1_projects.execute("SELECT * FROM projects WHERE is_deleted = FALSE")
        for p in v1_projects.fetchall():
            v2.cursor().execute(
                "INSERT INTO projects (id, name, description, owner_id, created_at) VALUES (%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING",
                (p.get("id"), p.get("name", ""), p.get("description", ""), p.get("owner_id"), p.get("created_at", datetime.now(timezone.utc))),
            )
            summary["projects"] += 1

        # ── Novels → contents(type=novel) ──
        v1_novels = v1.cursor()
        v1_novels.execute("SELECT * FROM novels WHERE is_deleted = FALSE")
        for n in v1_novels.fetchall():
            body = {"type": "doc", "content": []}
            meta = {
                "idea": n.get("idea", ""),
                "genre": n.get("genre", ""),
                "style": n.get("style", ""),
                "target_words": n.get("target_words", 0),
                "synopsis": n.get("synopsis", ""),
                "v1_id": n.get("id"),
            }
            v2.cursor().execute(
                "INSERT INTO contents (id, project_id, type, title, body, meta, status, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING",
                (n.get("id"), n.get("project_id"), "novel", n.get("title", "未命名"), json.dumps(body), json.dumps(meta), "draft", n.get("created_at", datetime.now(timezone.utc))),
            )
            summary["novels"] += 1

        # ── Chapters → contents(type=chapter) ──
        v1_chapters = v1.cursor()
        v1_chapters.execute("SELECT * FROM chapters WHERE is_deleted = FALSE ORDER BY novel_id, chapter_number")
        for ch in v1_chapters.fetchall():
            body_content = ch.get("content", "")
            if isinstance(body_content, str):
                body = {"type": "doc", "content": [{"type": "paragraph", "text": body_content}]}
            else:
                body = body_content
            meta = {"seq": ch.get("chapter_number", 1), "v1_id": ch.get("id")}
            v2.cursor().execute(
                "INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING",
                (ch.get("id"), ch.get("novel_project_id"), ch.get("novel_id"), "chapter", ch.get("title", "未命名"), json.dumps(body), json.dumps(meta), "draft", ch.get("created_at", datetime.now(timezone.utc))),
            )
            # Version snapshot
            v2.cursor().execute(
                "INSERT INTO versions (id, entity_type, entity_id, label, snapshot, created_at) VALUES (gen_random_uuid(),'content',%s,'v1_migration',%s,%s)",
                (ch.get("id"), json.dumps({"title": ch.get("title", ""), "body": body, "meta": meta}), datetime.now(timezone.utc)),
            )
            summary["chapters"] += 1

        # ── Characters → knowledge_items ──
        try:
            v1_chars = v1.cursor()
            v1_chars.execute("SELECT * FROM characters WHERE is_deleted = FALSE")
            for c in v1_chars.fetchall():
                v2.cursor().execute(
                    "INSERT INTO knowledge_items (id, project_id, content_id, kind, title, body, meta, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING",
                    (c.get("id"), c.get("project_id"), c.get("novel_id"), "character", c.get("name", ""), c.get("description", ""), json.dumps({"v1_id": c.get("id"), "role": c.get("role", "")}), c.get("created_at", datetime.now(timezone.utc))),
                )
                summary["characters"] += 1
        except Exception:
            pass  # Characters table might not exist in V1

        v2.commit()
    except Exception as e:
        summary["errors"] += 1
        print(f"Migration error: {e}", file=sys.stderr)
        v2.rollback()
    finally:
        v1.close()
        v2.close()

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="V1→V2 data migration")
    parser.add_argument("--v1-db", default=V1_DB)
    parser.add_argument("--v2-db", default=V2_DB)
    parser.add_argument("--dry-run", action="store_true", help="Print summary without migrating")
    args = parser.parse_args()

    V1_DB, V2_DB = args.v1_db, args.v2_db

    if args.dry_run:
        print("Dry run — checking connectivity...")
        c = connect(V2_DB)
        c.cursor().execute("SELECT count(*) as cnt FROM information_schema.tables WHERE table_schema='public'")
        print(f"V2 tables: {c.cursor().fetchone()}")
        c.close()
        sys.exit(0)

    result = migrate()
    print(f"Migration complete: {json.dumps(result, indent=2)}")
