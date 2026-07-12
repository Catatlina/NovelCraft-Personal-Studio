"""C3: Agent registry — register AgentNodes with contracts."""
from __future__ import annotations

# Agent definitions following denova AgentNode contract pattern
# Each agent has: name, role, prompt_source, tools, output_schema

AGENT_REGISTRY = {
    "story-architect": {
        "name": "StoryArchitect",
        "role": "故事架构师",
        "description": "设计故事结构、分卷大纲、章节脉络",
        "prompt_source": "bootstrap.gen_outline",
        "tools": ["outline_expand", "volume_plan"],
        "output_schema": {"outline": "list"},
    },
    "writer": {
        "name": "Writer",
        "role": "正文写手",
        "description": "根据大纲和上下文生成章节正文",
        "prompt_source": "bootstrap.gen_chapter1",
        "tools": ["context_assemble", "foreshadow_check"],
        "output_schema": {"chapter": "dict"},
    },
    "reviewer": {
        "name": "Reviewer",
        "role": "七维审核",
        "description": "OOC/一致性/节奏/文学性/逻辑/角色/对话审核",
        "prompt_source": "bootstrap.review_7dim",
        "tools": ["ooc_check", "consistency_check", "rhythm_check"],
        "output_schema": {"score": "int", "issues": "list", "dimensions": "dict"},
    },
    "deslop": {
        "name": "DeSlop",
        "role": "去AI味专家",
        "description": "检测并清除AI写作痕迹",
        "prompt_source": "editor.deai",
        "tools": ["check_ai_patterns", "normalize_punctuation"],
        "output_schema": {"text": "str"},
    },
    "trend-analyzer": {
        "name": "TrendAnalyzer",
        "role": "扫榜分析师",
        "description": "分析榜单趋势、市场热点、选题推荐",
        "prompt_source": "ranking.market_analysis",
        "tools": ["rank_scan", "market_analyze", "topic_suggest"],
        "output_schema": {"market_signals": "list", "audience": "dict", "topic_candidates": "list"},
    },
    "consistency-checker": {
        "name": "ConsistencyChecker",
        "role": "一致性核查",
        "description": "人物/地点/时间/物品/设定/伏笔六类一致性检查",
        "prompt_source": "review.consistency",
        "tools": ["entity_check", "timeline_check", "foreshadow_check"],
        "output_schema": {"score": "int", "issues": "list", "dimensions": "dict"},
    },
    "character-designer": {
        "name": "CharacterDesigner",
        "role": "人物设计师",
        "description": "设计人物背景、性格、关系、弧线",
        "prompt_source": "bootstrap.gen_characters",
        "tools": ["character_card", "relation_map", "arc_design"],
        "output_schema": {"characters": "list"},
    },
    "narrative-writer": {
        "name": "NarrativeWriter",
        "role": "叙事写手",
        "description": "专注于文字自然度和叙事节奏",
        "prompt_source": "editor.polish",
        "tools": ["prose_check", "rhythm_adjust", "voice_match"],
        "output_schema": {"text": "str"},
    },
}


def get_agent(agent_id: str) -> dict | None:
    """Get agent definition by ID."""
    return AGENT_REGISTRY.get(agent_id)


def list_agents() -> list[dict]:
    """List all registered agents."""
    return [{"id": k, **v} for k, v in AGENT_REGISTRY.items()]


def get_agent_prompt_source(agent_id: str) -> str:
    """Get the prompt source file for an agent."""
    agent = get_agent(agent_id)
    return agent["prompt_source"] if agent else ""


def validate_agent_output(agent_id: str, output: dict) -> bool:
    """Validate agent output against its schema."""
    agent = get_agent(agent_id)
    if not agent:
        return False
    schema = agent.get("output_schema", {})
    for key, expected_type in schema.items():
        if key not in output:
            return False
    return True


AGENT_EXECUTION_ROUTES = {
    "story-architect": ("gen_outline", "bootstrap.gen_outline"),
    "writer": ("gen_next_chapter", "narrative.gen_next_chapter"),
    "reviewer": ("review_7dim", "bootstrap.review_7dim"),
    "deslop": ("editor_deai", "editor.deai"),
    "trend-analyzer": ("ranking_market_analysis", "ranking.market_analysis"),
    "consistency-checker": ("review_7dim", "bootstrap.review_7dim"),
    "character-designer": ("gen_characters", "bootstrap.gen_characters"),
    "narrative-writer": ("editor_polish", "editor.polish"),
}


def execute_agent(agent_id: str, project_id: str, variables: dict,
                  client_mutation_id: str | None = None) -> dict:
    """Execute a registered agent through the audited AI gateway and ledger."""
    agent = get_agent(agent_id)
    route = AGENT_EXECUTION_ROUTES.get(agent_id)
    if not agent or not route:
        raise KeyError(agent_id)
    from app.gateway import complete

    task_type, prompt_name = route
    output = complete(
        run_id=None, node_key=f"agent:{agent_id}", project_id=project_id,
        task_type=task_type, prompt_name=prompt_name, variables=variables,
        client_mutation_id=client_mutation_id,
    )
    return {"status": "succeeded", "agent_id": agent_id, "task_type": task_type,
            "output": output}
