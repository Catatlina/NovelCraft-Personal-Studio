#!/usr/bin/env python3
"""Storage/context scale probe: one million persisted Chinese characters, no AI claim."""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import connect, encode, new_id  # noqa: E402
from app.services.assembler import ContextAssembler  # noqa: E402


def main() -> int:
    db = connect()
    project = db.execute("SELECT id FROM projects ORDER BY created_at LIMIT 1").fetchone()
    if not project:
        db.close()
        raise SystemExit("scale probe requires one existing project")
    novel_id = new_id()
    marker = f"scale-probe-{uuid.uuid4().hex[:10]}"
    paragraph = "雨落在旧城的玻璃穹顶上，远处钟声推动人物继续寻找被删去的真相。" * 33
    started = time.perf_counter()
    try:
        db.execute(
            "INSERT INTO contents (id,project_id,type,title,body,meta,status) VALUES (%s,%s,'novel',%s,%s,%s,'draft')",
            (novel_id, project["id"], marker, encode({"type": "doc", "content": []}),
             encode({"book_summary": "百万字存储与上下文预算探针"})),
        )
        total_chars = 0
        for seq in range(1, 1001):
            text = f"第{seq}章。{paragraph}"
            total_chars += len(text)
            db.execute(
                """INSERT INTO contents (id,project_id,parent_id,type,title,body,meta,status)
                   VALUES (%s,%s,%s,'chapter',%s,%s,%s,'reviewed')""",
                (new_id(), project["id"], novel_id, f"第{seq}章 探针",
                 encode({"type": "doc", "content": [{"type": "paragraph", "text": text}]}),
                 encode({"seq": seq, "chapter_summary": text[:180]})),
            )
        db.commit()
        inserted_seconds = time.perf_counter() - started

        query_started = time.perf_counter()
        count = db.execute(
            "SELECT COUNT(*) AS n FROM contents WHERE parent_id=%s AND type='chapter'", (novel_id,)
        ).fetchone()["n"]
        query_ms = (time.perf_counter() - query_started) * 1000
        context_started = time.perf_counter()
        context = ContextAssembler(novel_id).build()
        context_ms = (time.perf_counter() - context_started) * 1000
        result = {
            "status": "passed" if count == 1000 and total_chars >= 1_000_000 and len(context) <= 10_800 else "failed",
            "scope": "storage_and_context_budget_only",
            "ai_quality_claim": False,
            "chapters": count, "persisted_characters": total_chars,
            "insert_seconds": round(inserted_seconds, 3), "count_query_ms": round(query_ms, 3),
            "assembled_context_characters": len(context), "assemble_ms": round(context_ms, 3),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "passed" else 1
    finally:
        db.execute("DELETE FROM contents WHERE parent_id=%s", (novel_id,))
        db.execute("DELETE FROM contents WHERE id=%s", (novel_id,))
        db.commit()
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
