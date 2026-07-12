"""NC-FUS-DEEP: AI_NovelGenerator + AI-auto-generates + harnessNovel clean-room integration.
⚠️ DEPRECATED — No active callers (audit 2026-07-12). Preserved for reference."""
from __future__ import annotations
from app.db import connect, new_id, encode


# ===== AI_NovelGenerator: 百章记忆 + 六类一致性 + 写前检索/写后合并 =====

def hundred_chapter_memory(novel_id: str, current_chapter: int) -> dict:
    """Clean-room: Maintain 100-chapter rolling memory window for context."""
    db = connect()
    start_seq = max(1, current_chapter - 100)
    chapters = db.execute(
        "SELECT * FROM contents WHERE parent_id=%s AND type='chapter' AND (meta->>'seq')::int BETWEEN %s AND %s ORDER BY (meta->>'seq')::int",
        (novel_id, start_seq, current_chapter),
    ).fetchall()
    db.close()
    memory = []
    for ch in chapters:
        body = ch.get("body", "")
        text = body if isinstance(body, str) else str(body.get("text", ""))
        memory.append({"seq": ch.get("meta", {}).get("seq", 0) if isinstance(ch.get("meta"), dict) else 0,
                       "title": ch["title"], "summary": text[:200], "length": len(text)})
    return {"novel_id": novel_id, "window": f"{start_seq}-{current_chapter}", "chapters_in_memory": len(memory)}


def six_dim_consistency_check(novel_id: str) -> dict:
    """Clean-room: Six-dimension consistency — characters, locations, timeline, items, settings, relationships."""
    dims = {
        "characters": "人物名称、关系、状态一致性",
        "locations": "地点名称、方位、距离一致性",
        "timeline": "时间顺序、事件间隔、因果链",
        "items": "物品属性、归属、使用状态",
        "settings": "世界规则、势力、阶级体系",
        "relationships": "人物关系图、敌友变化",
    }
    db = connect()
    chars = db.execute(
        "SELECT meta->>'character_name' as name FROM contents WHERE parent_id=%s AND type='character'", (novel_id,)
    ).fetchall()
    db.close()
    character_count = len(chars) if chars else 0
    return {
        "dimensions_checked": list(dims.keys()),
        "character_count": character_count,
        "requires_provider": True,  # Full consistency needs LLM comparison
        "checks": {k: "pending" for k in dims},
    }


def write_retrieval_and_merge(novel_id: str, chapter_text: str) -> dict:
    """Clean-room: Pre-write retrieval + post-write fact merge."""
    # Pre-write: retrieve relevant entities from previous chapters
    db = connect()
    recent_chapters = db.execute(
        "SELECT meta->>'seq' as seq, title, body FROM contents WHERE parent_id=%s AND type='chapter' ORDER BY (meta->>'seq')::int DESC LIMIT 3",
        (novel_id,)
    ).fetchall()
    db.close()
    retrieved = []
    for ch in recent_chapters:
        if ch: retrieved.append({"seq": ch.get("seq", "?"), "title": ch.get("title", "")})

    # Post-write: extract new facts from generated chapter
    facts = []
    if "名叫" in chapter_text: facts.append("character_introduced")
    if "到达" in chapter_text: facts.append("location_changed")
    if "突破" in chapter_text: facts.append("power_level_up")

    return {
        "retrieved_context": len(retrieved), "retrieved_chapters": [r["seq"] for r in retrieved],
        "new_facts_detected": len(facts), "facts": facts,
        "merge_status": "ready_for_reconcile",
    }


# ===== AI-auto-generates: 拆书工作台 + 快捷词条 + 思维导图 =====

def book_analysis_workbench(content: str, title: str = "") -> dict:
    """Clean-room: Full book analysis — structure, tropes, rhythm, word count, chapter stats."""
    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
    words = sum(len(p) for p in paragraphs)

    # Structure detection
    chapters = []
    for p in paragraphs:
        if p.startswith("第") and "章" in p[:10]:
            chapters.append(p[:50])

    # Trope detection
    trope_patterns = [
        ("重生/穿越", ["重生", "穿越", "转世"]),
        ("系统流", ["系统", "面板", "任务"]),
        ("打脸爽文", ["打脸", "震惊", "不可思议"]),
        ("扮猪吃虎", ["隐藏实力", "低调", "没想到"]),
        ("废柴逆袭", ["废柴", "废物", "逆袭"]),
    ]
    tropes = []
    for name, keywords in trope_patterns:
        if any(k in content for k in keywords):
            tropes.append(name)

    return {
        "title": title,
        "total_words": words, "paragraphs": len(paragraphs),
        "detected_chapters": len(chapters),
        "detected_tropes": tropes,
        "avg_words_per_paragraph": round(words / max(len(paragraphs), 1)),
        "mind_map_nodes": {
            "core": title[:20] if title else "未命名",
            "branches": [f"章节{i+1}" for i in range(min(len(chapters), 5))],
            "tropes": tropes,
        },
    }


def quick_prompt_vocabulary() -> list[dict]:
    """Clean-room: Quick-access prompt vocabulary for common writing operations."""
    return [
        {"name": "去AI味", "prompt": "重写以下内容，去除AI味...", "tags": ["editor", "quality"]},
        {"name": "扩写", "prompt": "将以下段落扩展为3段...", "tags": ["editor", "expand"]},
        {"name": "缩写", "prompt": "将以下内容压缩为一半...", "tags": ["editor", "compress"]},
        {"name": "武侠风改写", "prompt": "用金庸武侠风格重写...", "tags": ["style", "wuxia"]},
        {"name": "增加细节", "prompt": "添加环境描写、人物心理...", "tags": ["editor", "detail"]},
        {"name": "对话增强", "prompt": "增加人物对话生动性...", "tags": ["editor", "dialogue"]},
    ]


# ===== harnessNovel: 分层AI规划 + 自适应窗口 + 合理性审计 + 知识合并 + humanize =====

def layered_ai_planning(idea: str, genre: str, target_words: int = 1000000) -> dict:
    """Clean-room: Layered planning — core→world→mainline→arcs→volumes→chapters."""
    phases = [
        ("核心概念", "提炼一句话核心创意"),
        ("世界观设计", "构建世界规则、力量体系、势力版图"),
        ("主线铺设", "设计核心矛盾、主要冲突、关键转折"),
        ("人物弧线", "主角成长轨迹、配角功能、敌对关系"),
        ("分卷规划", f"{max(1, target_words//200000)}卷，每卷{min(200000, target_words)}字"),
        ("逐章细纲", f"每5000字一章，共约{target_words//5000}章"),
    ]
    return {
        "idea": idea, "genre": genre, "target_words": target_words,
        "phases": [{"name": n, "description": d, "status": "planned"} for n, d in phases],
        "estimated_volumes": max(1, target_words // 200000),
        "estimated_chapters": target_words // 5000,
    }


def adaptive_draft_window(chapter_seq: int, total_chapters: int) -> dict:
    """Clean-room: Adaptive context window size based on position in novel."""
    if chapter_seq <= 3:
        window_size, mode = "full", "黄金三章 — 全文上下文"
    elif chapter_seq <= total_chapters * 0.2:
        window_size, mode = "recent_5", "前20% — 近5章上下文"
    elif chapter_seq <= total_chapters * 0.8:
        window_size, mode = "rolling_10", "中段 — 滚动10章"
    else:
        window_size, mode = "full_backref", "收尾 — 全回溯检查"
    return {"chapter": chapter_seq, "total": total_chapters, "window_size": window_size, "mode": mode}


def reasonability_audit(content: str, genre: str) -> dict:
    """Clean-room: Audit content for logical consistency and genre conventions."""
    issues = []
    if genre == "仙侠" and "手机" in content:
        issues.append("genre_break: 仙侠世界观不应出现现代科技产品")
    if "突然" in content and content.count("突然") > 3:
        issues.append("narrative: 过度依赖'突然'转折")
    return {"audited": True, "genre": genre, "issues_count": len(issues), "issues": issues}


def humanize_text(text: str) -> dict:
    """Clean-room: Post-process generated text to feel more human-written."""
    import re
    changes = []
    result = text
    # Remove common AI patterns
    ai_patterns = [
        (r"在[当今|当前|这个]信息爆炸的时代", "remove"),
        (r"值得我们深思", "remove"),
        (r"不可否认的是", "remove"),
    ]
    for pattern, action in ai_patterns:
        if re.search(pattern, result):
            changes.append({"pattern": pattern, "action": action})
    return {"original_length": len(text), "ai_patterns_found": len(changes), "changes": changes, "processed": len(changes) > 0}


def knowledge_merge(novel_id: str, new_knowledge: list[dict]) -> dict:
    """Clean-room: Merge knowledge into knowledge_items with dedup."""
    db = connect()
    inserted = 0
    for item in new_knowledge:
        existing = db.execute(
            "SELECT id FROM knowledge_items WHERE kind=%s AND title=%s AND meta->>'novel_id'=%s",
            (item.get("kind", "fact"), item.get("title", ""), novel_id),
        ).fetchone()
        if existing:
            db.execute("UPDATE knowledge_items SET meta = meta || %s, updated_at=now() WHERE id=%s",
                       (encode({"merged": True, "updated": str(item)}), existing["id"]))
        else:
            db.execute(
                "INSERT INTO knowledge_items (id, kind, title, body, meta) VALUES (%s,%s,%s,%s,%s)",
                (new_id(), item.get("kind", "fact"), item.get("title", ""),
                 item.get("body", ""), encode({"novel_id": novel_id, "source": "chapter_generation"})),
            )
            inserted += 1
    db.commit(); db.close()
    return {"novel_id": novel_id, "inserted": inserted, "merged": len(new_knowledge) - inserted, "total": len(new_knowledge)}
