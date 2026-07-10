"""M3: Knowledge hub import/export + style similarity + daily briefing."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.core.security import get_current_user
from app.db import connect, encode, new_id

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


@router.post("/import")
async def import_knowledge(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """TASK-035: Import text/JSON knowledge items."""
    text = (await file.read()).decode("utf-8", errors="replace")
    lines = [l.strip() for l in text.split("\n") if l.strip() and not l.strip().startswith("#")]
    db = connect()
    count = 0
    for line in lines[:100]:  # Cap at 100 items
        try:
            import json as _json
            item = _json.loads(line) if line.startswith("{") else {"title": line[:100], "body": line, "kind": "note"}
            db.execute(
                "INSERT INTO knowledge_items (id, kind, title, body, meta) VALUES (%s,%s,%s,%s,%s)",
                (new_id(), item.get("kind", "note"), item.get("title", "unknown"),
                 item.get("body", line), encode(item.get("meta", {}))),
            )
            count += 1
        except Exception:
            pass
    db.commit(); db.close()
    return {"code": 0, "message": "ok", "data": {"imported": count}}


@router.get("/style-check")
def check_style_similarity(text: str, user: dict = Depends(get_current_user)):
    """TASK-036: N-gram similarity check against stored styles."""
    if len(text) < 50:
        return {"code": 0, "message": "ok", "data": {"similarity": 0, "warning": None}}
    
    def ngrams(s: str, n: int = 4):
        return set(s[i:i+n] for i in range(len(s) - n + 1))
    
    text_ngrams = ngrams(text)
    db = connect()
    rows = db.execute("SELECT body FROM knowledge_items WHERE kind = 'reference' LIMIT 20").fetchall()
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


@router.post("/daily-briefing")
def daily_briefing(project_id: str = "", user: dict = Depends(get_current_user)):
    """TASK-038: Generate daily briefing from recent content + hotspots."""
    db = connect()
    recent = db.execute(
        "SELECT title, type, updated_at FROM contents WHERE project_id = %s AND is_deleted = FALSE ORDER BY updated_at DESC LIMIT 10",
        (project_id,),
    ).fetchall() if project_id else []
    stats = db.execute(
        "SELECT COUNT(*) as total, type FROM contents WHERE project_id = %s AND is_deleted = FALSE GROUP BY type",
        (project_id,),
    ).fetchall() if project_id else []
    db.close()
    
    items = [{"title": r.get("title",""), "type": r.get("type",""), "updated": str(r.get("updated_at",""))} for r in recent]
    return {"code": 0, "message": "ok", "data": {
        "recent_content": items,
        "stats": [{"type": s.get("type",""), "count": s.get("total",0)} for s in stats],
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    }}
