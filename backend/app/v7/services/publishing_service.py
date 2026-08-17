"""publishing_service — v0.9.2 发布准备服务

职责：
- 章节出版状态机：draft → quality_candidate → publish_ready → published
- 多平台发布变体管理（基础小说 + 平台变体）
- AI披露状态机与发布阻断
- 七道门禁结果持久化与查询
- 统计快照管理

状态规则：
- 旧 reviewed 保持兼容
- 新 quality_candidate：七项门禁均已输出，但不要求全部通过
- 新 publish_ready：真正满足出版准备条件（所有blocking门禁通过）
- 新 published：用户确认后的发布状态
- 生成完成 ≠ reviewed；内部审核通过 ≠ publish_ready；publish_ready ≠ 自动发布
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ..quality.statistics_v1 import compute_statistics
from ..quality.publishing_gates import GATE_DEFINITIONS, run_all_gates, PublishingGateReport
from ..quality.semantic_assessments import assess_payoff_semantically, generate_disclosure_text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


# ── 状态机定义 ────────────────────────────────────────────────
PUBLISHING_STATES = ["draft", "quality_candidate", "publish_ready", "published", "rejected"]
VALID_TRANSITIONS = {
    "draft": ["quality_candidate", "rejected"],
    "quality_candidate": ["publish_ready", "draft", "rejected"],
    "publish_ready": ["published", "quality_candidate", "rejected"],
    "published": ["quality_candidate"],  # 撤回重新准备
    "rejected": ["draft", "quality_candidate"],
}


def can_transition(current: str, target: str) -> bool:
    """检查状态转换是否合法。"""
    return target in VALID_TRANSITIONS.get(current, [])


# ── 统计快照 ──────────────────────────────────────────────────
def save_statistics_snapshot(db, chapter_id: str, text: str, variant_id: Optional[str] = None) -> dict[str, Any]:
    """计算并保存章节统计快照。"""
    stats = compute_statistics(text)
    snapshot_id = _new_id()
    db.execute(
        """
        INSERT INTO chapter_statistics_snapshots
            (id, chapter_id, variant_id, statistics_version, content_sha256, normalized_sha256,
             total_chars, total_bytes, chapter_count, paragraph_count, sentence_count,
             dialogue_count, dialogue_char_count, avg_sentence_length, full_statistics, anomaly_count)
        VALUES (%s, %s, %s, 'v1', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (chapter_id, statistics_version, content_sha256) DO UPDATE
            SET full_statistics = EXCLUDED.full_statistics,
                anomaly_count = EXCLUDED.anomaly_count,
                total_chars = EXCLUDED.total_chars
        RETURNING id
        """,
        (snapshot_id, chapter_id, variant_id, stats.content_sha256, stats.normalized_sha256,
         stats.total_chars, stats.total_bytes, stats.chapter_count, stats.total_paragraphs,
         stats.total_sentences, stats.total_dialogues, stats.total_dialogue_chars,
         stats.chapters[0].avg_sentence_length if stats.chapters else 0,
         json.dumps(stats.to_dict(), ensure_ascii=False),
         len(stats.global_anomalies)),
    )
    row = db.fetchone()
    return {"snapshot_id": row["id"] if row else snapshot_id, "stats": stats.to_dict()}


# ── 门禁结果持久化 ────────────────────────────────────────────
def save_gate_results(db, report: PublishingGateReport) -> None:
    """保存七道门禁结果到数据库。"""
    for gate_key, gate in report.gates.items():
        g = gate.to_dict()
        db.execute(
            """
            INSERT INTO quality_gate_results
                (id, chapter_id, variant_id, gate_key, gate_version, passed, score, threshold,
                 sub_gates, issues, warnings, evidence, is_blocking, runner, content_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (chapter_id, gate_key, content_sha256) DO UPDATE
                SET passed = EXCLUDED.passed,
                    score = EXCLUDED.score,
                    issues = EXCLUDED.issues,
                    warnings = EXCLUDED.warnings,
                    evidence = EXCLUDED.evidence,
                    sub_gates = EXCLUDED.sub_gates
            """,
            (_new_id(), report.chapter_id, report.variant_id, gate_key, g["gate_version"],
             g["passed"], g["score"], g["threshold"],
             json.dumps(g["sub_gates"], ensure_ascii=False),
             json.dumps(g["issues"], ensure_ascii=False),
             json.dumps(g["warnings"], ensure_ascii=False),
             json.dumps(g["evidence"], ensure_ascii=False),
             g["is_blocking"], g["runner"], report.content_sha256),
        )


# ── 平台配置管理 ──────────────────────────────────────────────
def get_platform_profile(db, project_id: str, platform: str, profile_name: Optional[str] = None) -> Optional[dict[str, Any]]:
    """获取平台发布配置。"""
    if profile_name:
        row = db.execute(
            "SELECT * FROM platform_publication_profiles WHERE project_id = %s AND platform = %s AND profile_name = %s AND is_active = TRUE",
            (project_id, platform, profile_name),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT * FROM platform_publication_profiles WHERE project_id = %s AND platform = %s AND is_active = TRUE ORDER BY created_at LIMIT 1",
            (project_id, platform),
        ).fetchone()
    return dict(row) if row else None


def create_platform_profile(db, project_id: str, platform: str, profile_name: str, **kwargs) -> dict[str, Any]:
    """创建平台发布配置。"""
    profile_id = _new_id()
    fields = ["word_count_min", "word_count_max", "chapter_word_min", "chapter_word_max",
              "ai_usage_policy", "policy_status", "policy_version"]
    values = {f: kwargs.get(f) for f in fields if f in kwargs}
    extra = {k: v for k, v in kwargs.items() if k not in fields}

    db.execute(
        f"""
        INSERT INTO platform_publication_profiles
            (id, project_id, platform, profile_name, policy_status, ai_usage_policy,
             policy_version, word_count_min, word_count_max, chapter_word_min, chapter_word_max, extra_metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (profile_id, project_id, platform, profile_name,
         values.get("policy_status", "unknown"),
         values.get("ai_usage_policy", "unknown"),
         values.get("policy_version", ""),
         values.get("word_count_min"), values.get("word_count_max"),
         values.get("chapter_word_min"), values.get("chapter_word_max"),
         json.dumps(extra, ensure_ascii=False)),
    )
    return {"id": profile_id}


# ── 发布变体管理 ──────────────────────────────────────────────
def create_publication_variant(
    db,
    novel_id: str,
    platform: str,
    variant_name: str,
    platform_profile_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """为基础小说创建平台发布变体。"""
    variant_id = _new_id()
    meta = metadata or {}
    db.execute(
        """
        INSERT INTO publication_variants
            (id, novel_id, platform_profile_id, platform, variant_name,
             title, synopsis, tags, category, publication_status, ai_disclosure_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', 'pending')
        RETURNING id
        """,
        (variant_id, novel_id, platform_profile_id, platform, variant_name,
         meta.get("title"), meta.get("synopsis"),
         json.dumps(meta.get("tags", []), ensure_ascii=False),
         meta.get("category")),
    )
    return {"variant_id": variant_id}


def get_variant(db, variant_id: str) -> Optional[dict[str, Any]]:
    row = db.execute("SELECT * FROM publication_variants WHERE id = %s", (variant_id,)).fetchone()
    return dict(row) if row else None


def update_variant_status(db, variant_id: str, new_status: str) -> dict[str, Any]:
    """更新变体发布状态，带状态机校验。"""
    variant = get_variant(db, variant_id)
    if not variant:
        raise ValueError(f"变体不存在: {variant_id}")
    current = variant["publication_status"]
    if not can_transition(current, new_status):
        raise ValueError(f"非法状态转换: {current} → {new_status}")

    if new_status == "publish_ready":
        rows = db.execute(
            """
            SELECT DISTINCT ON (gate_key) gate_key, passed
            FROM quality_gate_results
            WHERE variant_id = %s
            ORDER BY gate_key, created_at DESC
            """,
            (variant_id,),
        ).fetchall()
        latest = {str(row["gate_key"]): dict(row) for row in rows}
        failed = [
            key for key, definition in GATE_DEFINITIONS.items()
            if definition["is_blocking"]
            and (key not in latest or not latest[key].get("passed"))
        ]
        if failed:
            raise ValueError(f"尚未满足publish_ready门禁: {', '.join(failed)}")

    if new_status == "published":
        db.execute(
            "UPDATE publication_variants SET publication_status = %s, published_at = now(), updated_at = now() WHERE id = %s",
            (new_status, variant_id),
        )
    elif current == "published":
        db.execute(
            "UPDATE publication_variants SET publication_status = %s, published_at = NULL, updated_at = now() WHERE id = %s",
            (new_status, variant_id),
        )
    else:
        db.execute(
            "UPDATE publication_variants SET publication_status = %s, updated_at = now() WHERE id = %s",
            (new_status, variant_id),
        )
    return {"variant_id": variant_id, "old_status": current, "new_status": new_status}


# ── AI披露管理 ────────────────────────────────────────────────
def create_ai_disclosure(
    db,
    variant_id: str,
    chapter_id: Optional[str] = None,
    disclosure_text: str = "",
    ai_models_used: Optional[list[str]] = None,
    ai_usage_estimate: Optional[float] = None,
    generation_method: str = "auto",
    generated_by: Optional[str] = None,
) -> dict[str, Any]:
    """创建AI披露记录。"""
    if not get_variant(db, variant_id):
        raise ValueError(f"变体不存在: {variant_id}")
    record_id = _new_id()
    # 生成文本不等于人工确认；publish_ready 必须经过显式 confirm 接口。
    status = "generated" if disclosure_text.strip() else "pending"
    if generation_method not in {"auto", "manual", "provider", "template"}:
        raise ValueError(f"无效的AI披露生成方式: {generation_method}")
    db.execute(
        """
        INSERT INTO ai_disclosure_records
            (id, variant_id, chapter_id, disclosure_status, disclosure_text,
             generation_method, generated_by, ai_usage_estimate, ai_models_used)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (record_id, variant_id, chapter_id, status, disclosure_text, generation_method, generated_by,
         ai_usage_estimate, json.dumps(ai_models_used or [], ensure_ascii=False)),
    )
    # 同步更新变体的披露状态
    db.execute(
        "UPDATE publication_variants SET ai_disclosure_status = %s, ai_disclosure_text = %s, updated_at = now() WHERE id = %s",
        (status, disclosure_text, variant_id),
    )
    return {"disclosure_id": record_id, "status": status, "disclosure_text": disclosure_text}


def confirm_ai_disclosure(db, disclosure_id: str, confirmed_by: str = "user") -> dict[str, Any]:
    """人工确认AI披露。"""
    db.execute(
        """
        UPDATE ai_disclosure_records
        SET disclosure_status = 'confirmed', confirmed_by = %s, confirmed_at = now(), updated_at = now()
        WHERE id = %s AND NULLIF(BTRIM(disclosure_text), '') IS NOT NULL
        RETURNING variant_id
        """,
        (confirmed_by, disclosure_id),
    )
    row = db.fetchone()
    if not row:
        raise ValueError(f"AI披露记录不存在: {disclosure_id}")
    db.execute(
        "UPDATE publication_variants SET ai_disclosure_status = 'confirmed', updated_at = now() WHERE id = %s",
        (row["variant_id"],),
    )
    return {"disclosure_id": disclosure_id, "status": "confirmed"}


def generate_ai_disclosure_for_variant(
    db,
    variant_id: str,
    chapter_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """Generate a provider-backed disclosure draft and leave it unconfirmed."""
    row = db.execute(
        """
        SELECT v.*, n.project_id AS project_id
        FROM publication_variants v
        JOIN contents n ON n.id = v.novel_id AND n.type = 'novel' AND n.is_deleted = FALSE
        WHERE v.id = %s
        """,
        (variant_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"变体不存在: {variant_id}")
    variant = dict(row)
    profile = None
    if variant.get("platform_profile_id"):
        profile_row = db.execute(
            "SELECT * FROM platform_publication_profiles WHERE id = %s AND is_active = TRUE",
            (variant["platform_profile_id"],),
        ).fetchone()
        profile = dict(profile_row) if profile_row else None
    if profile is None:
        profile = get_platform_profile(db, str(variant["project_id"]), str(variant["platform"]))
    profile = profile or {}
    metadata = variant.get("extra_metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    draft = generate_disclosure_text(
        project_id=str(variant["project_id"]),
        variant_id=variant_id,
        variant_title=str(variant.get("title") or variant.get("variant_name") or ""),
        variant_synopsis=str(variant.get("synopsis") or ""),
        platform=str(variant.get("platform") or ""),
        ai_usage_policy=str(profile.get("ai_usage_policy") or "unknown"),
        source_models=metadata.get("source_models") if isinstance(metadata, dict) else None,
        chapter_context=str(chapter_id or ""),
        user_id=user_id,
    )
    record = create_ai_disclosure(
        db,
        variant_id=variant_id,
        chapter_id=chapter_id,
        disclosure_text=draft["disclosure_text"],
        ai_models_used=draft["ai_models_used"],
        ai_usage_estimate=draft["ai_usage_estimate"],
        generation_method="provider",
        generated_by=user_id,
    )
    return {**record, "rationale": draft.get("rationale", ""), "provenance": draft["provenance"]}


# ── 人工编辑记录 ──────────────────────────────────────────────
def record_human_editing(
    db,
    chapter_id: str,
    variant_id: Optional[str] = None,
    edit_type: str = "local_repair",
    before_sha256: str = "",
    after_sha256: str = "",
    repaired_sentences: Optional[list[int]] = None,
    repaired_paragraphs: Optional[list[int]] = None,
    chars_added: int = 0,
    chars_removed: int = 0,
    human_confirmed: bool = False,
    editor_name: str = "",
    editor_id: Optional[str] = None,
) -> dict[str, Any]:
    """记录人工编辑（用于allowed_with_human_editing政策）。"""
    record_id = _new_id()
    db.execute(
        """
        INSERT INTO human_editing_records
            (id, chapter_id, variant_id, editor_id, edit_type, repaired_sentence_indices,
             repaired_paragraph_indices, before_sha256, after_sha256,
             chars_added, chars_removed, human_confirmed, editor_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (record_id, chapter_id, variant_id, editor_id, edit_type,
         json.dumps(repaired_sentences or [], ensure_ascii=False),
         json.dumps(repaired_paragraphs or [], ensure_ascii=False),
         before_sha256, after_sha256, chars_added, chars_removed,
         human_confirmed, editor_name),
    )
    return {"editing_id": record_id}


def has_confirmed_human_editing(db, chapter_id: str, variant_id: Optional[str] = None) -> bool:
    """检查章节是否有已确认的人工编辑记录。"""
    if variant_id:
        row = db.execute(
            "SELECT COUNT(*) as cnt FROM human_editing_records WHERE chapter_id = %s AND variant_id = %s AND human_confirmed = TRUE",
            (chapter_id, variant_id),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT COUNT(*) as cnt FROM human_editing_records WHERE chapter_id = %s AND human_confirmed = TRUE",
            (chapter_id,),
        ).fetchone()
    return row["cnt"] > 0 if row else False


# ── 运行门禁并更新状态 ────────────────────────────────────────
def run_publishing_gates_for_chapter(
    db,
    chapter_id: str,
    text: str,
    variant_id: Optional[str] = None,
    project_id: Optional[str] = None,
    platform: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    existing_review_score: Optional[float] = None,
    external_score: Optional[float] = None,
    external_flagged: bool = False,
    user_id: Optional[str] = None,
) -> PublishingGateReport:
    """对章节运行七道门禁，保存结果，更新变体状态。"""
    # 获取平台配置
    platform_profile = None
    if project_id and platform:
        platform_profile = get_platform_profile(db, project_id, platform)

    # 获取变体元数据
    variant_meta = metadata or {}
    if variant_id:
        variant = get_variant(db, variant_id)
        if variant:
            variant_meta.update({
                "title": variant.get("title"),
                "synopsis": variant.get("synopsis"),
                "tags": variant.get("tags", []),
                "category": variant.get("category"),
            })
            external_flagged = external_flagged or variant.get("external_ai_flagged", False)
            external_score = external_score if external_score is not None else variant.get("external_ai_score")

    semantic_payoff = None
    if project_id and platform:
        # A configured publication run is intentionally provider-backed.  Any
        # missing route, provider outage, or malformed response propagates and
        # prevents a misleading quality result from being persisted.
        semantic_payoff = assess_payoff_semantically(
            project_id=str(project_id),
            chapter_id=str(chapter_id),
            text=text,
            platform=str(platform),
            user_id=user_id,
        )

    # 检查人工编辑
    human_editing_confirmed = has_confirmed_human_editing(db, chapter_id, variant_id)

    # 获取披露记录
    disclosure_record = None
    if variant_id:
        d_row = db.execute(
            "SELECT * FROM ai_disclosure_records WHERE variant_id = %s ORDER BY created_at DESC LIMIT 1",
            (variant_id,),
        ).fetchone()
        disclosure_record = dict(d_row) if d_row else None

    # 保存统计快照
    save_statistics_snapshot(db, chapter_id, text, variant_id)

    # 运行七道门
    report = run_all_gates(
        chapter_id=chapter_id,
        text=text,
        variant_id=variant_id,
        platform_profile=platform_profile,
        metadata=variant_meta,
        existing_review_score=existing_review_score,
        human_editing_confirmed=human_editing_confirmed,
        disclosure_record=disclosure_record,
        semantic_payoff=semantic_payoff,
        external_score=external_score,
        external_flagged=external_flagged,
    )

    # 保存门禁结果
    save_gate_results(db, report)

    # 更新变体状态
    if variant_id:
        gate_summary = {
            "overall_publish_ready": report.overall_publish_ready,
            "quality_candidate": report.quality_candidate,
            "blocking_failures": report.blocking_failures,
            "gate_scores": {k: {"passed": v.passed, "score": v.score} for k, v in report.gates.items()},
        }
        db.execute(
            """
            UPDATE publication_variants
            SET gate_summary = %s, last_gate_run_at = now(),
                external_ai_flagged = %s, external_ai_score = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (json.dumps(gate_summary, ensure_ascii=False), external_flagged, external_score, variant_id),
        )

        # 自动状态转换
        variant = get_variant(db, variant_id)
        current_status = variant["publication_status"] if variant else "draft"
        if report.overall_publish_ready and can_transition(current_status, "publish_ready"):
            update_variant_status(db, variant_id, "publish_ready")
        elif report.quality_candidate and can_transition(current_status, "quality_candidate"):
            update_variant_status(db, variant_id, "quality_candidate")

    return report


# ── 章节出版状态更新（contents表）────────────────────────────
def update_chapter_publishing_status(db, chapter_id: str, new_status: str) -> dict[str, Any]:
    """更新contents表的publishing_status字段。"""
    if new_status not in PUBLISHING_STATES:
        raise ValueError(f"无效状态: {new_status}")
    row = db.execute("SELECT id FROM contents WHERE id = %s", (chapter_id,)).fetchone()
    if not row:
        raise ValueError(f"章节不存在: {chapter_id}")
    db.execute(
        "UPDATE contents SET publishing_status = %s, updated_at = now() WHERE id = %s",
        (new_status, chapter_id),
    )
    return {"chapter_id": chapter_id, "publishing_status": new_status}
