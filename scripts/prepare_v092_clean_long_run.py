#!/usr/bin/env python3
"""Create a clean, isolated V7 long-run acceptance novel.

The source novel is read only.  Its chapters are never deleted or modified;
the new novel receives the story setup but no historical chapter prose or V7
state.  This is the only supported preparation path for a production-style
20-chapter run.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import connect, encode, new_id  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="prepare a clean V7 long-run novel")
    parser.add_argument("--source-novel-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--title", required=True)
    return parser.parse_args()


def clean_meta(source_meta: object) -> dict:
    meta = deepcopy(source_meta) if isinstance(source_meta, dict) else {}
    # These fields describe historical chapter planning and would contaminate
    # a from-scratch generation run.  Keep the premise, setting and style.
    for key in ("chapter_outlines", "chapter_tree", "story_arcs", "volume_plan", "source_facts"):
        meta.pop(key, None)
    meta["long_run_acceptance"] = {
        "schema_version": "v092-clean-long-run-v1",
        "source_novel_id": "",
        "historical_chapters_cleared": True,
        "v7_state_cleared": True,
    }
    return meta


def main() -> int:
    args = parse_args()
    conn = connect()
    try:
        source = conn.execute(
            "SELECT project_id, meta FROM contents "
            "WHERE id=%s AND type='novel' AND is_deleted=FALSE",
            (args.source_novel_id,),
        ).fetchone()
        if not source:
            raise RuntimeError("source novel not found or deleted")
        if str(source["project_id"]) != str(args.project_id):
            raise RuntimeError("source novel does not belong to the requested project")

        novel_id = new_id("cnt")
        meta = clean_meta(source.get("meta") or {})
        meta["long_run_acceptance"]["source_novel_id"] = str(args.source_novel_id)
        body = {"type": "doc", "content": []}
        conn.execute(
            """
            INSERT INTO contents
                (id, project_id, type, title, body, meta, status, owner_id)
            VALUES (%s, %s, 'novel', %s, %s, %s, 'draft', %s)
            """,
            (
                novel_id,
                args.project_id,
                args.title,
                encode(body),
                encode(meta),
                args.owner_id,
            ),
        )
        conn.execute(
            "INSERT INTO versions (id, entity_type, entity_id, label, snapshot) "
            "VALUES (%s, 'content', %s, 'initial_idea', %s)",
            (new_id("ver"), novel_id, encode({"title": args.title, "body": body, "meta": meta})),
        )
        conn.commit()
        chapter_count = conn.execute(
            "SELECT COUNT(*) AS count FROM contents "
            "WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE",
            (novel_id,),
        ).fetchone()["count"]
        print(json.dumps({
            "novel_id": str(novel_id),
            "project_id": str(args.project_id),
            "owner_id": str(args.owner_id),
            "title": args.title,
            "active_chapters": int(chapter_count),
            "historical_chapters_cleared": int(chapter_count) == 0,
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
