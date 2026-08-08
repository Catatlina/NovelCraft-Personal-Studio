#!/usr/bin/env python3
"""
预置品类数据导入脚本

导入6个内置品类：
- base（通用网文基类）
- tomato（番茄爽文）
- qidian（起点玄幻）
- jjwxc（晋江言情）
- datang（大唐后台，继承 tomato）
- fengshen（封神举国，继承 tomato）

用法：
    python scripts/seed_genres.py

幂等：重复运行不会重复插入，会根据 slug 判断是否已存在。
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.v7.db import async_engine, get_async_db
from app.v7.models.genre import GenrePack, GenreRule, GenreKnowledge, GenrePrompt
from app.v7.db import Base


# ── 预置品类数据 ──────────────────────────────────────────────────────────

GENRE_PACKS = [
    {
        "slug": "base",
        "name": "通用网文基类",
        "description": "所有品类的基础类，包含通用的写作规范和质量标准",
        "scope": "webnovel",
        "is_builtin": True,
        "parent_slug": None,
    },
    {
        "slug": "tomato",
        "name": "番茄爽文",
        "description": "番茄小说平台爽文风格，节奏快、冲突强、爽点密集",
        "scope": "fanqie",
        "is_builtin": True,
        "parent_slug": "base",
    },
    {
        "slug": "qidian",
        "name": "起点玄幻",
        "description": "起点中文网玄幻风格，世界观宏大、升级体系清晰",
        "scope": "qidian",
        "is_builtin": True,
        "parent_slug": "base",
    },
    {
        "slug": "jjwxc",
        "name": "晋江言情",
        "description": "晋江文学城言情风格，情感细腻、人物刻画深入",
        "scope": "jjwxc",
        "is_builtin": True,
        "parent_slug": "base",
    },
    {
        "slug": "datang",
        "name": "大唐后台",
        "description": "大唐历史背景的官场权谋文，继承番茄爽文风格",
        "scope": "fanqie",
        "is_builtin": True,
        "parent_slug": "tomato",
    },
    {
        "slug": "fengshen",
        "name": "封神举国",
        "description": "封神题材举国流小说，继承番茄爽文风格",
        "scope": "fanqie",
        "is_builtin": True,
        "parent_slug": "tomato",
    },
]

# ── 规则数据 ──────────────────────────────────────────────────────────────

GENRE_RULES = {
    "base": [
        # 风格卡
        {
            "rule_type": "style",
            "rule_key": "style_card",
            "rule_value": {
                "tone": "neutral",
                "pacing": "medium",
                "description_density": "moderate",
                "dialogue_ratio": 0.4,
            },
            "severity": "info",
            "priority": 50,
            "description": "通用网文风格基准",
        },
        # 质量门禁 - AI味阈值
        {
            "rule_type": "quality_threshold",
            "rule_key": "ai_smell_threshold",
            "rule_value": {
                "overall_score": 60,
                "dimensions": {
                    "transition_word_density": 70,
                    "paragraph_opening_similarity": 70,
                    "le_word_density": 70,
                    "abstract_adverb": 70,
                    "summary_sentence": 70,
                    "dialogue_completeness": 70,
                    "paragraph_rhythm": 70,
                },
            },
            "severity": "warning",
            "priority": 80,
            "description": "AI味检测通过阈值（通用标准）",
        },
        # 禁止规则 - 敏感内容
        {
            "rule_type": "forbidden",
            "rule_key": "sensitive_content",
            "rule_value": {
                "categories": ["politics", "pornography", "violence", "drugs"],
                "action": "block",
            },
            "severity": "blocking",
            "priority": 100,
            "description": "禁止敏感内容",
        },
    ],
    "tomato": [
        # 风格卡 - 番茄爽文
        {
            "rule_type": "style",
            "rule_key": "style_card",
            "rule_value": {
                "tone": "strong",
                "pacing": "fast",
                "description_density": "low",
                "dialogue_ratio": 0.5,
                "payoff_frequency": "high",
                "conflict_intensity": "high",
            },
            "severity": "info",
            "priority": 60,
            "description": "番茄爽文风格卡",
        },
        # 质量门禁 - 更严格的AI味阈值
        {
            "rule_type": "quality_threshold",
            "rule_key": "ai_smell_threshold",
            "rule_value": {
                "overall_score": 70,
                "dimensions": {
                    "transition_word_density": 75,
                    "paragraph_opening_similarity": 75,
                    "le_word_density": 75,
                    "abstract_adverb": 75,
                    "summary_sentence": 75,
                    "dialogue_completeness": 75,
                    "paragraph_rhythm": 75,
                },
            },
            "severity": "warning",
            "priority": 85,
            "description": "AI味检测通过阈值（番茄爽文更严格）",
        },
        # 爽点规则
        {
            "rule_type": "payoff",
            "rule_key": "payoff_frequency",
            "rule_value": {
                "min_per_chapter": 1,
                "types": ["face_slapping", "power_up", "treasure", "beauty", "revenge"],
            },
            "severity": "warning",
            "priority": 70,
            "description": "爽点频率要求",
        },
        # 钩子规则
        {
            "rule_type": "hook",
            "rule_key": "chapter_hook",
            "rule_value": {
                "opening_hook_required": True,
                "ending_cliffhanger_required": True,
            },
            "severity": "warning",
            "priority": 75,
            "description": "章节钩子要求",
        },
    ],
    "qidian": [
        # 风格卡 - 起点玄幻
        {
            "rule_type": "style",
            "rule_key": "style_card",
            "rule_value": {
                "tone": "grand",
                "pacing": "medium_fast",
                "description_density": "medium_high",
                "dialogue_ratio": 0.35,
                "world_building_depth": "high",
                "cultivation_system": "clear",
            },
            "severity": "info",
            "priority": 60,
            "description": "起点玄幻风格卡",
        },
        # 升级体系规则
        {
            "rule_type": "world_building",
            "rule_key": "cultivation_system",
            "rule_value": {
                "required": True,
                "levels_clear": True,
                "power_scaling_consistent": True,
            },
            "severity": "warning",
            "priority": 70,
            "description": "修炼体系要求",
        },
    ],
    "jjwxc": [
        # 风格卡 - 晋江言情
        {
            "rule_type": "style",
            "rule_key": "style_card",
            "rule_value": {
                "tone": "delicate",
                "pacing": "slow_medium",
                "description_density": "high",
                "dialogue_ratio": 0.45,
                "emotional_depth": "deep",
                "character_development": "detailed",
            },
            "severity": "info",
            "priority": 60,
            "description": "晋江言情风格卡",
        },
        # 情感线规则
        {
            "rule_type": "romance",
            "rule_key": "emotional_line",
            "rule_value": {
                "slow_burn": True,
                "emotional_arc_clear": True,
                "character_chemistry": "strong",
            },
            "severity": "warning",
            "priority": 75,
            "description": "情感线要求",
        },
    ],
    "datang": [
        # 风格卡 - 大唐后台
        {
            "rule_type": "style",
            "rule_key": "style_card",
            "rule_value": {
                "tone": "strategic",
                "pacing": "medium_fast",
                "description_density": "medium",
                "dialogue_ratio": 0.4,
                "political_intrigue": "high",
            },
            "severity": "info",
            "priority": 65,
            "description": "大唐官场风格卡",
        },
        # 历史准确性
        {
            "rule_type": "historical",
            "rule_key": "historical_accuracy",
            "rule_value": {
                "official_titles_correct": True,
                "social_system_consistent": True,
                "timeline_plausible": True,
            },
            "severity": "warning",
            "priority": 65,
            "description": "历史准确性要求",
        },
    ],
    "fengshen": [
        # 风格卡 - 封神举国
        {
            "rule_type": "style",
            "rule_key": "style_card",
            "rule_value": {
                "tone": "epic",
                "pacing": "fast",
                "description_density": "medium",
                "dialogue_ratio": 0.4,
                "national_fortune": "core",
            },
            "severity": "info",
            "priority": 65,
            "description": "封神举国风格卡",
        },
        # 举国流规则
        {
            "rule_type": "national_fortune",
            "rule_key": "national_upgrade",
            "rule_value": {
                "territory_expansion": True,
                "people_livelihood": True,
                "military_strength": True,
                "culture_development": True,
            },
            "severity": "warning",
            "priority": 70,
            "description": "举国升级要求",
        },
    ],
}

# ── 知识数据 ──────────────────────────────────────────────────────────────

GENRE_KNOWLEDGE = {
    "base": [
        {
            "knowledge_type": "reference",
            "title": "网文写作基本规范",
            "content": """网文写作基本规范：
1. 段落要短，每段2-3句话最佳
2. 对话要符合人物身份
3. 避免大段心理描写
4. 每章要有钩子
5. 节奏要张弛有度""",
            "tags": ["写作规范", "基础"],
            "priority": 80,
        },
        {
            "knowledge_type": "character",
            "title": "主角人设三要素",
            "content": """主角人设三要素：
1. 明确的目标（想要什么）
2. 强烈的动机（为什么想要）
3. 核心冲突（阻碍是什么）""",
            "tags": ["人物", "主角"],
            "priority": 75,
        },
    ],
    "tomato": [
        {
            "knowledge_type": "reference",
            "title": "番茄爽文黄金三章",
            "content": """番茄爽文黄金三章法则：
第一章：穿越/重生 + 金手指亮相 + 第一个冲突
第二章：金手指初显威 + 小爽点 + 埋下更大冲突
第三章：第一个大爽点 + 打脸反派 + 引出主线目标""",
            "tags": ["爽文", "黄金三章"],
            "priority": 90,
        },
        {
            "knowledge_type": "payoff",
            "title": "常见爽点类型",
            "content": """常见爽点类型：
1. 打脸爽：反派装逼被主角打脸
2. 升级爽：实力突破，境界提升
3. 宝物爽：获得稀有宝物/功法
4. 美女爽：美女倾心，红颜相伴
5. 复仇爽：仇人得到报应
6. 装逼爽：众人震惊，膜拜主角
7. 权势爽：地位提升，权力在手""",
            "tags": ["爽点", "类型"],
            "priority": 85,
        },
    ],
    "qidian": [
        {
            "knowledge_type": "world_setting",
            "title": "玄幻世界观构建要素",
            "content": """玄幻世界观构建核心要素：
1. 修炼体系：境界划分、升级方式
2. 势力分布：宗门、帝国、家族
3. 资源体系：灵石、丹药、功法、法宝
4. 地理设定：大陆、秘境、禁地
5. 种族设定：人族、妖族、魔族等""",
            "tags": ["世界观", "玄幻"],
            "priority": 85,
        },
        {
            "knowledge_type": "reference",
            "title": "升级节奏控制",
            "content": """升级节奏控制要点：
1. 小境界：每10-20章升一级
2. 大境界：每50-100章升一级
3. 每次升级要有铺垫和契机
4. 升级后要有展示实力的情节
5. 越到后期升级越慢""",
            "tags": ["升级", "节奏"],
            "priority": 75,
        },
    ],
    "jjwxc": [
        {
            "knowledge_type": "romance",
            "title": "言情情感递进层次",
            "content": """言情情感递进层次：
1. 初遇：印象深刻的第一次见面
2. 交集：因为各种原因产生交集
3. 好感：发现对方的优点，产生好感
4. 心动：某个瞬间彻底心动
5. 确认：双方确认心意
6. 考验：遇到外界考验，感情升温
7. 圆满：最终走到一起""",
            "tags": ["言情", "情感线"],
            "priority": 90,
        },
    ],
    "datang": [
        {
            "knowledge_type": "historical",
            "title": "唐代官职体系",
            "content": """唐代主要官职体系：
正一品：太师、太傅、太保、太尉、司徒、司空
从一品：太子太师、太子太傅、太子太保
正二品：尚书令、大行台尚书令
从二品：尚书左右仆射、太子少师、太子少傅、太子少保
正三品：侍中、中书令、吏部尚书、六部尚书
正四品上：黄门侍郎、中书侍郎
正五品上：谏议大夫、御史中丞
正六品上：太学博士、京兆/河南/太原府诸县令
正七品上：四门博士、詹事司直
正八品上：监察御史、协律郎
正九品上：校书郎、太祝""",
            "tags": ["唐代", "官职"],
            "priority": 90,
        },
        {
            "knowledge_type": "historical",
            "title": "唐代科举制度",
            "content": """唐代科举主要科目：
1. 秀才科：最高等级，最难考
2. 明经科：考儒家经典
3. 进士科：考诗赋和政论，最受重视
4. 明法科：考法律
5. 明字科：考文字学
6. 明算科：考数学

科举流程：
乡试 → 会试 → 殿试""",
            "tags": ["唐代", "科举"],
            "priority": 80,
        },
    ],
    "fengshen": [
        {
            "knowledge_type": "world_setting",
            "title": "封神神仙体系",
            "content": """封神演义神仙体系：

三清：
- 元始天尊（阐教教主）
- 灵宝天尊（通天教主，截教教主）
- 道德天尊（太上老君，人教教主）

阐教十二金仙：
广成子、赤精子、玉鼎真人、太乙真人、
黄龙真人、文殊广法天尊、普贤真人、
慈航道人、灵宝大法师、惧留孙、
道行天尊、清虚道德真君

截教仙人：
多宝道人、金灵圣母、无当圣母、龟灵圣母、
赵公明、三霄娘娘（云霄、琼霄、碧霄）等""",
            "tags": ["封神", "神仙体系"],
            "priority": 90,
        },
        {
            "knowledge_type": "reference",
            "title": "举国流核心玩法",
            "content": """举国流小说核心玩法：
1. 领地建设：从一村到一国，不断扩张
2. 民生发展：农业、商业、人口增长
3. 军事建设：军队训练、装备升级、开疆拓土
4. 人才招揽：文臣武将，各尽其用
5. 制度创新：政治制度、科举制度、税收制度
6. 文化繁荣：教育、科技、艺术发展
7. 气运提升：国家气运越强，实力越强""",
            "tags": ["举国流", "玩法"],
            "priority": 85,
        },
    ],
}

# ── Prompt 模板数据 ───────────────────────────────────────────────────────

GENRE_PROMPTS = {
    "base": [
        {
            "prompt_type": "writer",
            "prompt_name": "chapter_writer",
            "version": "1.0",
            "content": "你是一个专业的网文作家，请根据给定的大纲和前文，续写下一章内容。要求：情节紧凑、人物鲜明、语言流畅。",
            "description": "通用章节写作 Prompt",
        },
    ],
    "tomato": [
        {
            "prompt_type": "writer",
            "prompt_name": "tomato_chapter_writer",
            "version": "1.0",
            "content": "你是一个番茄爽文作家，请根据给定的大纲和前文，续写下一章内容。要求：节奏快、冲突强、爽点密集、结尾有钩子。每章至少一个爽点，让读者欲罢不能。",
            "description": "番茄爽文章节写作 Prompt",
        },
    ],
}


# ── 导入函数 ──────────────────────────────────────────────────────────────

async def seed_genres():
    """导入预置品类数据"""
    async with AsyncSession(async_engine) as db:
        # 先创建所有表（如果不存在）
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # 1. 导入品类包
        print("=== 导入品类包 ===")
        genre_map = {}  # slug -> GenrePack
        
        for pack_data in GENRE_PACKS:
            slug = pack_data["slug"]
            parent_slug = pack_data.pop("parent_slug", None)
            
            # 检查是否已存在
            result = await db.execute(
                select(GenrePack).where(GenrePack.slug == slug)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"  跳过已存在: {slug}")
                genre_map[slug] = existing
                continue
            
            # 查找父品类
            parent_id = None
            if parent_slug and parent_slug in genre_map:
                parent_id = genre_map[parent_slug].id
            
            # 创建新品类
            pack = GenrePack(
                **pack_data,
                parent_id=parent_id,
            )
            db.add(pack)
            await db.flush()  # 获取 ID
            
            genre_map[slug] = pack
            print(f"  已导入: {slug} ({pack.name})")
        
        await db.commit()
        
        # 2. 导入规则
        print("\n=== 导入品类规则 ===")
        for slug, rules in GENRE_RULES.items():
            if slug not in genre_map:
                print(f"  跳过未知品类: {slug}")
                continue
            
            genre = genre_map[slug]
            count = 0
            
            for rule_data in rules:
                rule_key = rule_data["rule_key"]
                
                # 检查是否已存在
                result = await db.execute(
                    select(GenreRule).where(
                        GenreRule.genre_id == genre.id,
                        GenreRule.rule_key == rule_key,
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    continue
                
                rule = GenreRule(
                    genre_id=genre.id,
                    **rule_data,
                )
                db.add(rule)
                count += 1
            
            await db.flush()
            print(f"  {slug}: 导入 {count} 条规则")
        
        await db.commit()
        
        # 3. 导入知识
        print("\n=== 导入品类知识 ===")
        for slug, knowledge_list in GENRE_KNOWLEDGE.items():
            if slug not in genre_map:
                print(f"  跳过未知品类: {slug}")
                continue
            
            genre = genre_map[slug]
            count = 0
            
            for knowledge_data in knowledge_list:
                title = knowledge_data["title"]
                
                # 检查是否已存在
                result = await db.execute(
                    select(GenreKnowledge).where(
                        GenreKnowledge.genre_id == genre.id,
                        GenreKnowledge.title == title,
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    continue
                
                knowledge = GenreKnowledge(
                    genre_id=genre.id,
                    **knowledge_data,
                )
                db.add(knowledge)
                count += 1
            
            await db.flush()
            print(f"  {slug}: 导入 {count} 条知识")
        
        await db.commit()
        
        # 4. 导入 Prompt 模板
        print("\n=== 导入 Prompt 模板 ===")
        for slug, prompts in GENRE_PROMPTS.items():
            if slug not in genre_map:
                print(f"  跳过未知品类: {slug}")
                continue
            
            genre = genre_map[slug]
            count = 0
            
            for prompt_data in prompts:
                prompt_name = prompt_data["prompt_name"]
                
                # 检查是否已存在
                result = await db.execute(
                    select(GenrePrompt).where(
                        GenrePrompt.genre_id == genre.id,
                        GenrePrompt.prompt_name == prompt_name,
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    continue
                
                prompt = GenrePrompt(
                    genre_id=genre.id,
                    **prompt_data,
                )
                db.add(prompt)
                count += 1
            
            await db.flush()
            print(f"  {slug}: 导入 {count} 个 Prompt")
        
        await db.commit()
        
        print("\n=== 导入完成 ===")
        print(f"共导入 {len(genre_map)} 个品类")


if __name__ == "__main__":
    asyncio.run(seed_genres())
