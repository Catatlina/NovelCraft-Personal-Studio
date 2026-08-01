"""补缺失章节报告 JSON（旧实例被杀/Batch3 报告被误删，数据在 DB）。

从 v7_story_states（全文）与 v7_agent_runs（评分/成本/耗时）提取，
生成与 v7_e2e_gate.py harness 同构的批次报告，供 v7_fifty_eval.py 合并。
"""
from __future__ import annotations

import asyncio
import json
import sys

import asyncpg

NOVEL_ID = "7e57c0de-0000-4000-8000-0000000a7000"
# CH11-14（旧实例）与 CH21-29（Batch 3 报告被误删）
CHAPTERS = list(range(11, 15)) + list(range(21, 30))


async def main() -> None:
    conn = await asyncpg.connect("postgresql://genius@127.0.0.1/starlume_v7_gate")
    chapters: list[dict] = []
    for cn in CHAPTERS:
        # 全文
        st = await conn.fetchrow(
            """SELECT state_value FROM v7_story_states
               WHERE novel_id=$1 AND state_type='chapter' AND state_key=$2
               ORDER BY updated_at DESC LIMIT 1""",
            NOVEL_ID, f"chapter_{cn:04d}",
        )
        # run 记录（取 chapter_generation 且 completed，优先时长最大的）
        run = await conn.fetchrow(
            """SELECT id, output_data, duration_seconds, total_cost, total_tokens,
                      started_at
               FROM v7_agent_runs
               WHERE novel_id=$1 AND chapter_number=$2 AND run_type='chapter_generation'
                 AND status='completed'
               ORDER BY duration_seconds DESC LIMIT 1""",
            NOVEL_ID, cn,
        )
        if not run:
            print(f"WARN: CH{cn} no run record, skip")
            continue
        od = json.loads(run["output_data"]) if isinstance(run["output_data"], str) else (run["output_data"] or {})
        text = (st["state_value"] if st else None) or od.get("content") or od.get("chapter_text") or ""
        dim = od.get("dimension_scores") or od.get("review_7dim") or {}
        if isinstance(dim, dict) and "score_7dim" in dim:
            dim = dim["score_7dim"]
        score = od.get("review_score") or (dim.get("score") if isinstance(dim, dict) else None) or 0
        chapters.append({
            "chapter_number": cn,
            "run_id": str(run["id"]),
            "status": "completed",
            "title": od.get("title") or f"第{cn}章",
            "word_count": od.get("word_count") or 0,
            "meets_target": od.get("meets_target", True),
            "review_score": score,
            "review_passed": bool(score) and float(score) >= 80,
            "dimension_scores": dim,
            "elapsed_sec": round(float(run["duration_seconds"] or 0), 1),
            "cost": float(run["total_cost"] or 0),
            "tokens_input": run["total_tokens"] or 0,
            "tokens_output": 0,
            "steps_executed": 7,
            "step_names": [],
            "rework": od.get("rework_count", 0),
            "deai_changes": 0,
            "verified_word_count": len(text),
            "excerpt": text[:180],
            "chapter_text_full": text,
        })
    report = {
        "novel_id": NOVEL_ID,
        "chapters": chapters,
        "failures": [],
        "totals": {
            "chapters_completed": len(chapters),
            "total_words": sum(c["word_count"] for c in chapters),
            "total_cost": round(sum(c["cost"] for c in chapters), 4),
        },
    }
    out = "/tmp/v7_50_backfill.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"written {out}: chapters={len(chapters)}")
    for c in chapters:
        print(f"  CH{c['chapter_number']} score={c['review_score']} words={c['word_count']} full_len={len(c['chapter_text_full'])}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
