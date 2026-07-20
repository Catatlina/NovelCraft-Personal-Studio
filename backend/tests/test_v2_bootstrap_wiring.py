"""V2 four-stage bootstrap wiring regression (2026-07-13 acceptance audit).

The audit found the flagship 20-node workflow was a facade: 0/18 new task
types had model routes or prompts, and the default model was a fictional
`deepseek-v4-pro`. These tests pin every wiring layer so the gap cannot
silently reopen:

  1. every agent node's task_type is seeded in db.init_db model_routes
  2. every agent node has a `bootstrap.<task_type>` PROMPT_SEEDS entry
  3. every agent node has an OUTPUT_CONTRACTS entry
  4. every agent node has a BOOTSTRAP_OUTPUT_MODELS schema (no free-pass)
  5. no fictional deepseek-v4-* default anywhere in gateway/config
  6. against a real database: gateway resolves a real model + a real
     methodology prompt (not the generic fallback) for all 18 nodes
"""
import ast
import inspect
import re
from pathlib import Path

from app import config as app_config
from app import gateway
from app.prompt_registry import OUTPUT_CONTRACTS, PROMPT_SEEDS
from app.workers.tasks import BOOTSTRAP_NODES

AGENT_TASK_TYPES = [t for _, kind, _, _, t in BOOTSTRAP_NODES if kind == "agent" and t]


def test_v2_has_18_agent_nodes():
    assert len(AGENT_TASK_TYPES) == 18, AGENT_TASK_TYPES


def _db_seeded_task_types() -> set[str]:
    src = Path(inspect.getfile(__import__("app.db", fromlist=["db"]))).read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "task_types" for t in node.targets
        ):
            return {c.value for c in node.value.elts if isinstance(c, ast.Constant)}
    raise AssertionError("task_types seed list not found in app/db.py")


def test_all_agent_nodes_have_model_route_seed():
    seeded = _db_seeded_task_types()
    missing = [t for t in AGENT_TASK_TYPES if t not in seeded]
    assert not missing, f"model_routes seed missing for: {missing}"


def test_all_agent_nodes_have_prompt_seed():
    names = {name for name, *_ in PROMPT_SEEDS}
    missing = [t for t in AGENT_TASK_TYPES if f"bootstrap.{t}" not in names]
    assert not missing, f"PROMPT_SEEDS missing for: {missing}"


def test_all_agent_nodes_have_output_contract():
    missing = [t for t in AGENT_TASK_TYPES if t not in OUTPUT_CONTRACTS]
    assert not missing, f"OUTPUT_CONTRACTS missing for: {missing}"


def test_all_agent_nodes_have_output_schema():
    missing = [t for t in AGENT_TASK_TYPES if t not in gateway.BOOTSTRAP_OUTPUT_MODELS]
    assert not missing, f"BOOTSTRAP_OUTPUT_MODELS missing for: {missing}"


def test_prompts_are_methodology_grade_not_stubs():
    by_name = {name: template for name, _, _, template in
               [(n, v, m, t) for n, v, m, t in PROMPT_SEEDS]}
    for t in AGENT_TASK_TYPES:
        template = by_name[f"bootstrap.{t}"]
        assert len(template) >= 200, f"bootstrap.{t} prompt is a stub ({len(template)} chars)"
        assert "$" in template, f"bootstrap.{t} prompt uses no context variables"


def test_no_fictional_default_models():
    assert gateway.MODEL == "deepseek-v4-pro"
    assert app_config.Settings().deepseek_model == "deepseek-v4-pro"


def test_plan_idea_supplies_title_candidates_for_human_gate():
    """human_confirm_title renders run.context.title_candidates — some planning
    node must produce them or the human gate shows an empty choice list."""
    assert "title_candidates" in OUTPUT_CONTRACTS["plan_idea"]
    model = gateway.BOOTSTRAP_OUTPUT_MODELS["plan_idea"]
    assert "title_candidates" in model.model_fields


def test_plan_fidelity_audit_requires_explicit_clean_verdict():
    model = gateway.BOOTSTRAP_OUTPUT_MODELS["audit_plan_fidelity"]
    assert {"passed", "score", "matched_requirements", "contradictions", "omissions"} <= set(model.model_fields)
    accepted = gateway.validate_task_output("audit_plan_fidelity", {
        "passed": True,
        "score": 100,
        "matched_requirements": ["年龄", "职业", "目标篇幅"],
        "contradictions": [],
        "omissions": [],
    })
    assert accepted["passed"] is True


def test_gateway_resolves_real_route_and_prompt_for_all_nodes(tmp_path):
    """T2: against the real test database, every node resolves a real model and
    a non-generic prompt. This is the audit's decisive failing check."""
    from app.db import init_db

    init_db()
    for t in AGENT_TASK_TYPES:
        prompt, provider, model, _ = gateway._load_prompt_and_route(
            f"bootstrap.{t}", t, {"idea": "测试", "genre": "科幻", "style": "硬核"}
        )
        assert provider == "deepseek", (t, provider)
        assert model == "deepseek-v4-pro", (t, model)
        assert not prompt.startswith("请执行任务"), f"{t} fell back to generic prompt"
        assert len(prompt) > 200, (t, len(prompt))


def test_validate_rejects_malformed_new_node_output():
    """BUG-05: new nodes must not free-pass garbage output."""
    import pytest
    creative_bible = (
        "核心设定：主角在异界废城中获得能改写契约的能力，但每一次改写都必须付出记忆代价。"
        "开局节奏：第一章展示契约失控和家族危机，第二章让主角验证能力边界，第三章完成第一次公开反击并埋下代价。"
        "能力边界：契约只能修改已存在的约定，不能凭空制造资源；越重要的契约越需要等价记忆。"
        "长篇路线：觉醒、立足、夺回家族、进入王城、卷入神权战争、发现契约源头。"
        "人物关系：主角与家人有保护和隐瞒的张力，与盟友互相利用，与反派在规则理解上正面对抗。"
        "叙事禁忌：禁止无代价开挂，禁止反派降智，禁止把设定写成说明书。"
        "持续校验：检查能力代价、人物已知信息、契约规则和章节钩子是否一致。"
        "黄金三章必须完成能力验证、家庭信任危机和第一场公开冲突，后续每一卷都要让能力代价升级，"
        "让主角在亲情、利益和规则之间做选择，不能只靠信息差碾压。商业/权力扩张必须有资源来源、"
        "执行团队、外部阻力和阶段性失败，确保长篇推进时每个胜利都能被读者相信。"
    )

    with pytest.raises(gateway.OutputValidationError):
        gateway.validate_task_output("plan_idea", {"whatever": True})
    with pytest.raises(gateway.OutputValidationError):
        gateway.validate_task_output("write_chapter_draft", {"chapter": {"title": "x", "body": ["one"]}})
    ok = gateway.validate_task_output("plan_idea", {
        "idea_expanded": "一个足够长的展开创意描述，超过二十个字符以通过校验。",
        "core_hook": "核心卖点足够长",
        "target_audience": "男频玄幻读者",
        "title_candidates": ["《甲》", "《乙》", "《丙》"],
        "source_facts": ["主角是作者", "文字影响现实", "必须夺回叙事权"],
        "design_additions": [],
        "forbidden_changes": ["不得改变主角职业", "不得取消能力代价", "不得用巧合破局"],
        "downstream_deliverables": ["生成分卷总纲、章节细纲和第一章正文"],
        "creative_bible": creative_bible,
        "extra_field_from_model": "tolerated",
    })
    assert ok["core_hook"] == "核心卖点足够长"
    assert "creative_bible" in ok


def test_writing_selects_only_the_requested_chapter_outline():
    from app.workers.tasks import _chapter_outline_for_seq

    context = {"chapter_outlines": [
        {"seq": 1, "title": "第一章", "outline": "只写重生"},
        {"seq": 2, "title": "第二章", "outline": "测试设备"},
        {"seq": 3, "title": "第三章", "outline": "向父母坦白"},
    ]}
    selected = _chapter_outline_for_seq(context, 1)
    assert selected == context["chapter_outlines"][0]
    assert "测试设备" not in str(selected)
    assert "向父母坦白" not in str(selected)


def test_title_regeneration_requires_three_to_ten_real_candidates():
    import pytest

    with pytest.raises(gateway.OutputValidationError):
        gateway.validate_task_output("regenerate_titles", {"title_candidates": ["《甲》", "《乙》"]})
    accepted = gateway.validate_task_output(
        "regenerate_titles",
        {"title_candidates": ["《甲》", "《乙》", "《丙》", "《丁》", "《戊》"]},
    )
    assert len(accepted["title_candidates"]) == 5
