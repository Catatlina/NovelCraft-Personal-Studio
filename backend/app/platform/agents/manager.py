"""
星禾AI工作台 · Agent Manager

Agent = Goal + Memory + Skills + Tools + Workflow
管理 Agent 的创建、配置、运行和生命周期。
"""

import json
from ...db import connect, new_id, row_to_dict

# ── Built-in Agents ──────────────────────────────────────────────────────────
BUILTIN_AGENTS = [
    {
        "slug": "novel_author",
        "name": "小说作者Agent",
        "version": "1.0.0",
        "category": "content_creation",
        "description": "全自动完成：扫榜→市场分析→选题→大纲→人物→章节→审核→入库",
        "goal": {"type": "novel_creation", "description": "创作高质量市场导向型小说", "success_criteria": ["完成所有章节", "质量评分≥7.0", "AI味评分≤3.0"]},
        "workflow": {
            "type": "dag",
            "steps": [
                {"id": "market_analysis", "name": "市场分析", "skill_slug": "novel_title", "timeout": 300, "retry": 2},
                {"id": "topic_selection", "name": "选题", "skill_slug": "novel_golden_three", "depends_on": ["market_analysis"], "human_approval": True},
                {"id": "outline", "name": "大纲", "skill_slug": "novel_world", "depends_on": ["topic_selection"]},
                {"id": "characters", "name": "人物设计", "skill_slug": "novel_character", "depends_on": ["outline"]},
                {"id": "quality_check", "name": "质量审核", "skill_slug": "novel_deai", "depends_on": ["characters"]},
            ],
        },
        "trigger_type": "manual",
        "is_builtin": True,
    },
    {
        "slug": "content_reviewer",
        "name": "内容审核Agent",
        "version": "1.0.0",
        "category": "quality",
        "description": "自动检查AI味道/一致性/质量，生成审核报告",
        "goal": {"type": "content_review", "description": "自动审核内容质量"},
        "workflow": {
            "type": "dag",
            "steps": [
                {"id": "deai_check", "name": "AI味检测", "skill_slug": "novel_deai", "timeout": 120},
                {"id": "report", "name": "生成报告", "depends_on": ["deai_check"]},
            ],
        },
        "trigger_type": "event",
        "trigger_config": {"event": "chapter.generated"},
        "is_builtin": True,
    },
    {
        "slug": "hotspot_analyst",
        "name": "热点分析Agent",
        "version": "1.0.0",
        "category": "analytics",
        "description": "定时扫描热点平台，生成每日晨报",
        "goal": {"type": "hotspot_analysis", "description": "定时采集和分析热点趋势"},
        "workflow": {"type": "dag", "steps": [{"id": "scan", "name": "扫描热点", "timeout": 300}]},
        "trigger_type": "scheduled",
        "trigger_config": {"cron": "0 */6 * * *"},
        "is_builtin": True,
    },
]


class AgentManager:
    """管理 Agent 生命周期：创建/配置/运行/状态追踪"""

    @staticmethod
    def seed_builtin():
        """种子内置 Agents（幂等）"""
        db = connect()
        cur = db.cursor()
        for agent in BUILTIN_AGENTS:
            cur.execute("SELECT id FROM agents WHERE slug = %s", (agent["slug"],))
            if cur.fetchone():
                continue
            aid = new_id()
            cur.execute(
                """INSERT INTO agents (id,slug,name,version,category,description,goal,workflow,
                   memory_config,model_preference,trigger_type,trigger_config,is_builtin,status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (aid, agent["slug"], agent["name"], agent["version"], agent["category"],
                 agent["description"], json.dumps(agent["goal"]), json.dumps(agent["workflow"]),
                 json.dumps(agent.get("memory_config", {"type": "buffer", "max_tokens": 8000})),
                 json.dumps(agent.get("model_preference", {})),
                 agent["trigger_type"], json.dumps(agent.get("trigger_config", {})),
                 agent["is_builtin"], "active"),
            )
        db.commit()
        cur.close()

    @staticmethod
    def list_agents():
        db = connect()
        cur = db.cursor()
        cur.execute("SELECT * FROM agents WHERE status='active' ORDER BY category, name")
        rows = [row_to_dict(r, cur) for r in cur.fetchall()]
        cur.close()
        return rows

    @staticmethod
    def get_agent(agent_id):
        db = connect()
        cur = db.cursor()
        cur.execute("SELECT * FROM agents WHERE id=%s", (agent_id,))
        row = cur.fetchone()
        cur.close()
        return row_to_dict(row, cur) if row else None

    @staticmethod
    def start_run(agent_id, user_id, project_id=None, inputs=None):
        """启动一个 Agent 运行"""
        db = connect()
        cur = db.cursor()
        run_id = new_id()
        cur.execute(
            """INSERT INTO agent_runs (id,agent_id,user_id,project_id,status,inputs)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (run_id, agent_id, user_id, project_id, "pending", json.dumps(inputs or {})),
        )
        # Initialize steps from agent workflow
        agent = AgentManager.get_agent(agent_id)
        if agent:
            workflow = json.loads(agent.get("workflow", "{}")) if isinstance(agent.get("workflow"), str) else agent.get("workflow", {})
            for step in workflow.get("steps", []):
                sid = new_id()
                cur.execute(
                    """INSERT INTO agent_run_steps (id,run_id,step_id,step_name,status)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (sid, run_id, step["id"], step.get("name", ""), "pending"),
                )
        db.commit()
        cur.close()
        return run_id

    @staticmethod
    def list_runs(agent_id=None, user_id=None, limit=20):
        db = connect()
        cur = db.cursor()
        q = "SELECT * FROM agent_runs WHERE 1=1"
        params = []
        if agent_id:
            q += " AND agent_id=%s"; params.append(agent_id)
        if user_id:
            q += " AND user_id=%s"; params.append(user_id)
        q += " ORDER BY started_at DESC LIMIT %s"; params.append(limit)
        cur.execute(q, params)
        rows = [row_to_dict(r, cur) for r in cur.fetchall()]
        cur.close()
        return rows

    @staticmethod
    def update_run_status(run_id, status, progress=None, error=None):
        db = connect()
        cur = db.cursor()
        cur.execute(
            "UPDATE agent_runs SET status=%s, progress=%s, error_message=%s WHERE id=%s",
            (status, progress, error, run_id),
        )
        db.commit()
        cur.close()
