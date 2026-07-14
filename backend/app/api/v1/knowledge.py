"""M3: Knowledge hub import/export + style similarity + daily briefing."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.core.security import get_current_user
from app.db import connect, encode, new_id
from app.services.knowledge_hub import rebuild_item_embeddings
from app.services.knowledge_parser import extract_document_text, parse_text_file

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_SUFFIXES = {".txt", ".md", ".json", ".jsonl", ".pdf", ".docx"}


def _require_project_editor(project_id: str, user: dict) -> None:
    db = connect()
    member = db.execute(
        "SELECT role FROM project_members WHERE project_id = %s AND user_id = %s",
        (project_id, user["id"]),
    ).fetchone()
    db.close()
    if not member or member["role"] not in {"owner", "editor"}:
        raise HTTPException(status_code=403, detail="insufficient permissions")


def _require_item_access(item_id: str, user: dict) -> dict:
    db = connect()
    item = db.execute("SELECT * FROM knowledge_items WHERE id = %s AND is_deleted = FALSE", (item_id,)).fetchone()
    if not item:
        db.close()
        raise HTTPException(status_code=404, detail="knowledge item not found")
    member = db.execute(
        "SELECT role FROM project_members WHERE project_id = %s AND user_id = %s",
        (item.get("project_id"), user["id"]),
    ).fetchone()
    db.close()
    if not member or member["role"] not in {"owner", "editor"}:
        raise HTTPException(status_code=403, detail="insufficient permissions")
    return item


@router.post("/{item_id}/reindex")
def reindex_knowledge_item(item_id: str, user: dict = Depends(get_current_user)):
    _require_item_access(item_id, user)
    count = rebuild_item_embeddings(item_id)
    return {"code": 0, "message": "ok", "data": {"item_id": item_id, "chunks": count}}


@router.post("/reindex-project")
def reindex_project(project_id: str, user: dict = Depends(get_current_user)):
    """切换 EMBEDDING_BACKEND 后全量重嵌当前项目（owner/editor）。"""
    from app.api.v1.complete_api import require_project_member
    from app.services.knowledge_hub import reindex_project_embeddings

    require_project_member(project_id, user, write=True)
    return {"code": 0, "message": "ok", "data": reindex_project_embeddings(project_id)}


@router.post("/import")
def import_knowledge(project_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Import a bounded document into the caller's project and index every parsed section."""
    _require_project_editor(project_id, user)
    filename = file.filename or "upload.txt"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="unsupported document type")
    raw = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file exceeds 20 MB")
    try:
        text = extract_document_text(raw, filename)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if suffix in {".json", ".jsonl"}:
        try:
            decoded = json.loads(text) if suffix == ".json" else [json.loads(line) for line in text.splitlines() if line.strip()]
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="invalid JSON document") from exc
        source_items = decoded if isinstance(decoded, list) else [decoded]
        items = [
            {
                "title": str(item.get("title", filename))[:500],
                "body": str(item.get("body", ""))[:50_000],
                "kind": str(item.get("kind", "reference"))[:50],
                "meta": item.get("meta", {}),
            }
            for item in source_items if isinstance(item, dict)
        ]
    else:
        items = parse_text_file(text, filename)
    items = [item for item in items[:100] if item.get("body")]
    if not items:
        raise HTTPException(status_code=400, detail="document contains no importable text")

    db = connect()
    item_ids = []
    for item in items:
        item_id = new_id()
        db.execute(
            "INSERT INTO knowledge_items (id, project_id, kind, title, body, meta) VALUES (%s,%s,%s,%s,%s,%s)",
            (
                item_id, project_id, item.get("kind", "reference"), item.get("title", filename),
                item.get("body", ""), encode(item.get("meta", {"source_filename": filename})),
            ),
        )
        item_ids.append(item_id)
    db.commit()
    db.close()
    chunks = sum(rebuild_item_embeddings(item_id) for item_id in item_ids)
    return {"code": 0, "message": "ok", "data": {"imported": len(item_ids), "chunks": chunks, "item_ids": item_ids}}


@router.get("/style-check")
def check_style_similarity(text: str, project_id: str, user: dict = Depends(get_current_user)):
    """TASK-036: N-gram similarity check against stored styles."""
    if len(text) < 50:
        return {"code": 0, "message": "ok", "data": {"similarity": 0, "warning": None}}

    def ngrams(s: str, n: int = 4):
        return set(s[i:i+n] for i in range(len(s) - n + 1))

    text_ngrams = ngrams(text)
    db = connect()
    member = db.execute("SELECT 1 FROM project_members WHERE project_id=%s AND user_id=%s",
                        (project_id, user["id"])).fetchone()
    if not member:
        db.close()
        raise HTTPException(403, "not a project member")
    rows = db.execute(
        "SELECT body FROM knowledge_items WHERE project_id=%s AND kind = 'reference' AND is_deleted=FALSE LIMIT 20",
        (project_id,),
    ).fetchall()
    db.close()

    max_sim = 0
    for row in rows:
        ref = (row.get("body") or "")
        if len(ref) < 50:
            continue
        ref_ngrams = ngrams(ref)
        if not ref_ngrams:
            continue
        sim = len(text_ngrams & ref_ngrams) / max(len(text_ngrams), 1)
        max_sim = max(max_sim, sim)
    
    warning = "相似度较高，建议修改" if max_sim > 0.6 else None
    return {"code": 0, "message": "ok", "data": {"similarity": round(max_sim, 3), "warning": warning}}
