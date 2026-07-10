"""TASK-045: Overseas translation + localization endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.db import connect, encode, new_id

router = APIRouter(prefix="/api/v1/overseas", tags=["overseas"])


@router.post("/translate")
def translate_content(
    content_id: str, target_lang: str = "en",
    user: dict = Depends(get_current_user),
):
    """TASK-045: Trigger AI translation of content to target language."""
    db = connect()
    content = dict(db.execute("SELECT * FROM contents WHERE id = %s", (content_id,)).fetchone() or {})
    db.close()
    if not content:
        return {"code": 1, "message": "content not found", "data": None}

    from app.gateway import complete
    body_text = str(content.get("body", ""))[:5000]
    output = complete(
        run_id=None, node_key=None, project_id=content.get("project_id", ""),
        task_type="editor_rewrite", prompt_name="editor.rewrite",
        variables={
            "selection": body_text,
            "instruction": f"Translate to {target_lang}. Preserve formatting and tone.",
        },
    )
    translated = output.get("text", body_text)

    trans_id = new_id()
    db2 = connect()
    db2.execute(
        """INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (trans_id, content.get("project_id", ""), content_id, "translation",
         f"[{target_lang}] {content.get('title', '')}", encode({"text": translated}),
         encode({"target_lang": target_lang, "source_id": content_id}), "draft"),
    )
    db2.commit(); db2.close()
    return {"code": 0, "message": "ok", "data": {"translation_id": trans_id, "language": target_lang}}


@router.get("/languages")
def supported_languages():
    """List supported target languages."""
    return {"code": 0, "message": "ok", "data": [
        {"code": "en", "name": "English"},
        {"code": "ja", "name": "Japanese"},
        {"code": "ko", "name": "Korean"},
        {"code": "es", "name": "Spanish"},
        {"code": "fr", "name": "French"},
        {"code": "de", "name": "German"},
        {"code": "pt", "name": "Portuguese"},
    ]}
