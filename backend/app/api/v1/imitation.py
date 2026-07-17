from __future__ import annotations

import ipaddress
import re as _re
import socket
import urllib.request
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.db import connect, encode, new_id
from app.gateway import BudgetExceeded, ProviderError, complete
from app.services.style_learn import check_similarity, learn_style

router = APIRouter(prefix="/api/v1/imitation", tags=["imitation"])

COPYRIGHT_WARNING = (
    "仿写仅可用于用户有权使用的文本风格学习；系统会按相似度红线阻断高相似输出，"
    "但该提示不构成法律意见，发布前仍需人工确认版权与平台规则风险。"
)


class ImitationRequest(BaseModel):
    project_id: str
    source_text: str = Field(default="", max_length=20000)
    source_url: str = Field(default="", max_length=1000)
    instruction: str = Field(default="提炼文风并仿写为原创片段，不复用原文具体表达", max_length=1000)


def _assert_public_https(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(422, "source_url must be HTTPS")
    infos = socket.getaddrinfo(parsed.hostname, 443, proto=socket.IPPROTO_TCP)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise HTTPException(422, "source_url host must resolve to a public address")


def _fetch_source(url: str) -> str:
    _assert_public_https(url)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NovelCraft/1.0)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        content_type = resp.headers.get("Content-Type", "")
        if "text" not in content_type and "html" not in content_type:
            raise HTTPException(415, "source_url must return text/html content")
        raw = resp.read(200_000).decode("utf-8", errors="replace")
    return _extract_text(raw)


def _extract_text(html: str) -> str:
    """Strip HTML tags/extract novel chapter content."""
    text = _re.sub(r"<(script|style|noscript|nav|footer|header)[^>]*>.*?</\1>", " ", html, flags=_re.DOTALL|_re.I)
    text = _re.sub(r"<[^>]+>", " ", text)
    text = _re.sub(r"&[a-z]+;", " ", text)
    text = _re.sub(r"\s+", " ", text)
    # Keep only substantial paragraphs (>30 chars, like novel text)
    paras = [p.strip() for p in text.split("\n") if len(p.strip()) > 30]
    return "\n\n".join(paras[:50]) if paras else text[:30000]


@router.post("")
def imitate(payload: ImitationRequest, user: dict = Depends(get_current_user)):
    db = connect()
    member = db.execute("SELECT role FROM project_members WHERE project_id=%s AND user_id=%s",
                        (payload.project_id, user["id"])).fetchone()
    db.close()
    if not member or member["role"] not in {"owner", "editor"}:
        raise HTTPException(403, "insufficient permissions")
    source = payload.source_text.strip() or (_fetch_source(payload.source_url.strip()) if payload.source_url.strip() else "")
    if len(source.strip()) < 200:
        raise HTTPException(422, "source text must contain at least 200 characters")
    try:
        output = complete(
            run_id=None, node_key=None, project_id=payload.project_id,
            task_type="style_imitation", prompt_name="style.imitation",
            variables={"source_text": source[:16000], "instruction": payload.instruction},
        )
    except (ProviderError, BudgetExceeded) as exc:
        raise HTTPException(502, {"code": "AI_PROVIDER_FAILED", "detail": str(exc)}) from exc
    text = str(output.get("text") or output.get("sample") or "").strip()
    if not text:
        raise HTTPException(502, {"code": "AI_OUTPUT_INVALID", "detail": "imitation output text is empty"})
    similarity = check_similarity(source, text)
    if similarity.get("verdict") == "blocked":
        raise HTTPException(422, {"code": "IMITATION_SIMILARITY_BLOCKED", **similarity,
                                  "copyright_warning": COPYRIGHT_WARNING})
    copyright_risk = "manual_review" if similarity.get("verdict") == "warning" else "low"
    style_profile = output.get("style_profile") or learn_style([source])
    content_id = new_id()
    db = connect()
    try:
        db.execute("""INSERT INTO contents (id,project_id,type,title,body,meta,status,owner_id)
                      VALUES (%s,%s,'imitation_sample',%s,%s,%s,'draft',%s)""",
                   (content_id, payload.project_id, output.get("title", "仿写样稿")[:200],
                    encode({"type": "doc", "content": [{"type": "paragraph", "text": text}]}),
                    encode({"source_url": payload.source_url, "instruction": payload.instruction,
                            "style_profile": style_profile, "similarity": similarity,
                            "copyright_risk": copyright_risk, "copyright_warning": COPYRIGHT_WARNING}),
                    user["id"]))
        db.commit()
    finally:
        db.close()
    return {"code": 0, "message": "ok", "data": {"content_id": content_id, **output,
                                                  "style_profile": style_profile,
                                                  "similarity": similarity,
                                                  "copyright_risk": copyright_risk,
                                                  "copyright_warning": COPYRIGHT_WARNING}}
