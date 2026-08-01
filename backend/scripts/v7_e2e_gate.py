#!/usr/bin/env python
"""
V7.0 QA Gate — end-to-end REAL generation harness.

Runs the full Story Director 7-step agent loop against a REAL database and a
REAL DeepSeek endpoint. There is no mock, no stub and no fallback: if the AI
gateway is unavailable the run fails loudly.

Usage:
    DATABASE_URL=postgresql+asyncpg://genius@127.0.0.1/starlume_v7_gate \
    DEEPSEEK_API_KEY=sk-xxx \
    python scripts/v7_e2e_gate.py --chapters 1 --reset

Options:
    --chapters N     number of consecutive chapters to generate (default 1)
    --start N        first chapter number (default 1)
    --reset          wipe all v7_* rows for the harness novel before running
    --words N        target word count per chapter (default 3000)
    --report PATH    write a JSON report to PATH
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.v7.brain.novel_brain import NovelBrain  # noqa: E402
from app.v7.director.story_director import StoryDirector  # noqa: E402
from app.v7.events.event_bus import EventBus  # noqa: E402
from app.v7.generation.generation_engine import chinese_word_count  # noqa: E402
from app.v7.repositories.decision import DecisionPermissionRepository  # noqa: E402
from app.v7.trace.tracer import ExecutionTracer  # noqa: E402

# Stable novel id so repeated runs accumulate against the same story.
HARNESS_NOVEL_ID = uuid.UUID("7e57c0de-0000-4000-8000-0000000a7000")

# Delete order respects foreign keys (children first). Tables are filtered at
# runtime against information_schema, so a table lacking novel_id is skipped
# rather than blowing up the harness.
V7_DELETE_ORDER = [
    "v7_state_changes",
    "v7_agent_traces",
    "v7_prompt_executions",
    "v7_brain_snapshots",
    "v7_story_versions",
    "v7_agent_runs",
    "v7_human_interventions",
    "v7_decision_logs",
    "v7_decision_permissions",
    "v7_event_logs",
    "v7_plot_nodes",
    "v7_story_goals",
    "v7_constraints",
    "v7_story_states",
    "v7_author_intents",
    "v7_cost_budgets",
]


async def novel_scoped_tables(session: AsyncSession) -> set[str]:
    """v7_* tables that actually carry a novel_id column in this database."""
    rows = await session.execute(
        text(
            "SELECT table_name FROM information_schema.columns "
            "WHERE column_name = 'novel_id' AND table_name LIKE 'v7\\_%'"
        )
    )
    return {r[0] for r in rows}

STORY_PREMISE = """《归墟灯》——东方玄幻。
主角江砚，二十三岁，原是大梁国钦天监最年轻的观星郎，因推演出"荧惑守心、国祚将倾"的星象，
被当朝国师以妖言惑众之名投入天牢，家族三十七口尽数流放。狱中第七日，他吞下父亲临刑前
偷偷塞给他的一枚残破铜灯芯，从此双目可见"归墟"——亡者残留在世间的执念之影。
他要做的，是用九盏归墟灯，把当年灭他满门的那道真相，一寸寸照出来。"""


def build_seed() -> dict[str, list[dict[str, Any]]]:
    """Return the deterministic story bible used to seed the brain."""
    return {
        "states": [
            {
                "type": "global",
                "key": "premise",
                "value": {
                    "title": "归墟灯",
                    "genre": "东方玄幻",
                    "premise": STORY_PREMISE,
                    "tone": "冷峻、克制、悬疑推进，忌爽文口水",
                    "pov": "第三人称限知视角，跟随江砚",
                    "target_chapters": 10,
                },
                "confidence": 0.98,
            },
            {
                "type": "character",
                "key": "江砚",
                "value": {
                    "name": "江砚",
                    "age": 23,
                    "role": "主角",
                    "identity": "前钦天监观星郎，现天牢死囚",
                    "ability": "吞下归墟灯芯后可见亡者执念之影，代价是每见一次折损一分阳寿",
                    "voice": "话少，习惯用星象和数字打比方，情绪压在句子底下",
                    "goal": "查清家族被灭门的真相，点亮九盏归墟灯",
                    "flaw": "过度自信于推演，容易忽略人心的不可测",
                    "status": "在押，第七日",
                },
                "confidence": 0.95,
            },
            {
                "type": "character",
                "key": "沈观澜",
                "value": {
                    "name": "沈观澜",
                    "age": 41,
                    "role": "反派",
                    "identity": "大梁国师，实际掌控钦天监",
                    "ability": "通晓改命之术，能以活人气数续国祚",
                    "voice": "温和有礼，越是要杀人越是客气",
                    "secret": "灭江家满门是为了掩盖他自己篡改星录一事",
                },
                "confidence": 0.92,
            },
            {
                "type": "character",
                "key": "阿箬",
                "value": {
                    "name": "阿箬",
                    "age": 16,
                    "role": "配角",
                    "identity": "天牢送饭的哑女，实为归墟灯守灯人后裔",
                    "voice": "不能说话，用手指在饭盒盖上写字",
                    "secret": "知道九盏灯的下落，但被下了噤声咒",
                },
                "confidence": 0.9,
            },
            {
                "type": "world",
                "key": "归墟灯",
                "value": {
                    "name": "归墟灯",
                    "count": 9,
                    "rule": "每盏灯锁一段被抹去的真相，点亮需以持灯人一段真实记忆为引",
                    "cost": "记忆一旦献出永不复返，持灯人会忘记自己为何要点灯",
                    "known_locations": ["天牢地底（第一盏）", "其余八盏下落不明"],
                },
                "confidence": 0.93,
            },
            {
                "type": "world",
                "key": "大梁国",
                "value": {
                    "name": "大梁",
                    "era": "开元二十七年",
                    "power": "钦天监凌驾三省六部，以星象定国策",
                    "conflict": "北境戎狄压境，国师主张以活人气数续国祚",
                },
                "confidence": 0.9,
            },
            {
                "type": "plot",
                "key": "主线_灭门真相",
                "value": {
                    "thread": "江家满门被灭的真相",
                    "status": "open",
                    "known": "官方说法是妖言惑众，实为沈观澜篡改星录灭口",
                    "reveal_plan": "第1-3章埋线，第7章半揭，第10章不完全揭示",
                },
                "confidence": 0.9,
            },
        ],
        "goals": [
            {
                "type": "arc",
                "name": "第一卷：天牢七日",
                "description": "江砚在天牢中觉醒归墟之眼，取得第一盏灯，越狱出天牢。",
                "target_chapter": 10,
                "priority": 90,
            },
            {
                "type": "chapter_goal",
                "name": "觉醒归墟之眼",
                "description": "江砚吞下灯芯后第一次看见亡者执念之影，并意识到父亲留下了信息。",
                "target_chapter": 2,
                "priority": 80,
            },
            {
                "type": "chapter_goal",
                "name": "结识阿箬",
                "description": "江砚发现送饭哑女阿箬并非普通囚役，两人建立初步信任。",
                "target_chapter": 4,
                "priority": 70,
            },
            {
                "type": "chapter_goal",
                "name": "点亮第一盏归墟灯",
                "description": "江砚献出一段童年记忆，点亮天牢地底的第一盏灯。",
                "target_chapter": 7,
                "priority": 85,
            },
            {
                "type": "chapter_goal",
                "name": "越狱",
                "description": "借第一盏灯照出的密道，江砚与阿箬逃出天牢，卷末留下追兵悬念。",
                "target_chapter": 10,
                "priority": 88,
            },
        ],
        "constraints": [
            {
                "type": "character",
                "name": "江砚不得使用现代口语",
                "value": {
                    "rule": "江砚的对白与内心独白必须保持古典书面语感，禁止出现现代词汇"
                           "（如'系统''数据''ok''搞定''情绪价值'等）。",
                },
                "severity": "error",
            },
            {
                "type": "world",
                "name": "归墟灯代价不可省略",
                "value": {
                    "rule": "每次动用归墟之眼或点灯，必须写出明确代价（阳寿折损或记忆献祭），"
                           "不得出现无代价的能力使用。",
                },
                "severity": "error",
            },
            {
                "type": "style",
                "name": "禁AI腔",
                "value": {
                    "rule": "禁止使用'值得一提的是''总的来说''不仅仅是……更是''仿佛……一般'"
                           "等AI高频句式；禁止段末总结升华说教。",
                },
                "severity": "error",
            },
            {
                "type": "plot",
                "name": "真相不得提前全揭",
                "value": {
                    "rule": "第10章之前不得明确写出'沈观澜篡改星录'这一真相，只能给出侧面线索。",
                },
                "severity": "error",
            },
            {
                "type": "style",
                "name": "每章须有钩子",
                "value": {"rule": "每章结尾必须留下未解的悬念或新的威胁，不得平淡收束。"},
                "severity": "warning",
            },
        ],
        "outlines": {
            1: "第七日。江砚在天牢中回忆被捕经过，吞下父亲留下的铜灯芯，剧痛中双目渗血。"
               "牢头前来宣读流放名单，江砚从名单的排序中察觉异常。章末灯芯发烫。",
            2: "灯芯化入眼中，江砚第一次看见'影'——一个死在这间牢房里的旧囚，反复重复同一个动作。"
               "他意识到这是执念残留，并付出第一次阳寿代价（咳血）。",
            3: "江砚试图读懂旧囚的执念，发现对方在墙上刻过东西。他借夜色摸索墙面，"
               "触到被泥灰掩盖的刻痕，其中一个字是'砚'。",
            4: "送饭哑女阿箬第一次引起江砚注意——她在饭盒盖上写下'别看'。江砚试探，"
               "阿箬手指发抖，颈侧浮出咒纹。",
            5: "国师沈观澜亲自来天牢'探望'。一场极有礼貌的对话，暗流汹涌。"
               "江砚用星象术语暗示自己什么都没忘，沈观澜微笑离开。",
            6: "牢中开始死人。江砚借归墟之眼看见新死者的执念，发现他们死前都见过同一个人。"
               "阳寿代价加重，江砚开始掉头发。",
            7: "阿箬带江砚下到天牢地底，第一盏归墟灯就在那里。点灯需献祭一段真实记忆——"
               "江砚献出了母亲的脸。灯亮，照出一条密道，也照出江家灭门夜的一角。",
            8: "灯照出的画面与官方卷宗矛盾。江砚推演出'有人改过星录'，但想不起自己为何执着于此"
               "（记忆献祭的后遗症）。阿箬用手指补全了他忘掉的部分。",
            9: "沈观澜察觉地底异动，封锁天牢。江砚与阿箬被困密道，追兵在后。"
               "江砚被迫再次动用归墟之眼寻路，代价是又一次咳血。",
            10: "密道尽头是钦天监的观星台底座。两人逃出天牢，但江砚发现自己已经忘了母亲长什么样。"
                "远处，沈观澜站在观星台上，正望着他们离开的方向。",
        },
    }


async def wipe_novel(session: AsyncSession, novel_id: uuid.UUID) -> dict[str, int]:
    """Delete all v7 rows for the harness novel. Returns deleted counts."""
    available = await novel_scoped_tables(session)
    deleted: dict[str, int] = {}
    for table in V7_DELETE_ORDER:
        if table not in available:
            continue
        res = await session.execute(
            text(f"DELETE FROM {table} WHERE novel_id = :nid"), {"nid": novel_id}
        )
        if res.rowcount:
            deleted[table] = res.rowcount
    await session.commit()
    return deleted


async def seed_brain(brain: NovelBrain, seed: dict[str, Any]) -> dict[str, int]:
    """Seed states / goals / constraints. Idempotent-ish: skips if already seeded."""
    existing = await brain.state.get_state("global", "premise")
    if existing:
        return {"skipped": 1}

    counts = {"states": 0, "goals": 0, "constraints": 0}
    for s in seed["states"]:
        await brain.state.update_state(
            s["type"], s["key"], s["value"], s["confidence"],
            source="human", reason="QA gate seed",
        )
        counts["states"] += 1
    for g in seed["goals"]:
        await brain.goals.create_goal(
            g["type"], g["name"],
            description=g["description"],
            target_chapter=g["target_chapter"],
            priority=g["priority"],
        )
        counts["goals"] += 1
    for c in seed["constraints"]:
        await brain.constraints.create_constraint(
            c["type"], c["name"], c["value"], severity=c["severity"],
        )
        counts["constraints"] += 1
    return counts


async def configure_human_approval(
    session: AsyncSession, novel_id: uuid.UUID
) -> None:
    """Simulate the human producer taking over the bulk run.

    In the real product a human would flip the ``chapter_plan`` permission to
    auto (or approve each escalated plan via the human-intervention UI). For an
    unattended QA gate we configure the same policy directly: auto-approve
    chapter plans whose assess confidence is at least 0.3. The confidence gate
    CODE stays active — a pathological assessment (<0.3) would still block.
    """
    repo = DecisionPermissionRepository(session)
    existing = await repo.get_by_type(novel_id, "chapter_plan")
    if existing:
        existing.permission_level = "auto"
        existing.confidence_threshold = 0.3
        session.add(existing)
    else:
        await repo.create({
            "novel_id": novel_id,
            "decision_type": "chapter_plan",
            "permission_level": "auto",
            "confidence_threshold": 0.3,
            "is_active": True,
            "priority": 50,
        })


async def db_snapshot(session: AsyncSession, novel_id: uuid.UUID) -> dict[str, int]:
    """Row counts per v7 table for the harness novel — the DB-side proof."""
    available = await novel_scoped_tables(session)
    out: dict[str, int] = {}
    for table in sorted(available):
        q = f"SELECT count(*) FROM {table} WHERE novel_id = :nid"
        out[table] = (await session.execute(text(q), {"nid": novel_id})).scalar_one()
    return out


def summarise_chapter(result: dict[str, Any]) -> dict[str, Any]:
    """Extract the QA-relevant numbers from one generate_chapter result."""
    usage = result.get("usage") or {}
    memory = result.get("memory") or {}
    steps = result.get("steps_executed") or []
    return {
        "chapter_number": result.get("chapter_number"),
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "title": result.get("title"),
        "word_count": result.get("word_count"),
        "meets_target": result.get("meets_target"),
        "steps_executed": len(steps),
        "step_names": list(steps),
        "review_score": result.get("review_score"),
        "review_passed": result.get("passed_review"),
        "dimension_scores": result.get("dimension_scores"),
        "rework": result.get("rework_count", 0),
        "memory_applied": memory.get("states_applied"),
        "memory_pending": memory.get("states_pending_review"),
        "memory_discarded": memory.get("states_discarded"),
        "memory_conflicts": memory.get("conflicts_found"),
        "tokens_input": usage.get("tokens_input"),
        "tokens_output": usage.get("tokens_output"),
        "cost": usage.get("cost"),
        "deai_changes": (result.get("deai") or {}).get("total_changes"),
        "deai_layers": (result.get("deai") or {}).get("layers_applied"),
        "human_approved": result.get("human_approved", False),
        "escalation_reason": result.get("escalation_reason"),
        "trace_step_count": (result.get("run_stats") or {}).get("step_count"),
        "run_total_tokens": (result.get("run_stats") or {}).get("total_tokens"),
        "run_total_cost": (result.get("run_stats") or {}).get("total_cost"),
        "run_duration_sec": (result.get("run_stats") or {}).get("duration_seconds"),
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chapters", type=int, default=1)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--words", type=int, default=3000)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--report", type=str, default=None)
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("FATAL: DATABASE_URL not set", file=sys.stderr)
        return 2
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("FATAL: DEEPSEEK_API_KEY not set — this harness performs REAL AI calls "
              "and will not fake results.", file=sys.stderr)
        return 2

    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    novel_id = HARNESS_NOVEL_ID
    report: dict[str, Any] = {
        "novel_id": str(novel_id),
        "database": db_url.split("@")[-1],
        "chapters_requested": args.chapters,
        "target_words": args.words,
        "chapters": [],
        "failures": [],
    }

    async with Session() as session:
        if args.reset:
            deleted = await wipe_novel(session, novel_id)
            print(f"[reset] deleted rows: {deleted or 'none'}")
            report["reset"] = deleted

        brain = NovelBrain(session, novel_id)
        seed = build_seed()
        seeded = await seed_brain(brain, seed)
        await session.commit()
        print(f"[seed] {seeded}")
        report["seed"] = seeded

    overall_start = time.time()

    for i in range(args.chapters):
        chapter_number = args.start + i
        outline = build_seed()["outlines"].get(chapter_number)
        started = time.time()
        # Fresh session per chapter — mirrors a real per-request lifecycle and
        # proves state is read back from the DB, not from in-memory carry-over.
        async with Session() as session:
            brain = NovelBrain(session, novel_id)
            tracer = ExecutionTracer(session, novel_id)
            event_bus = EventBus(session, novel_id)
            director = StoryDirector(session, novel_id, brain, tracer, event_bus)
            try:
                result = await director.generate_chapter(
                    chapter_number,
                    outline=outline,
                    target_word_count=args.words,
                )
                # The confidence gate escalated this chapter for human approval
                # (Sprint 2 QA gate working as designed). Simulate the human
                # producer approving the plan and regenerate, so a bulk run can
                # still produce a full 10-chapter draft.
                if result.get("status") == "pending_approval":
                    escalation_reason = result.get("blocked_reason")
                    await configure_human_approval(session, novel_id)
                    await session.commit()
                    result = await director.generate_chapter(
                        chapter_number,
                        outline=outline,
                        target_word_count=args.words,
                    )
                    result["human_approved"] = True
                    result["escalation_reason"] = escalation_reason
                await session.commit()
            except Exception as exc:  # noqa: BLE001 - harness must report truthfully
                await session.rollback()
                elapsed = time.time() - started
                tb = traceback.format_exc()
                print(f"\n### CH{chapter_number} FAILED after {elapsed:.1f}s: {exc}\n{tb}")
                report["failures"].append({
                    "chapter": chapter_number,
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": tb.splitlines()[-12:],
                    "elapsed_sec": round(elapsed, 1),
                })
                break

            elapsed = time.time() - started
            summary = summarise_chapter(result)
            summary["elapsed_sec"] = round(elapsed, 1)
            summary["dispatch_errors"] = len(event_bus.dispatch_errors)
            if event_bus.dispatch_errors:
                summary["dispatch_error_detail"] = event_bus.dispatch_errors[:3]

            text_body = result.get("content") or result.get("chapter_text") or ""
            summary["verified_word_count"] = chinese_word_count(text_body)
            summary["excerpt"] = text_body[:180]

            report["chapters"].append(summary)
            print(
                f"[CH{chapter_number:02d}] status={summary['status']} "
                f"words={summary['verified_word_count']} "
                f"score={summary['review_score']} "
                f"steps={summary['steps_executed']} "
                f"mem(a/p/d)={summary['memory_applied']}/{summary['memory_pending']}/"
                f"{summary['memory_discarded']} "
                f"tok={summary['tokens_input']}+{summary['tokens_output']} "
                f"cost=¥{summary['cost']} "
                f"deai={summary['deai_changes']} "
                f"{summary['elapsed_sec']}s"
            )

    report["total_elapsed_sec"] = round(time.time() - overall_start, 1)

    async with Session() as session:
        report["db_counts"] = await db_snapshot(session, novel_id)
        brain = NovelBrain(session, novel_id)
        report["brain_overview"] = await brain.get_overview()

    ok_chapters = [c for c in report["chapters"] if c["status"] == "completed"]
    report["totals"] = {
        "chapters_completed": len(ok_chapters),
        "total_words": sum(c["verified_word_count"] or 0 for c in ok_chapters),
        "total_cost": round(sum(c["cost"] or 0 for c in ok_chapters), 4),
        "total_tokens_in": sum(c["tokens_input"] or 0 for c in ok_chapters),
        "total_tokens_out": sum(c["tokens_output"] or 0 for c in ok_chapters),
        "avg_score": (
            round(sum(c["review_score"] or 0 for c in ok_chapters) / len(ok_chapters), 2)
            if ok_chapters else None
        ),
    }

    print("\n=== DB COUNTS ===")
    for k, v in report["db_counts"].items():
        if v:
            print(f"  {k}: {v}")
    print("=== TOTALS ===")
    print(json.dumps(report["totals"], ensure_ascii=False, indent=2))

    if args.report:
        Path(args.report).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"\n[report] written to {args.report}")

    await engine.dispose()
    return 0 if not report["failures"] and ok_chapters else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
