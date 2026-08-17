"""publishing — v0.9.2 发布准备API

七道门禁、发布变体、AI披露、统计快照、局部修复。
"""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.config import require_admin, require_admin_reads
from app.db import connect, encode, decode
from app.core.authz import ensure_project_member, ok, require_member

from app.v7.quality.statistics_v1 import compute_statistics
from app.v7.quality.publishing_gates import run_all_gates, GATE_DEFINITIONS
from app.v7.quality.local_repair import detect_risk_sentences, local_repair_pipeline
from app.v7.services.publishing_service import (
    can_transition,
    create_ai_disclosure,
    create_platform_profile,
    create_publication_variant,
    confirm_ai_disclosure,
    get_platform_profile,
    get_variant,
    generate_ai_disclosure_for_variant,
    has_confirmed_human_editing,
    record_human_editing,
    run_publishing_gates_for_chapter,
    save_statistics_snapshot,
    update_chapter_publishing_status,
    update_variant_status,
)

router = APIRouter(prefix="/api/v1/publishing", tags=["publishing"])


# ── 请求模型 ──────────────────────────────────────────────────
class StatisticsRequest(BaseModel):
    text: str = Field(min_length=1)


class GateRunRequest(BaseModel):
    chapter_id: str
    text: str = Field(min_length=1)
    variant_id: Optional[str] = None
    project_id: Optional[str] = None
    platform: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    existing_review_score: Optional[float] = None
    external_score: Optional[float] = None
    external_flagged: bool = False


class VariantCreateRequest(BaseModel):
    novel_id: str
    platform: str = Field(min_length=1, max_length=50)
    variant_name: str = Field(min_length=1, max_length=200)
    platform_profile_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class VariantStatusRequest(BaseModel):
    new_status: str = Field(pattern=r"^(draft|quality_candidate|publish_ready|published|rejected)$")


class PlatformProfileCreateRequest(BaseModel):
    project_id: str
    platform: str
    profile_name: str
    policy_status: Optional[str] = "unknown"
    policy_version: Optional[str] = ""
    ai_usage_policy: Optional[str] = "unknown"
    word_count_min: Optional[int] = None
    word_count_max: Optional[int] = None
    chapter_word_min: Optional[int] = None
    chapter_word_max: Optional[int] = None
    extra_metadata: Optional[dict[str, Any]] = None


class DisclosureCreateRequest(BaseModel):
    variant_id: str
    chapter_id: Optional[str] = None
    disclosure_text: str = ""
    ai_models_used: Optional[list[str]] = None
    ai_usage_estimate: Optional[float] = None


class DisclosureGenerateRequest(BaseModel):
    variant_id: str
    chapter_id: Optional[str] = None


class HumanEditingRequest(BaseModel):
    chapter_id: str
    variant_id: Optional[str] = None
    edit_type: str = "local_repair"
    before_sha256: str = ""
    after_sha256: str = ""
    repaired_sentences: Optional[list[int]] = None
    repaired_paragraphs: Optional[list[int]] = None
    chars_added: int = 0
    chars_removed: int = 0
    human_confirmed: bool = False
    editor_name: str = ""


class LocalRepairRequest(BaseModel):
    text: str = Field(min_length=1)
    max_rounds: int = Field(default=3, ge=1, le=5)
    max_repairs_per_round: int = Field(default=3, ge=1, le=5)


def _load_chapter_scope(db, chapter_id: str, user: dict, *, write: bool) -> dict[str, Any]:
    """Resolve a chapter and enforce its owning project scope."""
    row = db.execute(
        """SELECT id, project_id, parent_id, type
           FROM contents
           WHERE id=%s AND is_deleted=FALSE""",
        (chapter_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="chapter not found")
    chapter = dict(row)
    if chapter.get("type") != "chapter":
        raise HTTPException(status_code=400, detail="content is not a chapter")
    require_member(db, str(chapter["project_id"]), user, write=write)
    return chapter


def _load_variant_scope(db, variant_id: str, user: dict, *, write: bool) -> dict[str, Any]:
    """Resolve a variant through its novel and enforce project scope."""
    row = db.execute(
        """SELECT v.*, n.project_id AS novel_project_id, n.type AS novel_type
           FROM publication_variants v
           JOIN contents n ON n.id=v.novel_id AND n.type='novel' AND n.is_deleted=FALSE
           WHERE v.id=%s""",
        (variant_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="变体不存在")
    variant = dict(row)
    require_member(db, str(variant["novel_project_id"]), user, write=write)
    return variant


def _assert_variant_chapter_scope(
    chapter: dict[str, Any], variant: dict[str, Any], chapter_id: str
) -> None:
    if str(chapter.get("parent_id") or "") != str(variant.get("novel_id") or ""):
        raise HTTPException(status_code=409, detail="章节与发布变体不属于同一作品")


def _load_disclosure_scope(db, disclosure_id: str, user: dict, *, write: bool) -> dict[str, Any]:
    row = db.execute(
        """SELECT d.id, d.variant_id, v.novel_id, n.project_id
           FROM ai_disclosure_records d
           JOIN publication_variants v ON v.id=d.variant_id
           JOIN contents n ON n.id=v.novel_id AND n.type='novel' AND n.is_deleted=FALSE
           WHERE d.id=%s""",
        (disclosure_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="AI披露记录不存在")
    disclosure = dict(row)
    require_member(db, str(disclosure["project_id"]), user, write=write)
    return disclosure


# ── 统计快照 ──────────────────────────────────────────────────
@router.post("/statistics")
def compute_chapter_statistics(req: StatisticsRequest, user: dict = Depends(require_admin_reads)):
    """计算章节确定性统计。"""
    stats = compute_statistics(req.text)
    return ok(stats.to_dict(), message="统计计算完成")


@router.post("/statistics/save/{chapter_id}")
def save_chapter_statistics(chapter_id: str, req: StatisticsRequest, user: dict = Depends(require_admin)):
    """计算并保存章节统计快照。"""
    db = connect()
    try:
        _load_chapter_scope(db, chapter_id, user, write=True)
        result = save_statistics_snapshot(db, chapter_id, req.text)
        db.commit()
        return ok(result, message="统计快照已保存")
    finally:
        db.close()


# ── 七道门禁 ──────────────────────────────────────────────────
@router.get("/gates/definitions")
def get_gate_definitions(user: dict = Depends(require_admin_reads)):
    """获取七道门禁定义。"""
    return ok(GATE_DEFINITIONS, message="门禁定义")


@router.post("/gates/run")
def run_publishing_gates(req: GateRunRequest, user: dict = Depends(require_admin)):
    """运行七道发布准备门禁，保存结果并更新状态。"""
    db = connect()
    try:
        chapter = _load_chapter_scope(db, req.chapter_id, user, write=True)
        chapter_project_id = str(chapter["project_id"])
        if req.project_id and str(req.project_id) != chapter_project_id:
            raise HTTPException(status_code=409, detail="章节与项目不属于同一范围")
        if req.variant_id:
            variant = _load_variant_scope(db, req.variant_id, user, write=True)
            _assert_variant_chapter_scope(chapter, variant, req.chapter_id)
        report = run_publishing_gates_for_chapter(
            db=db,
            chapter_id=req.chapter_id,
            text=req.text,
            variant_id=req.variant_id,
            project_id=req.project_id or chapter_project_id,
            platform=req.platform,
            metadata=req.metadata,
            existing_review_score=req.existing_review_score,
            external_score=req.external_score,
            external_flagged=req.external_flagged,
            user_id=user.get("id"),
        )
        db.commit()
        return ok(report.to_dict(), message="七道门禁运行完成")
    finally:
        db.close()


@router.get("/gates/results/{chapter_id}")
def get_gate_results(chapter_id: str, variant_id: Optional[str] = None, user: dict = Depends(require_admin_reads)):
    """获取章节最新门禁结果。"""
    db = connect()
    try:
        chapter = _load_chapter_scope(db, chapter_id, user, write=False)
        if variant_id:
            variant = _load_variant_scope(db, variant_id, user, write=False)
            _assert_variant_chapter_scope(chapter, variant, chapter_id)
        if variant_id:
            rows = db.execute(
                "SELECT * FROM quality_gate_results WHERE chapter_id = %s AND variant_id = %s ORDER BY created_at DESC",
                (chapter_id, variant_id),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM quality_gate_results WHERE chapter_id = %s ORDER BY created_at DESC",
                (chapter_id,),
            ).fetchall()
        results = [dict(r) for r in rows]
        return ok({"results": results, "count": len(results)}, message="门禁结果")
    finally:
        db.close()


# ── 平台配置 ──────────────────────────────────────────────────
@router.get("/platform-profiles")
def list_platform_profiles(project_id: str, user: dict = Depends(require_admin_reads)):
    """列出项目的平台发布配置。"""
    db = connect()
    try:
        ensure_project_member(db, project_id, user)
        rows = db.execute(
            "SELECT * FROM platform_publication_profiles WHERE project_id = %s AND is_active = TRUE ORDER BY platform, profile_name",
            (project_id,),
        ).fetchall()
        return ok({"profiles": [dict(r) for r in rows], "count": len(rows)}, message="平台配置列表")
    finally:
        db.close()


@router.post("/platform-profiles")
def create_platform_profile_api(req: PlatformProfileCreateRequest, user: dict = Depends(require_admin)):
    """创建平台发布配置。"""
    db = connect()
    try:
        ensure_project_member(db, req.project_id, user, {"owner", "editor"})
        extra_metadata = dict(req.extra_metadata or {})
        # Keep policy_version a first-class field even if an older client sent
        # it inside extra_metadata.
        extra_metadata.pop("policy_version", None)
        result = create_platform_profile(
            db, req.project_id, req.platform, req.profile_name,
            policy_status=req.policy_status,
            policy_version=req.policy_version,
            ai_usage_policy=req.ai_usage_policy,
            word_count_min=req.word_count_min,
            word_count_max=req.word_count_max,
            chapter_word_min=req.chapter_word_min,
            chapter_word_max=req.chapter_word_max,
            **extra_metadata,
        )
        db.commit()
        return ok(result, message="平台配置已创建")
    finally:
        db.close()


# ── 发布变体 ──────────────────────────────────────────────────
@router.post("/variants")
def create_variant_api(req: VariantCreateRequest, user: dict = Depends(require_admin)):
    """为基础小说创建平台发布变体。"""
    db = connect()
    try:
        novel = db.execute(
            "SELECT project_id, type FROM contents WHERE id=%s AND type='novel' AND is_deleted=FALSE",
            (req.novel_id,),
        ).fetchone()
        if not novel:
            raise HTTPException(status_code=404, detail="novel not found")
        ensure_project_member(db, str(novel["project_id"]), user, {"owner", "editor"})
        if req.platform_profile_id:
            profile = db.execute(
                "SELECT project_id, platform FROM platform_publication_profiles WHERE id=%s AND is_active=TRUE",
                (req.platform_profile_id,),
            ).fetchone()
            if not profile:
                raise HTTPException(status_code=404, detail="platform profile not found")
            if str(profile["project_id"]) != str(novel["project_id"]):
                raise HTTPException(status_code=409, detail="平台配置与小说不属于同一项目")
            if str(profile["platform"]) != req.platform:
                raise HTTPException(status_code=409, detail="平台配置与变体平台不一致")
        result = create_publication_variant(
            db, req.novel_id, req.platform, req.variant_name,
            req.platform_profile_id, req.metadata,
        )
        db.commit()
        return ok(result, message="发布变体已创建")
    finally:
        db.close()


@router.get("/variants/{variant_id}")
def get_variant_api(variant_id: str, user: dict = Depends(require_admin_reads)):
    """获取发布变体详情。"""
    db = connect()
    try:
        _load_variant_scope(db, variant_id, user, write=False)
        variant = get_variant(db, variant_id)
        if not variant:
            raise HTTPException(status_code=404, detail="变体不存在")
        return ok(variant, message="变体详情")
    finally:
        db.close()


@router.get("/variants/novel/{novel_id}")
def list_variants_by_novel(novel_id: str, user: dict = Depends(require_admin_reads)):
    """列出小说的所有发布变体。"""
    db = connect()
    try:
        novel = db.execute(
            "SELECT project_id FROM contents WHERE id=%s AND type='novel' AND is_deleted=FALSE",
            (novel_id,),
        ).fetchone()
        if not novel:
            raise HTTPException(status_code=404, detail="novel not found")
        ensure_project_member(db, str(novel["project_id"]), user)
        rows = db.execute(
            "SELECT * FROM publication_variants WHERE novel_id = %s ORDER BY platform, variant_name",
            (novel_id,),
        ).fetchall()
        return ok({"variants": [dict(r) for r in rows], "count": len(rows)}, message="变体列表")
    finally:
        db.close()


@router.post("/variants/{variant_id}/status")
def update_variant_status_api(variant_id: str, req: VariantStatusRequest, user: dict = Depends(require_admin)):
    """更新变体发布状态（带状态机校验）。"""
    db = connect()
    try:
        _load_variant_scope(db, variant_id, user, write=True)
        result = update_variant_status(db, variant_id, req.new_status)
        db.commit()
        return ok(result, message="状态已更新")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


# ── AI披露 ────────────────────────────────────────────────────
@router.post("/disclosures")
def create_disclosure_api(req: DisclosureCreateRequest, user: dict = Depends(require_admin)):
    """创建AI披露记录。"""
    db = connect()
    try:
        variant = _load_variant_scope(db, req.variant_id, user, write=True)
        if req.chapter_id:
            chapter = _load_chapter_scope(db, req.chapter_id, user, write=True)
            _assert_variant_chapter_scope(chapter, variant, req.chapter_id)
        result = create_ai_disclosure(
            db, req.variant_id, req.chapter_id,
            req.disclosure_text, req.ai_models_used, req.ai_usage_estimate,
            generation_method="manual",
            generated_by=user.get("id"),
        )
        db.commit()
        return ok(result, message="AI披露记录已创建")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@router.post("/disclosures/generate")
def generate_disclosure_api(req: DisclosureGenerateRequest, user: dict = Depends(require_admin)):
    """通过真实Provider生成AI披露草稿；不会自动确认。"""
    db = connect()
    try:
        variant = _load_variant_scope(db, req.variant_id, user, write=True)
        if req.chapter_id:
            chapter = _load_chapter_scope(db, req.chapter_id, user, write=True)
            _assert_variant_chapter_scope(chapter, variant, req.chapter_id)
        result = generate_ai_disclosure_for_variant(
            db,
            variant_id=req.variant_id,
            chapter_id=req.chapter_id,
            user_id=user.get("id"),
        )
        db.commit()
        return ok(result, message="AI披露草稿已生成，待人工确认")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@router.get("/disclosures/variant/{variant_id}")
def get_latest_disclosure_api(variant_id: str, user: dict = Depends(require_admin_reads)):
    """读取变体最新披露记录，供发布准备页恢复确认流程。"""
    db = connect()
    try:
        _load_variant_scope(db, variant_id, user, write=False)
        row = db.execute(
            "SELECT id AS disclosure_id, disclosure_status, disclosure_text FROM ai_disclosure_records WHERE variant_id = %s ORDER BY created_at DESC LIMIT 1",
            (variant_id,),
        ).fetchone()
        return ok(dict(row) if row else {}, message="最新AI披露")
    finally:
        db.close()


@router.post("/disclosures/{disclosure_id}/confirm")
def confirm_disclosure_api(disclosure_id: str, user: dict = Depends(require_admin)):
    """人工确认AI披露。"""
    db = connect()
    try:
        _load_disclosure_scope(db, disclosure_id, user, write=True)
        result = confirm_ai_disclosure(db, disclosure_id, user.get("email", "user"))
        db.commit()
        return ok(result, message="AI披露已确认")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        db.close()


# ── 人工编辑记录 ──────────────────────────────────────────────
@router.post("/human-editing")
def record_human_editing_api(req: HumanEditingRequest, user: dict = Depends(require_admin)):
    """记录人工编辑（用于allowed_with_human_editing政策）。"""
    db = connect()
    try:
        chapter = _load_chapter_scope(db, req.chapter_id, user, write=True)
        if req.variant_id:
            variant = _load_variant_scope(db, req.variant_id, user, write=True)
            _assert_variant_chapter_scope(chapter, variant, req.chapter_id)
        result = record_human_editing(
            db, req.chapter_id, req.variant_id, req.edit_type,
            req.before_sha256, req.after_sha256,
            req.repaired_sentences, req.repaired_paragraphs,
            req.chars_added, req.chars_removed,
            req.human_confirmed, req.editor_name or user.get("email", ""),
            user.get("id"),
        )
        db.commit()
        return ok(result, message="人工编辑记录已保存")
    finally:
        db.close()


# ── 局部修复 ──────────────────────────────────────────────────
@router.post("/local-repair/detect")
def detect_risks_api(req: StatisticsRequest, user: dict = Depends(require_admin_reads)):
    """检测风险句子。"""
    stats = compute_statistics(req.text)
    risks = detect_risk_sentences(req.text, stats)
    return ok({
        "risks": [r.__dict__ for r in risks],
        "count": len(risks),
    }, message="风险检测完成")


@router.post("/local-repair/run")
def run_local_repair_api(req: LocalRepairRequest, user: dict = Depends(require_admin)):
    """运行局部修复流水线（规则级，AI修复由调用方注入）。"""
    result = local_repair_pipeline(
        req.text,
        max_rounds=req.max_rounds,
        max_repairs_per_round=req.max_repairs_per_round,
    )
    return ok(result.to_dict(), message="局部修复完成")


# ── 章节出版状态 ──────────────────────────────────────────────
@router.post("/chapters/{chapter_id}/publishing-status")
def update_chapter_status_api(
    chapter_id: str,
    req: VariantStatusRequest,
    user: dict = Depends(require_admin),
):
    """更新章节出版准备状态。"""
    db = connect()
    try:
        _load_chapter_scope(db, chapter_id, user, write=True)
        result = update_chapter_publishing_status(db, chapter_id, req.new_status)
        db.commit()
        return ok(result, message="章节出版状态已更新")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


# ── 发布就绪检查 ──────────────────────────────────────────────
@router.get("/variants/{variant_id}/publish-readiness")
def check_publish_readiness(variant_id: str, user: dict = Depends(require_admin_reads)):
    """检查变体是否满足publish_ready条件。"""
    db = connect()
    try:
        _load_variant_scope(db, variant_id, user, write=False)
        variant = get_variant(db, variant_id)
        if not variant:
            raise HTTPException(status_code=404, detail="变体不存在")

        # 获取最新门禁结果
        gate_rows = db.execute(
            """
            SELECT DISTINCT ON (gate_key) *
            FROM quality_gate_results
            WHERE variant_id = %s
            ORDER BY gate_key, created_at DESC
            """,
            (variant_id,),
        ).fetchall()

        gates = {r["gate_key"]: dict(r) for r in gate_rows}
        blocking_failures = [
            k for k, g in gates.items()
            if g.get("is_blocking", True) and not g.get("passed", False)
        ]

        # 检查AI披露
        ai_ok = variant.get("ai_disclosure_status") in ("confirmed", "not_required")

        # 检查平台规则状态
        platform_ok = True
        if variant.get("platform_profile_id"):
            profile = db.execute(
                "SELECT policy_status FROM platform_publication_profiles WHERE id = %s",
                (variant["platform_profile_id"],),
            ).fetchone()
            if profile and profile["policy_status"] != "confirmed":
                platform_ok = False

        ready = len(blocking_failures) == 0 and ai_ok and platform_ok and variant.get("publication_status") == "publish_ready"

        return ok({
            "variant_id": variant_id,
            "publication_status": variant.get("publication_status"),
            "publish_ready": ready,
            "blocking_failures": blocking_failures,
            "ai_disclosure_status": variant.get("ai_disclosure_status"),
            "platform_policy_confirmed": platform_ok,
            "external_ai_flagged": variant.get("external_ai_flagged", False),
            "external_ai_score": variant.get("external_ai_score"),
            "gate_summary": variant.get("gate_summary", {}),
        }, message="发布就绪检查完成")
    finally:
        db.close()
