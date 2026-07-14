"""C6: Foreshadow到期注入 + 跨章矛盾检测 + 弧线偏移校验"""
from __future__ import annotations
import json
from app.db import connect, decode, encode


def check_foreshadow_due(novel_id: str, current_chapter_seq: int) -> list[dict]:
    """Check if any foreshadows are due for resolution at this chapter."""
    db = connect()
    rows = db.execute(
        """SELECT f.*, (c.meta->>'seq') AS planted_seq FROM foreshadowings f
           JOIN contents c ON c.id = f.chapter_id
           WHERE c.parent_id = %s
           AND f.planned_resolve_chapter <= %s AND f.status != 'resolved'
           ORDER BY f.planned_resolve_chapter""",
        (novel_id, current_chapter_seq)
    ).fetchall()
    db.close()
    due = []
    for r in rows:
        due.append({
            "id": r["id"], "content": r.get("content", ""),
            "target": r.get("planned_resolve_chapter", 0),
            "planted_at": str(r.get("planted_seq") or ""),
            "status": r.get("status", "unknown"),
        })
    return due


def inject_foreshadow_context(due_items: list[dict]) -> str:
    """Generate a context injection for due foreshadows."""
    if not due_items:
        return ""
    lines = ["⚠️ 以下伏笔已到期，必须在本章中回收："]

    for item in due_items:
        lines.append(f"- [{item['status']}] {item['content'][:120]}")
    return "\n".join(lines)


def detect_cross_chapter_conflicts(novel_id: str) -> list[dict]:
    """TASK-019: Contradiction detection from persisted entity states.

    The previous version queried timeline_events columns that do not exist
    (character_name/event_time), so it silently never found anything. Entity
    states are what the pipeline actually records per chapter."""
    db = connect()
    rows = db.execute(
        """SELECT es.entity_name, es.location, c.title AS chapter_title,
                  (c.meta->>'seq')::int AS seq
           FROM entity_states es JOIN contents c ON c.id = es.chapter_id
           WHERE c.parent_id = %s AND es.entity_type = 'character'
             AND COALESCE(es.location, '') != ''
           ORDER BY seq, es.entity_name, es.created_at""",
        (novel_id,)
    ).fetchall()
    db.close()

    conflicts = []
    seen: dict[tuple, dict] = {}
    for row in rows:
        key = (row["entity_name"], row["seq"])
        prev = seen.get(key)
        if prev and prev["location"] != row["location"]:
            conflicts.append({
                "type": "entity_location_contradiction",
                "character": row["entity_name"],
                "chapter_a": prev.get("chapter_title", ""),
                "chapter_b": row.get("chapter_title", ""),
                "detail": f"{row['entity_name']} 在第{row['seq']}章被同时记录于 '{prev['location']}' 与 '{row['location']}'",
            })
        seen[key] = dict(row)
    return conflicts


def volume_gate(novel_id: str, volume_num: int) -> dict:
    """卷级门禁：before moving past a volume, verify the volume is complete and
    internally consistent. Result is persisted to the novel's meta.volume_gates
    so batch generation can enforce it.

    Blockers (gate fails): missing chapters in the planned range, chapters still
    in draft/needs_review, unresolved foreshadowing due within the volume,
    entity location contradictions inside the volume.
    Warnings (gate passes): chapters without summaries, volume summary AI failure.
    """
    from datetime import datetime, timezone

    db = connect()
    novel = db.execute(
        "SELECT id, project_id, meta FROM contents WHERE id=%s AND type='novel' AND is_deleted=FALSE",
        (novel_id,),
    ).fetchone()
    if not novel:
        db.close()
        raise ValueError("novel not found")
    meta = novel["meta"] if isinstance(novel["meta"], dict) else {}
    plan = meta.get("volume_plan") or []
    vol = next((v for v in plan if int(v.get("number", 0) or 0) == volume_num), None)
    if vol is None:
        db.close()
        return {"volume": volume_num, "passed": False,
                "blockers": [f"第{volume_num}卷没有分卷规划（meta.volume_plan），无法进行卷级门禁"],
                "warnings": [], "checked_at": datetime.now(timezone.utc).isoformat()}
    start_seq = int(vol.get("start_chapter", 0) or 0)
    end_seq = int(vol.get("end_chapter", 0) or 0)

    chapters = db.execute(
        """SELECT (meta->>'seq')::int AS seq, status, title,
                  COALESCE(meta->>'chapter_summary','') AS summary
           FROM contents
           WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE
             AND (meta->>'seq')::int BETWEEN %s AND %s
           ORDER BY (meta->>'seq')::int""",
        (novel_id, start_seq, end_seq),
    ).fetchall()
    db.close()

    blockers: list[str] = []
    warnings: list[str] = []

    present = {int(c["seq"]) for c in chapters if c.get("seq") is not None}
    missing = sorted(set(range(start_seq, end_seq + 1)) - present)
    if missing:
        blockers.append(f"缺少章节：{missing[:10]}{'…' if len(missing) > 10 else ''}（共{len(missing)}章）")

    unfinished = [int(c["seq"]) for c in chapters if c.get("status") in {"draft", "needs_review"}]
    if unfinished:
        blockers.append(f"章节未过审：{unfinished[:10]}{'…' if len(unfinished) > 10 else ''}（共{len(unfinished)}章）")

    overdue = [f for f in check_foreshadow_due(novel_id, end_seq)
               if int(f.get("target", 0) or 0) >= start_seq]
    if overdue:
        blockers.append("到期未回收伏笔：" + "；".join(f"{f['content'][:40]}（应于第{f['target']}章回收）" for f in overdue[:5]))

    conflicts = [c for c in detect_cross_chapter_conflicts(novel_id)
                 if any(f"第{seq}章" in (c.get("detail") or "") for seq in range(start_seq, end_seq + 1))]
    if conflicts:
        blockers.append("实体状态矛盾：" + "；".join(c["detail"][:80] for c in conflicts[:5]))

    no_summary = [int(c["seq"]) for c in chapters if not c.get("summary")]
    if no_summary:
        warnings.append(f"缺少章节摘要：{no_summary[:10]}{'…' if len(no_summary) > 10 else ''}（共{len(no_summary)}章）")

    result = {"volume": volume_num, "range": [start_seq, end_seq], "passed": not blockers,
              "blockers": blockers, "warnings": warnings,
              "checked_at": datetime.now(timezone.utc).isoformat()}

    if result["passed"]:
        summaries = [c["summary"] for c in chapters if c.get("summary")]
        if summaries:
            try:
                from app.services.summarizer import summarize_volume
                result["volume_summary"] = summarize_volume(novel_id, volume_num, summaries)["summary"]
            except Exception as exc:
                warnings.append(f"卷摘要生成失败（不阻断门禁）：{exc}")
                result["warnings"] = warnings

    db = connect()
    gates = meta.get("volume_gates") or {}
    gates[str(volume_num)] = result
    db.execute("UPDATE contents SET meta = meta || %s, updated_at = now() WHERE id = %s",
               (encode({"volume_gates": gates}), novel_id))
    if result.get("volume_summary"):
        vol_summaries = meta.get("volume_summaries") or {}
        vol_summaries[str(volume_num)] = result["volume_summary"]
        db.execute("UPDATE contents SET meta = meta || %s, updated_at = now() WHERE id = %s",
                   (encode({"volume_summaries": vol_summaries}), novel_id))
    db.commit(); db.close()
    return result


def volume_for_chapter(volume_plan: list[dict], chapter_seq: int) -> dict | None:
    """Locate the planned volume that contains a chapter seq."""
    for vol in volume_plan or []:
        try:
            if int(vol.get("start_chapter", 0) or 0) <= chapter_seq <= int(vol.get("end_chapter", 0) or 0):
                return vol
        except (TypeError, ValueError):
            continue
    return None


def validate_character_arc(novel_id: str, arc_config: list[dict]) -> list[dict]:
    """TASK-019: Validate character arcs against current progress."""
    db = connect()
    characters = db.execute(
        "SELECT DISTINCT meta->'character_name' as name FROM contents WHERE parent_id = %s AND type = 'character'",
        (novel_id,)
    ).fetchall()
    db.close()

    issues = []
    for arc in arc_config:
        name = arc.get("name", "")
        expected_stage = arc.get("stage", "")
        target_chapter = arc.get("target_chapter", 0)
        if target_chapter > 0 and target_chapter < arc.get("current_chapter", 0):
            issues.append({
                "character": name,
                "issue": f"弧线阶段 '{expected_stage}' 应于第{target_chapter}章完成，现已超期",
                "suggestion": "调整弧线进度或推进剧情",
            })
    return issues
