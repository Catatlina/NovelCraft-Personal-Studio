#!/usr/bin/env python3
"""v0.9.2 门禁快速验收 - 用已有真实章节测试"""
import json
import sys
from datetime import datetime

sys.path.insert(0, "/app")

from app.db import connect
from app.v7.quality.statistics_v1 import compute_statistics
from app.v7.quality.publishing_gates import run_all_gates

NOVEL_ID = "4a5cb342-c698-40f2-bb62-910c08de5944"

PLATFORM = {
    "platform": "fanqie",
    "policy_status": "confirmed",
    "ai_usage_policy": "allowed",
    "chapter_word_min": 1000,
    "chapter_word_max": 5000,
    "policy_version": "test",
    "last_verified_at": datetime.utcnow().isoformat(),
}
META = {
    "title": "重生后我靠签到系统在侯府杀疯了",
    "synopsis": "周薇重生回到侯府，依靠签到系统在深宅大院中步步为营逆袭复仇",
    "tags": ["重生", "签到", "宅斗", "逆袭"],
    "category": "古代言情",
}


def main():
    conn = connect()
    rows = conn.execute(
        "SELECT id, title, status, meta, body FROM contents WHERE parent_id=%s AND type='chapter' ORDER BY (meta->>'chapter_number')::int ASC",
        (NOVEL_ID,),
    ).fetchall()
    conn.close()

    print(f"找到 {len(rows)} 章")
    print("=" * 70)

    gate_stats = {}
    publish_ready_count = 0
    all_results = []

    for row in rows:
        body = row["body"]
        text = body.get("text", "") if isinstance(body, dict) else str(body)
        ch_num = row["meta"].get("chapter_number", "?") if row["meta"] else "?"

        stats = compute_statistics(text)
        report = run_all_gates(
            chapter_id=str(row["id"]),
            text=text,
            platform_profile=PLATFORM,
            metadata=META,
        )

        passed = [k for k, v in report.gates.items() if v.passed]
        failed = [k for k, v in report.gates.items() if not v.passed]

        if report.overall_publish_ready:
            publish_ready_count += 1

        for k, v in report.gates.items():
            if k not in gate_stats:
                gate_stats[k] = {"passed": 0, "total": 0, "scores": []}
            gate_stats[k]["total"] += 1
            if v.passed:
                gate_stats[k]["passed"] += 1
            gate_stats[k]["scores"].append(v.score)

        print(f"第{ch_num}章《{row['title']}》status={row['status']} 字数={len(text)}")
        print(f"  统计: {stats.total_paragraphs}段 {stats.total_sentences}句 {stats.total_dialogues}对话 异常={len(stats.global_anomalies)}")
        print(f"  门禁: 通过{len(passed)}/7 失败={failed}")
        print(f"  quality_candidate={report.quality_candidate} publish_ready={report.overall_publish_ready}")
        print()

        all_results.append({
            "chapter": ch_num,
            "title": row["title"],
            "status": row["status"],
            "text_length": len(text),
            "quality_candidate": report.quality_candidate,
            "publish_ready": report.overall_publish_ready,
            "blocking_failures": report.blocking_failures,
            "gates": {k: {"passed": v.passed, "score": v.score} for k, v in report.gates.items()},
        })

    print("=" * 70)
    print("汇总:")
    print(f"  总章节: {len(rows)}")
    print(f"  publish_ready通过: {publish_ready_count}/{len(rows)}")
    print()
    print("各门禁通过率:")
    for k in sorted(gate_stats.keys()):
        s = gate_stats[k]
        rate = s["passed"] / s["total"] * 100
        avg = sum(s["scores"]) / len(s["scores"]) if s["scores"] else 0
        print(f"  {k:<25} {s['passed']}/{s['total']} ({rate:.0f}%) 平均分={avg:.1f}")

    # 保存结果
    output = f"/tmp/v092_gate_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n完整结果已保存: {output}")


if __name__ == "__main__":
    main()
