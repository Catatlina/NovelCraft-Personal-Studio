"""
星禾AI工作台 · Skill Manager

Skill = 可安装/可启用/可禁用/可升级/可卸载的独立AI能力单元
"""

import json
from ...db import connect, new_id, row_to_dict

# ── Built-in Skills ──────────────────────────────────────────────────────────
BUILTIN_SKILLS = [
    {
        "slug": "novel_title", "name": "爆款标题生成", "version": "1.0.0",
        "category": "novel", "description": "基于市场趋势分析，生成高点击率的小说标题",
        "author": "星禾官方", "icon": "sparkles",
        "input_schema": {"type": "object", "properties": {"genre": {"type": "string"}, "theme": {"type": "string"}, "keywords": {"type": "array"}, "count": {"type": "integer", "default": 5}}, "required": ["genre"]},
        "prompt_template": "prompt/novel_title_v2", "model_preference": "deepseek-chat", "estimated_tokens": 800,
    },
    {
        "slug": "novel_golden_three", "name": "黄金三章", "version": "1.0.0",
        "category": "novel", "description": "生成吸引读者的开篇三章",
        "author": "星禾官方", "icon": "book-open",
        "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "genre": {"type": "string"}, "outline": {"type": "string"}}, "required": ["title", "genre"]},
        "prompt_template": "prompt/novel_golden_three_v1", "model_preference": "claude-sonnet-4-20250514", "estimated_tokens": 3000,
    },
    {
        "slug": "novel_character", "name": "人物设计", "version": "1.0.0",
        "category": "novel", "description": "创建立体丰满的小说人物角色",
        "author": "星禾官方", "icon": "users",
        "input_schema": {"type": "object", "properties": {"story_type": {"type": "string"}, "role_type": {"type": "string"}, "count": {"type": "integer", "default": 1}}, "required": ["story_type"]},
        "prompt_template": "prompt/novel_character_v1", "model_preference": "claude-sonnet-4-20250514", "estimated_tokens": 1500,
    },
    {
        "slug": "novel_world", "name": "世界观构建", "version": "1.0.0",
        "category": "novel", "description": "构建完整的小说世界观设定",
        "author": "星禾官方", "icon": "globe",
        "input_schema": {"type": "object", "properties": {"genre": {"type": "string"}, "era": {"type": "string"}, "scale": {"type": "string"}}, "required": ["genre"]},
        "prompt_template": "prompt/novel_world_v1", "model_preference": "claude-sonnet-4-20250514", "estimated_tokens": 2000,
    },
    {
        "slug": "novel_deai", "name": "AI降味", "version": "1.0.0",
        "category": "novel", "description": "检测并去除AI写作痕迹，让文字更自然",
        "author": "星禾官方", "icon": "wand-2",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}, "intensity": {"type": "string", "default": "medium"}}, "required": ["text"]},
        "prompt_template": "prompt/novel_deai_v1", "model_preference": "deepseek-chat", "estimated_tokens": 500,
    },
]


class SkillManager:
    """管理 Skill 生命周期"""

    @staticmethod
    def seed_builtin():
        """种子内置 Skills（幂等）"""
        db = connect()
        cur = db.cursor()
        for skill in BUILTIN_SKILLS:
            cur.execute("SELECT id FROM skills WHERE slug = %s", (skill["slug"],))
            if cur.fetchone():
                continue
            sid = new_id()
            cur.execute(
                """INSERT INTO skills (id,slug,name,version,category,description,author,icon,
                   input_schema,output_schema,prompt_template,model_preference,
                   estimated_tokens,is_builtin,is_public,status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (sid, skill["slug"], skill["name"], skill["version"], skill["category"],
                 skill["description"], skill["author"], skill.get("icon", ""),
                 json.dumps(skill.get("input_schema", {})), json.dumps(skill.get("output_schema", {})),
                 skill.get("prompt_template", ""), skill.get("model_preference", ""),
                 skill.get("estimated_tokens", 500), True, True, "active"),
            )
        db.commit()
        cur.close()

    @staticmethod
    def list_skills(user_id=None):
        db = connect()
        cur = db.cursor()
        cur.execute(
            """SELECT s.*, si.status as install_status FROM skills s
               LEFT JOIN skill_installations si ON s.id=si.skill_id AND si.user_id=%s
               WHERE s.status='active' ORDER BY s.category, s.name""",
            (user_id,),
        )
        rows = [row_to_dict(r, cur) for r in cur.fetchall()]
        cur.close()
        return rows

    @staticmethod
    def install(user_id, skill_id):
        db = connect()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO skill_installations (id,user_id,skill_id,status) VALUES (%s,%s,%s,%s) ON CONFLICT (user_id,skill_id) DO UPDATE SET status='active'",
            (new_id(), user_id, skill_id, "active"),
        )
        db.commit(); cur.close()

    @staticmethod
    def toggle(user_id, skill_id, active):
        db = connect()
        cur = db.cursor()
        cur.execute("UPDATE skill_installations SET status=%s WHERE user_id=%s AND skill_id=%s",
                    ("active" if active else "disabled", user_id, skill_id))
        db.commit(); cur.close()

    @staticmethod
    def uninstall(user_id, skill_id):
        db = connect()
        cur = db.cursor()
        cur.execute("DELETE FROM skill_installations WHERE user_id=%s AND skill_id=%s", (user_id, skill_id))
        db.commit(); cur.close()
