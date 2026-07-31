"""Thin DB repositories for the V6.1.2 single-chapter closed loop.

Keeps the ``DB.execute`` style of ``app/db.py`` (no ORM). Every function returns
plain dicts/lists so the loop module stays provider-agnostic.
"""
from __future__ import annotations

from typing import Any

from ..db import connect, decode, encode, new_id, row_to_dict


def _q(sql: str, params: tuple = ()) -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


# ── workflow_runs (ai_calls.run_id FK target) ────────────────────────────────
def ensure_workflow_run(project_id: str, novel_id: str, *,
                        workflow_key: str = "chapter_loop",
                        context: dict | None = None) -> str:
    """Create a running workflow_runs row and return its id."""
    run_id = new_id("run")
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO workflow_runs (id, project_id, novel_id, workflow_key, status, "
            "context, started_at) VALUES (%s, %s, %s, %s, 'running', %s, now())",
            (run_id, project_id, novel_id, workflow_key, encode(context or {})),
        )
        conn.commit()
    finally:
        conn.close()
    return run_id


def finish_workflow_run(run_id: str, status: str = "succeeded") -> None:
    conn = connect()
    try:
        conn.execute(
            "UPDATE workflow_runs SET status=%s, finished_at=now(), updated_at=now() "
            "WHERE id=%s",
            (status, run_id),
        )
        conn.commit()
    finally:
        conn.close()


# ── book_config / book_status ────────────────────────────────────────────────
def get_book_config(project_id: str, novel_id: str) -> dict | None:
    rows = _q(
        "SELECT * FROM book_config WHERE novel_id=%s AND project_id=%s AND is_deleted=FALSE",
        (novel_id, project_id),
    )
    return rows[0] if rows else None


def ensure_book_config(project_id: str, novel_id: str, **fields) -> dict:
    """Insert a book_config row if missing (idempotent per novel)."""
    existing = get_book_config(project_id, novel_id)
    if existing:
        return existing
    cfg_id = new_id("cfg")
    cols = ["id", "novel_id", "project_id"]
    vals: list[Any] = [cfg_id, novel_id, project_id]
    defaults = {
        "genre": "都市重生",
        "domain_type": "urban_business",
        "theme": "",
        "author_intent": {},
        "immutable_rules": [],
        "target_words": 1000000,
    }
    for k, v in defaults.items():
        if k in fields:
            v = fields[k]
        cols.append(k)
        vals.append(encode(v) if isinstance(v, (dict, list)) else v)
    placeholders = ", ".join(["%s"] * len(cols))
    conn = connect()
    try:
        conn.execute(
            f"INSERT INTO book_config ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(vals),
        )
        conn.commit()
    finally:
        conn.close()
    return get_book_config(project_id, novel_id)


BOOK_STATUSES = ("draft", "worldbuilding", "outline_confirmed", "serializing",
                 "paused", "completed", "archived")


def record_book_status(project_id: str, novel_id: str, status: str, reason: str = "") -> None:
    """Append a book-lifecycle transition. No-op if the status is unchanged."""
    if status not in BOOK_STATUSES:
        raise ValueError(f"invalid book status {status!r}; allowed: {BOOK_STATUSES}")
    conn = connect()
    try:
        last = conn.execute(
            "SELECT status FROM book_status WHERE novel_id=%s "
            "ORDER BY changed_at DESC LIMIT 1",
            (novel_id,),
        ).fetchone()
        if last and row_to_dict(last).get("status") == status:
            return
        conn.execute(
            "INSERT INTO book_status (id, project_id, novel_id, status, reason, changed_at) "
            "VALUES (%s, %s, %s, %s, %s, now())",
            (new_id("bs"), project_id, novel_id, status, reason),
        )
        conn.commit()
    finally:
        conn.close()


# ── style_cards (Phase A: only author_card / genre_card consumed) ────────────
def get_style_cards(project_id: str) -> dict | None:
    rows = _q(
        "SELECT id, author_card, genre_card FROM style_cards "
        "WHERE project_id=%s ORDER BY updated_at DESC LIMIT 1",
        (project_id,),
    )
    return rows[0] if rows else None


# ── reviews (structured 7-dim) ───────────────────────────────────────────────
def save_review(
    content_id: str,
    score_7dim: dict,
    issues: list[dict],
    review_hash: str,
    model: str,
    *,
    overall: float | None = None,
    run_id: str | None = None,
    review_type: str = "bootstrap",
) -> str:
    """Persist one structured 7-dim review.

    ``reviews`` is keyed on content_id (no project_id/chapter_seq columns);
    ``score_7dim`` must be the fixed {dim: {score, reason}} shape and
    ``issues_structured`` marks that ``issues`` uses the structured schema.
    """
    rid = new_id("rev")
    if overall is None:
        vals = [float(d.get("score", 0)) for d in score_7dim.values() if isinstance(d, dict)]
        overall = sum(vals) / len(vals) if vals else 0.0
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO reviews (id, content_id, workflow_run_id, score, dimensions, "
            "issues, score_7dim, issues_structured, review_type, model, review_hash, "
            "created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s, %s, now())",
            (rid, content_id, run_id, int(round(overall)), encode(score_7dim),
             encode(issues), encode(score_7dim), review_type, model, review_hash),
        )
        conn.commit()
    finally:
        conn.close()
    return rid


# ── repair_versions ──────────────────────────────────────────────────────────
def save_repair_version(project_id: str, content_id: str, **fields) -> str:
    rid = new_id("rep")
    cols = ["id", "project_id", "content_id"]
    vals: list[Any] = [rid, project_id, content_id]
    defaults = {
        "chapter_seq": None,
        "base_version_id": None,
        "repair_type": "local",
        "repair_scope": None,
        "repair_status": "pending",
        "before_text": "",
        "after_text": "",
        "repair_prompt": None,
        "second_review_score": None,
        "second_review_issues": None,
        "rolled_back": False,
        "reason": None,
        "model": None,
    }
    for k, v in defaults.items():
        if k in fields:
            v = fields[k]
        cols.append(k)
        vals.append(encode(v) if isinstance(v, (dict, list)) else v)
    placeholders = ", ".join(["%s"] * len(cols))
    conn = connect()
    try:
        conn.execute(
            f"INSERT INTO repair_versions ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(vals),
        )
        conn.commit()
    finally:
        conn.close()
    return rid


def update_repair_status(repair_id: str, status: str, **fields) -> None:
    sets = ["repair_status=%s"]
    params: list[Any] = [status]
    for k in ("second_review_score", "second_review_issues", "rolled_back", "reason"):
        if k in fields:
            v = fields[k]
            sets.append(f"{k}=%s")
            params.append(encode(v) if isinstance(v, (dict, list)) else v)
    params.append(repair_id)
    conn = connect()
    try:
        conn.execute(
            f"UPDATE repair_versions SET {', '.join(sets)} WHERE id=%s", tuple(params)
        )
        conn.commit()
    finally:
        conn.close()


# ── Story Bible: entity_states + knowledge_items ────────────────────────────
def upsert_entity_state(chapter_id: str, entity: dict) -> None:
    """Write one entity snapshot for a chapter.

    entity_states is a per-chapter snapshot table keyed by chapter_id
    (FK -> contents.id).  It has no project_id/novel_id/state columns:
    free-form state text is folded into known_info['state'].

    entity: {type, name, state, location, relationships, possessions,
             known_info, confidence, importance_level}
    """
    name = str(entity.get("name") or entity.get("entity_name") or "").strip()
    if not name:
        return
    etype = str(entity.get("type") or entity.get("entity_type") or "character")

    known = entity.get("known_info")
    if isinstance(known, str):
        known = {"note": known}
    elif not isinstance(known, dict):
        known = {}
    state_text = str(entity.get("state") or "").strip()
    if state_text:
        known = {**known, "state": state_text}

    rel = entity.get("relationships")
    rel = rel if isinstance(rel, (dict, list)) else {}
    poss = entity.get("possessions")
    poss = poss if isinstance(poss, list) else []

    try:
        confidence = min(1.0, max(0.0, float(entity.get("confidence", 1.0))))
    except (TypeError, ValueError):
        confidence = 1.0
    try:
        importance = min(10, max(1, int(entity.get("importance_level", 5))))
    except (TypeError, ValueError):
        importance = 5

    conn = connect()
    try:
        existing = row_to_dict(
            conn.execute(
                "SELECT id FROM entity_states "
                "WHERE chapter_id=%s AND entity_type=%s AND entity_name=%s",
                (chapter_id, etype, name),
            ).fetchone()
        )
        if existing:
            conn.execute(
                "UPDATE entity_states SET location=%s, relationships=%s, possessions=%s, "
                "known_info=%s, confidence=%s, importance_level=%s, updated_at=now() "
                "WHERE id=%s",
                (entity.get("location", ""), encode(rel), encode(poss), encode(known),
                 confidence, importance, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO entity_states (id, chapter_id, entity_type, entity_name, "
                "location, relationships, possessions, known_info, confidence, "
                "importance_level) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (new_id("ent"), chapter_id, etype, name, entity.get("location", ""),
                 encode(rel), encode(poss), encode(known), confidence, importance),
            )
        conn.commit()
    finally:
        conn.close()


def save_knowledge_fact(project_id: str, novel_id: str, fact: dict) -> None:
    """fact: {kind, title, body, fact_type, confidence, source_chapter, approved}."""
    kind = fact.get("kind", "fact")
    title = fact.get("title") or fact.get("body", "")[:50]
    body = fact.get("body", "")
    fact_type = fact.get("fact_type", "hard")
    confidence = float(fact.get("confidence", 1.0))
    conn = connect()
    try:
        # idempotent per (novel, chapter, fact body) so re-running a chapter
        # does not multiply the Story Bible
        dup = conn.execute(
            "SELECT id FROM knowledge_items WHERE content_id=%s AND kind=%s "
            "AND source_chapter IS NOT DISTINCT FROM %s AND body=%s AND is_deleted=FALSE",
            (novel_id, kind, fact.get("source_chapter"), body),
        ).fetchone()
        if dup:
            return
        conn.execute(
            "INSERT INTO knowledge_items (id, project_id, content_id, kind, title, body, "
            "fact_type, confidence, source_chapter, approved, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())",
            (new_id("ki"), project_id, novel_id, kind, title, body,
             fact_type, confidence, fact.get("source_chapter"),
             bool(fact.get("approved", False))),
        )
        conn.commit()
    finally:
        conn.close()


# ── Protagonist anchoring (Defect 1: 主角漂移) ───────────────────────────────
def save_protagonist(project_id: str, novel_id: str, name: str, pov: str = "") -> None:
    """Anchor the novel's protagonist + POV in book_config.author_intent so every
    later chapter generation is forced to keep the same lead and viewpoint."""
    cfg = ensure_book_config(project_id, novel_id)
    intent = decode(cfg.get("author_intent"), {}) or {}
    if not isinstance(intent, dict):
        intent = {}
    intent["protagonist"] = {"name": str(name).strip(), "pov": str(pov).strip()}
    conn = connect()
    try:
        conn.execute(
            "UPDATE book_config SET author_intent=%s, updated_at=now() WHERE id=%s",
            (encode(intent), cfg["id"]),
        )
        conn.commit()
    finally:
        conn.close()


def get_protagonist(project_id: str, novel_id: str) -> dict | None:
    cfg = get_book_config(project_id, novel_id)
    if not cfg:
        return None
    intent = decode(cfg.get("author_intent"), {}) or {}
    p = intent.get("protagonist") if isinstance(intent, dict) else None
    return p if isinstance(p, dict) and p.get("name") else None


def get_canonical_names(project_id: str, novel_id: str) -> list[str]:
    """Distinct character names already in the Story Bible — the model must reuse
    these exact spellings (Defect 2: name confusion)."""
    rows = _q(
        "SELECT DISTINCT es.entity_name FROM entity_states es "
        "JOIN contents c ON c.id = es.chapter_id "
        "WHERE c.parent_id=%s AND c.is_deleted=FALSE "
        "AND es.entity_type='character' AND es.importance_level >= 4 "
        "ORDER BY es.entity_name",
        (novel_id,),
    )
    return [r["entity_name"] for r in rows if r.get("entity_name")]


# ── Foreshadowing ledger (架构 §4.5) ─────────────────────────────────────────
# Note: the physical table is ``foreshadowings`` keyed by chapter_id -> contents.id.
# We keep the legacy ``status`` values ('planted'/'resolved') untouched so the
# existing ``narrative_engine.check_foreshadow_due`` keeps working, and derive
# open/due_soon/overdue at read time from planned_resolve_chapter.
DUE_SOON_WINDOW = 2  # chapters ahead of the deadline where we start pushing


def save_foreshadowing(chapter_id: str, seq: int, item: dict) -> str | None:
    """Register one foreshadowing planted in this chapter.

    item: {content, importance(1-10), reader_awareness, expected_payoff_window}
    Idempotent per (chapter_id, content) so re-running a chapter does not
    duplicate the ledger.
    """
    content = str(item.get("content") or "").strip()
    if not content:
        return None
    try:
        importance = min(10, max(1, int(item.get("importance", 5))))
    except (TypeError, ValueError):
        importance = 5
    awareness = str(item.get("reader_awareness") or "hidden").strip()
    if awareness not in ("hidden", "suspected", "known"):
        awareness = "hidden"
    try:
        window = int(item.get("expected_payoff_window", 10))
    except (TypeError, ValueError):
        window = 10
    window = max(1, window)
    planned = seq + window

    conn = connect()
    try:
        dup = conn.execute(
            "SELECT id FROM foreshadowings WHERE chapter_id=%s AND content=%s",
            (chapter_id, content),
        ).fetchone()
        if dup:
            return row_to_dict(dup)["id"]
        fid = new_id("fs")
        conn.execute(
            "INSERT INTO foreshadowings (id, chapter_id, content, planned_resolve_chapter, "
            "status, importance, reader_awareness, expected_payoff_window) "
            "VALUES (%s, %s, %s, %s, 'planted', %s, %s, %s)",
            (fid, chapter_id, content, planned, importance, awareness, window),
        )
        conn.commit()
        return fid
    finally:
        conn.close()


def resolve_foreshadowing(novel_id: str, content: str, resolve_chapter_id: str) -> bool:
    """Mark an open foreshadowing as resolved by this chapter.

    Matches on exact content first, then falls back to a prefix match because the
    model may echo the ledger entry with minor trailing punctuation.
    """
    content = str(content or "").strip()
    if not content:
        return False
    conn = connect()
    try:
        row = conn.execute(
            "SELECT f.id FROM foreshadowings f JOIN contents c ON c.id=f.chapter_id "
            "WHERE c.parent_id=%s AND f.status <> 'resolved' AND f.content=%s LIMIT 1",
            (novel_id, content),
        ).fetchone()
        if not row:
            row = conn.execute(
                "SELECT f.id FROM foreshadowings f JOIN contents c ON c.id=f.chapter_id "
                "WHERE c.parent_id=%s AND f.status <> 'resolved' "
                "AND (f.content LIKE %s OR %s LIKE f.content || '%%') LIMIT 1",
                (novel_id, content[:30] + "%", content),
            ).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE foreshadowings SET status='resolved', resolve_chapter_id=%s, "
            "updated_at=now() WHERE id=%s",
            (resolve_chapter_id, row_to_dict(row)["id"]),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_open_foreshadowings(novel_id: str, current_seq: int) -> list[dict]:
    """All unresolved foreshadowings with a derived due-state for this chapter.

    derived status: overdue (deadline already passed) / due_soon (within
    DUE_SOON_WINDOW) / open.
    """
    rows = _q(
        "SELECT f.id, f.content, f.planned_resolve_chapter, f.importance, "
        "f.reader_awareness, f.expected_payoff_window, c.seq AS planted_seq "
        "FROM foreshadowings f JOIN contents c ON c.id=f.chapter_id "
        "WHERE c.parent_id=%s AND c.is_deleted=FALSE AND f.status <> 'resolved' "
        "ORDER BY f.planned_resolve_chapter, f.importance DESC",
        (novel_id,),
    )
    out = []
    for r in rows:
        try:
            planned = int(r.get("planned_resolve_chapter") or 0)
        except (TypeError, ValueError):
            planned = 0
        if planned and current_seq >= planned:
            state = "overdue"
        elif planned and current_seq >= planned - DUE_SOON_WINDOW:
            state = "due_soon"
        else:
            state = "open"
        out.append({
            "id": r["id"], "content": r.get("content", ""),
            "planned_resolve_chapter": planned,
            "importance": r.get("importance", 5),
            "reader_awareness": r.get("reader_awareness", "hidden"),
            "planted_at": str(r.get("planted_seq") or ""),
            "state": state,
        })
    return out


# ── Character capability tree + arc (架构 §4.2 / §4.3) ───────────────────────
def upsert_capability(chapter_id: str, entity_name: str, change: dict) -> None:
    """Merge one capability into an entity's capability_tree for this chapter.

    Same skill => upgrade in place (keep the earliest acquired_chapter so the
    audit trail of "when did they learn it" is not lost).
    """
    skill = str(change.get("skill") or "").strip()
    name = str(entity_name or "").strip()
    if not skill or not name:
        return
    entry = {
        "skill": skill,
        "level": str(change.get("level") or "初级").strip(),
        "acquired_chapter": change.get("acquired_chapter"),
        "evidence": str(change.get("evidence") or "").strip(),
        "limitations": str(change.get("limitations") or "").strip(),
    }
    conn = connect()
    try:
        row = row_to_dict(conn.execute(
            "SELECT id, capability_tree FROM entity_states "
            "WHERE chapter_id=%s AND entity_type='character' AND entity_name=%s",
            (chapter_id, name),
        ).fetchone())
        if not row:
            return  # entity not in this chapter's snapshot; nothing to attach to
        tree = decode(row.get("capability_tree"), []) or []
        if not isinstance(tree, list):
            tree = []
        merged, found = [], False
        for old in tree:
            if isinstance(old, dict) and str(old.get("skill", "")).strip() == skill:
                found = True
                entry["acquired_chapter"] = old.get("acquired_chapter") or entry["acquired_chapter"]
                merged.append(entry)
            else:
                merged.append(old)
        if not found:
            merged.append(entry)
        conn.execute(
            "UPDATE entity_states SET capability_tree=%s, updated_at=now() WHERE id=%s",
            (encode(merged), row["id"]),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_character_arc(chapter_id: str, entity_name: str, arc: dict) -> None:
    """Update a character's arc stage; append turning points cumulatively."""
    name = str(entity_name or "").strip()
    if not name:
        return
    stage = str(arc.get("current_arc_stage") or "").strip()
    turning = str(arc.get("turning_point") or "").strip()
    if not stage and not turning:
        return
    conn = connect()
    try:
        row = row_to_dict(conn.execute(
            "SELECT id, character_arc FROM entity_states "
            "WHERE chapter_id=%s AND entity_type='character' AND entity_name=%s",
            (chapter_id, name),
        ).fetchone())
        if not row:
            return
        cur = decode(row.get("character_arc"), {}) or {}
        if not isinstance(cur, dict):
            cur = {}
        if stage:
            cur["current_arc_stage"] = stage
        if turning:
            points = cur.get("turning_points")
            points = points if isinstance(points, list) else []
            if turning not in points:
                points.append(turning)
            cur["turning_points"] = points
        conn.execute(
            "UPDATE entity_states SET character_arc=%s, updated_at=now() WHERE id=%s",
            (encode(cur), row["id"]),
        )
        conn.commit()
    finally:
        conn.close()


def get_capability_tree(novel_id: str, names: list[str] | None = None) -> dict[str, list[dict]]:
    """Latest capability tree per character across the whole novel.

    Rows are ordered oldest-first so later chapters overwrite earlier snapshots.
    """
    rows = _q(
        "SELECT es.entity_name, es.capability_tree, c.seq AS seq "
        "FROM entity_states es JOIN contents c ON c.id=es.chapter_id "
        "WHERE c.parent_id=%s AND c.is_deleted=FALSE AND es.entity_type='character' "
        "AND es.capability_tree <> '[]'::jsonb "
        "ORDER BY c.seq",
        (novel_id,),
    )
    out: dict[str, list[dict]] = {}
    wanted = {str(n).strip() for n in (names or []) if str(n).strip()}
    for r in rows:
        name = r.get("entity_name")
        if not name or (wanted and name not in wanted):
            continue
        tree = decode(r.get("capability_tree"), []) or []
        if not isinstance(tree, list) or not tree:
            continue
        by_skill = {str(c.get("skill", "")): c for c in out.get(name, []) if isinstance(c, dict)}
        for cap in tree:
            if isinstance(cap, dict) and cap.get("skill"):
                by_skill[str(cap["skill"])] = cap
        out[name] = list(by_skill.values())
    return out


# ── Step 4: richer Story Bible writeback (plot_threads/world_state/snapshot/arc)
def save_plot_thread(project_id: str, novel_id: str, thread: dict) -> None:
    name = str(thread.get("name") or "").strip()
    if not name:
        return
    status = thread.get("status", "active")
    if status not in ("active", "paused", "resolved", "abandoned"):
        status = "active"
    try:
        importance = min(10, max(1, int(thread.get("importance", 5))))
    except (TypeError, ValueError):
        importance = 5
    conn = connect()
    try:
        existing = row_to_dict(
            conn.execute(
                "SELECT id FROM plot_threads WHERE novel_id=%s AND name=%s AND is_deleted=FALSE",
                (novel_id, name),
            ).fetchone()
        )
        if existing:
            conn.execute(
                "UPDATE plot_threads SET status=%s, importance=%s, progress=%s, "
                "last_chapter_seq=%s, updated_at=now() WHERE id=%s",
                (status, importance, thread.get("progress", ""),
                 thread.get("last_chapter_seq"), existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO plot_threads (id, project_id, novel_id, name, status, "
                "importance, progress, last_chapter_seq) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (new_id("pt"), project_id, novel_id, name, status, importance,
                 thread.get("progress", ""), thread.get("last_chapter_seq")),
            )
        conn.commit()
    finally:
        conn.close()


def save_world_state(project_id: str, novel_id: str, chapter_seq: int, snapshot: dict) -> None:
    if not isinstance(snapshot, dict):
        snapshot = {}
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO world_state (id, project_id, novel_id, chapter_seq, state_version, snapshot) "
            "VALUES (%s, %s, %s, %s, 1, %s)",
            (new_id("ws"), project_id, novel_id, chapter_seq, encode(snapshot)),
        )
        conn.commit()
    finally:
        conn.close()


def save_chapter_snapshot(project_id: str, content_id: str, chapter_seq: int,
                           content_hash: str, *, entity_state_hash: str = "",
                           prompt_version: str = "", model: str = "deepseek-chat") -> None:
    """Lock a chapter's final text + entity hash so historical drift is detectable."""
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO chapter_snapshot (id, project_id, content_id, chapter_seq, "
            "content_hash, entity_state_hash, prompt_version, model) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (content_id) DO UPDATE SET chapter_seq=EXCLUDED.chapter_seq, "
            "content_hash=EXCLUDED.content_hash, entity_state_hash=EXCLUDED.entity_state_hash, "
            "prompt_version=EXCLUDED.prompt_version, model=EXCLUDED.model",
            (new_id("snap"), project_id, content_id, chapter_seq, content_hash,
             entity_state_hash, prompt_version, model),
        )
        conn.commit()
    finally:
        conn.close()


def save_arc_summary(project_id: str, novel_id: str, volume_seq: int, summary: str) -> None:
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO arc_summary (id, project_id, novel_id, volume_seq, summary) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (novel_id, volume_seq) DO UPDATE SET summary=EXCLUDED.summary, "
            "updated_at=now()",
            (new_id("arc"), project_id, novel_id, volume_seq, summary),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_chapter_bodies(novel_id: str, limit: int = 10) -> list[dict]:
    """Recent chapter bodies (raw text) for style relearning."""
    rows = _q(
        "SELECT c.seq, c.body->>'text' AS text FROM contents c "
        "WHERE c.parent_id=%s AND c.type='chapter' AND c.is_deleted=FALSE "
        "ORDER BY c.seq DESC LIMIT %s",
        (novel_id, limit),
    )
    return [{"seq": r["seq"], "text": r.get("text") or ""} for r in rows]


def update_author_card(project_id: str, card: dict) -> None:
    """Persist a relearned author style card (Step 6)."""
    conn = connect()
    try:
        existing = row_to_dict(
            conn.execute(
                "SELECT id FROM style_cards WHERE project_id=%s ORDER BY updated_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        )
        if existing:
            conn.execute(
                "UPDATE style_cards SET author_card=%s, updated_at=now() WHERE id=%s",
                (encode(card or {}), existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO style_cards (id, project_id, author_card) VALUES (%s, %s, %s)",
                (new_id("sc"), project_id, encode(card or {})),
            )
        conn.commit()
    finally:
        conn.close()


def save_style_relearn(project_id: str, novel_id: str, card: dict) -> dict:
    """Stage a relearned author card. Promotes to the live style_cards.author_card
    only after >=3 learn rounds (style_change_confidence gate: AI must not silently
    rewrite the author's voice). Returns {learn_count, applied}."""
    cfg = ensure_book_config(project_id, novel_id)
    intent = decode(cfg.get("author_intent"), {}) or {}
    if not isinstance(intent, dict):
        intent = {}
    intent["style_candidate"] = card
    intent["style_learn_count"] = int(intent.get("style_learn_count", 0)) + 1
    applied = intent["style_learn_count"] >= 3
    if applied:
        intent["author_card_applied"] = card
        update_author_card(project_id, card)
    conn = connect()
    try:
        conn.execute(
            "UPDATE book_config SET author_intent=%s, updated_at=now() WHERE id=%s",
            (encode(intent), cfg["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return {"learn_count": intent["style_learn_count"], "applied": applied}


def get_story_bible(project_id: str, novel_id: str) -> dict:
    # entity_states is per-chapter; take the latest snapshot per (type, name)
    # by walking chapters of this novel in reverse order.
    entities = _q(
        "SELECT * FROM ("
        "  SELECT DISTINCT ON (es.entity_type, es.entity_name)"
        "         es.entity_type, es.entity_name, es.location, es.known_info,"
        "         es.relationships, es.confidence::float8 AS confidence,"
        "         es.importance_level, c.seq AS chapter_seq"
        "  FROM entity_states es JOIN contents c ON c.id = es.chapter_id"
        "  WHERE c.parent_id=%s AND c.is_deleted=FALSE"
        "  ORDER BY es.entity_type, es.entity_name, c.seq DESC NULLS LAST,"
        "           es.updated_at DESC"
        ") t WHERE t.importance_level >= 4 "
        "ORDER BY t.importance_level DESC, t.chapter_seq DESC NULLS LAST LIMIT 40",
        (novel_id,),
    )
    facts = _q(
        "SELECT kind, title, body FROM knowledge_items "
        "WHERE project_id=%s AND content_id=%s AND is_deleted=FALSE "
        "AND (fact_type='hard' OR approved=TRUE) ORDER BY created_at DESC LIMIT 60",
        (project_id, novel_id),
    )
    return {"entities": entities, "facts": facts}


# ── context_package / chapter_summaries / generation_cost_log ────────────────
def save_context_package(project_id: str, content_id: str, chapter_seq: int,
                          context_hash: str, included: list, token_budget: int,
                          actual_tokens: int | None, layers: dict) -> None:
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO context_package (id, project_id, content_id, chapter_seq, "
            "context_hash, included, token_budget, actual_tokens, layers, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now()) "
            "ON CONFLICT (content_id) DO UPDATE SET "
            "  chapter_seq=EXCLUDED.chapter_seq, context_hash=EXCLUDED.context_hash, "
            "  included=EXCLUDED.included, token_budget=EXCLUDED.token_budget, "
            "  actual_tokens=EXCLUDED.actual_tokens, layers=EXCLUDED.layers",
            (new_id("cp"), project_id, content_id, chapter_seq, context_hash,
             encode(included), token_budget, actual_tokens, encode(layers)),
        )
        conn.commit()
    finally:
        conn.close()


def save_chapter_summary(project_id: str, content_id: str, chapter_seq: int,
                          summary: str, summary_type: str = "chapter",
                          generated_by: str = "deepseek", key_chars: list | None = None,
                          key_decisions: str | None = None) -> None:
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO chapter_summaries (id, project_id, content_id, chapter_seq, "
            "summary_type, generated_by, summary, key_chars, key_decisions, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now()) "
            "ON CONFLICT (content_id) DO UPDATE SET "
            "  chapter_seq=EXCLUDED.chapter_seq, summary_type=EXCLUDED.summary_type, "
            "  generated_by=EXCLUDED.generated_by, summary=EXCLUDED.summary, "
            "  key_chars=EXCLUDED.key_chars, key_decisions=EXCLUDED.key_decisions",
            (new_id("cs"), project_id, content_id, chapter_seq, summary_type, generated_by,
             summary, encode(key_chars or []), key_decisions),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_summaries(novel_id: str, limit: int = 10) -> list[dict]:
    """Latest chapter summaries of one novel, newest first."""
    return _q(
        "SELECT cs.content_id, cs.chapter_seq, cs.summary FROM chapter_summaries cs "
        "JOIN contents c ON c.id = cs.content_id "
        "WHERE c.parent_id=%s AND cs.is_deleted=FALSE AND cs.summary_type='chapter' "
        "ORDER BY cs.chapter_seq DESC LIMIT %s",
        (novel_id, limit),
    )


def save_generation_cost_log(project_id: str, rows: list[dict]) -> None:
    """rows: [{content_id, chapter_seq, phase, task_type, model, prompt_tokens,
    completion_tokens, cost_cny, success}]."""
    conn = connect()
    try:
        for r in rows:
            conn.execute(
                "INSERT INTO generation_cost_log (id, project_id, content_id, chapter_seq, "
                "phase, task_type, model, prompt_tokens, completion_tokens, total_tokens, "
                "cost_cny, success, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())",
                (new_id("gc"), project_id, r.get("content_id"), r.get("chapter_seq"),
                 r.get("phase"), r.get("task_type"), r.get("model"),
                 r.get("prompt_tokens", 0), r.get("completion_tokens", 0),
                 (r.get("prompt_tokens", 0) + r.get("completion_tokens", 0)),
                 r.get("cost_cny", 0.0), bool(r.get("success", True))),
            )
        conn.commit()
    finally:
        conn.close()


# ── Emotion curve (架构 §5.2) ────────────────────────────────────────────────
# Deterministic mapping from review dimensions → reader emotion state.
# Pure rule, zero LLM cost.
_EMOTION_MAP = [
    # (condition_fn, state) — evaluated top-down, first match wins
    (lambda d: d.get("emotion", {}).get("score", 100) < 68, "压抑"),
    (lambda d: d.get("plot", {}).get("score", 0) >= 88
     and d.get("emotion", {}).get("score", 0) >= 82, "爆发"),
    (lambda d: d.get("pacing", {}).get("score", 0) >= 85
     and d.get("emotion", {}).get("score", 0) >= 80, "爽"),
    (lambda d: d.get("conflict", d.get("plot", {})).get("score", 0) >= 80
     and d.get("emotion", {}).get("score", 0) < 80, "冲突"),
    (lambda d: d.get("plot", {}).get("score", 0) >= 80
     and d.get("pacing", {}).get("score", 0) >= 75, "期待"),
    (lambda _d: True, "缓冲"),  # fallback
]


def classify_emotion(dimensions: dict) -> str:
    """Map review 7-dim scores → one of 压抑/冲突/爆发/爽/缓冲/期待."""
    for cond, state in _EMOTION_MAP:
        if cond(dimensions):
            return state
    return "缓冲"


def save_emotion_state(project_id: str, content_id: str,
                       chapter_seq: int, state: str) -> None:
    """Upsert emotion state for one chapter (unique on content_id)."""
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO chapter_emotion_state (id, project_id, content_id, chapter_seq, state) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (content_id) DO UPDATE SET state=EXCLUDED.state",
            (new_id("emo"), project_id, content_id, chapter_seq, state),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_emotions(novel_id: str, limit: int = 20) -> list[dict]:
    """Recent emotion states for balance warning."""
    return _q(
        "SELECT ces.chapter_seq, ces.state FROM chapter_emotion_state ces "
        "JOIN contents c ON c.id=ces.content_id "
        "WHERE c.parent_id=%s AND c.is_deleted=FALSE "
        "ORDER BY ces.chapter_seq DESC LIMIT %s",
        (novel_id, limit),
    )


# ── Audit report (架构 §10.3, 零 LLM 规则聚合) ──────────────────────────────
def save_audit_report(project_id: str, novel_id: str, at_chapter: int,
                      character_changes: list, capability_changes: list,
                      foreshadowing_status: dict, style_drift: dict) -> None:
    """Upsert a rule-aggregated audit report (ON CONFLICT on novel+chapter)."""
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO chapter_audit_report "
            "(id, project_id, novel_id, at_chapter, character_changes, "
            "capability_changes, foreshadowing_status, style_drift) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (novel_id, at_chapter) DO UPDATE SET "
            "character_changes=EXCLUDED.character_changes, "
            "capability_changes=EXCLUDED.capability_changes, "
            "foreshadowing_status=EXCLUDED.foreshadowing_status, "
            "style_drift=EXCLUDED.style_drift",
            (new_id("audit"), project_id, novel_id, at_chapter,
             encode(character_changes), encode(capability_changes),
             encode(foreshadowing_status), encode(style_drift)),
        )
        conn.commit()
    finally:
        conn.close()
