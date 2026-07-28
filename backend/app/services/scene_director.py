"""V3-P3-⑪: 场景层（Scene）+ Scene Director。

- split_scenes：确定性地把整章文本切分为场景块（供测试/降级）
- persist_scenes / get_scenes：场景分镜持久化
- direct_scenes：调用 gateway.complete（真实 Provider）产出场景分镜并落库
"""
from __future__ import annotations

import re

from app.db import connect, encode, new_id

# 场景分隔符：独占一行的分割线 / 星标 / 章节内转场
_SCENE_BREAK = re.compile(r"(?:\n\s*(?:——+|—{2,}|\*{3,}|#+|☆{2,}|◇{2,})\s*\n)")

_BEATS = {"起势", "发展", "转折", "高潮", "落幕"}


def split_scenes(chapter_text: str) -> list[str]:
    """把整章正文切分为场景块列表（纯函数，确定性）。"""
    if not chapter_text or not chapter_text.strip():
        return []
    # 先按分隔线切，再对每个块按空行二次切，过长则整体保留
    blocks = _SCENE_BREAK.split(chapter_text)
    scenes: list[str] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        paras = [p.strip() for p in block.split("\n\n") if p.strip()]
        if len(paras) <= 1:
            scenes.append(block)
        else:
            scenes.extend(paras)
    return [s for s in scenes if s]


def normalize_scene(raw: dict, index: int) -> dict:
    """把 Director 输出的单个场景归一化为持久化结构。"""
    if not isinstance(raw, dict):
        return {"title": f"场景{index}", "beat": "发展", "goal": "", "setting": "", "pov": ""}
    beat = str(raw.get("beat", "") or "")
    if beat not in _BEATS:
        beat = "发展"
    return {
        "title": str(raw.get("title", f"场景{index}"))[:200],
        "beat": beat,
        "goal": str(raw.get("goal", "") or "")[:2000],
        "setting": str(raw.get("setting", "") or "")[:2000],
        "pov": str(raw.get("pov", "") or "")[:80],
    }


def persist_scenes(chapter_id: str, project_id: str, scenes: list[dict]) -> int:
    """清空并写入本章场景分镜，返回写入条数。"""
    normalized = [normalize_scene(s, i + 1) for i, s in enumerate(scenes or [])]
    if not normalized:
        return 0
    db = connect()
    db.execute("DELETE FROM scenes WHERE chapter_id = %s", (chapter_id,))
    for i, sc in enumerate(normalized, start=1):
        db.execute(
            """INSERT INTO scenes (id, chapter_id, project_id, scene_index, title, beat, goal, setting, pov, meta)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (new_id(), chapter_id, project_id, i, sc["title"], sc["beat"],
             sc["goal"], sc["setting"], sc["pov"], encode({"source": "scene_director"})),
        )
    db.close()
    return len(normalized)


def get_scenes(chapter_id: str) -> list[dict]:
    db = connect()
    rows = db.execute(
        "SELECT scene_index, title, beat, goal, setting, pov FROM scenes WHERE chapter_id = %s ORDER BY scene_index ASC",
        (chapter_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def direct_scenes(project_id: str, chapter_id: str, chapter_title: str,
                  chapter_function: str, arc_summary: str, recent_summary: str) -> list[dict]:
    """Scene Director 主体：调用真实 Provider 规划本章场景分镜并落库，返回场景列表。"""
    from app.gateway import complete
    output = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="scene_direct", prompt_name="scene.direct",
        variables={
            "chapter_title": chapter_title,
            "chapter_function": chapter_function or "（未设定）",
            "arc_summary": arc_summary or "（暂无）",
            "recent_summary": recent_summary or "（暂无）",
        },
    )
    scenes = output.get("scenes") or []
    persist_scenes(chapter_id, project_id, scenes)
    return get_scenes(chapter_id)
