"""
品类库初始化脚本

功能：
1. 创建基础品类树（base → tomato/qidian/jjwxc → datang/fengshen）
2. 导入通用网文基类规则包
3. 导入各品类预置内容

使用方式：
    python scripts/init_genre_library.py
"""
from __future__ import annotations

import asyncio
import sys
import os
from typing import Any

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy.ext.asyncio import AsyncSession
from app.v7.db import async_engine, get_async_db
from app.v7.models.genre import GenrePack, GenreRule, GenreKnowledge, GenrePrompt
from app.v7.services.genre_inheritance import clear_inheritance_cache


# ── 基础品类定义 ──────────────────────────────────────────────────────────

BASE_GENRES = [
    {
        "slug": "base",
        "name": "通用网文",
        "description": "所有网文品类的基础父类，包含通用规则和质量标准",
        "scope": "webnovel",
        "is_builtin": True,
        "parent_slug": None,
    },
    {
        "slug": "tomato",
        "name": "番茄爽文",
        "description": "番茄小说平台的爽文风格，快节奏、强冲突、爽点密集",
        "scope": "fanqie",
        "is_builtin": True,
        "parent_slug": "base",
    },
    {
        "slug": "qidian",
        "name": "起点玄幻",
        "description": "起点中文网的玄幻风格，世界观宏大、慢热、铺垫充分",
        "scope": "qidian",
        "is_builtin": True,
        "parent_slug": "base",
    },
    {
        "slug": "jjwxc",
        "name": "晋江言情",
        "description": "晋江文学城的言情风格，感情细腻、文笔优美",
        "scope": "jjwxc",
        "is_builtin": True,
        "parent_slug": "base",
    },
    {
        "slug": "datang",
        "name": "大唐后台",
        "description": "大唐背景的朝堂权谋文，继承番茄爽文风格",
        "scope": "fanqie",
        "is_builtin": True,
        "parent_slug": "tomato",
    },
    {
        "slug": "fengshen",
        "name": "封神举国",
        "description": "封神背景的举国流小说，继承番茄爽文风格",
        "scope": "fanqie",
        "is_builtin": True,
        "parent_slug": "tomato",
    },
]


# ── 通用网文基类规则 ──────────────────────────────────────────────────────

BASE_RULES = [
    # ── 章节基础规则 ──
    {
        "rule_type": "chapter_basic",
        "rule_key": "chapter_word_count_min",
        "rule_value": {"min": 2000, "unit": "words"},
        "severity": "warning",
        "priority": 80,
        "description": "章节最少字数",
    },
    {
        "rule_type": "chapter_basic",
        "rule_key": "chapter_word_count_max",
        "rule_value": {"max": 5000, "unit": "words"},
        "severity": "warning",
        "priority": 80,
        "description": "章节最多字数",
    },
    {
        "rule_type": "chapter_basic",
        "rule_key": "chapter_word_count_target",
        "rule_value": {"target": 3000, "unit": "words"},
        "severity": "info",
        "priority": 70,
        "description": "章节目标字数",
    },
    {
        "rule_type": "chapter_basic",
        "rule_key": "paragraph_count_min",
        "rule_value": {"min": 10, "unit": "paragraphs"},
        "severity": "warning",
        "priority": 60,
        "description": "最少段落数",
    },
    {
        "rule_type": "chapter_basic",
        "rule_key": "dialogue_ratio_min",
        "rule_value": {"min": 0.2, "unit": "ratio"},
        "severity": "info",
        "priority": 50,
        "description": "对话占比最低值",
    },
    {
        "rule_type": "chapter_basic",
        "rule_key": "dialogue_ratio_max",
        "rule_value": {"max": 0.7, "unit": "ratio"},
        "severity": "info",
        "priority": 50,
        "description": "对话占比最高值",
    },
    {
        "rule_type": "chapter_basic",
        "rule_key": "avg_paragraph_length_target",
        "rule_value": {"target": 80, "unit": "chars"},
        "severity": "info",
        "priority": 50,
        "description": "平均段落长度目标",
    },
    
    # ── 通用禁止词规则 ──
    {
        "rule_type": "forbidden_words",
        "rule_key": "sensitive_political",
        "rule_value": {
            "words": [],
            "description": "政治敏感词（根据实际情况补充）",
        },
        "severity": "blocking",
        "priority": 100,
        "description": "政治敏感词禁止",
    },
    {
        "rule_type": "forbidden_words",
        "rule_key": "sensitive_pornography",
        "rule_value": {
            "words": [],
            "description": "色情低俗词（根据实际情况补充）",
        },
        "severity": "blocking",
        "priority": 100,
        "description": "色情低俗词禁止",
    },
    {
        "rule_type": "forbidden_words",
        "rule_key": "sensitive_violence",
        "rule_value": {
            "words": [],
            "description": "暴力血腥词（根据实际情况补充）",
        },
        "severity": "error",
        "priority": 90,
        "description": "暴力血腥词禁止",
    },
    {
        "rule_type": "forbidden_words",
        "rule_key": "author_self_insertion",
        "rule_value": {
            "words": ["作者", "笔者", "我（作者）"],
            "description": "作者自我代入的词汇",
        },
        "severity": "warning",
        "priority": 60,
        "description": "禁止作者自我代入",
    },
    {
        "rule_type": "forbidden_words",
        "rule_key": "breaking_fourth_wall",
        "rule_value": {
            "words": ["各位读者", "读者朋友们", "看到这里", "本章完", "下章预告"],
            "description": "打破第四面墙的词汇",
        },
        "severity": "warning",
        "priority": 50,
        "description": "禁止打破第四面墙",
    },
    
    # ── AI 味禁止规则（词级） ──
    {
        "rule_type": "ai_smell_lexicon",
        "rule_key": "abstract_adverbs_max",
        "rule_value": {"max": 5, "unit": "per_1000_chars"},
        "severity": "warning",
        "priority": 70,
        "description": "抽象副词密度上限（深深地、缓缓地等）",
    },
    {
        "rule_type": "ai_smell_lexicon",
        "rule_key": "transition_words_max",
        "rule_value": {"max": 10, "unit": "per_1000_chars"},
        "severity": "warning",
        "priority": 70,
        "description": "转折词密度上限（然而、但是等）",
    },
    {
        "rule_type": "ai_smell_lexicon",
        "rule_key": "summary_sentences_max",
        "rule_value": {"max": 8, "unit": "per_1000_chars"},
        "severity": "warning",
        "priority": 65,
        "description": "总结句密度上限（他知道、从此等）",
    },
    {
        "rule_type": "ai_smell_lexicon",
        "rule_key": "le_word_max",
        "rule_value": {"max": 40, "unit": "per_1000_chars"},
        "severity": "info",
        "priority": 50,
        "description": "\"了\"字密度上限",
    },
    
    # ── AI 味禁止规则（模式级） ──
    {
        "rule_type": "ai_smell_structural",
        "rule_key": "paragraph_opening_repeat_max",
        "rule_value": {"max": 0.25, "unit": "ratio"},
        "severity": "warning",
        "priority": 65,
        "description": "段落首句雷同比例上限",
    },
    {
        "rule_type": "ai_smell_structural",
        "rule_key": "dialogue_omit_ratio_min",
        "rule_value": {"min": 0.15, "unit": "ratio"},
        "severity": "info",
        "priority": 50,
        "description": "对话省略比例下限（越高越自然）",
    },
    {
        "rule_type": "ai_smell_structural",
        "rule_key": "paragraph_rhythm_cv_min",
        "rule_value": {"min": 0.20, "unit": "ratio"},
        "severity": "info",
        "priority": 50,
        "description": "段落节奏变异系数下限（越高节奏越丰富）",
    },
    
    # ── 基础质量规则 ──
    {
        "rule_type": "quality_threshold",
        "rule_key": "overall_score_min",
        "rule_value": {"min": 60, "unit": "score"},
        "severity": "error",
        "priority": 90,
        "description": "总体评分最低标准",
    },
    {
        "rule_type": "quality_threshold",
        "rule_key": "plot_coherence_min",
        "rule_value": {"min": 70, "unit": "score"},
        "severity": "warning",
        "priority": 80,
        "description": "剧情连贯性最低标准",
    },
    {
        "rule_type": "quality_threshold",
        "rule_key": "character_consistency_min",
        "rule_value": {"min": 70, "unit": "score"},
        "severity": "warning",
        "priority": 80,
        "description": "人物一致性最低标准",
    },
    {
        "rule_type": "quality_threshold",
        "rule_key": "writing_quality_min",
        "rule_value": {"min": 65, "unit": "score"},
        "severity": "warning",
        "priority": 75,
        "description": "文笔质量最低标准",
    },
    {
        "rule_type": "quality_threshold",
        "rule_key": "dialogue_quality_min",
        "rule_value": {"min": 60, "unit": "score"},
        "severity": "info",
        "priority": 60,
        "description": "对话质量最低标准",
    },
    {
        "rule_type": "quality_threshold",
        "rule_key": "pacing_min",
        "rule_value": {"min": 60, "unit": "score"},
        "severity": "info",
        "priority": 60,
        "description": "节奏把控最低标准",
    },
    {
        "rule_type": "quality_threshold",
        "rule_key": "immersion_min",
        "rule_value": {"min": 60, "unit": "score"},
        "severity": "info",
        "priority": 60,
        "description": "沉浸感最低标准",
    },
    
    # ── 基础门禁规则 ──
    {
        "rule_type": "quality_gate",
        "rule_key": "required_checks",
        "rule_value": {
            "checks": [
                "sensitive_content",
                "profanity_check",
                "duplicate_check",
            ],
            "description": "必须通过的检查项",
        },
        "severity": "blocking",
        "priority": 100,
        "description": "质量门禁必须通过的检查项",
    },
    {
        "rule_type": "quality_gate",
        "rule_key": "max_reworks",
        "rule_value": {"max": 3, "unit": "times"},
        "severity": "error",
        "priority": 90,
        "description": "最大重写次数",
    },
    {
        "rule_type": "quality_gate",
        "rule_key": "max_local_repairs",
        "rule_value": {"max": 1, "unit": "times"},
        "severity": "warning",
        "priority": 80,
        "description": "最大本地修复次数",
    },
    
    # ── 风格卡规则 ──
    {
        "rule_type": "style_card",
        "rule_key": "general_style",
        "rule_value": {
            "tone": "neutral",
            "pacing": "moderate",
            "description": "通用网文风格：节奏适中，叙事清晰",
        },
        "severity": "info",
        "priority": 50,
        "description": "通用风格卡",
    },
]


# ── 番茄爽文规则（继承 base，覆盖部分规则） ──────────────────────────────

TOMATO_RULES = [
    # ── 章节基础（覆盖） ──
    {
        "rule_type": "chapter_basic",
        "rule_key": "chapter_word_count_target",
        "rule_value": {"target": 2500, "unit": "words"},
        "severity": "info",
        "priority": 70,
        "description": "番茄章节目标字数（更短）",
    },
    {
        "rule_type": "chapter_basic",
        "rule_key": "dialogue_ratio_min",
        "rule_value": {"min": 0.3, "unit": "ratio"},
        "severity": "info",
        "priority": 50,
        "description": "番茄对话占比最低值（更高）",
    },
    
    # ── AI 味规则（更严格） ──
    {
        "rule_type": "ai_smell_lexicon",
        "rule_key": "abstract_adverbs_max",
        "rule_value": {"max": 2, "unit": "per_1000_chars"},
        "severity": "warning",
        "priority": 80,
        "description": "番茄抽象副词密度上限（更严格）",
    },
    {
        "rule_type": "ai_smell_lexicon",
        "rule_key": "transition_words_max",
        "rule_value": {"max": 5, "unit": "per_1000_chars"},
        "severity": "warning",
        "priority": 80,
        "description": "番茄转折词密度上限（更严格）",
    },
    {
        "rule_type": "ai_smell_lexicon",
        "rule_key": "summary_sentences_max",
        "rule_value": {"max": 3, "unit": "per_1000_chars"},
        "severity": "warning",
        "priority": 75,
        "description": "番茄总结句密度上限（更严格）",
    },
    {
        "rule_type": "ai_smell_lexicon",
        "rule_key": "le_word_max",
        "rule_value": {"max": 30, "unit": "per_1000_chars"},
        "severity": "info",
        "priority": 60,
        "description": "番茄\"了\"字密度上限（更严格）",
    },
    
    # ── 模式级 AI 味（更严格） ──
    {
        "rule_type": "ai_smell_structural",
        "rule_key": "paragraph_opening_repeat_max",
        "rule_value": {"max": 0.15, "unit": "ratio"},
        "severity": "warning",
        "priority": 75,
        "description": "番茄段落首句雷同比例上限（更严格）",
    },
    {
        "rule_type": "ai_smell_structural",
        "rule_key": "dialogue_omit_ratio_min",
        "rule_value": {"min": 0.30, "unit": "ratio"},
        "severity": "info",
        "priority": 60,
        "description": "番茄对话省略比例下限（更高）",
    },
    {
        "rule_type": "ai_smell_structural",
        "rule_key": "paragraph_rhythm_cv_min",
        "rule_value": {"min": 0.30, "unit": "ratio"},
        "severity": "info",
        "priority": 60,
        "description": "番茄段落节奏变异系数下限（更高）",
    },
    
    # ── 爽点规则 ──
    {
        "rule_type": "payoff",
        "rule_key": "payoff_intensity_min",
        "rule_value": {"min": "medium", "unit": "level"},
        "severity": "warning",
        "priority": 90,
        "description": "番茄爽点强度最低标准",
    },
    {
        "rule_type": "payoff",
        "rule_key": "payoff_density_min",
        "rule_value": {"min": 1, "unit": "per_chapter"},
        "severity": "warning",
        "priority": 90,
        "description": "番茄每章最少爽点数",
    },
    {
        "rule_type": "payoff",
        "rule_key": "early_min_intensity",
        "rule_value": {"min": "high", "unit": "level", "chapters": 10},
        "severity": "error",
        "priority": 95,
        "description": "番茄前10章爽点强度最低标准（更高）",
    },
    {
        "rule_type": "payoff",
        "rule_key": "peak_intensity_interval",
        "rule_value": {"interval": 5, "unit": "chapters"},
        "severity": "info",
        "priority": 70,
        "description": "番茄每N章至少一次peak强度爽点",
    },
    
    # ── 节奏规则 ──
    {
        "rule_type": "pacing",
        "rule_key": "fast_pacing_required",
        "rule_value": {"required": True, "description": "快节奏要求"},
        "severity": "warning",
        "priority": 85,
        "description": "番茄要求快节奏",
    },
    {
        "rule_type": "pacing",
        "rule_key": "conflict_front_loaded",
        "rule_value": {"required": True, "description": "冲突前置要求"},
        "severity": "warning",
        "priority": 85,
        "description": "番茄要求冲突前置",
    },
    
    # ── 风格卡（覆盖） ──
    {
        "rule_type": "style_card",
        "rule_key": "tomato_style",
        "rule_value": {
            "tone": "casual",
            "pacing": "fast",
            "features": [
                "短句为主",
                "快节奏",
                "强冲突",
                "口语化表达",
                "爽点密集",
                "每章必有爽点",
                "强冲突前置",
            ],
            "description": "番茄爽文风格卡",
        },
        "severity": "info",
        "priority": 80,
        "description": "番茄爽文风格卡",
    },
]


# ── 番茄爽文知识库 ────────────────────────────────────────────────────────

TOMATO_KNOWLEDGE = [
    {
        "knowledge_type": "writing_tips",
        "title": "番茄爽文写作要点",
        "content": """番茄爽文核心要点：
1. 开篇即高潮：第一章就要有冲突和爽点
2. 节奏要快：不要拖沓，每章都要有进展
3. 爽点密集：平均每章1-2个爽点
4. 打脸要狠：反派越嚣张，打脸越爽
5. 升级要快：主角实力提升要快
6. 口语化：语言要通俗易懂，贴近读者
7. 情绪调动：要让读者有代入感，情绪跟着走
8. 章末钩子：每章结尾留悬念，让读者想看下一章""",
        "tags": ["写作技巧", "爽文", "番茄"],
        "priority": 90,
    },
    {
        "knowledge_type": "payoff_types",
        "title": "常见爽点类型",
        "content": """常见爽点类型：
1. 打脸：反派装逼被主角打脸
2. 升级：主角实力提升
3. 获得：获得宝物/技能/机遇
4. 反转：剧情反转，出人意料
5. 装逼：主角低调装逼，众人哗然
6. 救人：主角救场，众人感激
7. 复仇：主角复仇成功
8. 揭秘：揭开谜底，真相大白
9. 碾压：主角实力碾压对手
10. 收获：获得实际利益（钱财/地位/人脉）""",
        "tags": ["爽点", "类型"],
        "priority": 85,
    },
]


# ── 封神举国知识 ──────────────────────────────────────────────────────────

FENGSHEN_KNOWLEDGE = [
    {
        "knowledge_type": "world_setting",
        "title": "封神世界观硬约束",
        "content": """封神举国世界观硬约束：
1. 禁止后世修真概念：筑基/金丹/元婴/化神/炼虚/合体/大乘/渡劫
2. 禁止后世修真物品：灵根/灵石/储物袋/储物戒指/功法玉简/玉简/纳戒
3. 禁止后世修真者称呼：修仙者/修真者
4. 修炼体系应该用"炼气士"而不是"炼气期"
5. 时间流速：天上一日，地上一年
6. 神仙体系：阐教、截教、人道、西方教
7. 法宝体系：先天灵宝、后天灵宝、法器""",
        "tags": ["世界观", "硬约束", "封神"],
        "priority": 100,
    },
    {
        "knowledge_type": "character",
        "title": "封神主要人物",
        "content": """封神主要人物：
阐教：
- 元始天尊：阐教教主
- 老子：大师兄
- 通天教主：截教教主（三师弟）
- 十二金仙：广成子、赤精子、太乙真人等

截教：
- 通天教主：截教教主
- 多宝道人：大师兄
- 赵公明：财神
- 三霄娘娘：云霄、琼霄、碧霄

人间：
- 姜子牙：封神榜持有者
- 纣王：商朝末代君主
- 妲己：九尾狐
- 周文王、周武王：周朝君主""",
        "tags": ["人物", "封神"],
        "priority": 90,
    },
]


# ── 辅助函数 ──────────────────────────────────────────────────────────────

async def get_or_create_genre(db: AsyncSession, slug: str, data: dict[str, Any]) -> GenrePack:
    """获取或创建品类。"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(GenrePack).where(GenrePack.slug == slug)
    )
    genre = result.scalar_one_or_none()
    
    if genre:
        return genre
    
    # 处理 parent_id
    parent_slug = data.pop("parent_slug", None)
    parent_id = None
    if parent_slug:
        parent_result = await db.execute(
            select(GenrePack).where(GenrePack.slug == parent_slug)
        )
        parent = parent_result.scalar_one_or_none()
        if parent:
            parent_id = parent.id
    
    genre = GenrePack(
        **data,
        parent_id=parent_id,
    )
    db.add(genre)
    await db.flush()
    await db.refresh(genre)
    return genre


async def create_rule_if_not_exists(
    db: AsyncSession,
    genre_id: Any,
    rule_data: dict[str, Any],
) -> GenreRule | None:
    """如果规则不存在则创建。"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(GenreRule).where(
            GenreRule.genre_id == genre_id,
            GenreRule.rule_key == rule_data["rule_key"],
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        return None
    
    rule = GenreRule(
        genre_id=genre_id,
        **rule_data,
    )
    db.add(rule)
    await db.flush()
    return rule


async def create_knowledge_if_not_exists(
    db: AsyncSession,
    genre_id: Any,
    knowledge_data: dict[str, Any],
) -> GenreKnowledge | None:
    """如果知识条目不存在则创建。"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(GenreKnowledge).where(
            GenreKnowledge.genre_id == genre_id,
            GenreKnowledge.title == knowledge_data["title"],
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        return None
    
    knowledge = GenreKnowledge(
        genre_id=genre_id,
        **knowledge_data,
    )
    db.add(knowledge)
    await db.flush()
    return knowledge


# ── 主函数 ────────────────────────────────────────────────────────────────

async def init_genre_library() -> None:
    """初始化品类库。"""
    print("=" * 60)
    print("NovelCraft 品类库初始化")
    print("=" * 60)
    
    async with AsyncSession(async_engine) as db:
        # 1. 创建基础品类
        print("\n📦 创建基础品类...")
        for genre_data in BASE_GENRES:
            genre = await get_or_create_genre(db, genre_data["slug"], genre_data.copy())
            print(f"  ✅ {genre.name} ({genre.slug})")
        
        await db.commit()
        
        # 2. 导入通用网文基类规则
        print("\n📝 导入通用网文基类规则...")
        base_genre = await get_or_create_genre(db, "base", {})
        base_count = 0
        for rule_data in BASE_RULES:
            rule = await create_rule_if_not_exists(db, base_genre.id, rule_data)
            if rule:
                base_count += 1
        print(f"  ✅ 导入 {base_count} 条基础规则")
        
        await db.commit()
        
        # 3. 导入番茄爽文规则
        print("\n🍅 导入番茄爽文规则...")
        tomato_genre = await get_or_create_genre(db, "tomato", {})
        tomato_count = 0
        for rule_data in TOMATO_RULES:
            rule = await create_rule_if_not_exists(db, tomato_genre.id, rule_data)
            if rule:
                tomato_count += 1
        print(f"  ✅ 导入 {tomato_count} 条番茄规则")
        
        await db.commit()
        
        # 4. 导入番茄爽文知识
        print("\n📚 导入番茄爽文知识库...")
        tomato_knowledge_count = 0
        for knowledge_data in TOMATO_KNOWLEDGE:
            knowledge = await create_knowledge_if_not_exists(db, tomato_genre.id, knowledge_data)
            if knowledge:
                tomato_knowledge_count += 1
        print(f"  ✅ 导入 {tomato_knowledge_count} 条番茄知识")
        
        await db.commit()
        
        # 5. 导入封神举国知识
        print("\n⚡ 导入封神举国知识...")
        fengshen_genre = await get_or_create_genre(db, "fengshen", {})
        fengshen_knowledge_count = 0
        for knowledge_data in FENGSHEN_KNOWLEDGE:
            knowledge = await create_knowledge_if_not_exists(db, fengshen_genre.id, knowledge_data)
            if knowledge:
                fengshen_knowledge_count += 1
        print(f"  ✅ 导入 {fengshen_knowledge_count} 条封神知识")
        
        await db.commit()
        
        # 清空缓存
        clear_inheritance_cache()
        
        # 统计
        print("\n" + "=" * 60)
        print("初始化完成！")
        print("=" * 60)
        print(f"品类数量：{len(BASE_GENRES)}")
        print(f"基础规则：{len(BASE_RULES)} 条")
        print(f"番茄规则：{len(TOMATO_RULES)} 条")
        print(f"番茄知识：{len(TOMATO_KNOWLEDGE)} 条")
        print(f"封神知识：{len(FENGSHEN_KNOWLEDGE)} 条")
        print()
        print("品类树：")
        print("  通用网文 (base)")
        print("  ├── 番茄爽文 (tomato)")
        print("  │   ├── 大唐后台 (datang)")
        print("  │   └── 封神举国 (fengshen)")
        print("  ├── 起点玄幻 (qidian)")
        print("  └── 晋江言情 (jjwxc)")
        print()


def main():
    asyncio.run(init_genre_library())


if __name__ == "__main__":
    main()
