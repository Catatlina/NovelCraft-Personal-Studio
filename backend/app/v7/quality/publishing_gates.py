"""publishing_gates — v0.9.2 七道发布准备门禁

七道顶层门禁：
1. content_quality    内容质量（基础质量分）
2. continuity         连续性（人物/时间线/物品状态）
3. payoff_density     爽点密度（可见兑现/反馈/下一章压力）
4. readability        可读性（句段节奏/段落肌理/对话比例）
5. platform_compliance 平台合规（平台规则 + 元数据完整性 + 元数据质量）
6. ai_disclosure      AI披露合规（按平台政策阻断）
7. external_risk      外部AI检测风险（按作品策略记录或阻断）

关键规则：
- quality_candidate：七项门禁均已输出，但不要求全部通过。
- publish_ready：所有 is_blocking=TRUE 的门禁必须通过；外部硬门配置开启时必须满足95/5/0。
- 生成完成 ≠ reviewed；内部审核通过 ≠ publish_ready；publish_ready ≠ 自动发布。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from .statistics_v1 import compute_statistics, StatisticsResult


# ── 门禁定义 ──────────────────────────────────────────────────
GATE_DEFINITIONS = {
    "content_quality": {
        "name": "内容质量",
        "is_blocking": True,
        "default_threshold": 60.0,
        "description": "基础内容质量评分，低于阈值不可发布",
    },
    "continuity": {
        "name": "连续性",
        "is_blocking": True,
        "default_threshold": 0.0,  # 0个致命错误
        "description": "人物位置/时间线/物品状态无致命矛盾",
    },
    "payoff_density": {
        "name": "爽点密度",
        "is_blocking": True,
        "default_threshold": 1.0,  # 每章至少1个可见兑现
        "description": "每章至少一个可见结果、人物反馈和下一章压力",
    },
    "readability": {
        "name": "可读性",
        "is_blocking": True,
        "default_threshold": 0.0,  # 0个致命可读性问题
        "description": "句段节奏合理，无大面积异常标点或超长句",
    },
    "platform_compliance": {
        "name": "平台合规",
        "is_blocking": True,
        "default_threshold": 0.0,
        "description": "平台规则通过 + 元数据完整 + 元数据质量达标",
        "sub_gates": ["platform_rules", "metadata_completeness", "metadata_quality"],
    },
    "ai_disclosure": {
        "name": "AI披露合规",
        "is_blocking": True,
        "default_threshold": 0.0,
        "description": "按平台AI政策完成披露或人工编辑确认",
    },
    "external_risk": {
        "name": "外部检测风险",
        "is_blocking": False,  # 默认不阻断，平台禁止AI时才阻断
        "default_threshold": 80.0,
        "description": "按作品策略记录或阻断；硬门要求人工特征≥95、疑似AI≤5、AI特征=0",
    },
}


@dataclass
class GateResult:
    """单道门禁结果。"""
    gate_key: str
    gate_name: str
    passed: bool
    score: Optional[float] = None
    threshold: Optional[float] = None
    is_blocking: bool = True
    sub_gates: dict[str, Any] = field(default_factory=dict)
    issues: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    runner: str = "system"
    gate_version: str = "v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PublishingGateReport:
    """七道门门禁综合报告。"""
    chapter_id: str
    variant_id: Optional[str]
    content_sha256: str
    overall_publish_ready: bool
    quality_candidate: bool  # 七项均已输出
    gates: dict[str, GateResult] = field(default_factory=dict)
    blocking_failures: list[str] = field(default_factory=list)
    non_blocking_warnings: list[str] = field(default_factory=list)
    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_id": self.chapter_id,
            "variant_id": self.variant_id,
            "content_sha256": self.content_sha256,
            "overall_publish_ready": self.overall_publish_ready,
            "quality_candidate": self.quality_candidate,
            "gates": {k: v.to_dict() for k, v in self.gates.items()},
            "blocking_failures": self.blocking_failures,
            "non_blocking_warnings": self.non_blocking_warnings,
            "computed_at": self.computed_at,
        }


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── 门禁1：内容质量 ──────────────────────────────────────────
def gate_content_quality(
    text: str,
    stats: StatisticsResult,
    existing_review_score: Optional[float] = None,
    threshold: float = 60.0,
) -> GateResult:
    """内容质量门禁。优先使用已有V7审阅分，无则用统计启发式。"""
    issues = []
    score = existing_review_score

    if score is None:
        # 启发式评分（仅作占位，真实质量需V7审阅引擎）
        char_count = stats.total_chars
        anomaly_ratio = len(stats.global_anomalies) / max(char_count, 1)
        dialogue_ratio = stats.total_dialogue_chars / max(char_count, 1)
        # 基础分60，对话比例合理+10，异常少+10，字数足够+10
        score = 60.0
        if 0.15 <= dialogue_ratio <= 0.5:
            score += 10
        if anomaly_ratio < 0.001:
            score += 10
        if char_count >= 1500:
            score += 10
        score = min(score, 95.0)

    if char_count := stats.total_chars:
        if char_count < 500:
            issues.append({"type": "too_short", "message": f"章节字数{char_count}过少"})

    passed = score >= threshold and not any(i["type"] == "too_short" for i in issues)

    return GateResult(
        gate_key="content_quality",
        gate_name=GATE_DEFINITIONS["content_quality"]["name"],
        passed=passed,
        score=round(score, 2),
        threshold=threshold,
        is_blocking=True,
        issues=issues,
        evidence={"char_count": stats.total_chars, "review_score_used": existing_review_score is not None},
    )


# ── 门禁2：连续性 ────────────────────────────────────────────
def gate_continuity(
    text: str,
    stats: StatisticsResult,
    continuity_errors: Optional[list[dict[str, Any]]] = None,
) -> GateResult:
    """连续性门禁。致命错误数=0则通过。"""
    errors = continuity_errors or []
    fatal = [e for e in errors if e.get("severity") == "fatal"]
    warnings = [e for e in errors if e.get("severity") != "fatal"]

    return GateResult(
        gate_key="continuity",
        gate_name=GATE_DEFINITIONS["continuity"]["name"],
        passed=len(fatal) == 0,
        score=float(len(fatal)),
        threshold=0.0,
        is_blocking=True,
        issues=fatal,
        warnings=warnings,
        evidence={"fatal_count": len(fatal), "warning_count": len(warnings)},
    )


# ── 门禁3：爽点密度 ──────────────────────────────────────────
def gate_payoff_density(
    text: str,
    stats: StatisticsResult,
    payoff_markers: Optional[list[str]] = None,
    semantic_assessment: Optional[dict[str, Any]] = None,
) -> GateResult:
    """爽点密度门禁。

    Configured publication runs must provide a validated provider assessment;
    the deterministic keyword path remains available only to legacy callers and
    isolated unit tests that do not have project/platform context.
    """
    if semantic_assessment is not None:
        return _gate_semantic_payoff(semantic_assessment)

    issues = []
    # 启发式：检测结果类词汇
    result_patterns = [
        r"终于", r"成功", r"获得", r"得到", r"拿下", r"突破", r"晋升",
        r"震惊", r"惊呆", r"不敢相信", r"原来是", r"竟然", r"果然",
    ]
    found = []
    for pat in result_patterns:
        if re.search(pat, text):
            found.append(pat)

    marker_count = len(payoff_markers) if payoff_markers else len(found)
    if marker_count == 0:
        issues.append({"type": "no_visible_payoff", "message": "本章未检测到可见兑现标记"})

    # 检查章末是否有悬念/压力
    last_paragraph = ""
    if stats.chapters and stats.chapters[0].paragraphs:
        # 简化：取正文末尾
        last_chars = text[-200:]
        suspense_patterns = [r"但是", r"然而", r"就在这时", r"突然", r"没想到", r"下一章"]
        has_suspense = any(re.search(p, last_chars) for p in suspense_patterns)
    else:
        has_suspense = False

    if not has_suspense:
        issues.append({"type": "no_next_chapter_pressure", "message": "章末缺少下一章压力或悬念"})

    passed = marker_count >= 1 and has_suspense

    return GateResult(
        gate_key="payoff_density",
        gate_name=GATE_DEFINITIONS["payoff_density"]["name"],
        passed=passed,
        score=float(marker_count),
        threshold=1.0,
        is_blocking=True,
        issues=issues,
        evidence={"payoff_markers": found[:10], "has_suspense_ending": has_suspense},
    )


def _gate_semantic_payoff(assessment: dict[str, Any]) -> GateResult:
    """Turn a provider assessment into a fail-closed gate result."""
    issues: list[dict[str, Any]] = []
    try:
        payoff_count = int(assessment.get("payoff_count", -1))
        payoffs = assessment.get("payoffs")
        semantic_score = float(assessment.get("semantic_score", -1))
        ending_pressure = bool(assessment.get("ending_pressure"))
    except (TypeError, ValueError):
        payoff_count, payoffs, semantic_score, ending_pressure = -1, None, -1.0, False

    valid_evidence = isinstance(payoffs, list) and payoff_count == len(payoffs)
    if not valid_evidence:
        issues.append({"type": "invalid_semantic_evidence", "message": "Provider语义证据结构无效"})
    if payoff_count < 1:
        issues.append({"type": "no_semantic_payoff", "message": "Provider未确认本章有具体兑现结果"})
    if not ending_pressure:
        issues.append({"type": "no_next_chapter_pressure", "message": "Provider未确认章末存在下一章压力"})
    if semantic_score < 60:
        issues.append({"type": "semantic_score_below_threshold", "message": "Provider语义爽点评分低于60"})
    if valid_evidence:
        for item in payoffs:
            if not isinstance(item, dict) or any(
                not str(item.get(key) or "").strip()
                for key in ("event", "evidence_quote", "reader_effect", "consequence")
            ):
                issues.append({"type": "missing_payoff_evidence", "message": "Provider payoff 缺少事件、原文证据或后果"})
                valid_evidence = False
                break

    passed = valid_evidence and payoff_count >= 1 and ending_pressure and semantic_score >= 60
    return GateResult(
        gate_key="payoff_density",
        gate_name=GATE_DEFINITIONS["payoff_density"]["name"],
        passed=passed,
        score=semantic_score if semantic_score >= 0 else 0.0,
        threshold=60.0,
        is_blocking=True,
        issues=issues,
        evidence={
            "mode": "semantic_provider",
            "payoff_count": payoff_count,
            "payoffs": payoffs if isinstance(payoffs, list) else [],
            "ending_pressure": ending_pressure,
            "semantic_score": semantic_score,
            "rationale": str(assessment.get("rationale") or ""),
            "provenance": assessment.get("provenance", {}),
        },
        runner="v6.gateway",
        gate_version="v1.1",
    )


# ── 门禁4：可读性 ────────────────────────────────────────────
def gate_readability(
    text: str,
    stats: StatisticsResult,
) -> GateResult:
    """可读性门禁。检查异常标点、超长句、对话比例。"""
    issues = []
    warnings = []

    # 异常标点
    fatal_anomalies = [a for a in stats.global_anomalies
                       if a["type"] in ("重复句末标点", "重复逗号顿号", "不可见/异常字符")]
    if fatal_anomalies:
        issues.append({"type": "anomalous_punctuation", "message": f"发现{len(fatal_anomalies)}处异常标点", "count": len(fatal_anomalies)})

    # 超长句（>100字）
    long_sentences = []
    for ch in stats.chapters:
        for s in ch.sentences:
            if s["char_count"] > 100:
                long_sentences.append(s)
    if long_sentences:
        warnings.append({"type": "long_sentences", "message": f"发现{len(long_sentences)}个超长句(>100字)", "count": len(long_sentences)})

    # 对话比例
    if stats.total_chars > 0:
        dialogue_ratio = stats.total_dialogue_chars / stats.total_chars
        if dialogue_ratio > 0.7:
            issues.append({"type": "too_much_dialogue", "message": f"对话占比{dialogue_ratio:.1%}过高"})
        elif dialogue_ratio < 0.05 and stats.total_chars > 1000:
            warnings.append({"type": "too_little_dialogue", "message": f"对话占比{dialogue_ratio:.1%}过低"})

    # 平均句长
    avg_len = stats.chapters[0].avg_sentence_length if stats.chapters else 0
    if avg_len > 60:
        warnings.append({"type": "high_avg_sentence_length", "message": f"平均句长{avg_len:.1f}字偏长"})

    passed = len(issues) == 0

    return GateResult(
        gate_key="readability",
        gate_name=GATE_DEFINITIONS["readability"]["name"],
        passed=passed,
        score=float(len(issues)),
        threshold=0.0,
        is_blocking=True,
        issues=issues,
        warnings=warnings,
        evidence={
            "anomaly_count": len(stats.global_anomalies),
            "avg_sentence_length": avg_len,
            "dialogue_ratio": round(stats.total_dialogue_chars / max(stats.total_chars, 1), 4),
        },
    )


# ── 门禁5：平台合规（含三子门禁）────────────────────────────
def gate_platform_compliance(
    text: str,
    stats: StatisticsResult,
    platform_profile: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> GateResult:
    """平台合规门禁：平台规则 + 元数据完整性 + 元数据质量。"""
    sub_gates: dict[str, Any] = {}
    issues = []
    profile = platform_profile or {}
    meta = metadata or {}

    # 子门禁5a：平台规则
    platform_rules_passed = True
    platform_rules_issues = []
    policy_status = profile.get("policy_status", "unknown")
    if policy_status in ("stale", "unknown"):
        platform_rules_passed = False
        platform_rules_issues.append({
            "type": "policy_not_confirmed",
            "message": f"平台规则状态为{policy_status}，必须confirmed才能publish_ready",
        })

    # 字数检查
    ch_word_min = profile.get("chapter_word_min")
    ch_word_max = profile.get("chapter_word_max")
    if ch_word_min and stats.total_chars < ch_word_min:
        platform_rules_passed = False
        platform_rules_issues.append({"type": "chapter_too_short", "message": f"章节{stats.total_chars}字低于平台最低{ch_word_min}字"})
    if ch_word_max and stats.total_chars > ch_word_max:
        platform_rules_passed = False
        platform_rules_issues.append({"type": "chapter_too_long", "message": f"章节{stats.total_chars}字超过平台最高{ch_word_max}字"})

    sub_gates["platform_rules"] = {
        "passed": platform_rules_passed,
        "issues": platform_rules_issues,
        "policy_status": policy_status,
    }

    # 子门禁5b：元数据完整性
    metadata_completeness_passed = True
    metadata_issues = []
    required_fields = ["title", "synopsis", "tags", "category"]
    for f in required_fields:
        if not meta.get(f):
            metadata_completeness_passed = False
            metadata_issues.append({"type": "missing_metadata", "field": f, "message": f"缺少必填元数据：{f}"})
    sub_gates["metadata_completeness"] = {
        "passed": metadata_completeness_passed,
        "issues": metadata_issues,
    }

    # 子门禁5c：元数据质量
    metadata_quality_passed = True
    quality_issues = []
    title = meta.get("title", "")
    synopsis = meta.get("synopsis", "")
    tags = meta.get("tags", [])
    has_conflict = False
    has_protagonist = False

    # 书名点击欲（简单启发：长度2-10字，含冲突/悬念词）
    if len(title) < 2 or len(title) > 20:
        metadata_quality_passed = False
        quality_issues.append({"type": "title_length", "message": f"书名长度{len(title)}不合规"})

    # 简介含核心冲突和主角设定
    if synopsis:
        has_conflict = any(w in synopsis for w in ["冲突", "对抗", "危机", "挑战", "复仇", "逆袭", "崛起", "斗争"])
        has_protagonist = any(w in synopsis for w in ["他", "她", "主角", "少年", "重生", "穿越", "系统"])
        if not has_conflict:
            quality_issues.append({"type": "synopsis_no_conflict", "message": "简介未明确核心冲突"})
            metadata_quality_passed = False
        if not has_protagonist:
            quality_issues.append({"type": "synopsis_no_protagonist", "message": "简介未明确主角设定"})
            metadata_quality_passed = False
    else:
        metadata_quality_passed = False

    # 标签与正文匹配（启发式：标签词出现在正文中）
    if tags and isinstance(tags, list):
        matched = sum(1 for t in tags if t in text)
        if matched == 0:
            quality_issues.append({"type": "tags_not_matching", "message": "标签关键词未在正文中出现"})

    # 章节标题符合平台规则
    chapter_title = stats.chapters[0].title if stats.chapters else ""
    if chapter_title and len(chapter_title) > 30:
        quality_issues.append({"type": "chapter_title_too_long", "message": "章节标题过长"})

    sub_gates["metadata_quality"] = {
        "passed": metadata_quality_passed,
        "issues": quality_issues,
        "title_clickiness_score": min(100, len(title) * 5 + (10 if has_conflict else 0)) if title else 0,
    }

    all_passed = platform_rules_passed and metadata_completeness_passed and metadata_quality_passed
    issues = platform_rules_issues + metadata_issues + quality_issues

    return GateResult(
        gate_key="platform_compliance",
        gate_name=GATE_DEFINITIONS["platform_compliance"]["name"],
        passed=all_passed,
        score=0.0 if all_passed else 1.0,
        threshold=0.0,
        is_blocking=True,
        sub_gates=sub_gates,
        issues=issues,
        evidence={"platform": profile.get("platform", "unknown"), "policy_status": policy_status},
    )


# ── 门禁6：AI披露合规 ────────────────────────────────────────
def gate_ai_disclosure(
    platform_profile: Optional[dict[str, Any]] = None,
    disclosure_record: Optional[dict[str, Any]] = None,
    human_editing_confirmed: bool = False,
) -> GateResult:
    """AI披露合规门禁。按平台政策判定。

    allowed → 直接通过
    allowed_with_human_editing → 必须有人工确认和真实编辑记录
    required_disclosure → 必须生成并确认披露信息
    unknown → 不能通过
    prohibited → 不能通过（可作为内部草稿，但不能publish_ready）
    """
    profile = platform_profile or {}
    policy = profile.get("ai_usage_policy", "unknown")
    issues = []
    passed = False

    if policy == "allowed":
        passed = True
    elif policy == "allowed_with_human_editing":
        if human_editing_confirmed:
            passed = True
        else:
            issues.append({"type": "no_human_editing", "message": "平台要求人工编辑确认，但未找到已确认的人工编辑记录"})
    elif policy == "required_disclosure":
        if disclosure_record and disclosure_record.get("disclosure_status") == "confirmed":
            passed = True
        else:
            issues.append({"type": "no_disclosure", "message": "平台要求AI披露，但披露信息未生成或未确认"})
    elif policy == "unknown":
        issues.append({"type": "policy_unknown", "message": "平台AI使用政策未知，不能publish_ready"})
    elif policy == "prohibited":
        issues.append({"type": "ai_prohibited", "message": "该平台禁止AI生成内容发布"})
    else:
        issues.append({"type": "invalid_policy", "message": f"未知AI政策：{policy}"})

    return GateResult(
        gate_key="ai_disclosure",
        gate_name=GATE_DEFINITIONS["ai_disclosure"]["name"],
        passed=passed,
        score=0.0 if passed else 1.0,
        threshold=0.0,
        is_blocking=True,
        issues=issues,
        evidence={"ai_usage_policy": policy, "human_editing_confirmed": human_editing_confirmed},
    )


# ── 门禁7：外部检测风险 ──────────────────────────────────────
def gate_external_risk(
    platform_profile: Optional[dict[str, Any]] = None,
    external_score: Optional[float] = None,
    external_flagged: bool = False,
    external_evaluation: Optional[dict[str, Any]] = None,
) -> GateResult:
    """外部AI检测风险门禁。

    默认保留历史兼容行为（只记录风险）；作品配置
    ``extra_metadata.external_detector_hard_gate=true`` 后，必须有绑定当前
    正文哈希的真实报告，并满足人工特征≥95、疑似AI≤5、AI特征=0。
    """
    profile = platform_profile or {}
    policy = profile.get("ai_usage_policy", "unknown")
    extra = profile.get("extra_metadata") or {}
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except (TypeError, ValueError):
            extra = {}
    hard_gate = bool(
        profile.get("external_detector_hard_gate")
        or (isinstance(extra, dict) and extra.get("external_detector_hard_gate"))
    )
    is_blocking = hard_gate or policy == "prohibited"

    issues = []
    warnings = []
    passed = True
    evaluation = external_evaluation if isinstance(external_evaluation, dict) else None
    evaluation_status = str((evaluation or {}).get("status") or "not_run")
    human_score = (evaluation or {}).get("human_score")
    suspected_ai_score = (evaluation or {}).get("suspected_ai_score")
    ai_feature_score = (evaluation or {}).get("ai_feature_score")
    target_passed = evaluation_status == "external_95_5_0" and bool((evaluation or {}).get("target_passed"))

    if hard_gate and not target_passed:
        passed = False
        issues.append({
            "type": "external_target_not_met",
            "message": "外部硬门未通过：需要人工特征≥95、疑似AI≤5、AI特征=0的当前正文报告",
            "status": evaluation_status,
            "scores": {
                "human_score": human_score,
                "suspected_ai_score": suspected_ai_score,
                "ai_feature_score": ai_feature_score,
            },
        })
    if external_flagged or (external_score is not None and external_score >= 80) or (evaluation and not target_passed):
        warnings.append({
            "type": "ai_detected",
            "message": "外部检测报告未达到当前作品目标，发布页必须明显展示",
            "score": external_score if external_score is not None else suspected_ai_score,
        })
        if policy == "prohibited" and not hard_gate:
            passed = False
            issues.append({"type": "ai_prohibited_by_platform", "message": "平台禁止AI内容，外部检测命中后阻断发布"})

    return GateResult(
        gate_key="external_risk",
        gate_name=GATE_DEFINITIONS["external_risk"]["name"],
        passed=passed,
        score=float(suspected_ai_score if suspected_ai_score is not None else (external_score or 0.0)),
        threshold=5.0 if hard_gate else 80.0,
        is_blocking=is_blocking,
        issues=issues,
        warnings=warnings,
        evidence={
            "external_flagged": external_flagged,
            "external_score": external_score,
            "external_evaluation": evaluation,
            "hard_gate": hard_gate,
            "target": {"human_min": 95.0, "suspected_ai_max": 5.0, "ai_feature_max": 0.0},
            "target_passed": target_passed,
            "blocking_due_to_policy": is_blocking,
        },
        gate_version="v2.0",
    )


# ── 综合运行七道门 ───────────────────────────────────────────
def run_all_gates(
    chapter_id: str,
    text: str,
    variant_id: Optional[str] = None,
    platform_profile: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
    existing_review_score: Optional[float] = None,
    continuity_errors: Optional[list[dict[str, Any]]] = None,
    payoff_markers: Optional[list[str]] = None,
    semantic_payoff: Optional[dict[str, Any]] = None,
    disclosure_record: Optional[dict[str, Any]] = None,
    human_editing_confirmed: bool = False,
    external_score: Optional[float] = None,
    external_flagged: bool = False,
    external_evaluation: Optional[dict[str, Any]] = None,
) -> PublishingGateReport:
    """运行全部七道门禁，返回综合报告。"""
    stats = compute_statistics(text)
    content_hash = _content_hash(text)

    gates = {
        "content_quality": gate_content_quality(text, stats, existing_review_score),
        "continuity": gate_continuity(text, stats, continuity_errors),
        "payoff_density": gate_payoff_density(text, stats, payoff_markers, semantic_payoff),
        "readability": gate_readability(text, stats),
        "platform_compliance": gate_platform_compliance(text, stats, platform_profile, metadata),
        "ai_disclosure": gate_ai_disclosure(platform_profile, disclosure_record, human_editing_confirmed),
        "external_risk": gate_external_risk(platform_profile, external_score, external_flagged, external_evaluation),
    }

    # quality_candidate：七项均已输出（不要求全部通过）
    quality_candidate = len(gates) == 7

    # publish_ready：所有is_blocking的门禁必须通过
    blocking_failures = []
    non_blocking_warnings = []
    for key, gate in gates.items():
        if gate.is_blocking and not gate.passed:
            blocking_failures.append(key)
        if not gate.is_blocking and gate.warnings:
            non_blocking_warnings.append(key)

    overall_publish_ready = len(blocking_failures) == 0 and quality_candidate

    return PublishingGateReport(
        chapter_id=chapter_id,
        variant_id=variant_id,
        content_sha256=content_hash,
        overall_publish_ready=overall_publish_ready,
        quality_candidate=quality_candidate,
        gates=gates,
        blocking_failures=blocking_failures,
        non_blocking_warnings=non_blocking_warnings,
    )
