"""Persist an accepted V7 chapter into the V6 content/library model.

V7 brain state is useful for orchestration, but it is not the user's novel
library.  This boundary is deliberately synchronous because the V6 content
repository uses psycopg2.  It is called from the async director through
``asyncio.to_thread`` and is idempotent on the stable generation key.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from ...db import connect, encode, new_id, row_to_dict
from ...services.text_quality import duplicate_paragraph_stats
from .project_mapping import ensure_novel_project_link
from ..quality.continuity import build_state_delta


def generation_key(novel_id: str, chapter_number: int) -> str:
    return f"v7:{novel_id}:chapter:{chapter_number}:v1"


def rejected_version_mutation_id(generation_key_value: str, run_id: str) -> str:
    """Return a bounded, deterministic id for rejected-draft snapshots.

    ``versions.client_mutation_id`` is a VARCHAR(100), while the readable
    generation key plus a UUID run id can exceed that limit.  Keep the full
    identity in the digest so rejected-draft persistence is still idempotent
    without making the database write depend on the length of a UUID or key.
    """
    raw = f"{generation_key_value}:before-rejected:{run_id}".encode("utf-8")
    return f"v7-rejected:{hashlib.sha256(raw).hexdigest()}"


def _tiptap_body(paragraphs: list[str]) -> dict[str, Any]:
    text = "\n\n".join(p.strip() for p in paragraphs if str(p).strip())
    clean = [p.strip() for p in paragraphs if str(p).strip()]
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "text": paragraph,
                "content": [{"type": "text", "text": paragraph}],
            }
            for paragraph in clean
        ],
        "paragraphs": clean,
        "text": text,
    }


def build_transition_contract(
    *,
    chapter_number: int,
    title: str,
    text: str,
    summary: str,
    word_count: int,
    review_score: float,
    dimension_scores: dict[str, Any],
    reader_experience: dict[str, Any] | None = None,
    previous_context: dict[str, Any] | None = None,
    memory_items: list[dict[str, Any]] | None = None,
    constraints: list[dict[str, Any]] | None = None,
    state_conflicts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the small, durable hand-off object used by the next chapter."""
    previous_context = previous_context or {}
    items = memory_items or []
    conflicts = [item for item in (state_conflicts or []) if isinstance(item, dict)]
    open_threads = [
        {
            "key": item.get("key"),
            "summary": item.get("summary"),
            "category": item.get("category"),
        }
        for item in items
        if item.get("category") in {"foreshadowing", "plot_events"}
        and item.get("key")
    ]
    return {
        "schema_version": "v2",
        "chapter_number": chapter_number,
        "previous_chapter": chapter_number - 1 if chapter_number > 1 else None,
        "start_state": {
            "previous_tail": str(previous_context.get("previous_tail") or "")[-1200:],
            "previous_transition_contract": previous_context.get("previous_transition_contract") or {},
        },
        "end_state": {
            "title": title,
            "summary": summary,
            "last_tail": str(text or "")[-1200:],
            "word_count": word_count,
        },
        "events": [
            {"key": item.get("key"), "summary": item.get("summary"), "category": item.get("category")}
            for item in items
            if item.get("key") and item.get("summary")
        ],
        "state_delta": build_state_delta(items),
        "state_conflicts": conflicts,
        "open_threads": open_threads,
        "forbidden_changes": [
            {"name": c.get("name"), "description": c.get("description"), "severity": c.get("severity")}
            for c in (constraints or [])
            if c.get("name") or c.get("description")
        ],
        "next_chapter_bridge": str(text or "")[-600:],
        "quality": {
            "review_score": review_score,
            "dimension_scores": dimension_scores,
            "reader_experience": reader_experience or {},
        },
    }


def _persist_v7_chapter(
    *,
    novel_id: str,
    project_id: str | None,
    chapter_number: int,
    title: str,
    text: str,
    review_score: float,
    dimension_scores: dict[str, Any],
    run_id: str,
    chapter_summary: str,
    deai: dict[str, Any],
    transition_contract: dict[str, Any],
    status: str,
    quality_status: str,
    review_issues: list[dict[str, Any]] | None = None,
    quality_gate: dict[str, Any] | None = None,
    reader_experience: dict[str, Any] | None = None,
    rework_count: int = 0,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Upsert one canonical V7 result into the V6 product boundary.

    ``reviewed`` is reserved for a passed quality gate.  A rejected result is
    still persisted as ``needs_rewrite`` so the author can inspect the actual
    draft, its score and its repair reasons; it never becomes a publishable
    chapter merely because the provider returned text.
    """
    if not text.strip():
        raise ValueError("cannot persist an empty V7 chapter")
    if status not in {"reviewed", "needs_rewrite"}:
        raise ValueError(f"unsupported V7 content status: {status}")
    mapping = ensure_novel_project_link(novel_id, project_id)
    project_id = mapping["project_id"]

    key = generation_key(novel_id, chapter_number)
    paragraphs = [p.strip() for p in text.replace("\r\n", "\n").split("\n") if p.strip()]
    duplicate_paragraphs = duplicate_paragraph_stats(text)
    if status == "reviewed" and float(duplicate_paragraphs.get("duplicate_ratio") or 0.0) >= 0.01:
        raise ValueError(
            "cannot persist a reviewed chapter with repeated full paragraphs: "
            f"ratio={duplicate_paragraphs.get('duplicate_ratio')}"
        )
    body = _tiptap_body(paragraphs)
    meta = {
        "seq": chapter_number,
        "word_count": len("".join(paragraphs)),
        "source": "v7",
        "v7_run_id": str(run_id),
        "v7_state_key": f"chapter_{chapter_number:04d}",
        "generation_key": key,
        "quality_status": quality_status,
        "review_score": review_score,
        "dimension_scores": dimension_scores,
        "chapter_summary": chapter_summary,
        "deai": deai,
        "transition_contract": transition_contract,
        "reader_experience": reader_experience or {},
        "review_issues": review_issues or [],
        "quality_gate": quality_gate or {},
        "duplicate_paragraphs": duplicate_paragraphs,
        "rework_count": rework_count,
        "quality_reason": (
            "quality gate passed"
            if status == "reviewed"
            else "V7 quality gate did not pass; draft requires rewrite"
        ),
        "project_mapping": mapping,
        "canonical_engine": "v7",
    }
    if extra_meta:
        meta.update(extra_meta)

    conn = connect()
    try:
        # Reuse an old V6 row with the same chapter number when the canonical
        # engine takes over an existing book.  This prevents a V6 draft and a
        # V7 chapter from becoming two visible versions of the same chapter.
        existing = conn.execute(
            """
            SELECT id FROM contents
            WHERE project_id=%s AND parent_id=%s AND type='chapter'
              AND generation_key=%s AND is_deleted=FALSE
            LIMIT 1
            """,
            (project_id, novel_id, key),
        ).fetchone()
        if not existing:
            existing = conn.execute(
                """
                SELECT id FROM contents
                WHERE project_id=%s AND parent_id=%s AND type='chapter'
                  AND seq=%s AND is_deleted=FALSE
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (project_id, novel_id, chapter_number),
            ).fetchone()

        if existing and status == "needs_rewrite":
            # A rejected canonical draft may replace an older V6 draft or an
            # accepted version during an explicit regeneration.  Preserve the
            # previous body before the update so the editor can restore it.
            conn.execute(
                """
                INSERT INTO versions
                    (id, entity_type, entity_id, label, snapshot, reason, client_mutation_id)
                SELECT %s,'content',id,'before_v7_rejected',
                       jsonb_build_object('title',title,'body',body,'meta',meta),
                       'v7 quality gate rejected the new draft',%s
                FROM contents
                WHERE id=%s
                ON CONFLICT (client_mutation_id) WHERE client_mutation_id IS NOT NULL
                DO NOTHING
                """,
                (
                    new_id("version"),
                    rejected_version_mutation_id(key, str(run_id)),
                    existing["id"],
                ),
            )

        if existing:
            stored = conn.execute(
                """
                UPDATE contents
                SET title=%s, body=%s, meta=%s, status=%s,
                    generation_key=%s, seq=%s, updated_at=now()
                WHERE id=%s
                RETURNING id
                """,
                (title, encode(body), encode(meta), status, key, chapter_number, existing["id"]),
            ).fetchone()
        else:
            stored = conn.execute(
                """
                INSERT INTO contents
                    (id, project_id, parent_id, type, title, body, meta, status, generation_key, seq, created_at)
                VALUES (%s,%s,%s,'chapter',%s,%s,%s,%s,%s,%s,now())
                ON CONFLICT (project_id, generation_key)
                    WHERE generation_key IS NOT NULL AND is_deleted=FALSE
                DO UPDATE SET
                    parent_id=EXCLUDED.parent_id,
                    title=EXCLUDED.title,
                    body=EXCLUDED.body,
                    meta=EXCLUDED.meta,
                    status=EXCLUDED.status,
                    seq=EXCLUDED.seq,
                    updated_at=now()
                RETURNING id
                """,
                (
                    new_id("content"),
                    project_id,
                    novel_id,
                    title,
                    encode(body),
                    encode(meta),
                    status,
                    key,
                    chapter_number,
                ),
            ).fetchone()
        conn.commit()
        content_id = stored["id"] if stored else None
        if not content_id:
            raise RuntimeError("V6 chapter upsert returned no content id")
        # Keep the V6 editor/version history aligned with the content row.  The
        # stable mutation id makes retries safe even when the first request
        # succeeded but the caller lost its response.
        version_key = f"{key}:version" if status == "reviewed" else f"{key}:draft:{run_id}"
        conn.execute(
            """
            INSERT INTO versions
                (id, entity_type, entity_id, label, snapshot, reason, client_mutation_id)
            VALUES (%s,'content',%s,%s,%s,%s,%s)
            ON CONFLICT (client_mutation_id) WHERE client_mutation_id IS NOT NULL
            DO NOTHING
            """,
            (
                new_id("version"),
                content_id,
                "v7_generate" if status == "reviewed" else "v7_generate_draft",
                encode({"title": title, "body": body, "meta": meta}),
                "v7_bridge" if status == "reviewed" else "v7_quality_gate",
                version_key,
            ),
        )
        conn.commit()
        return {
            "content_id": str(content_id),
            "generation_key": key,
            "project_id": str(project_id),
            "status": status,
            "quality_status": quality_status,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def persist_accepted_v7_chapter(
    *,
    novel_id: str,
    project_id: str | None,
    chapter_number: int,
    title: str,
    text: str,
    review_score: float,
    dimension_scores: dict[str, Any],
    run_id: str,
    chapter_summary: str,
    deai: dict[str, Any],
    transition_contract: dict[str, Any],
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist a V7 chapter that passed the strict quality gate."""
    return _persist_v7_chapter(
        novel_id=novel_id,
        project_id=project_id,
        chapter_number=chapter_number,
        title=title,
        text=text,
        review_score=review_score,
        dimension_scores=dimension_scores,
        run_id=run_id,
        chapter_summary=chapter_summary,
        deai=deai,
        transition_contract=transition_contract,
        status="reviewed",
        quality_status="v7_quality_gate_passed",
        extra_meta=extra_meta,
    )


def persist_rejected_v7_draft(
    *,
    novel_id: str,
    project_id: str | None,
    chapter_number: int,
    title: str,
    text: str,
    review_score: float,
    dimension_scores: dict[str, Any],
    run_id: str,
    chapter_summary: str,
    deai: dict[str, Any],
    transition_contract: dict[str, Any],
    review_issues: list[dict[str, Any]] | None = None,
    quality_gate: dict[str, Any] | None = None,
    reader_experience: dict[str, Any] | None = None,
    rework_count: int = 0,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist a real but rejected V7 draft for inspection and repair."""
    return _persist_v7_chapter(
        novel_id=novel_id,
        project_id=project_id,
        chapter_number=chapter_number,
        title=title,
        text=text,
        review_score=review_score,
        dimension_scores=dimension_scores,
        run_id=run_id,
        chapter_summary=chapter_summary,
        deai=deai,
        transition_contract=transition_contract,
        status="needs_rewrite",
        quality_status="v7_quality_gate_failed",
        review_issues=review_issues,
        quality_gate=quality_gate,
        reader_experience=reader_experience,
        rework_count=rework_count,
        extra_meta=extra_meta,
    )
