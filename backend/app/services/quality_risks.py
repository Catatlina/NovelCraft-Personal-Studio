"""Shared, deterministic quality-risk classification and repair contracts.

The model is still responsible for literary judgment, but the application
must decide whether a chapter is actually safe to accept.  In particular,
"节奏/铺垫不足", causal gaps, continuity breaks, and AI-style warnings must
not remain advisory while an otherwise high average score passes the chapter.
"""
from __future__ import annotations

from typing import Any


RISK_LABELS: dict[str, str] = {
    "continuity": "跨章连贯性",
    "pacing": "节奏与铺垫",
    "plot_logic": "因果逻辑",
    "ai_feel": "AI 腔",
    "foreshadowing": "伏笔推进",
    "writing_quality": "文字质量",
}

RISK_GUIDANCE: dict[str, dict[str, Any]] = {
    "continuity": {
        "goal": "承接上一章已经落地的具体场景、人物状态、物品和未解悬念，并留下可验证的连续性证据",
        "checks": ["开头直接承接上一章尾部", "时间/地点/人物状态不跳变", "没有无铺垫的新核心人物或能力"],
    },
    "pacing": {
        "goal": "补足铺垫并让情绪曲线有升温、冲突、代价、缓冲和新钩子",
        "checks": ["关键转折前有可见的动作或线索铺垫", "每个场景都有目标-阻碍-结果", "高潮后有具体余波，不用总结句收尾"],
    },
    "plot_logic": {
        "goal": "把触发、依据、选择、阻碍、代价和结果写成可追溯的因果链",
        "checks": ["人物知道什么必须有来源", "选择必须有动机和代价", "时间、空间、伤势和道具状态前后一致"],
    },
    "ai_feel": {
        "goal": "去掉工整、总结、解释腔，保留事实但让表达像真人作者",
        "checks": ["长短段和句式有变化", "用动作/对白承载情绪和信息", "删除模板套话、公文连接词和章末总结体"],
    },
    "foreshadowing": {
        "goal": "把伏笔落到具体细节并推进或回收，不用旁白硬解释",
        "checks": ["伏笔在场景中有可见证据", "到期伏笔本章正面处理", "新规则先给迹象再给揭示"],
    },
    "writing_quality": {
        "goal": "在不改变事实的前提下改善画面、节奏和人物声音",
        "checks": ["避免连续同构句", "避免抽象评价替代动作", "对白和叙述符合人物口吻"],
    },
}

_DIMENSION_ALIASES: dict[str, str] = {
    "consistency": "continuity",
    "continuity": "continuity",
    "world_conflict": "continuity",
    "logic_consistency": "plot_logic",
    "logic": "plot_logic",
    "plot": "plot_logic",
    "plot_logic": "plot_logic",
    "pace": "pacing",
    "pacing": "pacing",
    "foreshadowing": "foreshadowing",
    "style": "writing_quality",
    "prose": "writing_quality",
    "writing_quality": "writing_quality",
}

_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ai_feel", ("ai腔", "ai 腔", "ai 味", "ai味", "机器味", "模板化", "套话", "工整", "机械", "总结体", "公文", "翻译腔", "流水账")),
    ("continuity", ("连续性", "连贯", "跨章", "前文", "时间线", "地点跳", "状态冲突", "前后矛盾", "设定冲突")),
    ("pacing", ("节奏", "铺垫", "情绪曲线", "推进过快", "推进太快", "仓促", "拖沓", "缓冲", "高潮后")),
    ("plot_logic", ("逻辑", "因果", "动机", "依据", "为什么", "说明不足", "解释不足", "跳跃", "突兀", "状态不一致")),
    ("foreshadowing", ("伏笔", "铺设", "暗示", "钩子", "规则限制", "代价未")),
)

_MEDIUM_HINTS = (
    "不足", "缺乏", "缺失", "未交代", "未铺垫", "未说明", "突兀", "仓促", "跳跃", "矛盾",
    "断裂", "拖沓", "工整", "机械", "套话", "ai腔", "ai味", "风险", "过于",
)


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(str(value.get(key) or "") for key in (
            "dimension", "type", "category", "description", "suggestion", "excerpt", "location",
        ))
    return str(value or "")


def _severity(issue: Any, text: str) -> str:
    if isinstance(issue, dict):
        explicit = str(issue.get("severity") or "").lower().strip()
        if explicit in {"high", "medium", "low"}:
            return explicit
    lowered = text.lower()
    return "medium" if any(hint.lower() in lowered for hint in _MEDIUM_HINTS) else "low"


def classify_quality_issue(issue: Any) -> dict[str, Any]:
    """Normalize legacy string issues and V7 structured issues."""
    text = _text(issue).strip()
    lowered = text.lower()
    explicit_dimension = ""
    if isinstance(issue, dict):
        explicit_dimension = str(issue.get("dimension") or issue.get("type") or issue.get("category") or "").lower()
    category = _DIMENSION_ALIASES.get(explicit_dimension)
    if category == "writing_quality" and any(keyword.lower() in lowered for keyword in ("ai腔", "ai 腔", "ai味", "机器味", "套话", "模板")):
        category = "ai_feel"
    if not category:
        for candidate, keywords in _CATEGORY_KEYWORDS:
            if any(keyword.lower() in lowered for keyword in keywords):
                category = candidate
                break
    category = category or "other"
    severity = _severity(issue, text)
    return {
        "category": category,
        "label": RISK_LABELS.get(category, "其他问题"),
        "severity": severity,
        "blocking": category in RISK_LABELS and severity in {"high", "medium"},
        "text": text,
        "description": str(issue.get("description") or text) if isinstance(issue, dict) else text,
        "suggestion": str(issue.get("suggestion") or "") if isinstance(issue, dict) else "",
        "location": str(issue.get("location") or "") if isinstance(issue, dict) else "",
    }


def build_quality_repair_contract(
    review_data: dict[str, Any],
    *,
    dimension_minimums: dict[str, float] | None = None,
    continuity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a stable repair contract used by V6, V7 and the editor.

    A risk is blocking only when it is actionable and material.  Low-severity
    editorial notes remain visible but do not force endless rewrites.
    """
    review_data = review_data if isinstance(review_data, dict) else {}
    issues = review_data.get("issues") or []
    risks = [classify_quality_issue(issue) for issue in issues if _text(issue).strip()]

    minimums = dimension_minimums or {}
    dimensions = review_data.get("dimension_scores") or review_data.get("dimensions") or {}
    if isinstance(dimensions, dict):
        for raw_name, minimum in minimums.items():
            value = dimensions.get(raw_name)
            if value is None:
                for alias, canonical in _DIMENSION_ALIASES.items():
                    if canonical == raw_name and alias in dimensions:
                        value = dimensions.get(alias)
                        break
            if isinstance(value, (int, float)) and float(value) < float(minimum):
                category = _DIMENSION_ALIASES.get(raw_name, raw_name)
                risks.append({
                    "category": category,
                    "label": RISK_LABELS.get(category, raw_name),
                    "severity": "high",
                    "blocking": True,
                    "text": f"{RISK_LABELS.get(category, raw_name)}评分不足：{float(value):.0f}/{float(minimum):.0f}",
                    "description": f"{RISK_LABELS.get(category, raw_name)}评分不足",
                    "suggestion": "按修复契约重写后重新审阅",
                    "location": "",
                })

    if continuity:
        status = str(continuity.get("status") or "").lower()
        if status in {"flagged", "unchecked"}:
            reason = "；".join(str(item.get("content") or item.get("description") or item) for item in (continuity.get("risks") or [])[:3])
            risks.append({
                "category": "continuity",
                "label": RISK_LABELS["continuity"],
                "severity": "high" if status == "flagged" else "medium",
                "blocking": True,
                "text": f"跨章连贯性检查{status}：{reason or continuity.get('error') or '缺少可验证证据'}",
                "description": reason or str(continuity.get("error") or "缺少可验证的连续性证据"),
                "suggestion": RISK_GUIDANCE["continuity"]["goal"],
                "location": "",
            })

    # De-duplicate synthetic + model findings by category/severity/text.
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for risk in risks:
        key = (str(risk.get("category")), str(risk.get("severity")), str(risk.get("text")))
        if key not in seen:
            seen.add(key)
            unique.append(risk)

    blocking = [risk for risk in unique if risk.get("blocking")]
    required_categories: list[str] = []
    for risk in blocking:
        category = str(risk.get("category"))
        if category not in required_categories:
            required_categories.append(category)

    required_repairs = []
    for category in required_categories:
        guidance = RISK_GUIDANCE.get(category, RISK_GUIDANCE["writing_quality"])
        required_repairs.append({
            "category": category,
            "label": RISK_LABELS.get(category, category),
            "goal": guidance["goal"],
            "checks": list(guidance["checks"]),
            "feedback": f"【{RISK_LABELS.get(category, category)}定向修复】{guidance['goal']}。验收：" + "；".join(guidance["checks"]),
        })

    return {
        "schema_version": "quality-repair-v1",
        "passed": not blocking,
        "risks": unique,
        "blocking_risks": blocking,
        "required_repairs": required_repairs,
        "required_repair_feedback": [item["feedback"] for item in required_repairs],
        "blocking_categories": required_categories,
    }


def repair_feedback(contract: dict[str, Any], issues: list[Any] | None = None) -> list[str]:
    """Build concise, provider-safe feedback for the next rewrite attempt."""
    feedback = [str(item) for item in (issues or []) if str(item).strip()]
    feedback.extend(str(item) for item in contract.get("required_repair_feedback") or [])
    return feedback


def evaluate_editor_review_gate(
    review_data: dict[str, Any],
    *,
    chars: int,
    minimum_chars: int,
    minimum_score: float = 85.0,
) -> dict[str, Any]:
    """Apply the same material-risk bar to an editor AI operation.

    Editor previews remain user-confirmed, but a generated candidate is not
    called quality-safe merely because it can be previewed.  The returned
    contract is also rendered into the preview response for honest review.
    """
    contract = build_quality_repair_contract(
        review_data,
        dimension_minimums={
            "continuity": minimum_score,
            "plot_logic": minimum_score,
            "pacing": minimum_score,
            "writing_quality": minimum_score,
        },
        continuity=review_data.get("continuity"),
    )
    failures: list[dict[str, Any]] = []
    score = float(review_data.get("score") or review_data.get("overall_score") or 0.0)
    if score < minimum_score:
        failures.append({"dimension": "overall_score", "actual": score, "minimum": minimum_score})
    if chars < minimum_chars:
        failures.append({"dimension": "length", "actual": chars, "minimum": minimum_chars})
    for risk in contract["blocking_risks"]:
        failures.append({
            "dimension": risk["category"],
            "actual": risk.get("severity"),
            "minimum": "resolved",
            "reason": risk.get("description") or risk.get("text"),
        })
    return {
        "passed": not failures,
        "score": score,
        "chars": chars,
        "minimum_score": minimum_score,
        "minimum_chars": minimum_chars,
        "failures": failures,
        "quality_repair_contract": contract,
    }
