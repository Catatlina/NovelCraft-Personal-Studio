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
    assert gateway.MODEL == "deepseek-chat"
    assert app_config.Settings().deepseek_model in {"deepseek-chat", "deepseek-reasoner"} or \
        not re.match(r"deepseek-v4", app_config.Settings().deepseek_model)
    for py in (Path(gateway.__file__), Path(app_config.__file__)):
        assert "deepseek-v4" not in py.read_text(), f"fictional model referenced in {py.name}"


def test_plan_idea_supplies_title_candidates_for_human_gate():
    """human_confirm_title renders run.context.title_candidates — some planning
    node must produce them or the human gate shows an empty choice list."""
    assert "title_candidates" in OUTPUT_CONTRACTS["plan_idea"]
    model = gateway.BOOTSTRAP_OUTPUT_MODELS["plan_idea"]
    assert "title_candidates" in model.model_fields


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
        assert model == "deepseek-chat", (t, model)
        assert not prompt.startswith("请执行任务"), f"{t} fell back to generic prompt"
        assert len(prompt) > 200, (t, len(prompt))


def test_validate_rejects_malformed_new_node_output():
    """BUG-05: new nodes must not free-pass garbage output."""
    import pytest

    with pytest.raises(gateway.OutputValidationError):
        gateway.validate_task_output("plan_idea", {"whatever": True})
    with pytest.raises(gateway.OutputValidationError):
        gateway.validate_task_output("write_chapter_draft", {"chapter": {"title": "x", "body": ["one"]}})
    ok = gateway.validate_task_output("plan_idea", {
        "idea_expanded": "一个足够长的展开创意描述，超过二十个字符以通过校验。",
        "core_hook": "核心卖点足够长",
        "target_audience": "男频玄幻读者",
        "title_candidates": ["《甲》", "《乙》", "《丙》"],
        "extra_field_from_model": "tolerated",
    })
    assert ok["core_hook"] == "核心卖点足够长"
