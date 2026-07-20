"""Batch API endpoints: C2 tool/branch, C3 golden case, C4 libraries, C5 diff, C6 chapter import/planning, C7 platform validate."""
from __future__ import annotations

import hashlib
import re

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.db import connect, encode, new_id
from app.core.authz import ok

router = APIRouter(prefix="/api/v1", tags=["batch"])


# --- C2: Tool/Branch ---

@router.post("/tools/{tool_name}/register")
def register_tool(tool_name: str, user: dict = Depends(get_current_user)):
    from app.services.batch_fixes import register_tool_node
    return ok(register_tool_node(tool_name, lambda: True))


@router.post("/runs/{run_id}/branch")
def evaluate_branch(run_id: str, condition: dict = {}, user: dict = Depends(get_current_user)):
    from app.services.batch_fixes import execute_branch_node
    return ok(execute_branch_node(condition, []))


# --- C3: Golden case ---

@router.get("/prompts/golden-check")
def run_golden_check(user: dict = Depends(get_current_user)):
    from app.services.batch_fixes import run_golden_case_check
    return ok(run_golden_case_check())


# --- C4: 4-libraries ---

@router.get("/library/{library}")
def list_library(library: str, project_id: str = "", user: dict = Depends(get_current_user)):
    from app.services.batch_fixes import list_library_items
    return ok(list_library_items(library, project_id))


@router.post("/library/{library}")
def create_library_item_endpoint(library: str, data: dict, project_id: str = "", user: dict = Depends(get_current_user)):
    from app.services.batch_fixes import create_library_item
    return ok({"id": create_library_item(library, data, project_id)})


# --- C5: Diff ---

@router.post("/contents/{content_id}/diff")
def diff_content(content_id: str, body: dict, user: dict = Depends(get_current_user)):
    from app.services.batch_fixes import diff_texts
    conn = connect()
    row = conn.execute("SELECT body FROM contents WHERE id = %s", (content_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    old_text = str(row["body"])
    new_text = body.get("body", "")
    diffs = diff_texts(old_text, new_text)
    return ok({"diffs": diffs, "count": len(diffs)})


# --- C6: Chapter import + Layered planning ---

@router.post("/novels/{novel_id}/import-chapters")
def import_chapters(novel_id: str, body: dict, user: dict = Depends(get_current_user)):
    from app.services.batch_fixes import import_chapter_directory
    text = body.get("text", "")
    chapters = import_chapter_directory(text, novel_id)
    db = connect()
    try:
        novel = db.execute("SELECT * FROM contents WHERE id=%s AND type='novel' AND is_deleted=FALSE",
                           (novel_id,)).fetchone()
        if not novel:
            raise HTTPException(404, "novel not found")
        member = db.execute("SELECT role FROM project_members WHERE project_id=%s AND user_id=%s",
                            (novel["project_id"], user["id"])).fetchone()
        if not member or member["role"] not in {"owner", "editor"}:
            raise HTTPException(403, "insufficient permissions")

        existing = db.execute("""SELECT id,title,meta FROM contents
                                  WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE""",
                              (novel_id,)).fetchall()
        max_row = db.execute("""SELECT COALESCE(MAX((meta->>'seq')::int),0) AS seq FROM contents
                                 WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE""",
                             (novel_id,)).fetchone()
        next_seq = int((max_row or {}).get("seq") or 0) + 1

        def normalized_title(value: str) -> str:
            value = re.sub(r"^第[一二三四五六七八九十百千\d]+章\s*", "", value.strip(), flags=re.I)
            return re.sub(r"\s+", "", value).casefold()

        seen = {normalized_title(str(row.get("title", ""))) for row in existing}
        ids: list[str] = []
        imported_chapters: list[dict] = []
        skipped = 0
        for parsed in chapters:
            title = parsed["title"].strip()
            identity = normalized_title(title)
            if not identity or identity in seen:
                skipped += 1
                continue
            seen.add(identity)
            chapter_id = new_id()
            display_title = f"第{next_seq}章 {title}"
            meta = {"seq": next_seq, "outline": title, "import_source": "chapter_directory",
                    "source_raw": parsed["raw"]}
            generation_key = "chapter-directory:" + hashlib.sha256(
                f"{novel_id}:{identity}".encode("utf-8")
            ).hexdigest()
            db.execute("""INSERT INTO contents
                          (id,project_id,parent_id,type,title,body,meta,status,owner_id,generation_key)
                          VALUES (%s,%s,%s,'chapter',%s,%s,%s,'planned',%s,%s)""",
                       (chapter_id, novel["project_id"], novel_id, display_title,
                        encode({"type": "doc", "content": []}), encode(meta), user["id"], generation_key))
            ids.append(chapter_id)
            imported_chapters.append({"id": chapter_id, "seq": next_seq, "title": title})
            next_seq += 1
        db.commit()
        return ok({"imported": len(ids), "skipped": skipped, "ids": ids,
                   "chapters": imported_chapters, "count": len(ids)})
    except Exception:
        if hasattr(db, "rollback"):
            db.rollback()
        raise
    finally:
        db.close()


@router.get("/novels/layered-plan")
def get_layered_plan(idea: str, genre: str = "东方玄幻", target_words: int = 1000000, user: dict = Depends(get_current_user)):
    from app.services.batch_fixes import build_layered_outline
    return ok(build_layered_outline(idea, genre, target_words))


# --- C7: Platform validate ---

@router.post("/publish/validate")
def validate_platform(content: str, platform: str, user: dict = Depends(get_current_user)):
    from app.services.batch_fixes import validate_content_for_platform
    return ok(validate_content_for_platform(content, platform))
