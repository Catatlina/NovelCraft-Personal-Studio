"""C3: Agent registry — register AgentNodes with contracts."""
from __future__ import annotations

import json
import uuid
from typing import Any

from app.db import connect
from app.services.novel_export import extract_body_text

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
        "description": "7个宏观维度 + 33个内部项的 OOC/连续性/节奏/逻辑/角色/AI腔审核",
        "prompt_source": "v7.review.33_dimension",
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
        "prompt_source": "v7.review.33_dimension",
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
    "reviewer": ("v7_review_33_dimension", "v7.review.33_dimension"),
    "deslop": ("editor_deai", "editor.deai"),
    "trend-analyzer": ("ranking_market_analysis", "ranking.market_analysis"),
    "consistency-checker": ("v7_review_33_dimension", "v7.review.33_dimension"),
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

    # A chapter writer is a product prose-generation entrypoint, so it must
    # use the same canonical V7 Director as continue/batch/bootstrap.  Do not
    # let this public agent endpoint silently reopen the retired V6 writer.
    if agent_id == "writer":
        novel_id = str(
            variables.get("novel_id")
            or variables.get("content_id")
            or variables.get("parent_id")
            or ""
        ).strip()
        if not novel_id:
            raise ValueError("writer agent requires variables.novel_id")
        chapter_number = variables.get("chapter_number") or variables.get("seq")
        if chapter_number is not None:
            try:
                chapter_number = int(chapter_number)
            except (TypeError, ValueError) as exc:
                raise ValueError("writer agent chapter_number must be an integer") from exc
        outline = variables.get("outline")
        if isinstance(outline, (dict, list)):
            outline = json.dumps(outline, ensure_ascii=False)
        from app.v7.runtime import generate_v7_chapter_sync

        result = generate_v7_chapter_sync(
            novel_id,
            project_id,
            chapter_number=chapter_number,
            prompt=str(variables.get("prompt") or variables.get("instruction") or "") or None,
            outline=str(outline) if outline else None,
        )
        status = str(result.get("status") or "failed")
        output = {
            "chapter": {
                "title": result.get("title") or f"第{result.get('chapter_number', chapter_number or '')}章",
                "body": result.get("content") or "",
            },
            **result,
            "canonical_engine": "v7",
        }
        return {
            "status": "succeeded" if status == "completed" else status,
            "agent_id": agent_id,
            "task_type": "v7_chapter_generation",
            "output": output,
        }

    # Reviewer and consistency-checker are the same V7 audit contract.  Keep
    # both public agent IDs for API compatibility, but do not send either one
    # through the retired V6 gateway contract.  The target row is loaded from
    # the V6 contents boundary only so V7 can seed Novel Brain and bridge its
    # evidence back to the editor/library.
    if agent_id in {"reviewer", "consistency-checker"}:
        content, chapter_text = _load_review_target(project_id, variables)
        from app.v7.review_service import review_chapter_v7_sync

        review = review_chapter_v7_sync(
            content,
            chapter_text,
            api_key=str(variables.get("api_key") or ""),
            api_url=str(variables.get("api_url") or ""),
            model=str(variables.get("model") or ""),
            use_cache=bool(variables.get("use_cache", False)),
        )
        output = {
            **review,
            # Legacy agent consumers use these two aliases.  The values are
            # copied from V7, never recomputed by a second scoring path.
            "score": review.get("overall_score"),
            "dimensions": review.get("dimension_scores") or {},
            "canonical_engine": "v7",
        }
        return {
            "status": "succeeded",
            "agent_id": agent_id,
            "task_type": "v7_review_33_dimension",
            "output": output,
        }

    from app.gateway import complete

    task_type, prompt_name = route
    output = complete(
        run_id=None, node_key=f"agent:{agent_id}", project_id=project_id,
        task_type=task_type, prompt_name=prompt_name, variables=variables,
        client_mutation_id=client_mutation_id,
    )
    return {"status": "succeeded", "agent_id": agent_id, "task_type": task_type,
            "output": output}


def _load_review_target(project_id: str, variables: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Resolve an agent review target without opening a second scoring path.

    ``content_id`` is preferred because it preserves the chapter metadata and
    transition contract.  A raw body may be supplied for editor-like callers,
    but it still needs a real novel/chapter row so V7 can load the story state.
    """
    content_id = str(
        variables.get("content_id") or variables.get("chapter_id") or ""
    ).strip()
    novel_id = str(
        variables.get("novel_id") or variables.get("parent_id") or ""
    ).strip()
    chapter_number = variables.get("chapter_number") or variables.get("seq")
    if chapter_number is not None:
        try:
            chapter_number = int(chapter_number)
        except (TypeError, ValueError) as exc:
            raise ValueError("review agent chapter_number must be an integer") from exc

    supplied_text = str(
        variables.get("body")
        or variables.get("chapter_text")
        or variables.get("text")
        or ""
    ).strip()

    db = connect()
    try:
        content = None
        if content_id:
            content = db.execute(
                "SELECT * FROM contents WHERE id=%s AND type='chapter' AND is_deleted=FALSE",
                (content_id,),
            ).fetchone()
        elif novel_id:
            if chapter_number:
                content = db.execute(
                    """SELECT * FROM contents
                       WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE
                         AND COALESCE(seq, 0)=%s
                       ORDER BY updated_at DESC LIMIT 1""",
                    (novel_id, chapter_number),
                ).fetchone()
            else:
                content = db.execute(
                    """SELECT * FROM contents
                       WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE
                       ORDER BY COALESCE(seq, 0) DESC, updated_at DESC LIMIT 1""",
                    (novel_id,),
                ).fetchone()

        if content and str(content.get("project_id") or "") != str(project_id):
            raise ValueError("review target does not belong to this project")

        if content is None and novel_id:
            novel = db.execute(
                "SELECT * FROM contents WHERE id=%s AND type='novel' AND is_deleted=FALSE",
                (novel_id,),
            ).fetchone()
            if novel and str(novel.get("project_id") or "") == str(project_id):
                # This supports a not-yet-persisted editor draft while keeping
                # the real novel UUID and project boundary for V7.
                content = {
                    "id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "parent_id": novel_id,
                    "type": "chapter",
                    "seq": chapter_number or 1,
                    "meta": {"seq": chapter_number or 1},
                    "body": supplied_text,
                }
    finally:
        db.close()

    if content is None:
        raise ValueError("review agent requires an existing chapter or variables.novel_id")
    if not supplied_text:
        supplied_text = extract_body_text(content.get("body") or "").strip()
    if not supplied_text:
        raise ValueError("review agent requires non-empty chapter text")
    try:
        uuid.UUID(str(content.get("parent_id") or ""))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("review agent requires a valid novel_id for V7 story state") from exc
    return content, supplied_text
