"""Batch API endpoints: C2 tool/branch, C3 golden case, C4 libraries, C5 diff, C6 chapter import/planning, C7 platform validate."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.db import connect

router = APIRouter(prefix="/api/v1", tags=["batch"])


def ok(data):
    return {"code": 0, "message": "ok", "data": data}


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
    return ok({"chapters": chapters, "count": len(chapters)})


@router.get("/novels/layered-plan")
def get_layered_plan(idea: str, genre: str = "东方玄幻", target_words: int = 1000000, user: dict = Depends(get_current_user)):
    from app.services.batch_fixes import build_layered_outline
    return ok(build_layered_outline(idea, genre, target_words))


# --- C7: Platform validate ---

@router.post("/publish/validate")
def validate_platform(content: str, platform: str, user: dict = Depends(get_current_user)):
    from app.services.batch_fixes import validate_content_for_platform
    return ok(validate_content_for_platform(content, platform))
