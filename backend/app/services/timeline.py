"""Timeline & arc extraction from chapters."""
from __future__ import annotations

import re
from typing import Any

from app.db import connect, encode, new_id

# ── V3 §10: 时间线真实锚点 ──────────────────────────────────────────────
# 仅当 Novel DNA 的 commercial_positioning 标注为"现实向"时启用年代校验；
# 架空/玄幻类不启用，避免误判。全部为确定性纯逻辑，不新增 AI 调用。

REALITY_MARKERS = ("现实向", "现实题材", "现实世界", "现实背景")

# 常见产品/技术的问世年份表（保守收录高置信项，用于年代错乱检测）。
ANACHRONISM_ERA_TABLE: dict[str, int] = {
    "微信": 2011, "微信支付": 2013, "支付宝": 2004, "扫码支付": 2011,
    "iPhone": 2007, "智能手机": 2007, "iPad": 2010,
    "高铁": 2008, "网约车": 2012, "共享单车": 2016,
    "抖音": 2016, "直播带货": 2016, "外卖平台": 2013,
    "5G": 2019, "新能源车": 2014, "扫地机器人": 2010,
}

_YEAR_RE = re.compile(r"(19\d{2}|20\d{2})\s*年?")


def is_reality_based(dna: Any) -> bool:
    """V3 §10: DNA 商业定位标注现实向时才启用锚点校验（纯函数）。"""
    if not isinstance(dna, dict):
        return False
    positioning = str(dna.get("commercial_positioning", ""))
    return any(marker in positioning for marker in REALITY_MARKERS)


def parse_year_anchor(anchor: Any) -> int | None:
    """从锚点文本（如 "2010年" / "2010年夏"）解析出年份（纯函数）。"""
    if anchor is None:
        return None
    m = _YEAR_RE.search(str(anchor))
    return int(m.group(1)) if m else None


def check_anachronisms(anchor_year: int | None, text: str) -> dict[str, Any]:
    """确定性年代错乱检测：锚点年份早于产品问世年份即告警（纯函数）。

    返回 {"status": "pass"|"warning", "issues": [...], "anchor_year": ...}。
    无锚点年份或文本为空时直接 pass（优雅降级）。
    """
    if not anchor_year or not text:
        return {"status": "pass", "issues": [], "anchor_year": anchor_year}
    issues: list[str] = []
    for item, born in ANACHRONISM_ERA_TABLE.items():
        if anchor_year < born and item in text:
            issues.append(
                f"锚点年份 {anchor_year} 早于「{item}」问世年份 {born}，疑似年代错乱"
            )
    status = "warning" if issues else "pass"
    return {"status": status, "issues": issues, "anchor_year": anchor_year}


def anchor_rule_for(anchor: Any) -> str:
    """由锚点自动生成校验规则引用文本（anachronism_check 列，纯函数）。"""
    year = parse_year_anchor(anchor)
    return f"不得出现{year}年前不存在的产品/技术" if year else ""


def extract_timeline(chapter_id: str, chapter_body: str) -> list[dict]:
    """Extract timeline events from chapter text."""
    project_id = _content_project_id(chapter_id)
    events = _call_ai("extract_timeline", chapter_body, "提取本章的时间线事件列表。", project_id)
    if not events:
        return []
    db = connect()
    for i, ev in enumerate(events):
        event_text = ev.get("event", str(ev)) if isinstance(ev, dict) else str(ev)
        # V3 §10: 持久化真实时间锚点 + 自动生成的校验规则引用（可选字段，缺省为 NULL）
        anchor = ev.get("real_world_anchor") if isinstance(ev, dict) else None
        anchor = str(anchor).strip() if anchor else None
        db.execute(
            "INSERT INTO timeline_events (id, chapter_id, event_text, event_order,"
            " real_world_anchor, anachronism_check) VALUES (%s, %s, %s, %s, %s, %s)",
            (new_id(), chapter_id, event_text, i + 1,
             anchor, anchor_rule_for(anchor) or None),
        )
    db.commit()
    db.close()
    return events


def update_arcs(novel_id: str, chapter_body: str) -> list[dict]:
    """Update character arcs based on chapter content."""
    arcs = _call_ai("extract_arcs", chapter_body, "提取本章中人物弧线的进展。",
                    _content_project_id(novel_id))
    if not arcs:
        return []
    db = connect()
    for a in (item for item in arcs if isinstance(item, dict)):
        name = a.get("character", a.get("name", ""))
        stage = a.get("stage", a.get("progress", ""))
        db.execute(
            "INSERT INTO arcs (id, novel_id, character_name, stage, goal, status) VALUES (%s, %s, %s, %s, %s, 'in_progress')",
            (new_id(), novel_id, name, stage, a.get("goal", "")),
        )
    db.commit()
    db.close()
    return arcs


def _content_project_id(content_id: str) -> str:
    db = connect()
    row = db.execute("SELECT project_id FROM contents WHERE id = %s", (content_id,)).fetchone()
    db.close()
    return row["project_id"] if row else ""


def _call_ai(task_type: str, text: str, instructions: str, project_id: str) -> list[dict]:
    from app.gateway import complete
    result = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type=task_type, prompt_name=f"narrative.{task_type}",
        variables={"body": text[:5000], "instructions": instructions},
    )
    return result.get("events", result.get("arcs", []))
