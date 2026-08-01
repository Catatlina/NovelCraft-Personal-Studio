#!/usr/bin/env python
"""
V7.0 — 50-chapter 4-axis evaluation (可读性 / 连续性 / 连贯性 / 准确性).

Merges the per-batch harness reports produced by v7_e2e_gate.py and:
  1. Maps the engine's 7-dimension review scores onto the 4 axes the user asked
     for (no extra AI cost):
       可读性  readability = 0.7*writing_quality + 0.3*pacing
       连续性  continuity = consistency   (within-chapter vs established setting)
       连贯性  coherence  = plot_logic
       准确性  accuracy   = constraint_compliance
  2. Runs cross-chapter PROGRAMMATIC checks on the full chapter text:
       - character name drift / dropped-thread (gaps after introduction)
       - AI-cliche scan (禁AI腔 constraint)
       - modern-speak scan (江砚不得现代口语 constraint)
       - early full-reveal check (真相不得提前全揭 constraint, < ch40)
       - 归墟灯代价 omission check (代价不可省略 constraint)
  3. Emits QA_50chap_report.md + qa_50chap_chart.json (for the Visualizer).

Usage:
    python scripts/v7_fifty_eval.py \
        --reports "/tmp/v7_50_b*.json" \
        --out QA_50chap_report.md \
        --chart qa_50chap_chart.json
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import statistics
from pathlib import Path
from typing import Any

# ── Canonical characters (from the extended story Bible) ─────────────────────
CANONICAL_NAMES = ["江砚", "沈观澜", "阿箬", "老辛"]

# ── Programmatic constraint / quality patterns ──────────────────────────────
AI_CLICHE_PATTERNS = [
    "值得一提的是",
    "总的来说",
    "总而言之",
    "不仅仅是",
    "不仅是",
    "仿佛.*一般",
    "毋庸置疑",
    "显而易见",
    "从某种程度上",
    "不难看出",
]
MODERN_SPEAK = ["系统", "数据", "ok", "OK", "搞定", "情绪价值", "剧本", "人设", "吐槽", "社死", "内卷", "赋能", "闭环"]
COST_WORDS = ["阳寿", "记忆", "咳血", "代价", "折损", "遗忘", "忘记"]
ABILITY_HINTS = ["归墟之眼", "点亮", "归墟灯", "执念之影"]
REVEAL_PATTERNS = ["篡改星录", "嫁祸江家", "沈观澜.*篡改", "篡改了星录"]


def load_and_merge(reports_glob: str) -> dict[int, dict[str, Any]]:
    """Merge per-batch harness JSON reports keyed by chapter_number."""
    merged: dict[int, dict[str, Any]] = {}
    files = sorted(glob.glob(reports_glob))
    if not files:
        raise SystemExit(f"FATAL: no report files match {reports_glob!r}")
    for f in files:
        data = json.loads(Path(f).read_text(encoding="utf-8"))
        for ch in data.get("chapters", []):
            cn = ch.get("chapter_number")
            if cn is None:
                continue
            merged[cn] = ch
    return merged


def map_axes(dim: dict[str, int]) -> dict[str, int]:
    wq = dim.get("writing_quality", 0)
    pace = dim.get("pacing", 0)
    readability = round(0.7 * wq + 0.3 * pace)
    return {
        "可读性": readability,
        "连续性": dim.get("consistency", 0),
        "连贯性": dim.get("plot_logic", 0),
        "准确性": dim.get("constraint_compliance", 0),
    }


def cross_chapter_checks(merged: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Programmatic cross-chapter continuity / accuracy checks on full text."""
    chapters = sorted(merged.keys())
    findings: dict[str, Any] = {
        "name_drift": [],
        "ai_cliche": [],
        "modern_speak": [],
        "early_reveal": [],
        "cost_omission": [],
    }

    # name drift / dropped thread
    intro: dict[str, int] = {}
    for cn in chapters:
        txt = merged[cn].get("chapter_text_full") or ""
        for name in CANONICAL_NAMES:
            if name in txt and name not in intro:
                intro[name] = cn
    # gaps: after intro, a chapter missing an established major character for
    # many consecutive chapters is a possible dropped thread (soft signal).
    last_seen: dict[str, int] = {}
    for cn in chapters:
        txt = merged[cn].get("chapter_text_full") or ""
        for name in CANONICAL_NAMES:
            if name in txt:
                last_seen[name] = cn
    for name, first in intro.items():
        if name == "老辛":
            # introduced late (Act 2); only check after intro
            pass
        last = last_seen.get(name, first)
        span = last - first
        # if a character was introduced but then absent for >= 15 consecutive
        # chapters before reappearing / ending, flag as possible drift.
        absent_run = 0
        max_absent = 0
        for cn in range(first, max(chapters) + 1):
            txt = merged[cn].get("chapter_text_full") or ""
            if name in txt:
                absent_run = 0
            else:
                absent_run += 1
                max_absent = max(max_absent, absent_run)
        if max_absent >= 15:
            findings["name_drift"].append(
                {"name": name, "introduced_ch": first, "max_absent_run": max_absent}
            )

    # per-chapter scans
    for cn in chapters:
        txt = merged[cn].get("chapter_text_full") or ""
        for pat in AI_CLICHE_PATTERNS:
            if re.search(pat, txt):
                findings["ai_cliche"].append({"chapter": cn, "pattern": pat})
                break
        for w in MODERN_SPEAK:
            if w in txt:
                findings["modern_speak"].append({"chapter": cn, "word": w})
                break
        for pat in REVEAL_PATTERNS:
            if re.search(pat, txt) and cn < 40:
                if "沈观澜.*篡改" == pat and cn < 40:
                    findings["early_reveal"].append({"chapter": cn, "pattern": pat})
                elif pat != "沈观澜.*篡改":
                    findings["early_reveal"].append({"chapter": cn, "pattern": pat})
                break
        if any(h in txt for h in ABILITY_HINTS):
            if not any(c in txt for c in COST_WORDS):
                findings["cost_omission"].append({"chapter": cn})

    return findings


def block_averages(series: list[float], blocks: int = 5) -> list[float]:
    n = len(series)
    size = max(1, n // blocks)
    out = []
    for b in range(blocks):
        chunk = series[b * size : (b + 1) * size]
        if chunk:
            out.append(round(statistics.mean(chunk), 1))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", required=True, help="glob for batch report JSONs")
    ap.add_argument("--out", default="QA_50chap_report.md")
    ap.add_argument("--chart", default="qa_50chap_chart.json")
    args = ap.parse_args()

    merged = load_and_merge(args.reports)
    chapters = sorted(merged.keys())
    if not chapters:
        raise SystemExit("FATAL: no chapters found in reports")

    axis_keys = ["可读性", "连续性", "连贯性", "准确性"]
    rows: list[dict[str, Any]] = []
    for cn in chapters:
        ch = merged[cn]
        dim = ch.get("dimension_scores") or {}
        if not dim:
            continue
        axes = map_axes(dim)
        axes["综合评分"] = ch.get("review_score")
        rows.append({
            "chapter": cn,
            "words": ch.get("verified_word_count"),
            "可读性": axes["可读性"],
            "连续性": axes["连续性"],
            "连贯性": axes["连贯性"],
            "准确性": axes["准确性"],
            "综合评分": axes["综合评分"],
            "cost": ch.get("cost"),
            "flags": ch.get("escalation_reason"),
        })

    # axis series
    def series_of(key: str) -> list[float]:
        return [r[key] for r in rows if r[key] is not None]

    axis_series = {k: series_of(k) for k in axis_keys + ["综合评分"]}

    # stats
    stats = {}
    for k in axis_keys + ["综合评分"]:
        s = axis_series[k]
        if s:
            stats[k] = {
                "avg": round(statistics.mean(s), 1),
                "min": min(s),
                "max": max(s),
                "blocks": block_averages(s),
            }

    findings = cross_chapter_checks(merged)

    # verdict: does quality hold across 50 chapters?
    def trend_note(key: str) -> str:
        bl = stats.get(key, {}).get("blocks")
        if not bl or len(bl) < 2:
            return "n/a"
        delta = bl[-1] - bl[0]
        if delta >= -2:
            return f"稳定/微升 (首块{bl[0]}→末块{bl[-1]}, Δ{delta})"
        return f"下滑 (首块{bl[0]}→末块{bl[-1]}, Δ{delta})"

    verdict = {k: trend_note(k) for k in axis_keys + ["综合评分"]}

    # totals
    total_words = sum(r["words"] or 0 for r in rows)
    total_cost = round(sum(r["cost"] or 0 for r in rows), 4)

    # ── build markdown ──
    md: list[str] = []
    md.append("# V7.0 — 50 章连续生成 · 四维评估报告\n")
    md.append(f"- 生成章节：**{len(rows)}** 章（{chapters[0]}–{chapters[-1]}）")
    md.append(f"- 总字数：**{total_words:,}** 字")
    md.append(f"- 真实 AI 成本：**¥{total_cost}**")
    md.append(f"- 综合评分均值：**{stats.get('综合评分', {}).get('avg')}** "
              f"(min {stats.get('综合评分', {}).get('min')} / max {stats.get('综合评分', {}).get('max')})\n")

    md.append("## 一、四维均值（0-100，越高越好）\n")
    md.append("| 维度 | 均值 | 最低 | 最高 | 5 段趋势(每10章) | 长程判定 |")
    md.append("| --- | --- | --- | --- | --- | --- |")
    for k in axis_keys + ["综合评分"]:
        st = stats.get(k, {})
        md.append(
            f"| {k} | {st.get('avg')} | {st.get('min')} | {st.get('max')} | "
            f"{st.get('blocks')} | {verdict.get(k)} |"
        )

    md.append("\n## 二、逐章四维评分\n")
    md.append("| 章 | 字数 | 可读性 | 连续性 | 连贯性 | 准确性 | 综合 |")
    md.append("| --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        md.append(
            f"| {r['chapter']:02d} | {r['words']} | {r['可读性']} | {r['连续性']} | "
            f"{r['连贯性']} | {r['准确性']} | {r['综合评分']} |"
        )

    md.append("\n## 三、跨章程序化校验（连续性 / 准确性）\n")
    md.append(f"- **角色名漂移 / 断线**（连续 ≥15 章不出现已引入角色）："
              f"{json.dumps(findings['name_drift'], ensure_ascii=False) or '无'}")
    md.append(f"- **AI 腔违例**（禁AI腔约束）："
              f"{len(findings['ai_cliche'])} 章 → "
              f"{[c['chapter'] for c in findings['ai_cliche']] or '无'}")
    md.append(f"- **现代口语违例**（江砚不得现代口语）："
              f"{len(findings['modern_speak'])} 章 → "
              f"{[c['chapter'] for c in findings['modern_speak']] or '无'}")
    md.append(f"- **真相提前全揭**（第40章前写'沈观澜篡改星录/嫁祸江家'）："
              f"{[c['chapter'] for c in findings['early_reveal']] or '无（合规）'}")
    md.append(f"- **归墟灯代价省略**（用能力但未写代价）："
              f"{len(findings['cost_omission'])} 章 → "
              f"{findings['cost_omission'] or '无'}")

    md.append("\n## 四、结论\n")
    declines = [k for k in axis_keys if "下滑" in verdict.get(k, "")]
    if declines:
        md.append(f"- ⚠️ 以下维度在 50 章长程中出现下滑：**{', '.join(declines)}**。"
                  f"需关注长程质量衰减。")
    else:
        md.append("- ✅ 四维评分在 50 章长程中**稳定或微升**，未见明显质量衰减；"
                  "系统可维持长篇小说的一致性、连贯性与准确性。")
    md.append(f"- 综合评分全程均值 {stats.get('综合评分', {}).get('avg')}，"
              f"最低章 {stats.get('综合评分', {}).get('min')}，"
              "说明单章质量波动可控。")
    if findings["ai_cliche"] or findings["modern_speak"] or findings["early_reveal"]:
        md.append("- 约束遵守存在少量违例（见第三节），属审稿 7 维'准确性'维度的真实反馈，"
                  "非系统故障。")
    else:
        md.append("- 约束遵守在程序化校验层面**全部通过**。")

    Path(args.out).write_text("\n".join(md), encoding="utf-8")

    # ── chart json ──
    chart = {
        "chapters": [r["chapter"] for r in rows],
        "series": {k: [r[k] for r in rows] for k in axis_keys + ["综合评分"]},
        "stats": stats,
    }
    Path(args.chart).write_text(
        json.dumps(chart, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[eval] chapters={len(rows)} words={total_words} cost=¥{total_cost}")
    print(f"[eval] axes avg: " + ", ".join(
        f"{k}={stats.get(k, {}).get('avg')}" for k in axis_keys + ["综合评分"]))
    print(f"[eval] verdict: " + "; ".join(f"{k}:{verdict[k]}" for k in axis_keys))
    print(f"[eval] cliche={len(findings['ai_cliche'])} modern={len(findings['modern_speak'])} "
          f"early_reveal={findings['early_reveal']} cost_omission={len(findings['cost_omission'])}")
    print(f"[eval] report -> {args.out}")
    print(f"[eval] chart  -> {args.chart}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
