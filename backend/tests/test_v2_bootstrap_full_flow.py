"""T2 full-flow: the audit's "Journey A" (从零建书 → 一键生成) end to end.

Runs the complete V2 four-stage workflow synchronously against the real test
database with a patched provider boundary: create_run seeds 19 nodes, planning runs to
the human gate, title confirmation resumes the run, and blueprint → writing →
finalization persist a real chapter row, knowledge items and an event ledger.

The 2026-07-13 acceptance audit proved this journey died at the first node
(no routes / no prompts / fictional model). This test locks the journey shut.
"""
import pytest

from app.db import connect, encode, init_db, new_id


V2_TASK_TYPES = [
    "plan_idea", "plan_market_fit", "plan_story_pattern", "plan_core_gameplay",
    "plan_world_architecture", "plan_character_system", "plan_conflict_map",
    "blueprint_volume_plan", "blueprint_chapter_outline", "blueprint_scene_beat",
    "write_chapter_draft", "write_self_review", "write_polish",
    "write_length_check", "write_fact_reconcile",
    "final_consistency_check", "final_continuity_audit", "final_humanize",
]


@pytest.fixture()
def seeded_novel(monkeypatch):
    init_db()
    db = connect()
    user_id = new_id()
    db.execute(
        "INSERT INTO users (id, email, password_hash, display_name) VALUES (%s,%s,%s,%s)",
        (user_id, f"t2-{user_id[:8]}@test.local", "x", "T2"),
    )
    project_id = new_id()
    db.execute(
        "INSERT INTO projects (id, name, owner_id) VALUES (%s,%s,%s)",
        (project_id, "T2 全链", user_id),
    )
    db.execute(
        "INSERT INTO project_members (id, project_id, user_id, role) VALUES (%s,%s,%s,'owner')",
        (new_id(), project_id, user_id),
    )
    novel_id = new_id()
    db.execute(
        "INSERT INTO contents (id, project_id, type, title, body, meta, status) "
        "VALUES (%s,%s,'novel','未命名',%s,%s,'draft')",
        (novel_id, project_id, encode({}),
         encode({"idea": "一个作者发现自己写的故事正在现实中发生", "genre": "悬疑", "style": "克制"})),
    )
    db.commit()
    db.close()
    yield project_id, novel_id


def _run_state(run_id):
    db = connect()
    run = db.execute("SELECT * FROM workflow_runs WHERE id=%s", (run_id,)).fetchone()
    nodes = db.execute(
        "SELECT node_key, status FROM run_nodes WHERE run_id=%s", (run_id,)
    ).fetchall()
    db.close()
    return run, {n["node_key"]: n["status"] for n in nodes}


def _provider_output(task_type: str) -> dict:
    creative_bible = (
        "核心设定：林序是一名被现实反噬的悬疑作者，他发现自己写下的章节会以扭曲方式发生，必须找出掌控文本与现实边界的执笔会。"
        "开局节奏：第一章用停电、短信和敲门制造异常；第二章追查旁证，确认不是幻觉；第三章进入修档馆，第一次触碰规则。"
        "能力边界：文字只能影响已有因果，不能凭空创造人物和财富；每次改写都会留下旁证，并让执笔会更快定位主角。"
        "长篇路线：第一阶段确认异常并保命，第二阶段建立证据链，第三阶段寻找同类，第四阶段反制执笔会，第五阶段揭开现实修档机制，第六阶段夺回叙事权。"
        "人物关系：林序逃避责任但擅长观察，沈澜守序理性却被真相动摇，闻烬相信控制叙事才能拯救世界。"
        "叙事禁忌：禁止说明书式解释规则，禁止反派降智，禁止靠巧合推进；每个规则必须通过场景、对话和代价展示。"
        "持续校验：检查旁证是否闭环、人物是否知道不该知道的信息、改写代价是否递增、悬疑线索是否能回收。"
    )
    long_body = [
        (
            f"第{index}段，停电来得突然。林序盯着屏幕，门外响起敲门声，短信弹了出来，像有人贴着他的耳朵说话。"
            "他没有立刻开门，只把手按在桌沿，听见自己的心跳一下一下撞在安静里。屏幕上那行字还亮着：三分钟后，有人会来取走你的名字。"
            "楼道里的声控灯忽明忽暗，旧门板被风推得轻轻作响。他想起小说里那个已经死去三章的女主角，想起她最后留下的句子：如果现实开始回信，千万别相信第一个敲门的人。"
            "林序把没水的钢笔握进掌心，笔尖却慢慢渗出墨色，像有什么东西正在借他的手重新写下结局。"
        )
        for index in range(1, 17)
    ]
    outputs = {
        "plan_idea": {"idea_expanded": "一个作者发现自己写下的故事正在现实中发生，他必须夺回人生的叙事权。", "core_hook": "写下的字会改变现实。", "target_audience": "悬疑脑洞读者", "title_candidates": ["《回声来信》", "《执笔者》", "《删章之后》"], "creative_bible": creative_bible},
        "plan_market_fit": {"market_score": 82, "competitive_landscape": "脑洞悬疑读者接受度高。", "market_gap": "创作者身份代入更强。"},
        "plan_story_pattern": {"story_model": "悬疑解谜", "act_structure": ["发现异常", "追查真相", "夺回叙事权"], "turning_points": [{"point": "文本成真", "chapter_hint": "第1章"}]},
        "plan_core_gameplay": {"power_system": "文字改写现实但留下旁证", "progression_path": "读者到执笔者", "pleasure_points": ["信息差反杀", "伏笔回收"]},
        "plan_world_architecture": {"worldview": {"name": "回声城", "rules": ["文字可改写现实", "改写留下旁证", "旁证可追溯执笔者"]}},
        "plan_character_system": {"characters": [{"name": "林序", "role": "主角", "arc": "逃避到承担"}, {"name": "沈澜", "role": "盟友", "arc": "守序到质疑"}, {"name": "闻烬", "role": "反派", "arc": "控制到崩塌"}]},
        "plan_conflict_map": {"conflicts": [{"type": "external", "between": ["林序", "执笔会"], "stakes": "人生叙事权", "escalation": "追踪升级为夺权"}]},
        "blueprint_volume_plan": {"volumes": [{"number": 1, "title": "回声来信", "arc": "发现异常", "start_chapter": 1, "end_chapter": 30}]},
        "blueprint_chapter_outline": {"chapter_outlines": [{"volume": 1, "seq": 1, "title": "第一章 来信", "outline": "主角发现文字成真", "beats": ["停电", "短信", "敲门"]}, {"volume": 1, "seq": 2, "title": "第二章 旁证", "outline": "寻找证据", "beats": ["追查", "受阻", "反转"]}, {"volume": 1, "seq": 3, "title": "第三章 修档馆", "outline": "进入新地点", "beats": ["抵达", "冲突", "钩子"]}]},
        "blueprint_scene_beat": {"scene_beats": [{"scene": 1, "pov": "林序", "location": "出租屋", "goal": "赶稿", "conflict": "文本成真", "outcome": "意外", "emotional_shift": "烦躁到惊惧"}, {"scene": 2, "pov": "林序", "location": "楼道", "goal": "确认敲门", "conflict": "无人回应", "outcome": "失败", "emotional_shift": "惊惧到好奇"}, {"scene": 3, "pov": "林序", "location": "街口", "goal": "求证", "conflict": "旁证出现", "outcome": "成功", "emotional_shift": "好奇到决心"}]},
        "write_chapter_draft": {"chapter": {"title": "第一章 来信", "body": long_body}},
        "write_self_review": {"self_score": 82, "strengths": ["钩子清晰"], "weaknesses": ["压力可加强"]},
        "write_polish": {"polished": {"body": long_body}, "changes_summary": "收紧节奏"},
        "write_length_check": {"actual_chars": 3600, "is_acceptable": True},
        "write_fact_reconcile": {"reconciliation": {"conflicts_found": 0}},
        "final_consistency_check": {"checks": {"timeline": {"status": "pass"}}, "overall_status": "pass"},
        "final_continuity_audit": {"continuity": {"status": "continuous"}},
        "final_humanize": {"humanized_text": "\n".join(long_body), "changes": ["收紧句子"]},
    }
    return outputs[task_type]


def test_journey_a_full_v2_flow_provider_boundary(seeded_novel, monkeypatch):
    from app.workers import tasks

    project_id, novel_id = seeded_novel
    monkeypatch.setattr(tasks, "complete", lambda **kwargs: _provider_output(kwargs["task_type"]))
    monkeypatch.setattr(tasks, "_summarize_and_store", lambda *_args, **_kwargs: None)

    # celery eager-ish: call the underlying function synchronously
    run_id = None

    def sync_dispatch(rid, start_key, api_key="", api_url="", model=""):
        tasks.execute_bootstrap.run(rid, start_key, api_key, api_url, model)

    original_delay = tasks.execute_bootstrap.delay
    tasks.execute_bootstrap.delay = sync_dispatch  # type: ignore[assignment]
    try:
        run_id = tasks.create_run(project_id, novel_id)

        run, node_status = _run_state(run_id)
        # 19 nodes seeded, planning succeeded, human gate reached
        assert len(node_status) == 19
        assert run["status"] == "waiting_human"
        for key in ("plan_idea", "plan_market_fit", "plan_story_pattern", "plan_core_gameplay",
                    "plan_world_architecture", "plan_character_system", "plan_conflict_map"):
            assert node_status[key] == "succeeded", (key, node_status[key])
        assert node_status["human_confirm_title"] == "waiting_human"

        # Human gate has real title candidates in context (frontend renders these)
        titles = run["context"].get("title_candidates") or []
        assert len(titles) >= 3, run["context"].keys()

        # Confirm title → workflow resumes through blueprint/writing/finalization
        tasks.confirm_human(run_id, titles[0])

        run, node_status = _run_state(run_id)
        assert run["status"] == "succeeded", (run["status"], node_status)
        for key in ("blueprint_volume_plan", "blueprint_chapter_outline", "blueprint_scene_beat",
                    "write_chapter_draft", "write_self_review", "write_polish",
                    "write_length_check", "write_fact_reconcile",
                    "final_consistency_check", "final_continuity_audit", "final_humanize"):
            assert node_status[key] == "succeeded", (key, node_status[key])
    finally:
        tasks.execute_bootstrap.delay = original_delay  # type: ignore[assignment]

    db = connect()
    # Novel got the confirmed title
    novel = db.execute("SELECT title FROM contents WHERE id=%s", (novel_id,)).fetchone()
    assert novel["title"] == titles[0]
    # A real chapter row exists with narrative body
    chapter = db.execute(
        "SELECT * FROM contents WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE",
        (novel_id,),
    ).fetchone()
    assert chapter is not None
    assert len(str(chapter["body"])) > 200
    # Worldview + characters landed in the knowledge hub
    kinds = [r["kind"] for r in db.execute(
        "SELECT kind FROM knowledge_items WHERE content_id=%s AND is_deleted=FALSE", (novel_id,)
    ).fetchall()]
    assert "worldview" in kinds and "character" in kinds
    # Event ledger (denova, mapped onto audit_logs) recorded the run lifecycle
    events = [r["action"] for r in db.execute(
        "SELECT action FROM audit_logs WHERE entity_type='workflow_run' AND entity_id=%s ORDER BY created_at",
        (run_id,),
    ).fetchall()]
    assert "run.started" in events and "run.completed" in events, events
    db.close()


def test_bootstrap_auto_confirms_title_for_unattended_basic_chain(seeded_novel, monkeypatch):
    from app.workers import tasks

    project_id, novel_id = seeded_novel
    monkeypatch.setattr(tasks, "complete", lambda **kwargs: _provider_output(kwargs["task_type"]))
    monkeypatch.setattr(tasks, "_summarize_and_store", lambda *_args, **_kwargs: None)

    def sync_dispatch(rid, start_key, api_key="", api_url="", model=""):
        tasks.execute_bootstrap.run(rid, start_key, api_key, api_url, model)

    original_delay = tasks.execute_bootstrap.delay
    tasks.execute_bootstrap.delay = sync_dispatch  # type: ignore[assignment]
    try:
        run_id = tasks.create_run(project_id, novel_id, auto_confirm_title=True)
    finally:
        tasks.execute_bootstrap.delay = original_delay  # type: ignore[assignment]

    run, node_status = _run_state(run_id)
    assert run["status"] == "succeeded", (run["status"], node_status)
    assert node_status["human_confirm_title"] == "succeeded"

    db = connect()
    human = db.execute(
        "SELECT output FROM run_nodes WHERE run_id=%s AND node_key='human_confirm_title'",
        (run_id,),
    ).fetchone()
    novel = db.execute("SELECT title FROM contents WHERE id=%s", (novel_id,)).fetchone()
    events = [r["action"] for r in db.execute(
        "SELECT action FROM audit_logs WHERE entity_type='workflow_run' AND entity_id=%s ORDER BY created_at",
        (run_id,),
    ).fetchall()]
    human_events = db.execute(
        """SELECT details FROM audit_logs
           WHERE entity_type='workflow_run' AND entity_id=%s AND action='human.confirmed'
           ORDER BY created_at""",
        (run_id,),
    ).fetchall()
    db.close()

    assert human["output"]["source"] == "auto_confirm"
    assert novel["title"] == "《回声来信》"
    assert "human.confirmed" in events
    assert any((event["details"].get("payload") or {}).get("action") == "auto_confirmed" for event in human_events)


def test_bootstrap_rejects_non_narrative_polish_before_overwriting_chapter(seeded_novel, monkeypatch):
    from app.services.novel_export import extract_body_text
    from app.workers import tasks

    project_id, novel_id = seeded_novel

    def provider_output(task_type: str) -> dict:
        if task_type == "write_polish":
            return {
                "polished": {
                    "body": [
                        "本章将深入探讨如何通过精准的语言表达和逻辑结构优化文本内容。",
                        "在润色过程中，首先需要明确章节的核心主题与目标读者。",
                        "其次，检查句子之间的衔接与过渡，提升阅读流畅性。",
                        "最后，删除冗余表述，替换模糊词汇。",
                    ]
                },
                "changes_summary": "错误地输出了润色说明。",
            }
        return _provider_output(task_type)

    monkeypatch.setattr(tasks, "complete", lambda **kwargs: provider_output(kwargs["task_type"]))
    monkeypatch.setattr(tasks, "_summarize_and_store", lambda *_args, **_kwargs: None)

    def sync_dispatch(rid, start_key, api_key="", api_url="", model=""):
        tasks.execute_bootstrap.run(rid, start_key, api_key, api_url, model)

    original_delay = tasks.execute_bootstrap.delay
    tasks.execute_bootstrap.delay = sync_dispatch  # type: ignore[assignment]
    try:
        run_id = tasks.create_run(project_id, novel_id, auto_confirm_title=True)
    finally:
        tasks.execute_bootstrap.delay = original_delay  # type: ignore[assignment]

    run, node_status = _run_state(run_id)
    assert run["status"] == "failed"
    assert node_status["write_polish"] == "failed"

    db = connect()
    chapter = db.execute(
        "SELECT body FROM contents WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE",
        (novel_id,),
    ).fetchone()
    failed_node = db.execute(
        "SELECT error FROM run_nodes WHERE run_id=%s AND node_key='write_polish'",
        (run_id,),
    ).fetchone()
    db.close()

    assert "non-narrative" in failed_node["error"]
    body_text = extract_body_text(chapter["body"])
    assert "停电来得突然" in body_text
    assert "本章将深入探讨" not in body_text


def test_journey_a_resumes_after_provider_failure(seeded_novel, monkeypatch):
    """Checkpoint contract: a provider failure marks failed, and a
    redrive resumes from the failed node instead of restarting or crashing
    (the P0 ledger-poisoning regression fixed on 2026-07-13)."""
    from app import gateway
    from app.workers import tasks

    project_id, novel_id = seeded_novel
    monkeypatch.setattr(tasks, "_summarize_and_store", lambda *_args, **_kwargs: None)

    fail_on = {"plan_story_pattern"}
    def flaky_complete(**kwargs):
        if kwargs.get("task_type") in fail_on:
            raise gateway.ProviderError("simulated provider outage")
        return _provider_output(kwargs["task_type"])

    monkeypatch.setattr(tasks, "complete", flaky_complete)

    def sync_dispatch(rid, start_key, api_key="", api_url="", model=""):
        tasks.execute_bootstrap.run(rid, start_key, api_key, api_url, model)

    original_delay = tasks.execute_bootstrap.delay
    tasks.execute_bootstrap.delay = sync_dispatch  # type: ignore[assignment]
    try:
        run_id = tasks.create_run(project_id, novel_id)
        run, node_status = _run_state(run_id)
        assert node_status["plan_story_pattern"] == "failed"
        assert node_status["plan_idea"] == "succeeded"

        # Provider recovers; redrive from the failed node
        fail_on.clear()
        tasks.execute_bootstrap.run(run_id, "plan_story_pattern")
        run, node_status = _run_state(run_id)
        assert run["status"] == "waiting_human"
        assert node_status["plan_story_pattern"] == "succeeded"
    finally:
        tasks.execute_bootstrap.delay = original_delay  # type: ignore[assignment]
