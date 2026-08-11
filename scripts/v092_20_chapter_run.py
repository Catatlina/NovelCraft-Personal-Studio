#!/usr/bin/env python3
"""v0.9.2 出版准备层 20章长跑验收脚本

在生产服务器上运行：
  docker exec novelcraft-personal-studio-api-1 python /tmp/v092_20_chapter_run.py

功能：
1. 用已有小说继续生成到20章（或创建新书）
2. 每章生成后调用七道发布门禁
3. 输出验收报告（质量分分布、连续性、爽点密度、publish_ready通过率）
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import traceback
from datetime import datetime

# 配置
NOVEL_ID = "4a5cb342-c698-40f2-bb62-910c08de5944"
PROJECT_ID = "09865df1-1ec9-443f-aaab-d27e51252b1c"
USER_ID = "6f149e43-f14e-4a18-a991-e1ebdd4881d5"
TARGET_CHAPTERS = 20
START_CHAPTER = 7  # 已有6章，从第7章开始

# 平台配置（用于门禁测试）
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
    "title": "重生后我靠签到系统在侯府杀疯了",
    "synopsis": "林晚重生回到侯府，依靠签到系统在深宅大院中步步为营，逆袭复仇的爽文故事",
    "tags": ["重生", "签到", "宅斗", "逆袭"],
    "category": "古代言情",
}


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


async def generate_one_chapter(chapter_num: int) -> dict:
    """生成一章，返回结果字典。"""
    from app.v7.runtime import generate_v7_chapter

    log(f"开始生成第 {chapter_num} 章...")
    start = time.time()
    try:
        result = await generate_v7_chapter(
            novel_id=NOVEL_ID,
            project_id=PROJECT_ID,
            chapter_number=chapter_num,
            user_id=USER_ID,
        )
        elapsed = time.time() - start
        chapter_id = result.get("chapter_id") or result.get("id") or ""
        status = result.get("status", "unknown")
        log(f"第 {chapter_num} 章生成完成: status={status}, chapter_id={chapter_id}, 耗时={elapsed:.1f}s")
        return {
            "chapter_number": chapter_num,
            "chapter_id": chapter_id,
            "status": status,
            "elapsed_seconds": round(elapsed, 1),
            "success": status in ("success", "completed", "reviewed"),
            "raw": result,
            "error": None,
        }
    except Exception as e:
        elapsed = time.time() - start
        log(f"第 {chapter_num} 章生成失败: {e}, 耗时={elapsed:.1f}s")
        traceback.print_exc()
        return {
            "chapter_number": chapter_num,
            "chapter_id": "",
            "status": "failed",
            "elapsed_seconds": round(elapsed, 1),
            "success": False,
            "raw": {},
            "error": str(e),
        }


def get_chapter_text(chapter_id: str) -> str:
    """从数据库获取章节正文。"""
    if not chapter_id:
        return ""
    from app.db import connect

    conn = connect()
    try:
        row = conn.execute(
            "SELECT body FROM contents WHERE id=%s AND type='chapter'",
            (chapter_id,),
        ).fetchone()
        if row and row["body"]:
            body = row["body"]
            if isinstance(body, dict):
                return body.get("text", body.get("content", ""))
            return str(body)
        return ""
    finally:
        conn.close()


def run_publishing_gates(chapter_id: str, text: str) -> dict:
    """运行七道发布门禁。"""
    from app.v7.quality.publishing_gates import run_all_gates

    if not text:
        return {"error": "empty text", "gates": {}}

    try:
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
                "is_blocking": g.is_blocking,
                "issues_count": len(g.issues),
                "warnings_count": len(g.warnings),
            }
        return {
            "quality_candidate": report.quality_candidate,
            "overall_publish_ready": report.overall_publish_ready,
            "blocking_failures": report.blocking_failures,
            "non_blocking_warnings": report.non_blocking_warnings,
            "gates": gates_summary,
        }
    except Exception as e:
        log(f"门禁运行失败: {e}")
        return {"error": str(e), "gates": {}}


def save_gate_results(chapter_id: str, gates_result: dict) -> None:
    """保存门禁结果到数据库。"""
    if not chapter_id or "gates" not in gates_result:
        return
    from app.db import connect

    conn = connect()
    try:
        for gate_key, gate_data in gates_result["gates"].items():
            conn.execute(
                """INSERT INTO quality_gate_results
                (chapter_id, gate_key, content_sha256, passed, score, threshold,
                 is_blocking, issues, warnings, evidence, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (chapter_id, gate_key, content_sha256) DO UPDATE
                SET passed=EXCLUDED.passed, score=EXCLUDED.score,
                    is_blocking=EXCLUDED.is_blocking, issues=EXCLUDED.issues,
                    warnings=EXCLUDED.warnings, created_at=NOW()""",
                (
                    chapter_id,
                    gate_key,
                    "runtime-" + chapter_id[:8],
                    gate_data.get("passed", False),
                    gate_data.get("score", 0),
                    0,
                    gate_data.get("is_blocking", False),
                    json.dumps([], ensure_ascii=False),
                    json.dumps([], ensure_ascii=False),
                    json.dumps({}, ensure_ascii=False),
                ),
            )
        conn.commit()
    except Exception as e:
        log(f"保存门禁结果失败: {e}")
    finally:
        conn.close()


async def main() -> None:
    log("=" * 60)
    log("v0.9.2 出版准备层 20章长跑验收开始")
    log(f"小说ID: {NOVEL_ID}")
    log(f"目标章节数: {TARGET_CHAPTERS}, 从第 {START_CHAPTER} 章开始")
    log("=" * 60)

    results = []
    success_count = 0
    publish_ready_count = 0

    for chapter_num in range(START_CHAPTER, TARGET_CHAPTERS + 1):
        gen_result = await generate_one_chapter(chapter_num)
        results.append(gen_result)

        if gen_result["success"]:
            success_count += 1
            chapter_id = gen_result["chapter_id"]
            text = get_chapter_text(chapter_id)
            log(f"第 {chapter_num} 章正文长度: {len(text)} 字符")

            if text:
                gates_result = run_publishing_gates(chapter_id, text)
                gen_result["gates"] = gates_result
                gen_result["text_length"] = len(text)

                if gates_result.get("overall_publish_ready"):
                    publish_ready_count += 1

                save_gate_results(chapter_id, gates_result)

                # 打印门禁摘要
                gates = gates_result.get("gates", {})
                passed_gates = [k for k, v in gates.items() if v.get("passed")]
                failed_gates = [k for k, v in gates.items() if not v.get("passed")]
                log(f"  门禁: 通过={len(passed_gates)}/7, 失败={failed_gates}")
                log(f"  publish_ready={gates_result.get('overall_publish_ready')}")
            else:
                gen_result["gates"] = {"error": "no text"}
                log(f"  警告: 第 {chapter_num} 章正文为空，跳过门禁")
        else:
            gen_result["gates"] = {"error": "generation failed"}

        # 每章之间短暂休息，避免限流
        if chapter_num < TARGET_CHAPTERS:
            await asyncio.sleep(2)

    # 生成报告
    log("\n" + "=" * 60)
    log("20章长跑验收报告")
    log("=" * 60)

    total = len(results)
    log(f"总生成章节数: {total}")
    log(f"生成成功: {success_count}/{total}")
    log(f"生成失败: {total - success_count}/{total}")
    log(f"publish_ready通过: {publish_ready_count}/{success_count}")

    # 各门禁通过率
    gate_stats = {}
    for r in results:
        gates = r.get("gates", {})
        for k, v in gates.get("gates", {}).items():
            if k not in gate_stats:
                gate_stats[k] = {"passed": 0, "total": 0, "scores": []}
            gate_stats[k]["total"] += 1
            if v.get("passed"):
                gate_stats[k]["passed"] += 1
            if v.get("score") is not None:
                gate_stats[k]["scores"].append(v["score"])

    log("\n各门禁通过率:")
    for gate_name, stats in sorted(gate_stats.items()):
        pass_rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
        avg_score = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
        log(f"  {gate_name}: {stats['passed']}/{stats['total']} ({pass_rate:.1f}%), 平均分={avg_score:.1f}")

    # 字数统计
    text_lengths = [r.get("text_length", 0) for r in results if r.get("text_length")]
    if text_lengths:
        log(f"\n正文字数统计:")
        log(f"  平均: {sum(text_lengths)/len(text_lengths):.0f} 字")
        log(f"  最少: {min(text_lengths)} 字")
        log(f"  最多: {max(text_lengths)} 字")

    # 耗时统计
    elapsed_list = [r["elapsed_seconds"] for r in results]
    if elapsed_list:
        log(f"\n生成耗时统计:")
        log(f"  平均: {sum(elapsed_list)/len(elapsed_list):.1f}s")
        log(f"  总耗时: {sum(elapsed_list):.1f}s")

    # 失败章节列表
    failed = [r for r in results if not r["success"]]
    if failed:
        log(f"\n失败章节:")
        for r in failed:
            log(f"  第{r['chapter_number']}章: {r.get('error', 'unknown')}")

    # 保存完整结果
    output_file = f"/tmp/v092_20ch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    log(f"\n完整报告已保存: {output_file}")

    log("\n" + "=" * 60)
    log("验收完成")
    log("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
