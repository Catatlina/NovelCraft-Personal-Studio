"""NC-FUS-DEEP: Deep fusion tests — prompt specs, workflow, book engine."""
import os, uuid
os.environ["NOVELCRAFT_ENV"] = "dev"

import pytest


# ============================================================================
# fusion_deep.py: PROMPT_SPECS, GOLDEN_VALIDATORS, CI runner, summary
# ============================================================================

def test_prompt_specs_total_count():
    """PROMPT_SPECS has exactly 10 prompt entries."""
    from app.services.fusion_deep import PROMPT_SPECS
    assert len(PROMPT_SPECS) == 10


def test_prompt_specs_all_have_version():
    """Every prompt spec has a version string."""
    from app.services.fusion_deep import PROMPT_SPECS
    for name, spec in PROMPT_SPECS.items():
        assert "version" in spec, f"{name} missing version"
        assert isinstance(spec["version"], str)
        assert spec["version"].count(".") >= 1  # semver-ish


def test_prompt_specs_all_have_upstream():
    """Every prompt spec declares an upstream oh-story source."""
    from app.services.fusion_deep import PROMPT_SPECS
    for name, spec in PROMPT_SPECS.items():
        assert "upstream" in spec, f"{name} missing upstream"
        assert spec["upstream"].startswith("oh-story/"), f"{name} upstream not oh-story: {spec['upstream']}"


def test_prompt_specs_mvp_core_have_golden_cases():
    """MVP core prompts (first 8) each have at least 1 golden case."""
    from app.services.fusion_deep import PROMPT_SPECS
    mvp_keys = [k for k in PROMPT_SPECS if k.startswith(("bootstrap.", "review.", "editor."))]
    assert len(mvp_keys) == 8
    for k in mvp_keys:
        cases = PROMPT_SPECS[k].get("golden_cases", [])
        assert len(cases) >= 1, f"{k} has no golden cases"


def test_golden_validators_not_empty():
    """not_empty validator rejects empty/falsy values."""
    from app.services.fusion_deep import GOLDEN_VALIDATORS
    v = GOLDEN_VALIDATORS["not_empty"]
    assert v("hello")
    assert v([1])
    assert v(42)
    assert v(True)
    assert not v("")
    assert not v([])
    assert not v(0)


def test_golden_validators_range():
    """range_0_100 validator respects boundaries."""
    from app.services.fusion_deep import GOLDEN_VALIDATORS
    v = GOLDEN_VALIDATORS["range_0_100"]
    assert v(0)
    assert v(50)
    assert v(100)
    assert v(50.5)
    assert not v(-1)
    assert not v(101)
    assert not v("abc")


def test_golden_validators_list_checks():
    """min_1, min_2, min_3 validators check list length."""
    from app.services.fusion_deep import GOLDEN_VALIDATORS
    assert GOLDEN_VALIDATORS["min_1"](["a"])
    assert not GOLDEN_VALIDATORS["min_1"]([])
    assert GOLDEN_VALIDATORS["min_2"](["a", "b"])
    assert not GOLDEN_VALIDATORS["min_2"](["a"])
    assert GOLDEN_VALIDATORS["min_3"](["a", "b", "c"])
    assert not GOLDEN_VALIDATORS["min_3"](["a", "b"])


def test_run_golden_case_ci_returns_correct_shape():
    """run_golden_case_ci returns dict with total, passed, failed, results."""
    from app.services.fusion_deep import run_golden_case_ci
    result = run_golden_case_ci()
    assert isinstance(result, dict)
    assert "total_prompts" in result
    assert "passed" in result
    assert "failed" in result
    assert "results" in result
    assert result["total_prompts"] == 10
    assert result["passed"] + result["failed"] == result["total_prompts"]
    assert isinstance(result["results"], dict)


def test_run_golden_case_ci_all_pass():
    """All golden case validators are known — CI should have 0 failures."""
    from app.services.fusion_deep import run_golden_case_ci
    result = run_golden_case_ci()
    assert result["failed"] == 0, f"Unexpected failures: {result['results']}"


def test_get_prompt_specs_summary():
    """get_prompt_specs_summary aggregates prompt metadata."""
    from app.services.fusion_deep import get_prompt_specs_summary
    s = get_prompt_specs_summary()
    assert s["total_prompts"] == 10
    assert len(s["prompt_names"]) == 10
    assert s["with_golden_cases"] == 10
    assert s["total_golden_cases"] == 12  # sum: 3+1+1+1+1+1+1+1+1+1
    assert len(s["upstream_sources"]) >= 1
    assert all(src.startswith("oh-story/") for src in s["upstream_sources"])


# ============================================================================
# fusion_deep_workflow.py: WorkflowPlan, event ledger, fact chain
# ============================================================================

def _unique_name():
    return f"fusion-deep-test-{uuid.uuid4().hex[:8]}"


def test_workflow_plan_create():
    """WorkflowPlan.create inserts a workflow and returns metadata."""
    from app.services.fusion_deep_workflow import WorkflowPlan
    name = _unique_name()
    pid = str(uuid.uuid4())
    nodes = [
        {"key": "n1", "type": "auto", "label": "Step 1"},
        {"key": "n2", "type": "human", "label": "Review"},
        {"key": "n3", "type": "auto", "label": "Step 3"},
    ]
    edges = [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}]
    result = WorkflowPlan.create(name, pid, nodes, edges)
    assert result["name"] == name
    assert result["node_count"] == 3
    assert result["edge_count"] == 2
    assert "workflow_id" in result
    assert len(result["workflow_id"]) == 36  # UUID


def test_record_event_valid():
    """record_event with a valid event type inserts and returns event metadata."""
    from app.services.fusion_deep_workflow import record_event
    run_id = str(uuid.uuid4())
    r = record_event(run_id, "run.created", node_key="n1", payload={"test": True})
    assert r["run_id"] == run_id
    assert r["type"] == "run.created"
    assert r["node"] == "n1"
    assert "event_id" in r


def test_record_event_invalid_type():
    """record_event rejects unknown event types."""
    from app.services.fusion_deep_workflow import record_event
    r = record_event(str(uuid.uuid4()), "invalid.event.type")
    assert r["status"] == "error"
    assert "unknown event type" in r["message"]


def test_get_event_ledger_returns_list():
    """get_event_ledger returns a list of events (may be empty)."""
    from app.services.fusion_deep_workflow import get_event_ledger
    ledger = get_event_ledger(str(uuid.uuid4()), limit=5)
    assert isinstance(ledger, list)


def test_get_event_ledger_includes_recorded_event():
    """get_event_ledger finds a previously recorded event."""
    from app.services.fusion_deep_workflow import record_event, get_event_ledger
    run_id = str(uuid.uuid4())
    record_event(run_id, "run.created", node_key="start")
    record_event(run_id, "node.completed", node_key="n1")
    ledger = get_event_ledger(run_id, limit=10)
    assert len(ledger) >= 2
    actions = [e["action"] for e in ledger]
    assert "run.created" in actions
    assert "node.completed" in actions
    # Verify shape
    for event in ledger:
        assert "id" in event
        assert "action" in event
        assert "created_at" in event


def test_reconcile_chapter_facts_nonexistent():
    """reconcile_chapter_facts returns error for missing chapter."""
    from app.services.fusion_deep_workflow import reconcile_chapter_facts
    r = reconcile_chapter_facts(str(uuid.uuid4()), str(uuid.uuid4()))
    assert r["status"] == "error"
    assert "chapter not found" in r["message"]


def test_create_fact_transaction():
    """create_fact_transaction records a reversible fact mutation."""
    from app.services.fusion_deep_workflow import create_fact_transaction
    content_id = str(uuid.uuid4())
    r = create_fact_transaction("update", content_id,
                                {"name": "old"}, {"name": "new"})
    assert r["operation"] == "update"
    assert r["reversible"] is True
    assert "transaction_id" in r


def test_get_fact_chain_empty():
    """get_fact_chain returns empty list for unknown content."""
    from app.services.fusion_deep_workflow import get_fact_chain
    chain = get_fact_chain(str(uuid.uuid4()))
    assert isinstance(chain, list)


# ============================================================================
# fusion_deep_book.py: book analysis, vocabulary, planning, audit, humanize
# ============================================================================

def test_book_analysis_workbench():
    """book_analysis_workbench analyzes content and detects tropes."""
    from app.services.fusion_deep_book import book_analysis_workbench
    content = """第一章 重生
    他重生回到了十年前。系统面板出现在眼前。
    所有人都震惊了，不可思议！这简直是打脸！
    他隐藏实力，低调行事，没人想得到。"""
    r = book_analysis_workbench(content, "重生之都市至尊")
    assert r["title"] == "重生之都市至尊"
    assert r["total_words"] > 0
    assert r["paragraphs"] >= 1
    assert r["detected_chapters"] >= 1
    assert "重生/穿越" in r["detected_tropes"]
    assert "系统流" in r["detected_tropes"]
    assert r["avg_words_per_paragraph"] > 0
    assert "mind_map_nodes" in r
    assert r["mind_map_nodes"]["core"] == "重生之都市至尊"


def test_book_analysis_workbench_no_tropes():
    """book_analysis_workbench returns empty tropes when none match."""
    from app.services.fusion_deep_book import book_analysis_workbench
    r = book_analysis_workbench("普通的一段文字，没有任何特殊关键词。", "测试")
    assert r["detected_tropes"] == []
    assert r["total_words"] > 0


def test_quick_prompt_vocabulary():
    """quick_prompt_vocabulary returns 6 predefined prompts."""
    from app.services.fusion_deep_book import quick_prompt_vocabulary
    vocab = quick_prompt_vocabulary()
    assert len(vocab) == 6
    names = [v["name"] for v in vocab]
    assert "去AI味" in names
    assert "扩写" in names
    assert "武侠风改写" in names
    for item in vocab:
        assert "name" in item
        assert "prompt" in item
        assert "tags" in item
        assert isinstance(item["tags"], list)
        assert len(item["tags"]) >= 1
        assert len(item["prompt"]) > 0


def test_layered_ai_planning():
    """layered_ai_planning produces 6 phases with correct estimates."""
    from app.services.fusion_deep_book import layered_ai_planning
    plan = layered_ai_planning("少年修仙逆袭", "仙侠", target_words=500000)
    assert plan["idea"] == "少年修仙逆袭"
    assert plan["genre"] == "仙侠"
    assert plan["target_words"] == 500000
    assert len(plan["phases"]) == 6
    assert plan["phases"][0]["name"] == "核心概念"
    assert plan["phases"][-1]["name"] == "逐章细纲"
    for p in plan["phases"]:
        assert p["status"] == "planned"
    assert plan["estimated_volumes"] == 2  # 500000 // 200000
    assert plan["estimated_chapters"] == 100  # 500000 // 5000


def test_layered_ai_planning_default_words():
    """layered_ai_planning defaults to 1M words."""
    from app.services.fusion_deep_book import layered_ai_planning
    plan = layered_ai_planning("测试", "都市")
    assert plan["target_words"] == 1000000
    assert plan["estimated_volumes"] == 5
    assert plan["estimated_chapters"] == 200


def test_adaptive_draft_window_opening():
    """First 3 chapters get full context window (黄金三章)."""
    from app.services.fusion_deep_book import adaptive_draft_window
    r = adaptive_draft_window(1, 100)
    assert r["window_size"] == "full"
    assert "黄金三章" in r["mode"]


def test_adaptive_draft_window_middle():
    """Mid-novel chapters get rolling_10 window."""
    from app.services.fusion_deep_book import adaptive_draft_window
    r = adaptive_draft_window(50, 100)
    assert r["window_size"] == "rolling_10"
    assert "滚动" in r["mode"]


def test_adaptive_draft_window_closing():
    """Final chapters get full_backref for consistency check."""
    from app.services.fusion_deep_book import adaptive_draft_window
    r = adaptive_draft_window(95, 100)
    assert r["window_size"] == "full_backref"
    assert "回溯" in r["mode"]


def test_reasonability_audit_genre_break():
    """reasonability_audit flags phone in xianxia world."""
    from app.services.fusion_deep_book import reasonability_audit
    r = reasonability_audit("他拿出手机看了看，然后御剑飞行。", "仙侠")
    assert r["audited"] is True
    assert r["genre"] == "仙侠"
    assert r["issues_count"] >= 1
    assert any("genre_break" in i for i in r["issues"])


def test_reasonability_audit_clean():
    """reasonability_audit finds no issues with good content."""
    from app.services.fusion_deep_book import reasonability_audit
    r = reasonability_audit("他御剑飞行，穿越云层，来到仙山脚下。", "仙侠")
    assert r["audited"] is True
    assert r["issues_count"] == 0


def test_humanize_text_detects_ai_patterns():
    """humanize_text finds common AI writing patterns."""
    from app.services.fusion_deep_book import humanize_text
    r = humanize_text("不可否认的是，这个方案值得我们深思。")
    assert r["ai_patterns_found"] >= 1
    assert len(r["changes"]) >= 1
    assert any("不可否认" in c["pattern"] for c in r["changes"])


def test_humanize_text_no_patterns():
    """humanize_text returns 0 when no AI patterns found."""
    from app.services.fusion_deep_book import humanize_text
    r = humanize_text("他走在雨中的街道上，想起了往事。")
    assert r["ai_patterns_found"] == 0
    assert r["changes"] == []


def test_knowledge_merge_inserts_new():
    """knowledge_merge inserts new knowledge items and returns counts."""
    from app.services.fusion_deep_book import knowledge_merge
    novel_id = str(uuid.uuid4())
    items = [
        {"kind": "fact", "title": f"test-fact-{uuid.uuid4().hex[:6]}",
         "body": "主角获得了一把神剑"},
    ]
    r = knowledge_merge(novel_id, items)
    assert r["novel_id"] == novel_id
    assert r["inserted"] == 1
    assert r["merged"] == 0
    assert r["total"] == 1


def test_hundred_chapter_memory_empty_novel():
    """hundred_chapter_memory returns 0 for novel with no chapters."""
    from app.services.fusion_deep_book import hundred_chapter_memory
    r = hundred_chapter_memory(str(uuid.uuid4()), 1)
    assert r["chapters_in_memory"] == 0
    assert "window" in r


def test_six_dim_consistency_check():
    """six_dim_consistency_check is explicit for an unknown novel, never fake-passes."""
    from app.services.fusion_deep_book import six_dim_consistency_check
    r = six_dim_consistency_check(str(uuid.uuid4()))
    assert len(r["dimensions_checked"]) == 6
    for dim in ["characters", "locations", "timeline", "items", "settings", "relationships"]:
        assert dim in r["dimensions_checked"]
    assert r["status"] == "not_found"
    assert r["checks"] == {}


def test_agent_execution_routes_through_gateway(monkeypatch):
    from app.services.agent_registry import execute_agent

    captured = {}
    def fake_complete(**kwargs):
        captured.update(kwargs)
        return {"outline": ["第一卷", "第二卷", "第三卷"]}
    monkeypatch.setattr("app.gateway.complete", fake_complete)
    result = execute_agent("story-architect", "project-1", {"idea": "旧城谜案"}, "agent-mutation")
    assert result["status"] == "succeeded"
    assert captured["project_id"] == "project-1"
    assert captured["prompt_name"] == "bootstrap.gen_outline"
    assert captured["client_mutation_id"] == "agent-mutation"


def test_write_retrieval_and_merge():
    """write_retrieval_and_merge returns retrieval context and detected facts."""
    from app.services.fusion_deep_book import write_retrieval_and_merge
    novel_id = str(uuid.uuid4())
    chapter_text = "主角名叫林枫，他到达了青云山，在战斗中突破了境界。"
    r = write_retrieval_and_merge(novel_id, chapter_text)
    assert r["merge_status"] == "ready_for_reconcile"
    # With no chapters in DB, retrieved_context is 0
    assert r["retrieved_context"] == 0
    # Facts detected from keyword matching
    assert r["new_facts_detected"] == 3
    assert "character_introduced" in r["facts"]
    assert "location_changed" in r["facts"]
    assert "power_level_up" in r["facts"]
