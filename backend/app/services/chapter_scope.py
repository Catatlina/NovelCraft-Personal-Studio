"""Canonical chapter-to-novel scope and legacy reconciliation.

``parent_id`` is the storage edge used by the existing content model.  This
module is the single policy boundary around that edge:

* real chapters must resolve to a live novel in the same project before they
  can enter V7 generation, editing, or review;
* historical rows without a parent are scanned using recorded provenance;
* only high-confidence evidence may auto-bind a row;
* ambiguous rows remain readable but cannot spend provider quota.

The reconciler never uses prose similarity as a source of truth.  Text/title
signals can strengthen an already plausible candidate, but an explicit run,
batch, lineage, or stored novel reference is required for automatic binding.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ..db import DB, decode, encode, new_id


SCOPE_CANONICAL = "canonical"
SCOPE_LEGACY_RESOLVED = "legacy_resolved"
SCOPE_LEGACY_PENDING = "legacy_pending"
SCOPE_LEGACY_UNLINKED = "legacy_unlinked"
SCOPE_INVALID = "invalid"

RESOLUTION_UNSCANNED = "unscanned"
RESOLUTION_PENDING = "pending"
RESOLUTION_AUTO_BOUND = "auto_bound"
RESOLUTION_CONFIRMED = "confirmed"
RESOLUTION_UNLINKED = "unlinked"
RESOLUTION_REJECTED = "rejected"

AUTO_BIND_THRESHOLD = 0.90
PENDING_THRESHOLD = 0.55


class ChapterScopeError(ValueError):
    """A chapter cannot safely enter the canonical V7 story scope."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _meta(value: Any) -> dict[str, Any]:
    parsed = decode(value, {}) if not isinstance(value, dict) else value
    return parsed if isinstance(parsed, dict) else {}


def _string(value: Any) -> str:
    return str(value or "").strip()


def _scope_status(content: dict[str, Any]) -> str:
    """Return the explicit scope state, tolerating pre-migration rows."""
    explicit = _string(content.get("scope_status"))
    if explicit:
        return explicit
    meta_status = _string(_meta(content.get("meta")).get("scope_status"))
    if meta_status:
        return meta_status
    if content.get("parent_id"):
        return SCOPE_CANONICAL
    # A missing column/value means this row predates the scope migration.  It
    # is still treated as untrusted by the runtime; this value is useful for
    # reconciliation reports and is never a permission to call a provider.
    return "pre_scope_migration"


def scope_status(content: dict[str, Any]) -> str:
    """Public read helper used by API serializers and tests."""
    return _scope_status(content)


def _chapter_seq(chapter: dict[str, Any]) -> int | None:
    meta = _meta(chapter.get("meta"))
    for value in (chapter.get("seq"), meta.get("seq"), meta.get("chapter_number")):
        try:
            if value is not None and int(value) > 0:
                return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _normal_title(value: Any) -> str:
    text = _string(value)
    text = re.sub(r"^第[一二三四五六七八九十百千万零〇\d]+章\s*", "", text)
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE).casefold()


def _nested_reference_values(value: Any) -> dict[str, set[str]]:
    """Extract only provenance identifiers from metadata/snapshots."""
    result = {"novel": set(), "run": set(), "batch": set()}
    if isinstance(value, dict):
        for key, item in value.items():
            key_norm = str(key).lower().replace("-", "_")
            if isinstance(item, (dict, list)):
                child = _nested_reference_values(item)
                for group, values in child.items():
                    result[group].update(values)
                continue
            value_text = _string(item)
            if not value_text:
                continue
            if key_norm in {"novel_id", "novelid", "source_novel_id", "book_id", "bookid"}:
                result["novel"].add(value_text)
            elif key_norm in {"run_id", "workflow_run_id", "workflowrunid"}:
                result["run"].add(value_text)
            elif key_norm in {"batch_id", "generation_batch_id", "batchid"}:
                result["batch"].add(value_text)
    elif isinstance(value, list):
        for item in value:
            child = _nested_reference_values(item)
            for group, values in child.items():
                result[group].update(values)
    return result


def _chapter_references(db: DB, chapter: dict[str, Any]) -> dict[str, set[str]]:
    refs = _nested_reference_values(_meta(chapter.get("meta")))
    chapter_id = _string(chapter.get("id"))
    if chapter_id:
        try:
            versions = db.execute(
                """SELECT snapshot FROM versions
                   WHERE entity_type='content' AND entity_id=%s
                   ORDER BY created_at DESC LIMIT 20""",
                (chapter_id,),
            ).fetchall()
            for row in versions:
                snapshot = decode(row.get("snapshot"), {})
                nested = _nested_reference_values(snapshot)
                for group, values in nested.items():
                    refs[group].update(values)
        except Exception:
            # A partially upgraded development database should still allow a
            # dry-run report.  Missing provenance is simply weaker evidence.
            try:
                db.rollback()
            except Exception:
                pass
        try:
            lineage = db.execute(
                """SELECT c.parent_id AS novel_id
                   FROM derivations d
                   JOIN contents c ON c.id=d.source_content_id
                   WHERE d.derived_content_id=%s
                     AND c.type='chapter' AND c.parent_id IS NOT NULL
                   LIMIT 20""",
                (chapter_id,),
            ).fetchall()
            refs["novel"].update(_string(row.get("novel_id")) for row in lineage if row.get("novel_id"))
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
    return refs


def _load_project_context(db: DB, project_id: str) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
    novels = db.execute(
        """SELECT id, project_id, title, meta
           FROM contents
           WHERE project_id=%s AND type='novel' AND is_deleted=FALSE
           ORDER BY created_at ASC""",
        (project_id,),
    ).fetchall()
    run_to_novel: dict[str, str] = {}
    try:
        runs = db.execute(
            """SELECT id, novel_id, context
               FROM workflow_runs
               WHERE project_id=%s AND novel_id IS NOT NULL""",
            (project_id,),
        ).fetchall()
        for row in runs:
            run_id = _string(row.get("id"))
            novel_id = _string(row.get("novel_id"))
            if run_id and novel_id:
                run_to_novel[run_id] = novel_id
            nested = _nested_reference_values(decode(row.get("context"), {}))
            for nested_run_id in nested["run"]:
                if novel_id:
                    run_to_novel[nested_run_id] = novel_id
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    batch_to_novel: dict[str, str] = {}
    try:
        batches = db.execute(
            """SELECT id, novel_id FROM generation_batches
               WHERE project_id=%s AND novel_id IS NOT NULL""",
            (project_id,),
        ).fetchall()
        for row in batches:
            batch_id = _string(row.get("id"))
            novel_id = _string(row.get("novel_id"))
            if batch_id and novel_id:
                batch_to_novel[batch_id] = novel_id
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    return novels, run_to_novel, batch_to_novel


def _candidate_for_novel(
    chapter: dict[str, Any],
    novel: dict[str, Any],
    novels: list[dict[str, Any]],
    refs: dict[str, set[str]],
    run_to_novel: dict[str, str],
    batch_to_novel: dict[str, str],
) -> dict[str, Any]:
    novel_id = _string(novel.get("id"))
    score = 0.0
    evidence: list[dict[str, Any]] = []

    def strong(kind: str, detail: str, value: str) -> None:
        nonlocal score
        score = max(score, 1.0)
        evidence.append({"kind": kind, "detail": detail, "value": value})

    if novel_id in refs["novel"]:
        strong("metadata_novel_id", "章节元数据或版本快照直接指向该小说", novel_id)
    if any(run_to_novel.get(run_id) == novel_id for run_id in refs["run"]):
        matched = next(run_id for run_id in refs["run"] if run_to_novel.get(run_id) == novel_id)
        strong("workflow_run_novel_id", "工作流运行记录指向该小说", matched)
    if any(batch_to_novel.get(batch_id) == novel_id for batch_id in refs["batch"]):
        matched = next(batch_id for batch_id in refs["batch"] if batch_to_novel.get(batch_id) == novel_id)
        strong("generation_batch_novel_id", "批量生成记录指向该小说", matched)

    if len(novels) == 1:
        score = max(score, 0.55)
        evidence.append({"kind": "same_project_unique_novel", "detail": "项目内只有一部小说"})

    chapter_seq = _chapter_seq(chapter)
    novel_meta = _meta(novel.get("meta"))
    outlines = novel_meta.get("chapter_outlines") or []
    for outline in outlines:
        if not isinstance(outline, dict):
            continue
        try:
            outline_seq = int(outline.get("seq") or 0)
        except (TypeError, ValueError):
            outline_seq = 0
        if not chapter_seq or outline_seq != chapter_seq:
            continue
        score = max(score, 0.65)
        evidence.append({"kind": "chapter_sequence", "detail": "章节序号与作品细纲匹配", "value": chapter_seq})
        if _normal_title(chapter.get("title")) and _normal_title(chapter.get("title")) == _normal_title(outline.get("title")):
            score = max(score, 0.93)
            evidence.append({"kind": "outline_title_exact", "detail": "章节标题与作品细纲精确匹配"})
        break

    return {
        "novel_id": novel_id,
        "title": _string(novel.get("title")) or "未命名作品",
        "score": round(min(score, 1.0), 4),
        "evidence": evidence,
    }


def _classify_candidates(candidates: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    ordered = sorted(candidates, key=lambda item: float(item.get("score") or 0), reverse=True)
    if not ordered or float(ordered[0].get("score") or 0) <= 0:
        return RESOLUTION_UNLINKED, None
    top = ordered[0]
    second_score = float(ordered[1].get("score") or 0) if len(ordered) > 1 else 0.0
    margin = float(top.get("score") or 0) - second_score
    kinds = {str(item.get("kind")) for item in top.get("evidence") or []}
    has_strong = bool(kinds & {
        "metadata_novel_id",
        "workflow_run_novel_id",
        "generation_batch_novel_id",
        "lineage_novel_id",
        "version_novel_id",
    })
    exact_outline = "outline_title_exact" in kinds
    if float(top.get("score") or 0) >= AUTO_BIND_THRESHOLD and margin >= 0.12 and (has_strong or exact_outline):
        return RESOLUTION_AUTO_BOUND, top
    if float(top.get("score") or 0) >= PENDING_THRESHOLD:
        return RESOLUTION_PENDING, top
    return RESOLUTION_UNLINKED, top


def _scope_meta(meta: dict[str, Any], *, status: str, confidence: float | None,
                selected_novel_id: str | None = None, source: str = "legacy_reconciler") -> dict[str, Any]:
    updated = dict(meta)
    updated["scope_status"] = status
    updated["scope_resolution"] = {
        "status": status,
        "confidence": confidence,
        "selected_novel_id": selected_novel_id,
        "source": source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return updated


def _upsert_resolution(
    db: DB,
    chapter: dict[str, Any],
    *,
    status: str,
    confidence: float | None,
    candidates: list[dict[str, Any]],
    evidence: dict[str, Any],
    selected_novel_id: str | None,
    resolved_by: str | None = None,
    source: str = "legacy_reconciler",
) -> None:
    db.execute(
        """INSERT INTO legacy_chapter_resolutions
           (id, chapter_id, project_id, status, confidence, candidates, evidence,
            selected_novel_id, source, resolved_by, resolved_at, updated_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
           ON CONFLICT (chapter_id) DO UPDATE SET
             project_id=EXCLUDED.project_id,
             status=EXCLUDED.status,
             confidence=EXCLUDED.confidence,
             candidates=EXCLUDED.candidates,
             evidence=EXCLUDED.evidence,
             selected_novel_id=EXCLUDED.selected_novel_id,
             source=EXCLUDED.source,
             resolved_by=COALESCE(EXCLUDED.resolved_by, legacy_chapter_resolutions.resolved_by),
             resolved_at=COALESCE(EXCLUDED.resolved_at, legacy_chapter_resolutions.resolved_at),
             updated_at=now()""",
        (
            new_id(),
            chapter["id"],
            chapter["project_id"],
            status,
            confidence,
            encode(candidates),
            encode(evidence),
            selected_novel_id,
            source,
            resolved_by,
            datetime.now(timezone.utc) if resolved_by else None,
        ),
    )


def _write_scope_status(db: DB, chapter: dict[str, Any], status: str,
                        *, confidence: float | None, selected_novel_id: str | None = None,
                        source: str = "legacy_reconciler") -> None:
    meta = _scope_meta(
        _meta(chapter.get("meta")),
        status=status,
        confidence=confidence,
        selected_novel_id=selected_novel_id,
        source=source,
    )
    db.execute(
        "UPDATE contents SET scope_status=%s, meta=%s, updated_at=now() WHERE id=%s",
        (status, encode(meta), chapter["id"]),
    )


def scan_legacy_chapters(
    db: DB,
    *,
    project_id: str,
    apply: bool = False,
    auto_bind: bool = True,
) -> dict[str, Any]:
    """Scan orphan chapters and optionally apply only safe auto-bindings."""
    chapters = db.execute(
        """SELECT id, project_id, parent_id, type, title, body, meta, status,
                  seq, created_at, scope_status
           FROM contents
           WHERE project_id=%s AND type='chapter' AND parent_id IS NULL
             AND is_deleted=FALSE
           ORDER BY created_at ASC""",
        (project_id,),
    ).fetchall()
    novels, run_to_novel, batch_to_novel = _load_project_context(db, project_id)
    novel_ids = {_string(novel.get("id")) for novel in novels}
    counts = {
        "scanned": 0,
        "auto_bindable": 0,
        "auto_bound": 0,
        "pending": 0,
        "unlinked": 0,
        "deferred": 0,
        "applied": bool(apply),
    }
    items: list[dict[str, Any]] = []

    for chapter in chapters:
        counts["scanned"] += 1
        refs = _chapter_references(db, chapter)
        # Ignore stale references that cannot belong to a novel in this project.
        refs["novel"] &= novel_ids
        candidates = [
            _candidate_for_novel(chapter, novel, novels, refs, run_to_novel, batch_to_novel)
            for novel in novels
        ]
        candidates = [item for item in candidates if float(item.get("score") or 0) > 0]
        decision, selected = _classify_candidates(candidates)
        selected_id = _string((selected or {}).get("novel_id")) or None
        confidence = float((selected or {}).get("score") or 0) or None
        if decision == RESOLUTION_AUTO_BOUND:
            counts["auto_bindable"] += 1
        elif decision == RESOLUTION_PENDING:
            counts["pending"] += 1
        else:
            counts["unlinked"] += 1

        item = {
            "chapter_id": _string(chapter.get("id")),
            "title": _string(chapter.get("title")),
            "seq": _chapter_seq(chapter),
            "decision": decision,
            "confidence": confidence,
            "selected_novel_id": selected_id,
            "candidates": sorted(candidates, key=lambda value: float(value.get("score") or 0), reverse=True)[:10],
        }
        items.append(item)

        if not apply:
            continue
        if decision == RESOLUTION_AUTO_BOUND and auto_bind and selected_id:
            _write_scope_status(
                db,
                chapter,
                SCOPE_LEGACY_RESOLVED,
                confidence=confidence,
                selected_novel_id=selected_id,
            )
            db.execute(
                "UPDATE contents SET parent_id=%s, scope_status=%s, updated_at=now() WHERE id=%s",
                (selected_id, SCOPE_LEGACY_RESOLVED, chapter["id"]),
            )
            _upsert_resolution(
                db,
                chapter,
                status=RESOLUTION_AUTO_BOUND,
                confidence=confidence,
                candidates=item["candidates"],
                evidence={"references": {key: sorted(values) for key, values in refs.items()}},
                selected_novel_id=selected_id,
            )
            db.execute(
                """INSERT INTO audit_logs (id, action, entity_type, entity_id, details, created_at)
                   VALUES (%s,'legacy_chapter.auto_bound','content',%s,%s,now())""",
                (
                    new_id(), chapter["id"],
                    encode({"novel_id": selected_id, "confidence": confidence, "evidence": item["candidates"]}),
                ),
            )
            counts["auto_bound"] += 1
        else:
            # A high-confidence candidate is only a proposal when the caller
            # explicitly disables auto-binding. Never persist an
            # ``auto_bound`` resolution without also setting parent_id.
            effective_decision = (
                RESOLUTION_PENDING if decision == RESOLUTION_AUTO_BOUND else decision
            )
            target_status = (
                SCOPE_LEGACY_PENDING
                if effective_decision == RESOLUTION_PENDING
                else SCOPE_LEGACY_UNLINKED
            )
            if decision == RESOLUTION_AUTO_BOUND and apply and not auto_bind:
                counts["deferred"] += 1
            _write_scope_status(db, chapter, target_status, confidence=confidence, selected_novel_id=selected_id)
            _upsert_resolution(
                db,
                chapter,
                status=effective_decision,
                confidence=confidence,
                candidates=item["candidates"],
                evidence={"references": {key: sorted(values) for key, values in refs.items()}},
                selected_novel_id=selected_id,
            )

    if apply:
        db.commit()
    return {"project_id": project_id, "counts": counts, "items": items}


def list_legacy_resolutions(db: DB, *, project_id: str, status: str | None = None) -> list[dict[str, Any]]:
    where = "r.project_id=%s"
    params: list[Any] = [project_id]
    if status:
        where += " AND r.status=%s"
        params.append(status)
    rows = db.execute(
        f"""SELECT r.*, c.title, c.status AS chapter_status, c.scope_status,
                    c.created_at AS chapter_created_at
             FROM legacy_chapter_resolutions r
             JOIN contents c ON c.id=r.chapter_id
             WHERE {where}
             ORDER BY r.updated_at DESC""",
        tuple(params),
    ).fetchall()
    for row in rows:
        row["candidates"] = decode(row.get("candidates"), [])
        row["evidence"] = decode(row.get("evidence"), {})
    return rows


def bind_legacy_chapter(db: DB, *, chapter_id: str, novel_id: str, user_id: str | None) -> dict[str, Any]:
    chapter = db.execute(
        """SELECT id, project_id, parent_id, type, title, body, meta, status, scope_status
           FROM contents WHERE id=%s AND is_deleted=FALSE FOR UPDATE""",
        (chapter_id,),
    ).fetchone()
    if not chapter:
        raise ChapterScopeError("CHAPTER_NOT_FOUND", "章节不存在", details={"chapter_id": chapter_id})
    if chapter.get("type") != "chapter":
        raise ChapterScopeError("NOT_A_CHAPTER", "只能绑定章节内容")
    target = db.execute(
        """SELECT id, project_id, type, title
           FROM contents WHERE id=%s AND is_deleted=FALSE""",
        (novel_id,),
    ).fetchone()
    if not target or target.get("type") != "novel":
        raise ChapterScopeError("NOVEL_NOT_FOUND", "目标作品不存在")
    if _string(target.get("project_id")) != _string(chapter.get("project_id")):
        raise ChapterScopeError("PROJECT_SCOPE_MISMATCH", "章节和目标作品不属于同一项目")
    existing_parent = _string(chapter.get("parent_id"))
    if existing_parent and existing_parent != _string(novel_id):
        raise ChapterScopeError("CHAPTER_ALREADY_BOUND", "章节已经绑定到另一部作品")

    meta = _scope_meta(
        _meta(chapter.get("meta")),
        status=SCOPE_LEGACY_RESOLVED,
        confidence=1.0,
        selected_novel_id=novel_id,
        source="human_confirmation",
    )
    db.execute(
        """UPDATE contents
           SET parent_id=%s, scope_status=%s, meta=%s, updated_at=now()
           WHERE id=%s""",
        (novel_id, SCOPE_LEGACY_RESOLVED, encode(meta), chapter_id),
    )
    _upsert_resolution(
        db,
        chapter,
        status=RESOLUTION_CONFIRMED,
        confidence=1.0,
        candidates=[{"novel_id": novel_id, "title": target.get("title"), "score": 1.0}],
        evidence={"manual_confirmation": True},
        selected_novel_id=novel_id,
        resolved_by=user_id,
        source="human_confirmation",
    )
    db.execute(
        """INSERT INTO audit_logs (id, user_id, action, entity_type, entity_id, details, created_at)
           VALUES (%s,%s,'legacy_chapter.confirmed','content',%s,%s,now())""",
        (new_id(), user_id, chapter_id, encode({"novel_id": novel_id})),
    )
    return {
        "chapter_id": chapter_id,
        "novel_id": novel_id,
        "scope_status": SCOPE_LEGACY_RESOLVED,
        "resolution_status": RESOLUTION_CONFIRMED,
    }


def require_canonical_v7_chapter(db: DB, content: dict[str, Any], *, operation: str) -> str | None:
    """Fail closed before any provider call for an unscoped chapter."""
    if _string(content.get("type")) != "chapter":
        return None
    parent_id = _string(content.get("parent_id"))
    if not parent_id:
        raise ChapterScopeError(
            "CHAPTER_SCOPE_REQUIRED",
            "该历史章节尚未绑定到作品，请先完成章节归属确认",
            details={"operation": operation, "scope_status": _scope_status(content), "version_written": False},
        )
    parent = db.execute(
        """SELECT id, project_id, type
           FROM contents WHERE id=%s AND is_deleted=FALSE""",
        (parent_id,),
    ).fetchone()
    if not parent or parent.get("type") != "novel":
        raise ChapterScopeError(
            "CHAPTER_SCOPE_INVALID",
            "章节的作品归属无效，请重新绑定作品",
            details={"operation": operation, "parent_id": parent_id, "version_written": False},
        )
    if _string(parent.get("project_id")) != _string(content.get("project_id")):
        raise ChapterScopeError(
            "CHAPTER_SCOPE_INVALID",
            "章节与作品不属于同一项目",
            details={"operation": operation, "parent_id": parent_id, "version_written": False},
        )
    current_status = _scope_status(content)
    if current_status not in {SCOPE_CANONICAL, SCOPE_LEGACY_RESOLVED}:
        raise ChapterScopeError(
            "CHAPTER_SCOPE_REVIEW_REQUIRED",
            "该章节归属状态尚未完成确认，暂不能进入 V7",
            details={"operation": operation, "scope_status": current_status, "version_written": False},
        )
    return parent_id


def validate_novel_parent(db: DB, *, project_id: str, novel_id: str) -> None:
    """Validate a chapter write target before creating a new row."""
    novel = db.execute(
        """SELECT id, project_id, type
           FROM contents WHERE id=%s AND is_deleted=FALSE""",
        (novel_id,),
    ).fetchone()
    if not novel or novel.get("type") != "novel":
        raise ChapterScopeError("NOVEL_NOT_FOUND", "章节必须挂接到有效作品")
    if _string(novel.get("project_id")) != _string(project_id):
        raise ChapterScopeError("PROJECT_SCOPE_MISMATCH", "作品和章节不属于同一项目")


def scope_summary(db: DB, *, project_id: str) -> dict[str, Any]:
    rows = db.execute(
        """SELECT COALESCE(scope_status, 'untracked') AS scope_status, COUNT(*) AS count
           FROM contents
           WHERE project_id=%s AND type='chapter' AND is_deleted=FALSE
           GROUP BY COALESCE(scope_status, 'untracked')""",
        (project_id,),
    ).fetchall()
    counts = {str(row["scope_status"]): int(row["count"]) for row in rows}
    return {
        "project_id": project_id,
        "counts": counts,
        "unresolved": counts.get(SCOPE_LEGACY_PENDING, 0) + counts.get(SCOPE_LEGACY_UNLINKED, 0),
        "new_chapter_gate": "parent_id_required_for_v7",
    }
