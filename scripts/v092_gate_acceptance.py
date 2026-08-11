#!/usr/bin/env python3
"""v0.9.2 七道发布门禁验收脚本

用已有小说的前20章跑门禁，验证门禁功能正确性。
在生产服务器API容器内运行：
  docker exec -w /app -e PYTHONPATH=/app novelcraft-personal-studio-api-1 python /tmp/v092_gate_acceptance.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime

sys.path.insert(0, "/app")

# 用百章一致性小说
NOVEL_ID = "657fb6af-7f1e-4ae5-b492-442e837d9853"
PROJECT_ID = "ba03e391-087b-44ee-9575-3b38bc8cb3de"

PLATFORM_PROFILE = {
    "platform": "fanqie",
    "policy_status": "confirmed",
    "ai_usage_policy": "allowed",
    "chapter_word_min": 1000,
    "chapter_word_max": 5000,
    "policy_version": "test-v1",
    "last_verified_at": datetime.utcnow().isoformat(),
}

METADATA = {
    "title": "百章一致性小说",
    "synopsis": "测试用长篇小说，用于验证系统一致性和质量门禁功能",
    "tags": ["测试", "一致性", "长篇"],
    "category": "玄幻",
}


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def get_chapters(novel_id: str, limit: int = 20) -> list[dict]:
    """获取小说的前N章。"""
    from app.db import connect

    conn = connect()
    try:
        rows = conn.execute(
            """SELECT id, title, status, meta, body
               FROM contents
               WHERE parent_id=%s AND type='chapter'
               ORDER BY (meta->>'chapter_number')::int ASC
               LIMIT %s""",
            (novel_id, limit),
        ).fetchall()
        chapters = []
        for row in rows:
            body = row["body"]
            text = ""
            if isinstance(body, dict):
                text = body.get("text", body.get("content", ""))
            elif body:
                text = str(body)
            chapters.append({
                "id": str(row["id"]),
                "title": row["title"],
                "status": row["status"],
                "chapter_number": row["meta"].get("chapter_number", 0) if row["meta"] else 0,
                "text": text,
                "text_length": len(text),
            })
        return chapters
    finally:
        conn.close()


def run_gates(chapter_id: str, text: str) -> dict:
    """运行七道门禁。"""
    from app.v7.quality.publishing_gates import run_all_gates

    if not text:
        return {"error": "empty text", "gates": {}}

    report = run_all_gates(
        chapter_id=chapter_id,
        text=text,
        platform_profile=PLATFORM_PROFILE,
        metadata=METADATA,
    )

    gates_summary = {}
    for k, g in report.gates.items():
        gates_summary[k] = {
            "passed": g.passed,
            "score": g.score,
            "threshold": g.threshold,
            "is_blocking": g.is_blocking,
            "issues_count": len(g.issues),
            "warnings_count": len(g.warnings),
            "issues": g.issues[:3],  # 只保留前3个issue
        }

    return {
        "quality_candidate": report.quality_candidate,
        "overall_publish_ready": report.overall_publish_ready,
        "blocking_failures": report.blocking_failures,
        "non_blocking_warnings": report.non_blocking_warnings,
        "gates": gates_summary,
    }


def run_statistics(chapter_id: str, text: str) -> dict:
    """运行确定性统计。"""
    from app.v7.quality.statistics_v1 import compute_statistics

    if not text:
        return {}

    result = compute_statistics(text)
    return {
        "chapter_count": result.chapter_count,
        "total_chars": result.total_chars,
        "total_paragraphs": result.total_paragraphs,
        "total_sentences": result.total_sentences,
        "total_dialogues": result.total_dialogues,
        "content_sha256": result.content_sha256[:16] + "...",
        "normalized_sha256": result.normalized_sha256[:16] + "...",
        "anomaly_count": len(result.global_anomalies),
    }


def main() -> None:
    log("=" * 70)
    log("v0.9.2 出版准备层 - 七道门禁验收测试")
    log(f"小说ID: {NOVEL_ID}")
    log(f"测试章节数: 20")
    log("=" * 70)

    # 获取前20章
    log("获取章节列表...")
    chapters = get_chapters(NOVEL_ID, 20)
    log(f"获取到 {len(chapters)} 章")

    if not chapters:
        log("错误：没有找到章节")
        sys.exit(1)

    results = []
    gate_pass_counts = {}
    gate_scores = {}
    publish_ready_count = 0
    quality_candidate_count = 0
    total_time = 0

    for i, ch in enumerate(chapters, 1):
        log(f"\n--- 第 {i}/20 章: {ch['title']} (字数: {ch['text_length']}) ---")

        start = time.time()

        # 运行统计
        stats = run_statistics(ch["id"], ch["text"])
        log(f"  统计: {stats.get('total_paragraphs', 0)}段, {stats.get('total_sentences', 0)}句, "
            f"{stats.get('total_dialogues', 0)}对话, {stats.get('anomaly_count', 0)}异常标点")

        # 运行门禁
        gates_result = run_gates(ch["id"], ch["text"])
        elapsed = time.time() - start
        total_time += elapsed

        results.append({
            "chapter_number": ch["chapter_number"],
            "chapter_id": ch["id"],
            "title": ch["title"],
            "text_length": ch["text_length"],
            "status": ch["status"],
            "statistics": stats,
            "gates": gates_result,
            "elapsed_seconds": round(elapsed, 2),
        })

        # 统计门禁通过率
        if gates_result.get("quality_candidate"):
            quality_candidate_count += 1
        if gates_result.get("overall_publish_ready"):
            publish_ready_count += 1

        gates = gates_result.get("gates", {})
        passed_gates = []
        failed_gates = []
        for k, v in gates.items():
            if k not in gate_pass_counts:
                gate_pass_counts[k] = {"passed": 0, "total": 0}
                gate_scores[k] = []
            gate_pass_counts[k]["total"] += 1
            if v.get("passed"):
                gate_pass_counts[k]["passed"] += 1
                passed_gates.append(k)
            else:
                failed_gates.append(k)
            if v.get("score") is not None:
                gate_scores[k].append(v["score"])

        log(f"  门禁: 通过 {len(passed_gates)}/7, 失败: {failed_gates}")
        log(f"  quality_candidate={gates_result.get('quality_candidate')}, "
            f"publish_ready={gates_result.get('overall_publish_ready')}")
        log(f"  耗时: {elapsed:.2f}s")

    # 生成报告
    log("\n" + "=" * 70)
    log("验收报告汇总")
    log("=" * 70)

    log(f"\n总章节数: {len(results)}")
    log(f"quality_candidate通过: {quality_candidate_count}/{len(results)} "
        f"({quality_candidate_count/len(results)*100:.1f}%)")
    log(f"publish_ready通过: {publish_ready_count}/{len(results)} "
        f"({publish_ready_count/len(results)*100:.1f}%)")
    log(f"总耗时: {total_time:.1f}s, 平均每章: {total_time/len(results):.2f}s")

    log("\n各门禁通过率:")
    log(f"  {'门禁名称':<25} {'通过/总数':<12} {'通过率':<10} {'平均分':<10}")
    log(f"  {'-'*25} {'-'*12} {'-'*10} {'-'*10}")
    for gate_name in sorted(gate_pass_counts.keys()):
        stats = gate_pass_counts[gate_name]
        pass_rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
        avg_score = sum(gate_scores[gate_name]) / len(gate_scores[gate_name]) if gate_scores[gate_name] else 0
        log(f"  {gate_name:<25} {stats['passed']}/{stats['total']:<10} {pass_rate:<10.1f}% {avg_score:<10.1f}")

    # 字数统计
    lengths = [r["text_length"] for r in results]
    log(f"\n正文字数统计:")
    log(f"  平均: {sum(lengths)/len(lengths):.0f} 字")
    log(f"  最少: {min(lengths)} 字")
    log(f"  最多: {max(lengths)} 字")

    # 失败章节详情
    failed_chapters = [r for r in results if not r["gates"].get("overall_publish_ready")]
    if failed_chapters:
        log(f"\npublish_ready未通过章节 ({len(failed_chapters)}章):")
        for r in failed_chapters[:5]:  # 只显示前5个
            blocking = r["gates"].get("blocking_failures", [])
            log(f"  第{r['chapter_number']}章《{r['title']}》: 阻断门禁={blocking}")

    # 保存完整报告
    output_file = f"/tmp/v092_gate_acceptance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    log(f"\n完整报告已保存: {output_file}")

    log("\n" + "=" * 70)
    log("验收完成")
    log("=" * 70)


if __name__ == "__main__":
    main()
