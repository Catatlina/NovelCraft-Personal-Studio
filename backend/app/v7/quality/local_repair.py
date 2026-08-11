"""local_repair — v0.9.2 风险句定位后的局部修复引擎

替换旧的"整章去AI重写"：
- 先定位高风险句子（AI味/异常/不通顺）
- 只修复1-3处最高优先级的风险句
- 修复后复审，不通过则再修一轮（最多3轮）
- 整章重写仅作为最后兜底，且必须显式触发

修复类型：
- ai_smell: AI味句子（模板化、空泛、过度修饰）
- awkward: 不通顺/语法问题
- inconsistency: 与上下文不一致
- pacing: 节奏问题（过长/过短/拖沓）
- punctuation: 标点异常
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from .statistics_v1 import compute_statistics, StatisticsResult


# ── AI味检测模式 ──────────────────────────────────────────────
AI_SMELL_PATTERNS = [
    (re.compile(r"不禁[^\n。！？]{0,10}"), "ai_smell", "不禁XX模板"),
    (re.compile(r"不由得[^\n。！？]{0,10}"), "ai_smell", "不由得XX模板"),
    (re.compile(r"仿佛.{0,20}一般"), "ai_smell", "仿佛XX一般模板"),
    (re.compile(r"宛如.{0,20}一般"), "ai_smell", "宛如XX一般模板"),
    (re.compile(r"犹如.{0,20}一般"), "ai_smell", "犹如XX一般模板"),
    (re.compile(r"在这.{0,10}的时刻"), "ai_smell", "在这XX时刻模板"),
    (re.compile(r"此时此刻"), "ai_smell", "此时此刻滥用"),
    (re.compile(r"总而言之"), "ai_smell", "总而言之模板化总结"),
    (re.compile(r"综上所述"), "ai_smell", "综上所述模板化总结"),
    (re.compile(r"不仅.{0,10}而且"), "ai_smell", "不仅而且过度连接"),
    (re.compile(r"一方面.{0,20}另一方面"), "ai_smell", "一方面另一方面议论文腔"),
]

AWKWARD_PATTERNS = [
    (re.compile(r"[，、]{2,}"), "punctuation", "重复标点"),
    (re.compile(r"[。！？]{2,}"), "punctuation", "重复句末标点"),
    (re.compile(r"的的"), "awkward", "的的重复"),
    (re.compile(r"了了"), "awkward", "了了重复"),
    (re.compile(r"是是"), "awkward", "是是重复"),
]


@dataclass
class RiskSentence:
    """风险句子定位。"""
    sentence_index: int
    paragraph_index: int
    char_start: int
    char_end: int
    text: str
    risk_type: str  # ai_smell / awkward / inconsistency / pacing / punctuation
    risk_score: float  # 0-100
    reason: str
    suggested_fix: str = ""


@dataclass
class RepairResult:
    """局部修复结果。"""
    original_text: str
    repaired_text: str
    original_sha256: str
    repaired_sha256: str
    repairs_made: list[RiskSentence] = field(default_factory=list)
    rounds_used: int = 0
    max_rounds: int = 3
    remaining_risks: list[RiskSentence] = field(default_factory=list)
    quality_improved: bool = False
    repair_log: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_sha256": self.original_sha256,
            "repaired_sha256": self.repaired_sha256,
            "repairs_made": [asdict(r) for r in self.repairs_made],
            "rounds_used": self.rounds_used,
            "remaining_risks": [asdict(r) for r in self.remaining_risks],
            "quality_improved": self.quality_improved,
            "repair_log": self.repair_log,
        }


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def detect_risk_sentences(text: str, stats: Optional[StatisticsResult] = None) -> list[RiskSentence]:
    """检测高风险句子，按风险分排序。"""
    if stats is None:
        stats = compute_statistics(text)

    risks: list[RiskSentence] = []

    # 遍历所有句子
    for ch in stats.chapters:
        for sent in ch.sentences:
            sent_text = sent.get("text", "")
            if not sent_text:
                continue
            sent_idx = sent["index"]
            para_idx = sent.get("paragraph_index", 0)

            # AI味检测
            for pattern, risk_type, reason in AI_SMELL_PATTERNS:
                if pattern.search(sent_text):
                    score = min(90, 50 + len(sent_text) * 0.1)
                    risks.append(RiskSentence(
                        sentence_index=sent_idx,
                        paragraph_index=para_idx,
                        char_start=sent.get("char_start", 0),
                        char_end=sent.get("char_end", 0),
                        text=sent_text,
                        risk_type=risk_type,
                        risk_score=score,
                        reason=reason,
                    ))
                    break  # 每句只记一次最高优先级

            # 不通顺/标点检测
            for pattern, risk_type, reason in AWKWARD_PATTERNS:
                if pattern.search(sent_text):
                    risks.append(RiskSentence(
                        sentence_index=sent_idx,
                        paragraph_index=para_idx,
                        char_start=sent.get("char_start", 0),
                        char_end=sent.get("char_end", 0),
                        text=sent_text,
                        risk_type=risk_type,
                        risk_score=70.0,
                        reason=reason,
                    ))

            # 超长句（节奏问题）
            if sent["char_count"] > 120:
                risks.append(RiskSentence(
                    sentence_index=sent_idx,
                    paragraph_index=para_idx,
                    char_start=sent.get("char_start", 0),
                    char_end=sent.get("char_end", 0),
                    text=sent_text,
                    risk_type="pacing",
                    risk_score=60.0,
                    reason=f"句子过长({sent['char_count']}字)，建议拆分",
                ))

    # 去重（同一句子多个问题只保留最高分）
    seen: dict[int, RiskSentence] = {}
    for r in risks:
        if r.sentence_index not in seen or r.risk_score > seen[r.sentence_index].risk_score:
            seen[r.sentence_index] = r

    return sorted(seen.values(), key=lambda x: x.risk_score, reverse=True)


def apply_local_repair(
    text: str,
    risks: list[RiskSentence],
    max_repairs: int = 3,
) -> tuple[str, list[RiskSentence]]:
    """应用局部修复（规则级修复，AI修复由调用方注入）。

    只修复最高优先级的max_repairs处。
    """
    repaired = text
    made = []

    for risk in risks[:max_repairs]:
        original = risk.text
        fixed = original

        # 规则级修复
        if risk.risk_type == "punctuation":
            fixed = re.sub(r"[，、]{2,}", "，", fixed)
            fixed = re.sub(r"[。！？]{2,}", "。", fixed)
        elif risk.risk_type == "awkward":
            fixed = re.sub(r"的的", "的", fixed)
            fixed = re.sub(r"了了", "了", fixed)
        elif risk.risk_type == "ai_smell":
            # 移除模板化表达（保守替换）
            fixed = re.sub(r"不禁([^\n。！？]{0,10})", r"\1", fixed)
            fixed = re.sub(r"不由得([^\n。！？]{0,10})", r"\1", fixed)
            fixed = re.sub(r"此时此刻，?", "", fixed)
            fixed = re.sub(r"总而言之，?", "", fixed)
        elif risk.risk_type == "pacing":
            # 超长句在逗号处拆分
            if "，" in fixed and len(fixed) > 120:
                parts = fixed.split("，", 1)
                if len(parts) == 2:
                    fixed = parts[0] + "。" + parts[1]

        if fixed != original and fixed in repaired:
            repaired = repaired.replace(original, fixed, 1)
            risk.suggested_fix = fixed
            made.append(risk)

    return repaired, made


def local_repair_pipeline(
    text: str,
    max_rounds: int = 3,
    max_repairs_per_round: int = 3,
    ai_repair_fn: Optional[Any] = None,
) -> RepairResult:
    """局部修复流水线：检测→修复→复审，最多max_rounds轮。

    ai_repair_fn: 可选的AI修复函数 signature: (sentence_text, risk_type, reason) -> fixed_text
    如果不提供，只做规则级修复。
    """
    original_hash = _hash(text)
    current = text
    all_repairs: list[RiskSentence] = []
    log: list[str] = []

    for round_num in range(1, max_rounds + 1):
        stats = compute_statistics(current)
        risks = detect_risk_sentences(current, stats)

        if not risks:
            log.append(f"第{round_num}轮：无风险句子，修复完成")
            break

        top_risks = risks[:max_repairs_per_round]
        log.append(f"第{round_num}轮：检测到{len(risks)}处风险，修复前{len(top_risks)}处最高优先级")

        # AI修复（如果提供）
        if ai_repair_fn:
            for risk in top_risks:
                try:
                    fixed = ai_repair_fn(risk.text, risk.risk_type, risk.reason)
                    if fixed and fixed != risk.text:
                        risk.suggested_fix = fixed
                        current = current.replace(risk.text, fixed, 1)
                        all_repairs.append(risk)
                except Exception as e:
                    log.append(f"  AI修复失败: {e}，回退规则修复")

        # 规则级修复（补充AI未处理的）
        remaining = [r for r in top_risks if not r.suggested_fix]
        if remaining:
            current, rule_repairs = apply_local_repair(current, remaining, max_repairs_per_round)
            all_repairs.extend(rule_repairs)

        # 复审：重新检测
        new_stats = compute_statistics(current)
        new_risks = detect_risk_sentences(current, new_stats)
        log.append(f"  复审：剩余{len(new_risks)}处风险")

        if not new_risks:
            break

    final_hash = _hash(current)
    remaining = detect_risk_sentences(current)

    return RepairResult(
        original_text=text,
        repaired_text=current,
        original_sha256=original_hash,
        repaired_sha256=final_hash,
        repairs_made=all_repairs,
        rounds_used=round_num if 'round_num' in dir() else 0,
        max_rounds=max_rounds,
        remaining_risks=remaining,
        quality_improved=original_hash != final_hash and len(remaining) < len(detect_risk_sentences(text)),
        repair_log=log,
    )


def should_use_full_rewrite(risks: list[RiskSentence], text_length: int) -> bool:
    """判断是否应该回退到整章重写（仅作为最后兜底）。

    条件：风险句超过正文句子数的50%，或风险总分极高。
    """
    if not risks:
        return False
    stats = compute_statistics(text_length if isinstance(text_length, str) else "")
    total_sentences = stats.total_sentences if isinstance(text_length, str) else 100
    risk_ratio = len(risks) / max(total_sentences, 1)
    avg_score = sum(r.risk_score for r in risks) / len(risks)
    return risk_ratio > 0.5 or (avg_score > 80 and len(risks) > 10)
