"""Agent Manager — real execution via AI gateway, not stubs."""
from app.gateway import complete
from app.db import connect, new_id, encode


class AgentManager:
    agents: dict = {}

    @classmethod
    def register(cls, agent_id: str, config: dict):
        cls.agents[agent_id] = config

    @classmethod
    def list_all(cls) -> list[dict]:
        return [{"id": k, "name": v.get("name", k), "goal": v.get("goal", ""), "skills": v.get("skills", [])} for k, v in cls.agents.items()]

    @classmethod
    async def execute(cls, agent_id: str, project_id: str, variables: dict) -> dict:
        config = cls.agents.get(agent_id)
        if not config:
            raise KeyError(agent_id)
        prompt = config["prompt_template"].format(**variables)
        result = await complete(
            task_type=f"agent.{agent_id}",
            prompt=prompt,
            project_id=project_id,
        )
        return {"agent": agent_id, "output": result, "variables": variables}


# Register built-in agents
AgentManager.register("novel-author", {
    "name": "小说作者",
    "goal": "自动扫榜→分析→选题→大纲→写作→审核",
    "skills": ["ranking-analysis", "outline-generator", "chapter-writer", "reviewer"],
    "prompt_template": "作为小说作者Agent，完成以下任务：{task}",
})

AgentManager.register("content-editor", {
    "name": "内容编辑",
    "goal": "润色、去AI味、优化排版",
    "skills": ["polish", "de-ai", "format"],
    "prompt_template": "作为内容编辑Agent，{task}",
})

AgentManager.register("hotspot-analyzer", {
    "name": "热点分析师",
    "goal": "追踪热点、分析趋势、推荐选题",
    "skills": ["hotspot-tracking", "trend-analysis", "topic-suggestion"],
    "prompt_template": "分析当前热点：{query}",
})
