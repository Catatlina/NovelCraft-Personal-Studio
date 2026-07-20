"""Celery tasks — workflow execution and scheduled jobs.

V2 Bootstrap: 4-stage professional architecture
  Stage 1 - Planning: Idea → MarketFit → StoryPattern → CoreGameplay →
                       WorldArchitecture → CharacterSystem → ConflictMap
  Stage 2 - Blueprint: VolumePlan → ChapterOutlineBatch → SceneBeatSheet
  Stage 3 - Writing:   ChapterDraft → SelfReview → Polish → LengthCheck → FactReconcile
  Stage 4 - Finalization: ConsistencyCheck(6-dim) → ContinuityAudit → Humanize

Features:
  - Context window management (write-before-search + write-after-reconcile, up to 100 chapters)
  - Chapter idempotency (ON CONFLICT with generation_key)
  - Budget tracking per chapter/node
  - Event ledger (record_event from fusion_deep_workflow)
  - Checkpoint support (resume from any failed node)
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any

from app.db import connect, encode, new_id, row_to_dict
from app.gateway import (BudgetExceeded, OutputValidationError, ProviderError, complete,
                         validate_task_output, _request_api_key, _request_api_base_url, _request_model)
from app.services.novel_export import extract_body_text

from .celery_app import celery_app

# ── 4-stage bootstrap node definitions ──────────────────────────────────────

BOOTSTRAP_STAGES = {
    "planning": {
        "label": "规划阶段",
        "nodes": [
            ("plan_idea",              "agent", "StoryArchitect", "创意展开",         "plan_idea"),
            ("plan_market_fit",        "agent", "StoryArchitect", "市场匹配分析",     "plan_market_fit"),
            ("plan_story_pattern",     "agent", "StoryArchitect", "故事模式识别",     "plan_story_pattern"),
            ("plan_core_gameplay",     "agent", "StoryArchitect", "核心玩法/爽点",    "plan_core_gameplay"),
            ("plan_world_architecture","agent", "StoryArchitect", "世界观架构",       "plan_world_architecture"),
            ("plan_character_system",  "agent", "Character",      "人物系统设计",     "plan_character_system"),
            ("plan_conflict_map",      "agent", "StoryArchitect", "冲突图谱",         "plan_conflict_map"),
        ],
    },
    "blueprint": {
        "label": "蓝图阶段",
        "nodes": [
            ("blueprint_volume_plan",     "agent", "StoryArchitect", "分卷规划",          "blueprint_volume_plan"),
            ("blueprint_chapter_outline", "agent", "StoryArchitect", "逐章细纲",          "blueprint_chapter_outline"),
            ("blueprint_scene_beat",      "agent", "StoryArchitect", "场景节拍表",        "blueprint_scene_beat"),
        ],
    },
    "writing": {
        "label": "写作阶段",
        "nodes": [
            ("write_chapter_draft",    "agent", "Writer",    "章节初稿",          "write_chapter_draft"),
            ("write_self_review",      "agent", "Writer",    "自我审阅",          "write_self_review"),
            ("write_polish",           "agent", "Writer",    "润色打磨",          "write_polish"),
            ("write_length_check",     "agent", "Reviewer",  "篇幅检查",          "write_length_check"),
            ("write_fact_reconcile",   "agent", "Reviewer",  "事实核对",          "write_fact_reconcile"),
        ],
    },
    "finalization": {
        "label": "最终化阶段",
        "nodes": [
            ("final_humanize",          "agent", "Writer",    "去AI味人文化",      "final_humanize"),
            ("final_consistency_check", "agent", "Reviewer",  "七维一致性检查",    "final_consistency_check"),
            ("final_continuity_audit",  "agent", "Reviewer",  "连续性审计",        "final_continuity_audit"),
        ],
    },
}

# Human confirmation node sits between planning and blueprint
HUMAN_NODE = ("human_confirm_title", "human", None, "选定书名", None)

# Flattened list preserving stage order (used by create_run for node seeding)
BOOTSTRAP_NODES: list[tuple[str, str, str | None, str, str | None]] = []
for _stage_key, _stage_def in BOOTSTRAP_STAGES.items():
    if _stage_key == "planning":
        BOOTSTRAP_NODES.extend(list(_stage_def["nodes"]))
        BOOTSTRAP_NODES.append(HUMAN_NODE)
    else:
        BOOTSTRAP_NODES.extend(list(_stage_def["nodes"]))

# Node key → stage lookup
NODE_STAGE: dict[str, str] = {}
for stage_key, stage_def in BOOTSTRAP_STAGES.items():
    for node_key, *_ in stage_def["nodes"]:
        NODE_STAGE[node_key] = stage_key
NODE_STAGE["human_confirm_title"] = "human"

# ── Budget defaults (CNY) ───────────────────────────────────────────────────

# Default budget per chapter (all 5 writing nodes combined)
DEFAULT_CHAPTER_BUDGET_CNY = 0.50
MIN_CHAPTER_CHARS = 1500

# Per-node budget allocation (planning ≈ blueprint < writing < finalization)
NODE_BUDGET_MULTIPLIERS: dict[str, float] = {
    # Planning: cheaper, broad strokes
    "plan_idea": 0.5, "plan_market_fit": 0.5, "plan_story_pattern": 0.5,
    "plan_core_gameplay": 0.5, "plan_world_architecture": 0.8,
    "plan_character_system": 0.8, "plan_conflict_map": 0.8,
    # Blueprint: structured output
    "blueprint_volume_plan": 0.5, "blueprint_chapter_outline": 1.0,
    "blueprint_scene_beat": 0.8,
    # Writing: heavy generation
    "write_chapter_draft": 2.0, "write_self_review": 0.5,
    "write_polish": 0.5, "write_length_check": 0.3,
    "write_fact_reconcile": 0.5,
    # Finalization: thorough checking
    "final_consistency_check": 0.5, "final_continuity_audit": 0.5,
    "final_humanize": 1.0,
}

# ── Chapter idempotency key format ──────────────────────────────────────────

def _chapter_idempotency_key(novel_id: str, chapter_seq: int) -> str:
    return f"novel:{novel_id}:chapter:{chapter_seq}:bootstrap:v2"


_NON_NARRATIVE_MARKERS = (
    "本章将深入探讨",
    "在润色过程中",
    "首先需要明确章节",
    "目标读者",
    "逻辑结构",
    "提升阅读流畅性",
    "删除冗余表述",
    "替换模糊词汇",
    "去AI味是",
    "具体改动可以",
    "输出JSON",
    "处理后的完整正文",
    "本文将",
)


def _chapter_paragraphs_from_text(text: str) -> list[str]:
    return [line.strip() for line in str(text or "").replace("\r\n", "\n").split("\n") if line.strip()]


def _chapter_doc_from_paragraphs(paragraphs: list[str]) -> dict[str, Any]:
    return {"type": "doc", "content": [{"type": "paragraph", "text": p} for p in paragraphs]}


def _looks_like_non_narrative_text(text: str) -> bool:
    compact = str(text or "")
    hits = sum(1 for marker in _NON_NARRATIVE_MARKERS if marker in compact)
    return hits >= 2


def _assert_story_revision_quality(
    *,
    task_type: str,
    before_text: str,
    after_paragraphs: list[str],
    min_ratio: float = 0.65,
) -> None:
    after_text = "\n".join(after_paragraphs).strip()
    before_chars = len(str(before_text or "").strip())
    after_chars = len(after_text)
    before_paragraph_count = len(_chapter_paragraphs_from_text(before_text))
    if not after_text:
        raise OutputValidationError(f"{task_type} returned empty chapter text")
    if _looks_like_non_narrative_text(after_text):
        raise OutputValidationError(f"{task_type} returned non-narrative instructional text")
    if before_chars >= 200 and after_chars < int(before_chars * min_ratio):
        raise OutputValidationError(
            f"{task_type} shortened chapter too much: {after_chars}/{before_chars} chars"
        )
    if before_paragraph_count >= 6 and len(after_paragraphs) < before_paragraph_count - 2:
        raise OutputValidationError(
            f"{task_type} dropped too many paragraphs: {len(after_paragraphs)}/{before_paragraph_count}"
        )


def _assert_min_chapter_length(task_type: str, text: str) -> None:
    from app.services.text_metrics import count_content_chars
    chars = count_content_chars(text)
    if chars < MIN_CHAPTER_CHARS:
        raise OutputValidationError(f"{task_type} chapter too short: {chars}/{MIN_CHAPTER_CHARS} chars")


def _draft_length_feedback(output: dict) -> str:
    """Return a concrete retry instruction when a draft misses the hard length gate."""
    chapter = output.get("chapter") if isinstance(output, dict) else None
    body = chapter.get("body", []) if isinstance(chapter, dict) else []
    text = "\n".join(
        part if isinstance(part, str) else str(part.get("text", ""))
        for part in body if isinstance(part, (str, dict))
    )
    try:
        _assert_min_chapter_length("write_chapter_draft", text)
    except OutputValidationError as exc:
        return str(exc)
    return ""


def _quality_evidence_payload(output: dict, self_review: dict | None = None) -> dict:
    """Build the durable seven-dimension provenance stored on a chapter."""
    score_by_status = {"pass": 90, "warning": 65, "fail": 35}
    checks = output.get("checks") if isinstance(output.get("checks"), dict) else {}
    dimensions = {
        name: score_by_status.get(str(check.get("status", "")), 0)
        for name, check in checks.items() if isinstance(check, dict)
    }
    self_review = self_review if isinstance(self_review, dict) else {}
    score = self_review.get("self_score")
    if score is None and dimensions:
        score = sum(dimensions.values()) / len(dimensions)
    issues = [str(item) for item in self_review.get("weaknesses", []) if str(item).strip()]
    return {
        "score": float(score or 0),
        "dimensions": dimensions,
        "issues": issues,
        "source": "write_self_review+final_consistency_check",
    }


def _chapter_outline_for_seq(context: dict, chapter_seq: int) -> dict:
    """Select exactly one outline so prose never consumes later chapters."""
    outlines = context.get("chapter_outlines") or []
    if not isinstance(outlines, list):
        return {}
    for outline in outlines:
        if not isinstance(outline, dict):
            continue
        try:
            if int(outline.get("seq") or 0) == chapter_seq:
                return outline
        except (TypeError, ValueError):
            continue
    if 0 < chapter_seq <= len(outlines) and isinstance(outlines[chapter_seq - 1], dict):
        return outlines[chapter_seq - 1]
    return {}
# ── Isolated request context decorator ──────────────────────────────────────

def _isolated_request_context(fn):
    """Prevent BYOK credentials leaking between tasks in a reused worker process."""
    @wraps(fn)
    def wrapped(*args, **kwargs):
        _request_api_key.set(None)
        _request_api_base_url.set(None)
        _request_model.set(None)
        try:
            return fn(*args, **kwargs)
        finally:
            _request_api_key.set(None)
            _request_api_base_url.set(None)
            _request_model.set(None)
    return wrapped
# ═══════════════════════════════════════════════════════════════════════════
# Event ledger helpers
# ═══════════════════════════════════════════════════════════════════════════

def _record_bootstrap_event(run_id: str, event_type: str, node_key: str = "",
                            payload: dict | None = None) -> dict:
    """Record a bootstrap lifecycle event in the immutable audit ledger."""
    try:
        from app.services.fusion_deep_workflow import record_event
        return record_event(run_id, event_type, node_key=node_key,
                            payload=payload or {})
    except Exception:
        # Event ledger is BestEffort — never block workflow on audit failure
        return {"status": "ledger_unavailable"}
# ═══════════════════════════════════════════════════════════════════════════
# Context window management (write-before-search + write-after-reconcile)
# ═══════════════════════════════════════════════════════════════════════════

def _write_before_search(novel_id: str, chapter_seq: int, window_size: int = 100) -> dict:
    """Retrieve recent chapters as context before writing a new one.

    Implements a rolling memory window of up to `window_size` chapters,
    returning summaries + entity states to ground the generation.

    Returns:
        dict with keys: recent_chapters, entity_summary, world_state, total_retrieved
    """
    db = connect()
    start_seq = max(1, chapter_seq - window_size)
    recent = db.execute(
        """SELECT meta->>'seq' AS seq, title,
                  meta->>'chapter_summary' AS summary,
                  meta->>'word_count' AS word_count,
                  status
           FROM contents
           WHERE parent_id = %s AND type = 'chapter'
             AND (meta->>'seq')::int BETWEEN %s AND %s
           ORDER BY (meta->>'seq')::int""",
        (novel_id, start_seq, chapter_seq - 1),
    ).fetchall()
    recent_chapters = []
    for ch in recent:
        recent_chapters.append({
            "seq": int(ch.get("seq") or 0),
            "title": ch.get("title", ""),
            "summary": (ch.get("summary") or "")[:300],
            "word_count": int(ch.get("word_count") or 0),
        })

    # Entity snapshot for continuity
    entity_rows = db.execute(
        """SELECT entity_type, entity_name, location, relationships, possessions
           FROM entity_states es
           JOIN contents c ON c.id = es.chapter_id
           WHERE c.parent_id = %s""",
        (novel_id,),
    ).fetchall()
    entities_by_type: dict[str, list[dict]] = {}
    for er in entity_rows:
        etype = er.get("entity_type", "unknown")
        entities_by_type.setdefault(etype, []).append({
            "name": er.get("entity_name", ""),
            "location": er.get("location", ""),
        })

    # Character states
    char_rows = db.execute(
        "SELECT title, meta FROM contents WHERE parent_id = %s AND type = 'character' AND is_deleted = FALSE",
        (novel_id,),
    ).fetchall()

    db.close()
    return {
        "recent_chapters": recent_chapters,
        "entity_summary": {k: v[-5:] for k, v in entities_by_type.items()},
        "character_count": len(char_rows),
        "total_retrieved": len(recent),
    }
def _write_after_reconcile(novel_id: str, chapter_id: str, chapter_text: str) -> dict:
    """Post-write reconciliation: detect new facts and compare with existing state.

    Extracts signals from the freshly written chapter and cross-references
    them against the entity_states table to flag potential inconsistencies.
    """
    db = connect()
    # Collect all entity names for cross-reference
    entity_names = db.execute(
        """SELECT DISTINCT entity_name FROM entity_states es
           JOIN contents c ON c.id = es.chapter_id
           WHERE c.parent_id = %s""",
        (novel_id,),
    ).fetchall()
    db.close()

    known_names = {r.get("entity_name", "") for r in entity_names if r.get("entity_name")}
    mentioned = sorted(n for n in known_names if n and n in chapter_text)
    new_entities = sorted(
        n for n in _extract_names_from_text(chapter_text)
        if n not in known_names and len(n) >= 2
    )

    return {
        "known_entities_mentioned": len(mentioned),
        "mentioned": mentioned[:20],
        "new_entities_detected": len(new_entities),
        "new_entities": new_entities[:10],
        "reconciliation_needed": len(new_entities) > 0,
    }
def _extract_names_from_text(text: str) -> set[str]:
    """Simple Chinese name extraction heuristic for reconciliation."""
    import re
    # Two-character Chinese given names and common surname+name patterns
    names: set[str] = set()
    # Match 2-3 character Chinese words between sentence boundaries
    matches = re.findall(r'[\u4e00-\u9fff]{2,3}', text)
    # Filter out common non-name words
    stop_words = {"一个", "可以", "没有", "自己", "他们", "我们", "什么", "知道",
                  "已经", "这个", "那个", "就是", "不是", "如果", "因为", "所以",
                  "但是", "不过", "而且", "然后", "开始", "已经", "现在", "突然",
                  "感觉", "发现", "看到", "想到", "说道", "出来", "起来", "下来",
                  "这里", "那里", "忽然", "一股", "一道", "一声", "一阵", "无数"}
    for m in matches:
        if m not in stop_words:
            names.add(m)
    return names
def _track_budget(run_id, node_key, cost_cny):
    """Synchronize workflow budget with the real ai_calls ledger.

    The gateway already records every real provider call and increments
    budgets.spent_cny. This helper exists for workflow checkpoints, so it must
    report real numbers instead of a 0/0 placeholder. To avoid double-counting
    legacy/worker paths, we recompute the workflow project's bootstrap spend
    from ai_calls and sync the budget row to that value.
    """
    db = connect()
    try:
        run = db.execute("SELECT project_id FROM workflow_runs WHERE id=%s", (run_id,)).fetchone()
        if not run:
            return {"status": "error", "message": "workflow run not found"}
        project_id = run["project_id"]
        spent_row = db.execute(
            "SELECT COALESCE(SUM(cost_cny),0) AS spent FROM ai_calls WHERE project_id=%s AND status='succeeded'",
            (project_id,),
        ).fetchone()
        spent = float(spent_row["spent"] or 0)
        budget = db.execute(
            "SELECT * FROM budgets WHERE project_id=%s AND scope='bootstrap'",
            (project_id,),
        ).fetchone()
        if not budget:
            from app.config import settings
            db.execute(
                "INSERT INTO budgets (id, project_id, scope, limit_cny, spent_cny) VALUES (%s,%s,'bootstrap',%s,%s)",
                (new_id("bdg"), project_id, settings.default_monthly_budget_cny, spent),
            )
            limit = float(settings.default_monthly_budget_cny)
        else:
            limit = float(budget["limit_cny"])
            db.execute(
                "UPDATE budgets SET spent_cny=%s, updated_at=now() WHERE id=%s",
                (spent, budget["id"]),
            )
        db.commit()
        status = "exceeded" if limit and spent > limit else "ok"
        return {"status": status, "project_id": str(project_id), "scope": "bootstrap",
                "node_key": node_key, "last_cost_cny": float(cost_cny or 0),
                "spent": round(spent, 6), "limit": round(limit, 6)}
    finally:
        db.close()

def _create_checkpoint(run_id: str, node_key: str, context: dict) -> str:
    """Save a checkpoint snapshot for later resumption."""
    db = connect()
    ckpt_id = new_id()
    db.execute(
        """INSERT INTO audit_logs (id, entity_type, entity_id, action, details, created_at)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (ckpt_id, "workflow_run", run_id, "checkpoint.created",
         encode({"node": node_key, "context_snapshot": context,
                 "timestamp": datetime.now(timezone.utc).isoformat()}),
         datetime.now(timezone.utc)),
    )
    db.commit()
    db.close()
    _record_bootstrap_event(run_id, "checkpoint.created", node_key=node_key,
                            payload={"checkpoint_id": ckpt_id})
    return ckpt_id
def _resume_from_checkpoint(run_id: str) -> str | None:
    """Find the latest checkpoint and return the node_key to resume from."""
    db = connect()
    ckpt = db.execute(
        """SELECT details FROM audit_logs
           WHERE entity_type = 'workflow_run' AND entity_id = %s
             AND action = 'checkpoint.created'
           ORDER BY created_at DESC LIMIT 1""",
        (run_id,),
    ).fetchone()
    db.close()
    if not ckpt:
        return None
    details = ckpt.get("details", {})
    if isinstance(details, dict):
        return details.get("node")
    return None


def _attach_user_context(novel_id: str) -> None:
    """Best-effort: attribute a worker process's AI calls to the novel owner.

    Worker tasks run outside the HTTP request lifecycle, so the request-scoped
    ``_request_user_id`` ContextVar is unset. Without this, ``ai_calls.user_id``
    stays NULL for generated chapters and the user's token bill undercounts. We
    resolve the owner from the novel and set the ContextVar for the task's run.
    """
    try:
        from app.gateway import _request_user_id
        db = connect()
        try:
            owner = db.execute(
                "SELECT owner_id FROM contents WHERE id = %s", (novel_id,)
            ).fetchone()
        finally:
            db.close()
        if owner and owner.get("owner_id"):
            _request_user_id.set(owner["owner_id"])
    except Exception:
        pass
# ═══════════════════════════════════════════════════════════════════════════
# Core bootstrap execution
# ═══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
@_isolated_request_context
def execute_bootstrap(self, run_id: str, start_key: str = "plan_idea",
                       api_key: str = "", api_url: str = "", model: str = "") -> dict:
    """Execute the 4-stage bootstrap workflow with context management, budget
    tracking, event ledger, and checkpoint support.

    Stages:
      1. Planning (7 agent nodes) → human_confirm_title
      2. Blueprint (3 agent nodes)
      3. Writing (5 agent nodes per chapter, initially ch 1)
      4. Finalization (3 agent nodes)

    The workflow can resume from any failed node via checkpoint.
    """
    # Set context vars for this worker process
    if api_key:
        _request_api_key.set(api_key)
    if api_url:
        _request_api_base_url.set(api_url)
    if model:
        _request_model.set(model)

    # Attribute AI calls to the novel owner for per-user metering/billing.
    _run_lookup = connect()
    _run_row = _run_lookup.execute("SELECT novel_id FROM workflow_runs WHERE id = %s", (run_id,)).fetchone()
    _run_lookup.close()
    if _run_row and _run_row.get("novel_id"):
        _attach_user_context(_run_row["novel_id"])

    # Determine start index in flattened node list
    try:
        start_index = next(i for i, node in enumerate(BOOTSTRAP_NODES) if node[0] == start_key)
    except StopIteration:
        # Try checkpoint resumption
        resume_key = _resume_from_checkpoint(run_id)
        if resume_key:
            try:
                start_index = next(i for i, node in enumerate(BOOTSTRAP_NODES) if node[0] == resume_key)
            except StopIteration:
                start_index = 0
        else:
            start_index = 0

    # Verify run exists
    conn = connect()
    run = conn.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,)).fetchone()
    if run is None:
        conn.close()
        return {"status": "error", "detail": "run not found"}
    conn.close()

    _record_bootstrap_event(run_id, "run.started", node_key=start_key)

    # ── Stage-aware iteration ───────────────────────────────────────────
    current_stage: str | None = None
    chapter_seq = 1  # Bootstrap always generates chapter 1

    for node_key, kind, agent, title, task_type in BOOTSTRAP_NODES[start_index:]:
        stage = NODE_STAGE.get(node_key, "unknown")

        # Stage transition: create checkpoint and log
        if stage != current_stage and stage != "human":
            current_stage = stage
            stage_label = BOOTSTRAP_STAGES.get(stage, {}).get("label", stage)
            conn = connect()
            run = conn.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,)).fetchone()
            context = run["context"] if run and isinstance(run["context"], dict) else {}
            conn.close()
            _create_checkpoint(run_id, node_key, context)
            _record_bootstrap_event(
                run_id, "checkpoint.created", node_key=node_key,
                payload={"stage": stage, "label": stage_label},
            )

        # ── DB state check ──────────────────────────────────────────────
        conn = connect()
        node = conn.execute(
            "SELECT * FROM run_nodes WHERE run_id = %s AND node_key = %s",
            (run_id, node_key),
        ).fetchone()
        run = conn.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,)).fetchone()
        if node is None or run is None:
            conn.close()
            return {"status": "error", "detail": "run or node not found"}

        # Skip already-completed nodes
        if node["status"] == "succeeded":
            conn.close()
            _record_bootstrap_event(run_id, "node.completed", node_key=node_key,
                                    payload={"skipped": "already_succeeded"})
            continue

        # ── Human node ──────────────────────────────────────────────────
        if kind == "human":
            run_context = run["context"] if isinstance(run["context"], dict) else {}
            if (run_context.get("auto_confirm_title") or run_context.get("title_locked")) and node_key == "human_confirm_title":
                title_candidates = run_context.get("title_candidates") or []
                selected_title = (
                    str(run_context.get("selected_title") or "").strip()
                    if run_context.get("title_locked")
                    else (str(title_candidates[0]).strip() if title_candidates else "")
                )
                if not selected_title:
                    conn.execute(
                        """UPDATE run_nodes
                           SET status = 'failed',
                               started_at = COALESCE(started_at, now()),
                               finished_at = now(),
                               error = %s
                           WHERE run_id = %s AND node_key = %s""",
                        ("missing title candidates for auto confirm", run_id, node_key),
                    )
                    conn.execute(
                        "UPDATE workflow_runs SET status = 'failed', current_node_key = %s, updated_at = now() WHERE id = %s",
                        (node_key, run_id),
                    )
                    conn.commit()
                    conn.close()
                    _record_bootstrap_event(
                        run_id,
                        "human.rejected",
                        node_key=node_key,
                        payload={"reason": "missing_title_candidates"},
                    )
                    return {"status": "error", "detail": "missing title candidates for auto confirm"}
                run_context["selected_title"] = selected_title
                conn.execute(
                    """UPDATE contents
                       SET title = %s,
                           meta = jsonb_set(COALESCE(meta, '{}'::jsonb), '{selected_title}', to_jsonb(%s::text), true),
                           updated_at = now()
                       WHERE id = %s""",
                    (selected_title, selected_title, run["novel_id"]),
                )
                conn.execute(
                    """UPDATE run_nodes
                       SET status = 'succeeded',
                           started_at = COALESCE(started_at, now()),
                           finished_at = now(),
                           output = %s
                       WHERE run_id = %s AND node_key = %s""",
                    (encode({"selected_title": selected_title, "source": "locked_title" if run_context.get("title_locked") else "auto_confirm"}), run_id, node_key),
                )
                conn.execute(
                    """UPDATE workflow_runs
                       SET status = 'pending',
                           current_node_key = 'blueprint_volume_plan',
                           context = %s,
                           updated_at = now()
                       WHERE id = %s""",
                    (encode(run_context), run_id),
                )
                conn.commit()
                conn.close()
                _record_bootstrap_event(
                    run_id,
                    "human.confirmed",
                    node_key=node_key,
                    payload={"selected_title": selected_title, "action": "auto_confirmed"},
                )
                continue
            conn.execute(
                "UPDATE run_nodes SET status = 'waiting_human', started_at = COALESCE(started_at, now()) WHERE run_id = %s AND node_key = %s",
                (run_id, node_key),
            )
            conn.execute(
                "UPDATE workflow_runs SET status = 'waiting_human', current_node_key = %s, updated_at = now() WHERE id = %s",
                (node_key, run_id),
            )
            conn.commit()
            conn.close()
            celery_app.backend.set(f"run:{run_id}:human", node_key)
            _record_bootstrap_event(run_id, "human.confirmed", node_key=node_key,
                                    payload={"action": "waiting"})
            return {"status": "waiting_human", "node_key": node_key}

        # ── Claim node (with idempotency via status guard) ─────────────
        claim = conn.execute(
            """UPDATE run_nodes SET status='running', attempt=attempt+1, started_at=now(), error=NULL
               WHERE run_id=%s AND node_key=%s
                 AND status IN ('pending','failed','pending_budget')
               RETURNING id""", (run_id, node_key),
        )
        if hasattr(claim, "rowcount") and claim.rowcount != 1:
            conn.close()
            return {"status": "already_claimed", "node_key": node_key}
        conn.execute(
            "UPDATE workflow_runs SET status = 'running', current_node_key = %s, updated_at = now() WHERE id = %s",
            (node_key, run_id),
        )
        conn.commit()
        conn.close()

        _record_bootstrap_event(run_id, "node.started", node_key=node_key,
                                payload={"stage": stage, "agent": agent})

        time.sleep(0.3)

        # ── Build node execution context ───────────────────────────────
        run_context = run["context"] if isinstance(run["context"], dict) else {}
        project_id = run["project_id"]
        novel_id = run["novel_id"]

        # Stage-aware context enrichment
        if stage == "blueprint":
            # Blueprint needs planning outputs as inputs
            run_context = _enrich_blueprint_context(run_context, novel_id)
        elif stage == "writing":
            # Writing needs chapter context window
            context_window = _write_before_search(novel_id, chapter_seq, window_size=100)
            run_context["_context_window"] = context_window
            run_context["_chapter_seq"] = chapter_seq
            run_context["_chapter_outline"] = _chapter_outline_for_seq(run_context, chapter_seq)
            # Chapter idempotency: check if chapter already exists
            idem_key = _chapter_idempotency_key(novel_id, chapter_seq)
            conn = connect()
            existing_ch = conn.execute(
                """SELECT id, title, status, meta FROM contents
                   WHERE parent_id = %s AND type = 'chapter'
                     AND generation_key = %s AND is_deleted = FALSE""",
                (novel_id, idem_key),
            ).fetchone()
            conn.close()
            if existing_ch and node_key == "write_chapter_draft":
                run_context["_existing_chapter"] = {
                    "id": existing_ch["id"],
                    "title": existing_ch["title"],
                    "status": existing_ch["status"],
                }
        elif stage == "finalization":
            # Finalization needs full chapter text + all prior context
            run_context = _enrich_finalization_context(run_context, novel_id)

        # ── Execute AI call ─────────────────────────────────────────────
        # Idempotent within one claimed node attempt, but a deliberate retry
        # must obtain a fresh provider result instead of replaying the output
        # that caused the previous attempt to fail (or that depended on stale
        # upstream planning context).
        node_attempt = int(node.get("attempt") or 0) + 1
        client_mutation_id = f"bootstrap:{run_id}:{node_key}:attempt-v1:{node_attempt}"

        try:
            if task_type == "plan_idea":
                # A planning model is not allowed to grade its own fidelity.
                # Run an independent, recorded AI audit against the raw user
                # request and feed any concrete defects into a fresh sample.
                # The node cannot advance to title selection until the audit has
                # zero contradictions and omissions.
                fidelity_feedback: list[str] = []
                output = {}
                fidelity_cycle = int(node.get("attempt") or 0) + 1
                for fidelity_attempt in range(1, 4):
                    plan_variables = {
                        **run_context,
                        "fidelity_feedback": "；".join(fidelity_feedback),
                    }
                    output = complete(
                        run_id=run_id,
                        node_key=node_key,
                        project_id=project_id,
                        task_type=task_type,
                        prompt_name="bootstrap.plan_idea",
                        variables=plan_variables,
                        client_mutation_id=(
                            f"bootstrap:{run_id}:{node_key}:fidelity-v2:cycle:{fidelity_cycle}:plan:{fidelity_attempt}"
                        ),
                    )
                    output = validate_task_output(task_type, output)
                    audit = complete(
                        run_id=run_id,
                        node_key=node_key,
                        project_id=project_id,
                        task_type="audit_plan_fidelity",
                        prompt_name="bootstrap.audit_plan_fidelity",
                        variables={
                            "idea": run_context.get("idea", ""),
                            "plan_output": json.dumps(output, ensure_ascii=False),
                        },
                        client_mutation_id=(
                            f"bootstrap:{run_id}:{node_key}:fidelity-v2:cycle:{fidelity_cycle}:audit:{fidelity_attempt}"
                        ),
                    )
                    audit = validate_task_output("audit_plan_fidelity", audit)
                    contradictions = [str(item).strip() for item in audit.get("contradictions", []) if str(item).strip()]
                    omissions = [str(item).strip() for item in audit.get("omissions", []) if str(item).strip()]
                    passed = (
                        audit.get("passed") is True
                        and float(audit.get("score") or 0) == 100
                        and not contradictions
                        and not omissions
                    )
                    if passed:
                        output["plan_fidelity_audit"] = audit
                        break
                    fidelity_feedback = contradictions + omissions
                else:
                    raise OutputValidationError(
                        "plan fidelity audit rejected output after 3 real revisions: "
                        + "；".join(fidelity_feedback[:8])
                    )
            else:
                length_feedback = ""
                quality_attempts = 3 if task_type == "write_chapter_draft" else 1
                for quality_attempt in range(1, quality_attempts + 1):
                    variables = {**run_context, "length_retry_feedback": length_feedback}
                    output = complete(
                        run_id=run_id,
                        node_key=node_key,
                        project_id=project_id,
                        task_type=task_type or "",
                        prompt_name=f"bootstrap.{task_type}" if task_type else "",
                        variables=variables,
                        client_mutation_id=(
                            f"{client_mutation_id}:quality:{quality_attempt}"
                            if quality_attempts > 1 else client_mutation_id
                        ),
                    )
                    output = validate_task_output(task_type or "", output)
                    if task_type != "write_chapter_draft":
                        break
                    length_feedback = _draft_length_feedback(output)
                    if not length_feedback:
                        break
                else:
                    raise OutputValidationError(
                        f"write_chapter_draft failed length gate after {quality_attempts} real generations: "
                        f"{length_feedback}"
                    )
        except BudgetExceeded:
            _mark_node(run_id, node_key, "pending_budget", "budget exceeded")
            _record_bootstrap_event(run_id, "node.failed", node_key=node_key,
                                    payload={"reason": "budget_exceeded"})
            return {"status": "pending_budget", "node_key": node_key}
        except OutputValidationError as exc:
            _mark_node(run_id, node_key, "failed", str(exc))
            _record_bootstrap_event(run_id, "node.failed", node_key=node_key,
                                    payload={"reason": "invalid_output"})
            return {"status": "invalid_output", "node_key": node_key}
        except ProviderError as exc:
            # Provider failures are retryable through Celery (max_retries=3).
            # The gateway already exhausted its internal backoff before
            # re-raising, so we let the whole run retry rather than failing it
            # silently. Once Celery exhausts its retries this becomes terminal.
            _mark_node(run_id, node_key, "pending_provider", f"provider error: {exc}"[:500])
            _record_bootstrap_event(run_id, "node.retrying", node_key=node_key,
                                    payload={"reason": "provider_error", "detail": str(exc)[:200]})
            raise self.retry(exc=exc, countdown=5)
        except Exception as exc:
            _mark_node(run_id, node_key, "failed", str(exc))
            _record_bootstrap_event(run_id, "node.failed", node_key=node_key,
                                    payload={"error": str(exc)[:200]})
            raise self.retry(exc=exc, countdown=5)

        # ── Persist output + track budget ──────────────────────────────
        budget_info = _estimate_node_cost(run_id, node_key, output)
        _track_budget(run_id, node_key, budget_info.get("cost_cny", 0))

        try:
            _persist_output(run_id, node_key, task_type or "", output, novel_id, project_id)
        except OutputValidationError as exc:
            _mark_node(run_id, node_key, "failed", str(exc))
            _record_bootstrap_event(run_id, "node.failed", node_key=node_key,
                                    payload={"reason": "invalid_persisted_output", "detail": str(exc)[:200]})
            return {"status": "invalid_output", "node_key": node_key}

        _record_bootstrap_event(run_id, "node.completed", node_key=node_key,
                                payload={"budget": budget_info})

    # ── Workflow complete ──────────────────────────────────────────────────
    conn = connect()
    completed_run = conn.execute("SELECT * FROM workflow_runs WHERE id=%s", (run_id,)).fetchone()
    completed_context = completed_run["context"] if completed_run and isinstance(completed_run["context"], dict) else {}
    chapter_id = completed_context.get("chapter_id")
    chapter = conn.execute("SELECT status FROM contents WHERE id=%s", (chapter_id,)).fetchone() if chapter_id else None
    needs_review = bool(chapter and chapter["status"] == "needs_rewrite")
    final_status = "needs_review" if needs_review else "succeeded"
    novel_status = "needs_review" if needs_review else "draft"
    topic_status = "needs_review" if needs_review else "generated"
    conn.execute(
        """UPDATE workflow_runs SET status=%s, current_node_key=NULL, finished_at=now(), updated_at=now()
           WHERE id=%s""", (final_status, run_id),
    )
    if completed_run and completed_run.get("novel_id"):
        conn.execute("UPDATE contents SET status=%s,updated_at=now() WHERE id=%s",
                     (novel_status, completed_run["novel_id"]))
        conn.execute("UPDATE topic_candidates SET status=%s WHERE novel_id=%s",
                     (topic_status, completed_run["novel_id"]))
    conn.commit()
    conn.close()
    celery_app.backend.set(f"run:{run_id}:status", final_status)
    _record_bootstrap_event(run_id, "run.completed", payload={"status": final_status})
    return {"status": final_status}


@celery_app.task(name="app.core.billing.reset_monthly_usage")
def monthly_usage_reset() -> dict[str, Any]:
    """Celery wrapper for the monthly usage reset (P1-T2).

    The heavy lifting lives in ``app.core.billing.reset_monthly_usage`` so it
    stays testable without a Celery runtime. Registered under the canonical
    name so the beat schedule can reference ``app.core.billing.reset_monthly_usage``.
    """
    from app.core.billing import reset_monthly_usage
    return reset_monthly_usage()
# ═══════════════════════════════════════════════════════════════════════════
# Context enrichment helpers
# ═══════════════════════════════════════════════════════════════════════════

def _enrich_blueprint_context(context: dict, novel_id: str) -> dict:
    """Enrich context for blueprint stage with character/worldview/conflict data."""
    db = connect()
    # Fetch all knowledge items produced in planning stage
    knowledge_rows = db.execute(
        """SELECT kind, title, body, meta FROM knowledge_items
           WHERE content_id = %s AND is_deleted = FALSE
           ORDER BY kind""",
        (novel_id,),
    ).fetchall()
    db.close()

    enriched = dict(context)
    worldview = ""
    characters_text = ""
    for kr in knowledge_rows:
        kind = kr.get("kind", "")
        body = kr.get("body", "")
        if kind == "worldview" and body:
            worldview = body
        elif kind == "character" and body:
            characters_text += f"\n- {kr.get('title', '')}: {body}"

    if worldview:
        enriched["_worldview_text"] = worldview[:3000]
    if characters_text:
        enriched["_characters_text"] = characters_text[:3000]
    return enriched
def _enrich_finalization_context(context: dict, novel_id: str) -> dict:
    """Enrich context for finalization with full chapter body + entity states."""
    enriched = dict(context)
    chapter_seq = int(context.get("_chapter_seq") or 1)
    enriched["_chapter_outline"] = _chapter_outline_for_seq(context, chapter_seq)
    # Get chapter body text
    chapter_id = context.get("chapter_id", "")
    if chapter_id:
        db = connect()
        ch = db.execute("SELECT body, meta FROM contents WHERE id = %s", (chapter_id,)).fetchone()
        db.close()
        if ch:
            body = ch.get("body", "")
            enriched["_chapter_body"] = extract_body_text(body)[:12000]

    # Get entity snapshot
    reconc_res = _write_after_reconcile(novel_id, chapter_id or "",
                                        enriched.get("_chapter_body", ""))
    enriched["_reconciliation"] = reconc_res
    return enriched
# ═══════════════════════════════════════════════════════════════════════════
# Budget estimation
# ═══════════════════════════════════════════════════════════════════════════

def _estimate_node_cost(run_id: str, node_key: str, output: dict) -> dict:
    """Estimate the cost of a single node execution.

    Queries the ai_calls table for the most recent call matching this
    run_id + node_key to get actual token usage.
    """
    try:
        db = connect()
        ai_call = db.execute(
            """SELECT prompt_tokens, completion_tokens, cost_cny
               FROM ai_calls
               WHERE client_mutation_id LIKE %s
               ORDER BY created_at DESC LIMIT 1""",
            (f"bootstrap:{run_id}:{node_key}%",),
        ).fetchone()
        db.close()
        if ai_call:
            return {
                "cost_cny": float(ai_call.get("cost_cny") or 0),
                "prompt_tokens": int(ai_call.get("prompt_tokens") or 0),
                "completion_tokens": int(ai_call.get("completion_tokens") or 0),
            }
    except Exception:
        pass
    # Fallback: multiplier-based estimate
    multiplier = NODE_BUDGET_MULTIPLIERS.get(node_key, 1.0)
    return {"cost_cny": round(multiplier * 0.02, 6), "prompt_tokens": 0,
            "completion_tokens": 0, "estimated": True}
# ═══════════════════════════════════════════════════════════════════════════
# Run creation + dispatch
# ═══════════════════════════════════════════════════════════════════════════

def create_run(project_id: str, novel_id: str,
               api_key: str = "", api_url: str = "", model: str = "",
               selected_title: str = "", idempotency_key: str | None = None,
               auto_confirm_title: bool = False) -> str:
    """Create a workflow run through the complete planning-to-audit pipeline.

    A preselected title locks only the title gate. It never bypasses source
    decomposition, creative-bible planning, or quality controls.
    """
    db = connect()
    if idempotency_key:
        existing = db.execute(
            "SELECT * FROM workflow_runs WHERE project_id=%s AND idempotency_key=%s",
            (project_id, idempotency_key),
        ).fetchone()
        if existing:
            db.close()
            if existing["status"] == "dispatch_failed" or (
                existing["status"] == "pending" and not existing.get("last_dispatched_at")
            ):
                dispatch_bootstrap_run(existing["id"], existing.get("current_node_key") or "plan_idea",
                                       api_key, api_url, model)
            return existing["id"]

    novel = db.execute("SELECT * FROM contents WHERE id = %s", (novel_id,)).fetchone()
    if novel is None:
        db.close()
        raise ValueError("novel not found")

    meta = novel["meta"] if isinstance(novel["meta"], dict) else {}
    context = {"novel_id": novel_id, "idea": meta.get("idea", ""), "suggested_title": "", **meta}
    if selected_title:
        context["suggested_title"] = selected_title
    if auto_confirm_title:
        context["auto_confirm_title"] = True

    run_id = new_id()
    db.execute(
        "INSERT INTO workflow_runs "
        "(id, project_id, novel_id, workflow_key, status, current_node_key, context, idempotency_key) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (run_id, project_id, novel_id, "bootstrap", "pending", "plan_idea", encode(context), idempotency_key),
    )

    # Seed all nodes from BOOTSTRAP_NODES
    for node_key, kind, agent, title, _task_type in BOOTSTRAP_NODES:
        db.execute(
            "INSERT INTO run_nodes (id, run_id, node_key, kind, agent, title) VALUES (%s, %s, %s, %s, %s, %s)",
            (new_id(), run_id, node_key, kind, agent, title),
        )

    start_key = "plan_idea"

    db.commit()
    db.close()

    # Record ledger event
    _record_bootstrap_event(run_id, "run.created", node_key=start_key,
                            payload={
                                "selected_title": selected_title if selected_title else None,
                                "auto_confirm_title": bool(auto_confirm_title),
                            })

    dispatch_bootstrap_run(run_id, start_key, api_key, api_url, model)
    return run_id
def dispatch_bootstrap_run(run_id: str, start_key: str, api_key: str = "",
                           api_url: str = "", model: str = "") -> None:
    """Dispatch or redrive one committed run, persisting broker failures."""
    try:
        execute_bootstrap.delay(run_id, start_key, api_key, api_url, model)
    except Exception as exc:
        db = connect()
        db.execute("""UPDATE workflow_runs SET status='dispatch_failed', dispatch_attempts=dispatch_attempts+1,
                      dispatch_error=%s, updated_at=now() WHERE id=%s""", (str(exc), run_id))
        db.commit(); db.close()
        raise
    db = connect()
    db.execute("""UPDATE workflow_runs SET status=CASE WHEN status='dispatch_failed' THEN 'pending' ELSE status END,
                  dispatch_attempts=dispatch_attempts+1, last_dispatched_at=now(), dispatch_error=NULL, updated_at=now()
                  WHERE id=%s""", (run_id,))
    db.commit(); db.close()
def confirm_human(run_id: str, selected_title: str,
                  api_key: str = "", api_url: str = "", model: str = "") -> None:
    """Confirm human node selection and continue workflow to blueprint stage."""
    db = connect()
    run = db.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,)).fetchone()
    if run is None:
        db.close()
        raise ValueError("run not found")
    context = run["context"] if isinstance(run["context"], dict) else {}
    context["selected_title"] = selected_title
    db.execute("UPDATE contents SET title = %s, updated_at = now() WHERE id = %s", (selected_title, run["novel_id"]))
    db.execute(
        "UPDATE run_nodes SET status = 'succeeded', output = %s, finished_at = now() WHERE run_id = %s AND node_key = %s",
        (encode({"selected_title": selected_title}), run_id, "human_confirm_title"),
    )
    db.execute(
        "UPDATE workflow_runs SET status = 'pending', current_node_key = %s, context = %s, updated_at = now() WHERE id = %s",
        ("blueprint_volume_plan", encode(context), run_id),
    )
    db.commit()
    db.close()

    _record_bootstrap_event(run_id, "human.confirmed", node_key="human_confirm_title",
                            payload={"selected_title": selected_title})
    execute_bootstrap.delay(run_id, "blueprint_volume_plan", api_key, api_url, model)
# ═══════════════════════════════════════════════════════════════════════════
# Node marking + output persistence
# ═══════════════════════════════════════════════════════════════════════════

def _mark_node(run_id: str, node_key: str, status: str, error: str) -> None:
    db = connect()
    db.execute(
        "UPDATE run_nodes SET status = %s, error = %s, finished_at = now() WHERE run_id = %s AND node_key = %s",
        (status, error, run_id, node_key),
    )
    db.execute(
        "UPDATE workflow_runs SET status = %s, current_node_key = %s, updated_at = now() WHERE id = %s",
        (status, node_key, run_id),
    )
    db.commit()
    db.close()
def _persist_output(run_id: str, node_key: str, task_type: str, output: dict,
                    novel_id: str = "", project_id: str = "") -> None:
    """Persist node output to DB, update context, handle knowledge items."""
    db = connect()
    knowledge_ids_to_reindex: list[str] = []

    run = db.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,)).fetchone()
    if run is None:
        db.close()
        return

    node = db.execute("SELECT * FROM run_nodes WHERE run_id=%s AND node_key=%s FOR UPDATE",
                      (run_id, node_key)).fetchone()
    if node and node["status"] == "succeeded":
        db.close()
        return

    context = run["context"] if isinstance(run["context"], dict) else {}
    context.update(output)
    _novel_id = novel_id or run["novel_id"]
    _project_id = project_id or run["project_id"]

    # ── Stage-aware output handling ─────────────────────────────────────
    stage = NODE_STAGE.get(node_key, "unknown")

    if task_type == "plan_idea":
        context["idea_expanded"] = output.get("idea_expanded", output.get("idea", ""))
        creative_bible = str(output.get("creative_bible") or "").strip()
        if creative_bible:
            meta_row = db.execute("SELECT meta FROM contents WHERE id = %s", (_novel_id,)).fetchone()
            if meta_row:
                m = meta_row["meta"] if isinstance(meta_row["meta"], dict) else {}
                m["creative_bible"] = creative_bible
                m["core_hook"] = output.get("core_hook", "")
                m["target_audience"] = output.get("target_audience", "")
                m["source_facts"] = output.get("source_facts", [])
                m["design_additions"] = output.get("design_additions", [])
                m["forbidden_changes"] = output.get("forbidden_changes", [])
                m["planning_module"] = "creative_bible_v2"
                db.execute("UPDATE contents SET meta = %s, updated_at = now() WHERE id = %s", (encode(m), _novel_id))
            knowledge_id = new_id()
            generation_key = f"run:{run_id}:node:{node_key}:creative-bible:v1"
            stored = db.execute(
                """INSERT INTO knowledge_items
                   (id, project_id, content_id, kind, title, body, meta, generation_key)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (content_id, generation_key) WHERE generation_key IS NOT NULL AND is_deleted=FALSE
                   DO UPDATE SET title=EXCLUDED.title, body=EXCLUDED.body, meta=EXCLUDED.meta, updated_at=now()
                   RETURNING id""",
                (
                    knowledge_id,
                    _project_id,
                    _novel_id,
                    "creative_bible",
                    "创作圣经",
                    creative_bible,
                    encode({"source_node": node_key, "core_hook": output.get("core_hook", "")}),
                    generation_key,
                ),
            ).fetchone()
            knowledge_ids_to_reindex.append(stored["id"] if stored else knowledge_id)
    elif task_type == "plan_market_fit":
        context["market_fit"] = output
    elif task_type == "plan_story_pattern":
        context["story_pattern"] = output
    elif task_type == "plan_core_gameplay":
        context["core_gameplay"] = output
    elif task_type == "plan_world_architecture":
        wv = output.get("worldview", output)
        if isinstance(wv, dict) and wv.get("name"):
            knowledge_id = new_id()
            generation_key = f"run:{run_id}:node:{node_key}:worldview:v2"
            stored = db.execute(
                """INSERT INTO knowledge_items
                   (id, project_id, content_id, kind, title, body, meta, generation_key)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (content_id, generation_key) WHERE generation_key IS NOT NULL AND is_deleted=FALSE
                   DO UPDATE SET title=EXCLUDED.title, body=EXCLUDED.body, meta=EXCLUDED.meta, updated_at=now()
                   RETURNING id""",
                (knowledge_id, _project_id, _novel_id, "worldview",
                 wv.get("name", ""), "\n".join(wv.get("rules", [])), encode(wv), generation_key),
            ).fetchone()
            knowledge_ids_to_reindex.append(stored["id"] if stored else knowledge_id)
        # Also update novel metadata
        meta_row = db.execute("SELECT meta FROM contents WHERE id = %s", (_novel_id,)).fetchone()
        if meta_row:
            m = meta_row["meta"] if isinstance(meta_row["meta"], dict) else {}
            m["worldview"] = wv
            db.execute("UPDATE contents SET meta = %s, updated_at = now() WHERE id = %s", (encode(m), _novel_id))
    elif task_type == "plan_character_system":
        characters = output.get("characters", [])
        for index, c in enumerate(characters):
            knowledge_id = new_id()
            generation_key = f"run:{run_id}:node:{node_key}:character:{index}:v2"
            stored = db.execute(
                """INSERT INTO knowledge_items
                   (id, project_id, content_id, kind, title, body, meta, generation_key)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (content_id, generation_key) WHERE generation_key IS NOT NULL AND is_deleted=FALSE
                   DO UPDATE SET title=EXCLUDED.title, body=EXCLUDED.body, meta=EXCLUDED.meta, updated_at=now()
                   RETURNING id""",
                (knowledge_id, _project_id, _novel_id, "character", c.get("name", ""),
                 c.get("arc", ""), encode(c), generation_key),
            ).fetchone()
            knowledge_ids_to_reindex.append(stored["id"] if stored else knowledge_id)
    elif task_type == "plan_conflict_map":
        context["conflict_map"] = output
    elif task_type == "blueprint_volume_plan":
        meta_row = db.execute("SELECT meta FROM contents WHERE id = %s", (_novel_id,)).fetchone()
        if meta_row:
            m = meta_row["meta"] if isinstance(meta_row["meta"], dict) else {}
            m["volume_plan"] = output.get("volumes", output.get("volume_plan", []))
            m["chapter_tree"] = output.get("chapter_tree", [])
            db.execute("UPDATE contents SET meta = %s, updated_at = now() WHERE id = %s", (encode(m), _novel_id))
    elif task_type == "blueprint_chapter_outline":
        meta_row = db.execute("SELECT meta FROM contents WHERE id = %s", (_novel_id,)).fetchone()
        if meta_row:
            m = meta_row["meta"] if isinstance(meta_row["meta"], dict) else {}
            m["chapter_outlines"] = output.get("chapter_outlines", output.get("outlines", []))
            db.execute("UPDATE contents SET meta = %s, updated_at = now() WHERE id = %s", (encode(m), _novel_id))
    elif task_type == "blueprint_scene_beat":
        context["scene_beat_sheet"] = output
    elif task_type == "write_chapter_draft":
        _persist_chapter_draft(db, run, node_key, output, context, _novel_id, _project_id, run_id,
                               knowledge_ids_to_reindex)
    elif task_type == "write_self_review":
        context["self_review"] = output
        cid = context.get("chapter_id", "")
        if cid:
            db.execute(
                "UPDATE contents SET meta = meta || %s, updated_at = now() WHERE id = %s",
                (encode({"self_review": output, "review_score": output.get("self_score")}), cid),
            )
    elif task_type == "write_polish":
        _persist_chapter_polish(db, node_key, output, context, run_id)
    elif task_type == "write_length_check":
        context["length_check"] = output
    elif task_type == "write_fact_reconcile":
        _persist_fact_reconcile(db, node_key, output, context, _novel_id, run_id)
    elif task_type in ("final_consistency_check", "final_continuity_audit", "final_humanize"):
        context[task_type] = output
        if task_type == "final_consistency_check":
            checks = output.get("checks") if isinstance(output.get("checks"), dict) else {}
            failed_checks = {
                name: check for name, check in checks.items()
                if not isinstance(check, dict)
                or check.get("status") != "pass"
                or bool(check.get("issues"))
            }
            if output.get("overall_status") != "pass" or failed_checks:
                cid = context.get("chapter_id", "")
                if cid:
                    db.execute(
                        "UPDATE contents SET status='needs_rewrite', meta=meta || %s, updated_at=now() WHERE id=%s",
                        (encode({"quality_gate": {"status": "failed", "checks": checks}}), cid),
                    )
                db.commit()
                db.close()
                raise OutputValidationError(
                    "final consistency gate rejected chapter: " + ", ".join(failed_checks.keys())
                )
            cid = context.get("chapter_id", "")
            if cid:
                db.execute(
                    "UPDATE contents SET meta = meta || %s, updated_at = now() WHERE id = %s",
                    (encode({
                        "final_consistency_check": output,
                        "review_7dim": _quality_evidence_payload(output, context.get("self_review")),
                    }), cid),
                )
        if task_type == "final_continuity_audit":
            continuity = output.get("continuity") if isinstance(output.get("continuity"), dict) else {}
            if continuity.get("status") != "continuous" or bool(continuity.get("gaps")):
                cid = context.get("chapter_id", "")
                if cid:
                    db.execute(
                        "UPDATE contents SET status='needs_rewrite', meta=meta || %s, updated_at=now() WHERE id=%s",
                        (encode({"continuity_gate": {"status": "failed", "audit": continuity}}), cid),
                    )
                db.commit()
                db.close()
                raise OutputValidationError("final continuity gate rejected chapter")
            cid = context.get("chapter_id", "")
            if cid:
                db.execute(
                    "UPDATE contents SET meta = meta || %s, updated_at = now() WHERE id = %s",
                    (encode({"final_continuity_audit": output}), cid),
                )
        if task_type == "final_humanize":
            cid = context.get("chapter_id", "")
            if cid and output.get("humanized_text"):
                current = db.execute("SELECT body FROM contents WHERE id = %s", (cid,)).fetchone()
                before_text = extract_body_text(current["body"] if current else "")
                paragraphs = _chapter_paragraphs_from_text(output.get("humanized_text", ""))
                try:
                    _assert_story_revision_quality(
                        task_type=task_type,
                        before_text=before_text,
                        after_paragraphs=paragraphs,
                        min_ratio=0.80,
                    )
                    _assert_min_chapter_length(task_type, "\n".join(paragraphs))
                except OutputValidationError:
                    db.close()
                    raise
                from app.services.text_metrics import count_content_chars
                db.execute(
                    "UPDATE contents SET body = %s, meta = meta || %s, updated_at = now() WHERE id = %s",
                    (
                        encode(_chapter_doc_from_paragraphs(paragraphs)),
                        encode({
                            "humanized": True,
                            "humanized_at": datetime.now(timezone.utc).isoformat(),
                            "word_count": count_content_chars("\n".join(paragraphs)),
                        }),
                        cid,
                    ),
                )
                context["chapter_text"] = "\n".join(paragraphs)

    # ── Common persist ──────────────────────────────────────────────────
    db.execute(
        "UPDATE run_nodes SET status = 'succeeded', output = %s, finished_at = now() WHERE run_id = %s AND node_key = %s",
        (encode(output), run_id, node_key),
    )
    db.execute(
        "UPDATE workflow_runs SET context = %s, updated_at = now() WHERE id = %s",
        (encode(context), run_id),
    )
    db.commit()
    db.close()

    # Reindex knowledge items
    if knowledge_ids_to_reindex:
        from app.services.knowledge_hub import rebuild_item_embeddings
        for knowledge_id in knowledge_ids_to_reindex:
            try:
                rebuild_item_embeddings(knowledge_id)
            except Exception as exc:
                from app.core.alerts import send_alert
                send_alert(f"知识向量重建失败 {knowledge_id}: {exc}", "warning")
def _persist_chapter_draft(db, run, node_key: str, output: dict, context: dict,
                           novel_id: str, project_id: str, run_id: str,
                           knowledge_ids_to_reindex: list[str]) -> None:
    """Persist chapter draft to contents table with idempotency key."""
    from app.services.text_metrics import count_content_chars
    chapter = output.get("chapter", {})
    body = {"type": "doc", "content": [{"type": "paragraph", "text": t} for t in chapter.get("body", [])]}
    chapter_text = "\n".join(t if isinstance(t, str) else t.get("text", "") for t in chapter.get("body", []))
    if _looks_like_non_narrative_text(chapter_text):
        db.close()
        raise OutputValidationError("write_chapter_draft returned non-narrative instructional text")
    try:
        _assert_min_chapter_length("write_chapter_draft", chapter_text)
    except OutputValidationError:
        db.close()
        raise
    chapter_seq = int(context.get("_chapter_seq", 1))
    chapter_meta = {"seq": chapter_seq, "word_count": count_content_chars(chapter_text)}
    cid = new_id()
    generation_key = _chapter_idempotency_key(novel_id, chapter_seq)
    stored = db.execute(
        """INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status, generation_key)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (project_id, generation_key) WHERE generation_key IS NOT NULL AND is_deleted=FALSE
           DO UPDATE SET title=EXCLUDED.title, body=EXCLUDED.body, meta=EXCLUDED.meta, updated_at=now()
           RETURNING id""",
        (cid, project_id, novel_id, "chapter", chapter.get("title", f"第一章"),
         encode(body), encode(chapter_meta), "pending_review", generation_key),
    ).fetchone()
    cid = stored["id"] if stored else cid
    context["chapter_id"] = cid
    context["chapter_text"] = chapter_text
    db.execute(
        """INSERT INTO versions (id, entity_type, entity_id, label, snapshot, client_mutation_id)
           VALUES (%s,'content',%s,'ai_generate',%s,%s)
           ON CONFLICT (client_mutation_id) WHERE client_mutation_id IS NOT NULL DO NOTHING""",
        (new_id(), cid, encode({"title": chapter.get("title", ""), "body": body, "meta": chapter_meta}),
         f"run:{run_id}:node:{node_key}:version"),
    )
    # Auto-summarize chapter
    _summarize_and_store(db, cid, chapter.get("body", []))
def _persist_chapter_polish(db, node_key: str, output: dict, context: dict, run_id: str) -> None:
    """Apply polished text to the chapter in contents."""
    cid = context.get("chapter_id", "")
    if not cid:
        return
    polished = output.get("polished", output.get("chapter", output))
    if isinstance(polished, dict) and polished.get("body"):
        current = db.execute("SELECT body FROM contents WHERE id = %s", (cid,)).fetchone()
        before_text = extract_body_text(current["body"] if current else "")
        polished_paragraphs = [
            str(t if isinstance(t, str) else t.get("text", "")).strip()
            for t in polished.get("body", [])
            if str(t if isinstance(t, str) else t.get("text", "")).strip()
        ]
        try:
            _assert_story_revision_quality(
                task_type="write_polish",
                before_text=before_text or context.get("chapter_text", ""),
                after_paragraphs=polished_paragraphs,
            )
            _assert_min_chapter_length("write_polish", "\n".join(polished_paragraphs))
        except OutputValidationError:
            db.close()
            raise
        polished_body = _chapter_doc_from_paragraphs(polished_paragraphs)
        db.execute("UPDATE contents SET body = %s, updated_at = now() WHERE id = %s", (encode(polished_body), cid))
        context["chapter_text"] = "\n".join(polished_paragraphs)
def _persist_fact_reconcile(db, node_key: str, output: dict, context: dict,
                            novel_id: str, run_id: str) -> None:
    """Reconcile chapter facts against entity states."""
    cid = context.get("chapter_id", "")
    if not cid:
        return
    # Record reconciliation result in chapter meta
    reconc_result = output.get("reconciliation", output)
    prev_meta = db.execute("SELECT meta->'fact_reconcile' AS prev FROM contents WHERE id = %s", (cid,)).fetchone()
    db.execute(
        "UPDATE contents SET meta = meta || %s, updated_at = now() WHERE id = %s",
        (encode({"fact_reconcile": reconc_result}), cid),
    )
    # show-me-the-story fact chain: every reconcile is a reversible fact transaction
    from app.services.fusion_deep_workflow import create_fact_transaction
    create_fact_transaction(
        "fact_reconcile", cid,
        previous_value=(prev_meta or {}).get("prev") or {},
        new_value=reconc_result if isinstance(reconc_result, dict) else {"value": reconc_result},
    )
    # Run cross-reference reconciliation
    chapter_text = context.get("chapter_text", "")
    if chapter_text:
        reconc = _write_after_reconcile(novel_id, cid, chapter_text)
        db.execute(
            "UPDATE contents SET meta = meta || %s WHERE id = %s",
            (encode({"_auto_reconcile": reconc}), cid),
        )
def _summarize_and_store(db, chapter_id: str, body: list) -> None:
    """M2: Generate and store chapter summary after generation."""
    try:
        from app.services.summarizer import summarize_chapter
        texts = []
        for p in body:
            if isinstance(p, dict):
                texts.append(p.get("text", ""))
            elif isinstance(p, str):
                texts.append(p)
        text = "\n".join(texts)
        if not text.strip():
            return
        result = summarize_chapter(chapter_id, text)
        summary = result.get("summary", "")
        if summary:
            db.execute(
                "UPDATE contents SET meta = meta || %s, updated_at = now() WHERE id = %s",
                (encode({"chapter_summary": summary}), chapter_id),
            )
    except Exception:
        pass  # Non-critical
# ══════════════════════════════════════════════════════════════════════════
# Chapter generation (M2 — unchanged from original)
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=2)
@_isolated_request_context
def gen_next_chapter_task(self, novel_id: str, project_id: str,
                           api_key: str = "", api_url: str = "", model: str = "",
                           batch_id: str = "", batch_ordinal: int = 0) -> dict:
    """M2: Generate the next chapter using context assembler (with distributed lock)."""
    from app.gateway import _request_api_key, _request_api_base_url, _request_model
    from .lock import acquire_lock, release_lock

    if api_key:
        _request_api_key.set(api_key)
    if api_url:
        _request_api_base_url.set(api_url)
    if model:
        _request_model.set(model)
    # Attribute generated chapters to the novel owner for per-user metering.
    _attach_user_context(novel_id)

    lock_key = f"lock:novel:{novel_id}:gen_chapter"
    if not acquire_lock(lock_key):
        return {"status": "skipped", "reason": "another generation in progress"}
    try:
        return _generate_next_chapter_unlocked(novel_id, project_id, batch_id, batch_ordinal)
    finally:
        release_lock(lock_key)
def _batch_generation_key(batch_id: str, ordinal: int) -> str:
    return f"batch:{batch_id}:slot:{ordinal}:v1"
def _generate_next_chapter_unlocked(novel_id: str, project_id: str,
                                    batch_id: str = "", batch_ordinal: int = 0) -> dict:
    """Generate one chapter. The caller owns the per-novel distributed lock."""
    from app.services.assembler import ContextAssembler
    from app.services.entity_tracker import extract_and_store
    db = connect()
    slot_key = _batch_generation_key(batch_id, batch_ordinal) if batch_id and batch_ordinal else ""
    if slot_key:
        existing = db.execute("""SELECT * FROM contents WHERE project_id=%s AND parent_id=%s
                                  AND generation_key=%s AND type='chapter' AND is_deleted=FALSE""",
                              (project_id, novel_id, slot_key)).fetchone()
        if existing:
            db.close()
            meta = existing["meta"] if isinstance(existing.get("meta"), dict) else {}
            continuity = meta.get("continuity")
            if not isinstance(continuity, dict):
                continuity = _continuity_report(novel_id, int(meta.get("seq") or 0))
                repair_db = connect()
                repair_db.execute("UPDATE contents SET meta=meta || %s,updated_at=now() WHERE id=%s",
                                  (encode({"continuity": continuity}), existing["id"]))
                repair_db.commit(); repair_db.close()
            if existing["status"] in {"reviewed", "needs_rewrite"}:
                return {"chapter_id": existing["id"], "title": existing["title"], "seq": meta.get("seq"),
                        "continuity": continuity,
                        "accepted": existing["status"] == "reviewed",
                        "review_status": existing["status"], "final_score": meta.get("review_score"),
                        "rewrite_attempts": meta.get("rewrite_attempts", 0), "reused": True}
            from app.services.novel_export import extract_body_text
            paragraphs = [part for part in extract_body_text(existing.get("body", "")).splitlines() if part.strip()]
            review = _review_and_finalize_chapter(
                existing["id"], novel_id, project_id, int(meta.get("seq") or 0), slot_key,
                existing["title"], paragraphs, continuity,
            )
            return {"chapter_id": existing["id"], "title": review["title"], "seq": meta.get("seq"),
                    "continuity": meta.get("continuity", {"status": "unchecked"}),
                    "accepted": review["accepted"], "review_status": review["review_status"],
                    "final_score": review["final_score"], "rewrite_attempts": review["rewrite_attempts"],
                    "reused": True}
    # Find last chapter seq
    last = db.execute(
        "SELECT COALESCE(MAX((meta->>'seq')::int), 0) as seq FROM contents WHERE parent_id = %s AND type='chapter'",
        (novel_id,),
    ).fetchone()
    next_seq = (last["seq"] if last else 0) + 1
    db.close()

    # Build context
    assembler = ContextAssembler(novel_id)
    context = assembler.build()

    # M2: Check for due foreshadows + inject into context
    from app.services.narrative_engine import check_foreshadow_due, inject_foreshadow_context
    due_foreshadows = check_foreshadow_due(novel_id, next_seq)
    if due_foreshadows:
        inject_str = inject_foreshadow_context(due_foreshadows)
        context = inject_str + "\n\n" + context

    # Generate — output is schema-validated by the gateway; the stable mutation id
    # lets a retry replay the succeeded ai_call instead of paying for a new one.
    generation_key = slot_key or f"novel:{novel_id}:chapter:{next_seq}:v1"
    output = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="gen_next_chapter", prompt_name="narrative.gen_next_chapter",
        variables={"context": context, "context_length": len(context), "assembled_layers": list(assembler.layers_built.keys())},
        client_mutation_id=generation_key,
    )

    chapter = output["chapter"]
    body = {"type": "doc", "content": [{"type": "paragraph", "text": t} for t in chapter["body"]]}
    cid = new_id()

    db = connect()
    from app.services.text_metrics import count_content_chars
    text = "\n".join(t if isinstance(t, str) else t.get("text", "") for t in chapter["body"])
    _assert_min_chapter_length("gen_next_chapter", text)
    chapter_meta = {"seq": next_seq, "word_count": count_content_chars(text)}
    if batch_id and batch_ordinal:
        chapter_meta.update({"batch_id": batch_id, "batch_ordinal": batch_ordinal,
                             "ordinal": batch_ordinal, "quality_status": "draft_pending_review"})
    stored = db.execute(
        """INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status, generation_key)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (project_id, generation_key) WHERE generation_key IS NOT NULL AND is_deleted=FALSE
           DO UPDATE SET title=EXCLUDED.title, body=EXCLUDED.body, meta=EXCLUDED.meta, updated_at=now()
           RETURNING id""",
        (cid, project_id, novel_id, "chapter", chapter.get("title", f"第{next_seq}章"),
         encode(body), encode(chapter_meta), "pending_review", generation_key),
    ).fetchone()
    cid = stored["id"] if stored else cid
    db.execute(
        """INSERT INTO versions (id, entity_type, entity_id, label, snapshot, client_mutation_id)
           VALUES (%s, 'content', %s, 'ai_generate', %s, %s)
           ON CONFLICT (client_mutation_id) WHERE client_mutation_id IS NOT NULL DO NOTHING""",
        (new_id(), cid, encode({"title": chapter.get("title", ""), "body": body, "meta": chapter_meta}),
         generation_key),
    )
    db.commit()
    db.close()

    # Enrichments must never prevent the persisted draft from reaching the
    # continuity/review gates. Failures are recorded for later reconciliation.
    from app.services.foreshadowing import extract_and_store_foreshadowing
    from app.services.timeline import extract_timeline, update_arcs
    enrichment_errors = []
    for label, action in (
        ("entities", lambda: extract_and_store(cid, novel_id, text)),
        ("foreshadowing", lambda: extract_and_store_foreshadowing(cid, next_seq, text)),
        ("timeline", lambda: extract_timeline(cid, text)),
        ("arcs", lambda: update_arcs(novel_id, text)),
    ):
        try:
            action()
        except Exception as exc:
            enrichment_errors.append({"stage": label, "error": str(exc)[:300]})

    # Continuity check + risk report (DB comparison, no extra AI spend); a check
    # failure is recorded as unchecked, never silently dropped.
    continuity = _continuity_report(novel_id, next_seq)

    # Persist continuity evidence before the review gate so the reviewer can see it.
    db = connect()
    db.execute(
        "UPDATE contents SET meta = meta || %s, updated_at = now() WHERE id = %s",
        (encode({"continuity": continuity, "enrichment_errors": enrichment_errors}), cid),
    )
    db.commit()
    db.close()
    review = _review_and_finalize_chapter(
        cid, novel_id, project_id, next_seq, generation_key, chapter.get("title", ""),
        list(chapter["body"]), continuity,
    )
    db = connect()
    _summarize_and_store(db, cid, review["body"])
    db.commit(); db.close()
    return {"chapter_id": cid, "title": chapter.get("title", ""), "seq": next_seq,
            "continuity": continuity, "accepted": review["accepted"],
            "review_status": review["review_status"], "final_score": review["final_score"],
            "rewrite_attempts": review["rewrite_attempts"]}
def _review_and_finalize_chapter(chapter_id: str, novel_id: str, project_id: str, chapter_seq: int,
                                 generation_key: str, title: str, paragraphs: list[str],
                                 continuity: dict, threshold: float = 80, max_rewrites: int = 2) -> dict:
    """Review every generated chapter; rewrites must be reviewed again before acceptance."""
    current_title = title
    current_body = list(paragraphs)
    for attempt in range(max_rewrites + 1):
        current_text = "\n".join(current_body)
        length_issue = ""
        try:
            _assert_min_chapter_length("chapter_review", current_text)
        except OutputValidationError as exc:
            length_issue = str(exc)
        review = complete(
            run_id=None, node_key=None, project_id=project_id,
            task_type="review_7dim", prompt_name="bootstrap.review_7dim",
            variables={"chapter_id": chapter_id, "chapter_seq": chapter_seq, "body": current_text,
                       "continuity": continuity, "threshold": threshold},
            client_mutation_id=f"{generation_key}:review:{attempt}:v1",
        )
        score = float(review["score"])
        issues = list(review.get("issues", []))
        if length_issue:
            score = min(score, threshold - 1)
            issues.append(length_issue)
        review_key = f"{generation_key}:review-record:{attempt}:v1"
        db = connect()
        db.execute(
            """INSERT INTO reviews (id,content_id,score,dimensions,issues,generation_key)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT (content_id,generation_key) WHERE generation_key IS NOT NULL
               DO UPDATE SET score=EXCLUDED.score,dimensions=EXCLUDED.dimensions,issues=EXCLUDED.issues""",
            (new_id(), chapter_id, score, encode(review["dimensions"]), encode(issues), review_key),
        )
        status = "pending_review"
        db.execute("""UPDATE contents SET status=%s,meta=meta || %s,updated_at=now() WHERE id=%s""",
                   (status, encode({"review_score": score, "review_issues": issues,
                                    "review_attempts": attempt + 1,
                                    "quality_status": "ai_review_passed" if score >= threshold else "draft_pending_review"}), chapter_id))
        db.commit(); db.close()
        if score >= threshold:
            return {"accepted": False, "review_status": "pending_review", "final_score": score,
                    "rewrite_attempts": attempt, "title": current_title, "body": current_body}
        if attempt == max_rewrites:
            db = connect()
            db.execute("""UPDATE contents SET status='needs_rewrite',meta=meta || %s,updated_at=now()
                          WHERE id=%s""", (encode({"quality_status": "needs_review"}), chapter_id))
            db.commit(); db.close()
            return {"accepted": False, "review_status": "needs_rewrite", "final_score": score,
                    "rewrite_attempts": attempt, "title": current_title, "body": current_body}

        rewritten = complete(
            run_id=None, node_key=None, project_id=project_id,
            task_type="gen_next_chapter", prompt_name="narrative.gen_next_chapter",
            variables={"rewrite": True, "chapter_seq": chapter_seq, "current_title": current_title,
                       "current_body": current_text, "review_feedback": issues, "continuity": continuity},
            client_mutation_id=f"{generation_key}:rewrite:{attempt + 1}:v1",
        )["chapter"]
        current_title = rewritten["title"]
        current_body = list(rewritten["body"])
        _assert_min_chapter_length("chapter_rewrite", "\n".join(current_body))
        rewritten_doc = {"type": "doc", "content": [{"type": "paragraph", "text": text}
                                                         for text in current_body]}
        from app.services.text_metrics import count_content_chars
        db = connect()
        db.execute("""UPDATE contents SET title=%s,body=%s,meta=meta || %s,status='pending_review',updated_at=now()
                      WHERE id=%s""",
                   (current_title, encode(rewritten_doc),
                    encode({"word_count": count_content_chars("\n".join(current_body)),
                            "rewrite_attempts": attempt + 1,
                            "quality_status": "draft_pending_review"}), chapter_id))
        db.commit(); db.close()
def _continuity_report(novel_id: str, chapter_seq: int) -> dict:
    """Cross-chapter conflicts + overdue foreshadows as a persisted risk report."""
    from datetime import datetime, timezone
    from app.services.narrative_engine import check_foreshadow_due, detect_cross_chapter_conflicts
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        conflicts = detect_cross_chapter_conflicts(novel_id)
        overdue = check_foreshadow_due(novel_id, chapter_seq)
    except Exception as exc:
        return {"status": "unchecked", "error": str(exc), "checked_at": checked_at}
    risks = ([{"type": "conflict", **c} for c in conflicts]
             + [{"type": "foreshadow_due", "content": f.get("content", ""), "foreshadow_id": f.get("id")}
                for f in overdue])
    return {"status": "flagged" if risks else "clean", "risks": risks, "checked_at": checked_at}


@celery_app.task(bind=True, max_retries=1)
@_isolated_request_context
def regenerate_chapter_task(self, chapter_id: str, reason: str = "",
                            api_key: str = "", api_url: str = "", model: str = "") -> dict:
    """Regenerate one rejected chapter in place.

    This is the manual-review path: rejecting a chapter must not create the next
    chapter by accident. It rewrites the same content row and leaves it
    ``pending_review`` for another human decision.
    """
    from app.services.novel_export import extract_body_text
    from app.services.text_metrics import count_content_chars

    db = connect()
    chapter = db.execute("SELECT * FROM contents WHERE id=%s AND type='chapter' AND is_deleted=FALSE", (chapter_id,)).fetchone()
    if not chapter:
        db.close()
        return {"status": "error", "message": "chapter not found"}
    novel = db.execute("SELECT * FROM contents WHERE id=%s AND type='novel' AND is_deleted=FALSE", (chapter["parent_id"],)).fetchone()
    if not novel:
        db.close()
        return {"status": "error", "message": "novel not found"}
    chapter_meta = chapter["meta"] if isinstance(chapter.get("meta"), dict) else {}
    seq = int(chapter_meta.get("seq") or 1)
    current_text = extract_body_text(chapter.get("body", ""))
    project_id = chapter["project_id"]
    novel_id = chapter["parent_id"]
    db.close()

    output = complete(
        run_id=None,
        node_key=None,
        project_id=project_id,
        task_type="gen_next_chapter",
        prompt_name="narrative.gen_next_chapter",
        variables={
            "rewrite": True,
            "manual_review_rejected": True,
            "chapter_seq": seq,
            "current_title": chapter["title"],
            "current_body": current_text,
            "review_feedback": [reason or "人工审核拒绝：请重写本章，保留章节序号，强化冲突、叙事和可读性。"],
            "context": f"小说：《{novel['title']}》\n章节序号：第{seq}章\n拒绝原因：{reason}",
        },
        client_mutation_id=f"manual-review:{chapter_id}:regenerate:{int(time.time())}:v1",
    )
    rewritten = output["chapter"]
    paragraphs = [str(p).strip() for p in rewritten.get("body", []) if str(p).strip()]
    text = "\n".join(paragraphs)
    if _looks_like_non_narrative_text(text):
        db = connect()
        db.execute(
            "UPDATE contents SET status='needs_rewrite', meta=meta || %s, updated_at=now() WHERE id=%s",
            (encode({"manual_review": {"status": "regenerate_failed", "reason": "non_narrative_output"}}), chapter_id),
        )
        db.commit(); db.close()
        raise OutputValidationError("manual regeneration returned non-narrative text")
    _assert_min_chapter_length("manual_regeneration", text)

    db = connect()
    previous_snapshot = {"title": chapter["title"], "body": chapter["body"], "meta": chapter_meta}
    db.execute(
        "INSERT INTO versions (id, entity_type, entity_id, label, snapshot, reason) VALUES (%s,'content',%s,'before_manual_regenerate',%s,%s)",
        (new_id("ver"), chapter_id, encode(previous_snapshot), reason[:500]),
    )
    meta_patch = {
        "word_count": count_content_chars(text),
        "manual_review": {
            "status": "regenerated",
            "reason": reason,
            "regenerated_at": datetime.now(timezone.utc).isoformat(),
        },
        "quality_status": "draft_pending_review",
    }
    db.execute(
        """UPDATE contents
           SET title=%s, body=%s, status='pending_review', meta=meta || %s, updated_at=now()
           WHERE id=%s""",
        (
            rewritten.get("title") or chapter["title"],
            encode(_chapter_doc_from_paragraphs(paragraphs)),
            encode(meta_patch),
            chapter_id,
        ),
    )
    db.commit(); db.close()
    return {"status": "pending_review", "chapter_id": chapter_id, "title": rewritten.get("title") or chapter["title"], "seq": seq}
def _run_batch_slot(batch: dict, ordinal: int, api_key: str = "", api_url: str = "",
                    model: str = "") -> dict:
    """Run or resume one stable batch slot."""
    generation_key = _batch_generation_key(batch["id"], ordinal)
    db = connect()
    existing = db.execute("""SELECT * FROM contents WHERE project_id=%s AND parent_id=%s
                              AND generation_key=%s AND type='chapter' AND is_deleted=FALSE""",
                          (batch["project_id"], batch["novel_id"], generation_key)).fetchone()
    db.close()
    if existing:
        meta = existing["meta"] if isinstance(existing.get("meta"), dict) else {}
        continuity = meta.get("continuity")
        if not isinstance(continuity, dict):
            continuity = _continuity_report(batch["novel_id"], int(meta.get("seq") or 0))
            repair_db = connect()
            repair_db.execute("UPDATE contents SET meta=meta || %s,updated_at=now() WHERE id=%s",
                              (encode({"continuity": continuity}), existing["id"]))
            repair_db.commit(); repair_db.close()
        if existing.get("status") in {"reviewed", "needs_rewrite"}:
            accepted = existing["status"] == "reviewed"
            return {"chapter_id": existing["id"], "accepted": accepted,
                    "review_status": existing["status"], "reused": True}
        from app.services.novel_export import extract_body_text
        paragraphs = [line for line in extract_body_text(existing.get("body", "")).splitlines() if line.strip()]
        review = _review_and_finalize_chapter(
            existing["id"], batch["novel_id"], batch["project_id"], int(meta.get("seq") or 0),
            generation_key, existing["title"], paragraphs,
            continuity,
        )
        return {"chapter_id": existing["id"], **review, "reused": True}
    return gen_next_chapter_task.run(
        batch["novel_id"], batch["project_id"], api_key, api_url, model,
        batch["id"], ordinal,
    )
def _recount_batch_progress(db, batch_id: str) -> dict | None:
    """Rebuild counters from distinct persisted slots; never blindly trust increments."""
    cursor = db.execute("""SELECT status,meta FROM contents WHERE type='chapter'
                           AND meta->>'batch_id'=%s AND is_deleted=FALSE""", (batch_id,))
    if not hasattr(cursor, "fetchall"):
        return None
    rows = cursor.fetchall()
    by_ordinal = {}
    for row in rows:
        meta = row.get("meta", {}) if isinstance(row.get("meta"), dict) else {}
        if meta.get("batch_id") and meta.get("batch_id") != batch_id:
            continue
        ordinal = int(meta.get("batch_ordinal") or meta.get("ordinal") or 0)
        if ordinal > 0:
            by_ordinal[ordinal] = meta.get("quality_status") or row.get("status")
    generated = len(by_ordinal)
    accepted = sum(status in {"accepted", "reviewed"} for status in by_ordinal.values())
    # A generated draft has not completed AI/manual review yet and must not
    # inflate reviewed/completed counters.
    needs_review = sum(status in {"needs_review", "needs_rewrite", "pending_review", "ai_review_passed"} for status in by_ordinal.values())
    reviewed = accepted + needs_review
    terminal = reviewed
    db.execute("""UPDATE generation_batches SET generated_count=%s,reviewed_count=%s,
                  accepted_count=%s,needs_review_count=%s,completed_count=%s,updated_at=now() WHERE id=%s""",
               (generated, reviewed, accepted, needs_review, terminal, batch_id))
    return {"generated_count": generated, "reviewed_count": reviewed, "accepted_count": accepted,
            "needs_review_count": needs_review, "completed_count": terminal}
def _increment_batch_progress_legacy(db, batch_id: str, accepted: bool) -> None:
    """Only for non-production lightweight adapters without fetchall support."""
    db.execute("UPDATE generation_batches SET completed_count = completed_count + 1, updated_at=now() WHERE id=%s",
               (batch_id,))
    db.execute("""UPDATE generation_batches SET generated_count=generated_count+1,
                   reviewed_count=reviewed_count+1,accepted_count=accepted_count+%s,
                   needs_review_count=needs_review_count+%s,updated_at=now() WHERE id=%s""",
               (1 if accepted else 0, 0 if accepted else 1, batch_id))
@celery_app.task(bind=True, max_retries=1)
def batch_generate_chapters_task(
    self,
    batch_id: str,
    api_key: str = "",
    api_url: str = "",
    model: str = "",
) -> dict:
    """Generate a persisted batch, observing cancellation and resuming from completed_count."""
    db = connect()
    batch = db.execute("SELECT * FROM generation_batches WHERE id = %s", (batch_id,)).fetchone()
    if not batch:
        db.close()
        return {"status": "error", "message": "batch not found"}
    db.execute("UPDATE generation_batches SET status = 'running', error = NULL, updated_at = now() WHERE id = %s", (batch_id,))
    db.commit()
    db.close()

    start_ordinal = batch.get("completed_count", 0) + 1
    had_needs_review = False
    try:
        for ordinal in range(start_ordinal, batch["requested_count"] + 1):
            db = connect()
            db.execute("UPDATE generation_batches SET current_ordinal=%s,updated_at=now() WHERE id=%s",
                       (ordinal, batch_id))
            db.commit(); db.close()
            db = connect()
            state = db.execute("SELECT cancel_requested FROM generation_batches WHERE id = %s", (batch_id,)).fetchone()
            db.close()
            if not state or state["cancel_requested"]:
                return {"status": "cancelled", "batch_id": batch_id}
            result = _run_batch_slot(batch, ordinal, api_key, api_url, model)
            if result.get("status") == "skipped":
                raise RuntimeError(result.get("reason", "chapter generation skipped"))
            accepted = result.get("accepted", True)
            had_needs_review = had_needs_review or not accepted
            db = connect()
            counts = _recount_batch_progress(db, batch_id)
            if counts is None:
                _increment_batch_progress_legacy(db, batch_id, accepted)
            db.commit()
            db.close()
    except BudgetExceeded as exc:
        db = connect()
        db.execute(
            "UPDATE generation_batches SET status = 'failed', error = %s, updated_at = now() WHERE id = %s",
            (str(exc), batch_id),
        )
        db.commit()
        db.close()
        from app.core.alerts import send_alert
        send_alert(f"批次 {batch_id} 因预算不足失败：{exc}", "warning")
        return {"status": "failed", "batch_id": batch_id, "reason": str(exc)}
    except ProviderError as exc:
        db = connect()
        db.execute(
            "UPDATE generation_batches SET status = 'failed', error = %s, updated_at = now() WHERE id = %s",
            (str(exc), batch_id),
        )
        db.commit()
        db.close()
        from app.core.alerts import send_alert
        send_alert(f"批次 {batch_id} 因 AI provider 失败：{exc}", "warning")
        return {"status": "failed", "batch_id": batch_id, "reason": str(exc)}
    except Exception as exc:
        db = connect()
        db.execute(
            "UPDATE generation_batches SET status = 'failed', error = %s, updated_at = now() WHERE id = %s",
            (str(exc), batch_id),
        )
        db.commit()
        db.close()
        from app.core.alerts import send_alert
        send_alert(f"批次 {batch_id} 失败：{exc}", "error")
        raise

    db = connect()
    final_status = "needs_review" if had_needs_review else "succeeded"
    db.execute("""UPDATE generation_batches SET status=%s,quality_status=%s,current_ordinal=NULL,updated_at=now()
                  WHERE id=%s""",
               (final_status, "needs_review" if had_needs_review else "verified", batch_id))
    db.commit()
    db.close()
    return {"status": final_status, "batch_id": batch_id, "completed_count": batch["requested_count"]}
@celery_app.task
def expand_outline_task(novel_id: str, project_id: str) -> dict:
    """M2: Expand volume outline into chapter-level outlines."""
    db = connect()
    meta_row = db.execute("SELECT meta FROM contents WHERE id = %s", (novel_id,)).fetchone()
    db.close()
    if not meta_row:
        return {"error": "novel not found"}
    meta = meta_row["meta"] if isinstance(meta_row["meta"], dict) else {}
    outline = meta.get("outline", [])
    if not outline:
        return {"error": "no outline to expand"}

    chapters = []
    for vol_idx, vol_line in enumerate(outline):
        output = complete(
            run_id=None, node_key=None, project_id=project_id,
            task_type="expand_outline", prompt_name="narrative.expand_outline",
            variables={"volume": vol_line, "volume_num": vol_idx + 1, "chapters_per_volume": 10},
        )
        for ch in output.get("chapters", []):
            chapters.append({"volume": vol_idx + 1, "seq": len(chapters) + 1, "title": ch.get("title", ""), "outline": ch.get("outline", "")})

    db = connect()
    db.execute(
        "UPDATE contents SET meta = meta || %s, updated_at = now() WHERE id = %s",
        (encode({"chapter_outlines": chapters}), novel_id),
    )
    db.commit()
    db.close()
    return {"chapters": len(chapters), "sample": chapters[:3]}
@celery_app.task
def auto_serial_check() -> dict:
    """M2 beat: check for novels with auto-serial enabled and generate next chapter."""
    db = connect()
    novels = db.execute(
        "SELECT id, project_id FROM contents WHERE type='novel' AND meta->>'auto_serial' = 'true' AND is_deleted = FALSE"
    ).fetchall()
    db.close()
    results = []
    for novel in novels:
        try:
            gen_next_chapter_task.delay(novel["id"], novel["project_id"])
            results.append({"novel_id": novel["id"], "status": "dispatched"})
        except Exception as e:
            results.append({"novel_id": novel["id"], "status": f"error: {e}"})
    return {"checked": len(novels), "results": results}
@celery_app.task
def purge_stale_autosaves() -> dict:
    """C5-05: 7-day retention for routine save versions.

    Only manual_save/offline_save are purged, and the 10 most recent per
    entity are always kept; semantic branches (ai_edit/ai_generate/
    initial_idea/offline_conflict/before_restore) are never touched."""
    db = connect()
    db.execute(
        """DELETE FROM versions WHERE id IN (
             SELECT id FROM (
               SELECT id, ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY created_at DESC) AS rn
               FROM versions
               WHERE label IN ('manual_save', 'offline_save')
                 AND created_at < now() - interval '7 days'
             ) ranked WHERE ranked.rn > 10
           )"""
    )
    deleted = getattr(db._cur, "rowcount", 0)
    db.commit()
    db.close()
    return {"deleted": deleted}
@celery_app.task
def purge_stale_operational_data() -> dict:
    """Bound unbounded operational tables while retaining recent audit evidence."""
    import os

    ai_days = max(30, int(os.getenv("AI_CALL_RETENTION_DAYS", "365")))
    operation_days = max(30, int(os.getenv("OPERATION_LOG_RETENTION_DAYS", "180")))
    audit_days = max(30, int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "365")))
    db = connect()
    deleted = {}
    for table, days in (("ai_calls", ai_days), ("operation_logs", operation_days),
                        ("audit_logs", audit_days)):
        db.execute(
            f"DELETE FROM {table} WHERE created_at < now() - (%s * interval '1 day')", (days,),
        )
        deleted[table] = max(0, int(getattr(db._cur, "rowcount", 0)))
    db.commit()
    db.close()
    return {"deleted": deleted, "retention_days": {
        "ai_calls": ai_days, "operation_logs": operation_days, "audit_logs": audit_days,
    }}
def check_queue_backlog(threshold: int | None = None) -> str | None:
    """Alert when the celery queue piles up (e.g. stale dispatches burning
    provider credits — 404 messages were found queued on 2026-07-12)."""
    import os

    import redis as redis_lib

    limit = threshold if threshold is not None else int(os.getenv("QUEUE_BACKLOG_THRESHOLD", "50"))
    try:
        client = redis_lib.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        depth = int(client.llen("celery"))
    except Exception:
        return None
    if depth > limit:
        return f"celery queue backlog: {depth} messages (threshold {limit})"
    return None
@celery_app.task
def daily_cost_report() -> dict:
    """Beat: 昨日 AI 成本日报 — 个人部署最实用的一条监控。"""
    from app.core.alerts import send_alert

    db = connect()
    rows = db.execute(
        """SELECT task_type, COUNT(*) AS n, COALESCE(SUM(prompt_tokens),0) AS pt,
                  COALESCE(SUM(completion_tokens),0) AS ct, COALESCE(SUM(cost_cny),0) AS cost
           FROM ai_calls
           WHERE created_at >= now() - interval '24 hours' AND status = 'succeeded'
           GROUP BY task_type ORDER BY cost DESC"""
    ).fetchall()
    failed = db.execute(
        "SELECT COUNT(*) AS n FROM ai_calls WHERE created_at >= now() - interval '24 hours' AND status != 'succeeded'"
    ).fetchone()["n"]
    db.close()
    total_calls = sum(r["n"] for r in rows)
    total_tokens = sum(r["pt"] + r["ct"] for r in rows)
    total_cost = float(sum(r["cost"] for r in rows))
    if total_calls or failed:
        lines = [f"过去24h：{total_calls} 次调用 / {total_tokens} tokens / ¥{total_cost:.4f}，失败 {failed} 次"]
        lines += [f"• {r['task_type']}: {r['n']} 次, {r['pt'] + r['ct']} tokens" for r in rows[:6]]
        send_alert("AI 成本日报\n" + "\n".join(lines), "info")
    return {"calls": total_calls, "tokens": total_tokens, "cost_cny": round(total_cost, 4), "failed": failed}
@celery_app.task
def patrol_check() -> dict:
    """M2 beat: consistency patrol — check foreshadowing, chapter gaps, quality."""
    db = connect()
    # Check for overdue foreshadowing (planted but past planned chapter)
    overdue = db.execute(
        """SELECT f.id, f.content, f.planned_resolve_chapter, c.title as chapter_title
           FROM foreshadowings f
           JOIN contents c ON f.chapter_id = c.id
           WHERE f.status = 'planted'
             AND f.planned_resolve_chapter IS NOT NULL
             AND f.planned_resolve_chapter <= (
               SELECT COALESCE(MAX((latest.meta->>'seq')::int), 0)
               FROM contents latest
               WHERE latest.parent_id = c.parent_id AND latest.type = 'chapter'
                 AND latest.is_deleted = FALSE
             )"""
    ).fetchall()

    # Check for chapters needing rewrite
    needs_rewrite = db.execute(
        "SELECT id, title FROM contents WHERE status = 'needs_rewrite' AND is_deleted = FALSE"
    ).fetchall()

    # Check for orphan chapters (no parent novel)
    orphans = db.execute(
        "SELECT id, title FROM contents WHERE type='chapter' AND parent_id IS NULL AND is_deleted = FALSE"
    ).fetchall()

    db.close()

    issues = []
    if overdue:
        issues.append(f"{len(overdue)} unfulfilled foreshadowings")
    if needs_rewrite:
        issues.append(f"{len(needs_rewrite)} chapters need rewrite")
    if orphans:
        issues.append(f"{len(orphans)} orphan chapters")
    backlog = check_queue_backlog()
    if backlog:
        issues.append(backlog)

    # Send alerts for issues
    if issues:
        from app.core.alerts import send_alert
        send_alert("巡检发现问题:\n" + "\n".join(f"• {i}" for i in issues), "warning")

    return {
        "status": "ok" if not issues else "issues_found",
        "issues": issues,
        "foreshadowing_count": len(overdue),
        "needs_rewrite_count": len(needs_rewrite),
    }
@celery_app.task(bind=True, max_retries=2)
def bootstrap_short_story_task(self, project_id: str, short_id: str) -> dict:
    """M3: Generate short story from idea."""
    from app.services.short_story import SHORT_STORY_TEMPLATES

    db = connect()
    story = row_to_dict(db.execute("SELECT * FROM contents WHERE id = %s", (short_id,)).fetchone())
    if not story:
        db.close()
        return {"error": "story not found"}
    meta = story.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    template_key = meta.get("template", "viral")
    template = SHORT_STORY_TEMPLATES.get(template_key, SHORT_STORY_TEMPLATES["viral"])
    context = {"idea": meta.get("idea",""), "genre": meta.get("genre",""),
               "style": meta.get("style",""), "template": template["name"],
               "max_words": meta.get("max_words", template["max_words"])}
    db.close()

    output = complete(run_id=None, node_key="s1", project_id=project_id,
                     task_type="gen_short_titles", prompt_name="shortstory.gen_titles",
                     variables=context)
    titles = output.get("titles", [])
    context["title"] = titles[0] if titles else "未命名短篇"

    output = complete(run_id=None, node_key="s2", project_id=project_id,
                     task_type="gen_short_story", prompt_name="shortstory.gen_story",
                     variables=context)
    story_out = output.get("story", {})
    body = {"type":"doc","content":[{"type":"paragraph","text":t} for t in story_out.get("body",[])]}
    db = connect()
    db.execute("UPDATE contents SET title=%s, body=%s, meta=meta||%s, status=%s, updated_at=now() WHERE id=%s",
               (story_out.get("title", context["title"]), encode(body),
                encode({"short_score": 0, "template": template_key}), "completed", short_id))
    db.commit()
    db.close()
    return {"status": "completed", "title": story_out.get("title", "")}
