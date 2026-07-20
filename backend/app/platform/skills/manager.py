"""Skill Manager — installable, upgradeable AI capabilities."""
from app.db import connect, new_id, encode, decode


class SkillManager:
    skills: dict = {}

    @classmethod
    def register(cls, skill_id: str, config: dict):
        cls.skills[skill_id] = config

    @classmethod
    def list_all(cls) -> list[dict]:
        return [{"id": k, "name": v.get("name", k), "description": v.get("description", ""), "category": v.get("category", ""), "version": v.get("version", "1.0")} for k, v in cls.skills.items()]

    @classmethod
    def get(cls, skill_id: str) -> dict | None:
        return cls.skills.get(skill_id)


# Register built-in skills
SkillManager.register("ranking-analysis", {
    "name": "爆款分析", "description": "分析榜单数据，提取爆款特征",
    "category": "novel", "version": "1.0",
    "input": {"rankings": "list"}, "output": {"analysis": "dict"},
})
SkillManager.register("golden-chapters", {
    "name": "黄金三章", "description": "生成吸引人的开篇三章",
    "category": "novel", "version": "1.0",
    "input": {"idea": "str", "genre": "str"}, "output": {"chapters": "list"},
})
SkillManager.register("character-designer", {
    "name": "人物设计", "description": "设计人物角色卡",
    "category": "novel", "version": "1.0",
    "input": {"story_context": "str"}, "output": {"characters": "list"},
})
SkillManager.register("de-ai", {
    "name": "AI降味", "description": "降低AI写作痕迹",
    "category": "editing", "version": "1.0",
    "input": {"text": "str"}, "output": {"processed_text": "str"},
})
SkillManager.register("seo-optimizer", {
    "name": "SEO优化", "description": "优化标题和关键词",
    "category": "marketing", "version": "1.0",
    "input": {"title": "str", "content": "str"}, "output": {"optimized": "dict"},
})
