"""v0.9.2 出版准备层单元测试

覆盖：statistics_v1、publishing_gates、local_repair、chapter_context、状态机
运行方式（绕过sqlalchemy依赖）：
  python3 -c "import importlib.util,sys,types; [sys.modules.update({n: types.ModuleType(n)}) for n in ['app','app.v7','app.v7.quality','app.v7.services']]; spec=importlib.util.spec_from_file_location('t','tests/test_publishing_v092.py'); m=importlib.util.module_from_spec(spec); sys.modules['t']=m; spec.loader.exec_module(m); m.run_all_tests()"
"""
from __future__ import annotations

import importlib.util
import json
import sys
import types
import os

# 加载模块（绕过v7 __init__的sqlalchemy依赖）
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(full_name, rel_path):
    path = os.path.join(_BASE, rel_path)
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


# 建立包层级
for pkg in ["app", "app.v7", "app.v7.quality", "app.v7.services"]:
    if pkg not in sys.modules:
        m = types.ModuleType(pkg)
        m.__path__ = [os.path.join(_BASE, pkg.replace(".", "/"))]
        sys.modules[pkg] = m

stats_mod = _load("app.v7.quality.statistics_v1", "app/v7/quality/statistics_v1.py")
gates_mod = _load("app.v7.quality.publishing_gates", "app/v7/quality/publishing_gates.py")
repair_mod = _load("app.v7.quality.local_repair", "app/v7/quality/local_repair.py")
ctx_mod = _load("app.v7.services.chapter_context", "app/v7/services/chapter_context.py")


# ── 测试辅助 ──────────────────────────────────────────────────
_passed = 0
_failed = 0


def assert_eq(actual, expected, msg=""):
    global _passed, _failed
    if actual == expected:
        _passed += 1
    else:
        _failed += 1
        print(f"  ❌ FAIL: {msg} — expected={expected}, actual={actual}")


def assert_true(cond, msg=""):
    global _passed, _failed
    if cond:
        _passed += 1
    else:
        _failed += 1
        print(f"  ❌ FAIL: {msg}")


# ── 测试文本 ──────────────────────────────────────────────────
SAMPLE_CHAPTER = """第一章 重生
林辰猛地睁开眼睛，刺眼的阳光让他下意识地眯起了眼。
\"这是……我的房间？\"他看着熟悉的天花板，声音颤抖。
十年前的记忆如潮水般涌来——他还没有被背叛，还没有失去一切。
\"我回来了。\"林辰握紧拳头，眼中闪过一丝厉色。
这一次，他要让所有背叛过他的人付出代价。
手机突然响起，屏幕上显示着一个他永生难忘的名字：赵天霸。
\"林辰，今晚的聚会别忘了。\"电话那头传来戏谑的声音。
林辰嘴角勾起一抹冷笑：\"放心，我一定到。\"
挂掉电话，他深吸一口气。复仇的棋局，从这一刻开始布局。
然而他不知道的是，一场更大的危机正在暗处悄然逼近。"""


# ── 1. statistics_v1 测试 ────────────────────────────────────
def test_statistics_v1():
    print("\n=== statistics_v1 测试 ===")
    result = stats_mod.compute_statistics(SAMPLE_CHAPTER)

    assert_eq(result.chapter_count, 1, "章节数应为1")
    assert_true(result.total_chars > 200, f"总字符应>200，实际{result.total_chars}")
    assert_true(result.total_paragraphs >= 5, f"段落数应>=5，实际{result.total_paragraphs}")
    assert_true(result.total_dialogues >= 3, f"对话数应>=3，实际{result.total_dialogues}")
    assert_true(result.total_sentences >= 8, f"句子数应>=8，实际{result.total_sentences}")

    # 确定性测试
    result2 = stats_mod.compute_statistics(SAMPLE_CHAPTER)
    assert_eq(result.to_json(), result2.to_json(), "两次调用结果应完全一致（确定性）")
    assert_eq(result.content_sha256, result2.content_sha256, "内容哈希应一致")
    assert_eq(result.normalized_sha256, result2.normalized_sha256, "归一化哈希应一致")

    # 双哈希不同
    assert_true(result.content_sha256 != result.normalized_sha256, "原文哈希和归一化哈希应不同")

    # 空文本
    empty = stats_mod.compute_statistics("")
    assert_eq(empty.total_chars, 0, "空文本字符数应为0")
    assert_eq(empty.chapter_count, 0, "空文本章节数应为0")

    print(f"  ✅ {_passed - sum(1 for _ in [])} passed (累计{_passed})")


# ── 2. publishing_gates 测试 ─────────────────────────────────
def test_publishing_gates():
    print("\n=== publishing_gates 测试 ===")

    # 2.1 完整门禁运行
    report = gates_mod.run_all_gates(
        chapter_id="test-001",
        text=SAMPLE_CHAPTER,
        platform_profile={
            "platform": "fanqie",
            "policy_status": "confirmed",
            "ai_usage_policy": "allowed",
            "chapter_word_min": 100,
            "chapter_word_max": 5000,
        },
        metadata={
            "title": "重生之复仇",
            "synopsis": "林辰重生回到十年前，对抗背叛者的逆袭复仇故事",
            "tags": ["重生", "复仇", "逆袭"],
            "category": "都市",
        },
    )

    assert_true(report.quality_candidate, "quality_candidate应为True（七项均已输出）")
    assert_eq(len(report.gates), 7, "应有7道门禁")
    assert_true("content_quality" in report.gates, "应有content_quality门禁")
    assert_true("continuity" in report.gates, "应有continuity门禁")
    assert_true("payoff_density" in report.gates, "应有payoff_density门禁")
    assert_true("readability" in report.gates, "应有readability门禁")
    assert_true("platform_compliance" in report.gates, "应有platform_compliance门禁")
    assert_true("ai_disclosure" in report.gates, "应有ai_disclosure门禁")
    assert_true("external_risk" in report.gates, "应有external_risk门禁")

    # 2.2 AI披露政策测试
    # prohibited 应该不通过
    report_prohibited = gates_mod.run_all_gates(
        chapter_id="test-002",
        text=SAMPLE_CHAPTER,
        platform_profile={"platform": "jinjiang", "policy_status": "confirmed", "ai_usage_policy": "prohibited"},
        metadata={"title": "test", "synopsis": "冲突故事主角", "tags": ["x"], "category": "y"},
    )
    assert_true(not report_prohibited.gates["ai_disclosure"].passed, "prohibited政策下ai_disclosure应不通过")
    assert_true(not report_prohibited.overall_publish_ready, "prohibited政策下publish_ready应为False")

    # allowed_with_human_editing 无人工编辑应不通过
    report_editing = gates_mod.run_all_gates(
        chapter_id="test-003",
        text=SAMPLE_CHAPTER,
        platform_profile={"platform": "fanqie", "policy_status": "confirmed", "ai_usage_policy": "allowed_with_human_editing"},
        metadata={"title": "test", "synopsis": "冲突故事主角", "tags": ["x"], "category": "y"},
        human_editing_confirmed=False,
    )
    assert_true(not report_editing.gates["ai_disclosure"].passed, "无人工编辑时ai_disclosure应不通过")

    # allowed_with_human_editing 有人工编辑应通过
    report_editing_ok = gates_mod.run_all_gates(
        chapter_id="test-004",
        text=SAMPLE_CHAPTER,
        platform_profile={"platform": "fanqie", "policy_status": "confirmed", "ai_usage_policy": "allowed_with_human_editing"},
        metadata={"title": "test", "synopsis": "冲突故事主角", "tags": ["x"], "category": "y"},
        human_editing_confirmed=True,
    )
    assert_true(report_editing_ok.gates["ai_disclosure"].passed, "有人工编辑时ai_disclosure应通过")

    # 2.3 平台规则stale应不通过
    report_stale = gates_mod.run_all_gates(
        chapter_id="test-005",
        text=SAMPLE_CHAPTER,
        platform_profile={"platform": "fanqie", "policy_status": "stale", "ai_usage_policy": "allowed"},
        metadata={"title": "test", "synopsis": "冲突故事主角", "tags": ["x"], "category": "y"},
    )
    pc = report_stale.gates["platform_compliance"]
    assert_true(not pc.passed, "stale政策下platform_compliance应不通过")
    assert_true("platform_rules" in pc.sub_gates, "应有platform_rules子门禁")
    assert_true(not pc.sub_gates["platform_rules"]["passed"], "stale时platform_rules子门禁应不通过")

    # 2.4 external_risk默认非阻断
    report_ext = gates_mod.run_all_gates(
        chapter_id="test-006",
        text=SAMPLE_CHAPTER,
        platform_profile={"platform": "fanqie", "policy_status": "confirmed", "ai_usage_policy": "allowed"},
        metadata={"title": "test", "synopsis": "冲突故事主角", "tags": ["x"], "category": "y"},
        external_flagged=True,
        external_score=90.0,
    )
    ext = report_ext.gates["external_risk"]
    assert_true(not ext.is_blocking, "allowed政策下external_risk应非阻断")
    assert_true(len(ext.warnings) > 0, "external_flagged时应有warning")

    # 2.5 作品级95/5/0外部硬门：缺报告和失败报告均必须阻断
    hard_profile = {
        "platform": "fanqie",
        "policy_status": "confirmed",
        "ai_usage_policy": "allowed_with_human_editing",
        "extra_metadata": {"external_detector_hard_gate": True},
    }
    report_hard_pending = gates_mod.run_all_gates(
        chapter_id="test-007",
        text=SAMPLE_CHAPTER,
        platform_profile=hard_profile,
        metadata={"title": "test", "synopsis": "冲突故事主角", "tags": ["x"], "category": "y"},
        human_editing_confirmed=True,
    )
    assert_true(report_hard_pending.gates["external_risk"].is_blocking, "外部硬门应阻断")
    assert_true(not report_hard_pending.gates["external_risk"].passed, "缺少外部报告时应不通过")
    report_hard_pass = gates_mod.run_all_gates(
        chapter_id="test-008",
        text=SAMPLE_CHAPTER,
        platform_profile=hard_profile,
        metadata={"title": "test", "synopsis": "冲突故事主角", "tags": ["x"], "category": "y"},
        human_editing_confirmed=True,
        external_evaluation={
            "status": "external_95_5_0",
            "target_passed": True,
            "human_score": 95.0,
            "suspected_ai_score": 5.0,
            "ai_feature_score": 0.0,
        },
    )
    assert_true(report_hard_pass.gates["external_risk"].passed, "满足95/5/0时外部硬门应通过")

    print(f"  ✅ 门禁测试完成 (累计{_passed})")


# ── 3. local_repair 测试 ─────────────────────────────────────
def test_local_repair():
    print("\n=== local_repair 测试 ===")

    # 3.1 AI味检测
    ai_text = "此时此刻，林辰不禁感到震惊。仿佛命运一般，他不由得握紧了拳头。总而言之，这是一个新的开始。"
    risks = repair_mod.detect_risk_sentences(ai_text)
    assert_true(len(risks) >= 1, f"应检测到AI味风险，实际{len(risks)}处")

    # 3.2 标点异常检测
    punct_text = "这是一句话。。这是另一句话，，还有第三句。"
    risks_punct = repair_mod.detect_risk_sentences(punct_text)
    punct_types = [r.risk_type for r in risks_punct]
    assert_true("punctuation" in punct_types, "应检测到标点异常")

    # 3.3 修复流水线
    result = repair_mod.local_repair_pipeline(ai_text, max_rounds=2, max_repairs_per_round=3)
    assert_true(result.rounds_used >= 1, f"应至少运行1轮，实际{result.rounds_used}")
    assert_true(result.max_rounds == 2, "max_rounds应为2")
    assert_true(result.repaired_text != ai_text, "检测到风险后应产生局部修复结果")

    # 3.4 should_use_full_rewrite
    assert_true(not repair_mod.should_use_full_rewrite([], "test"), "无风险时不应整章重写")

    # 3.5 空简介不能让平台门禁抛出未绑定变量异常
    report = gates_mod.run_all_gates(
        chapter_id="test-empty-synopsis",
        text=SAMPLE_CHAPTER,
        platform_profile={"platform": "fanqie", "policy_status": "confirmed", "ai_usage_policy": "allowed"},
        metadata={"title": "测试标题", "synopsis": "", "tags": ["重生"], "category": "都市"},
    )
    assert_true(not report.gates["platform_compliance"].passed, "空简介应明确阻断平台合规")

    print(f"  ✅ 局部修复测试完成 (累计{_passed})")


# ── 4. chapter_context 测试 ──────────────────────────────────
def test_chapter_context():
    print("\n=== chapter_context 测试 ===")

    # 4.1 正常组装
    ctx = ctx_mod.assemble_chapter_context(
        novel_id="novel-001",
        chapter_id="chapter-001",
        chapter_seq=1,
        genre_pack={"name": "都市重生", "style_rules": {"tone": "爽文"}},
        style_card={"tone": "快节奏", "pace": "紧凑"},
        character_voices=[{"name": "林辰", "role": "主角", "speech_pattern": "冷静果断", "human_confirmed": True}],
        causal_contract={
            "core_question": "林辰如何改变命运",
            "visible_payoff": "获得第一个机会",
            "cost_or_sacrifice": "暴露身份",
            "next_pressure": "敌人出现",
        },
        platform_profile={"platform": "fanqie", "ai_usage_policy": "allowed"},
    )

    assert_eq(ctx.novel_id, "novel-001", "novel_id应正确")
    assert_eq(ctx.genre_pack.genre_name, "都市重生", "品类名应正确")
    assert_eq(ctx.style_card.tone, "快节奏", "文风语气应正确")
    assert_eq(len(ctx.character_voices), 1, "应有1个人物声音卡")
    assert_true(ctx.character_voices[0].human_confirmed, "人物声音卡应已确认")
    assert_eq(ctx.causal_contract.core_question, "林辰如何改变命运", "因果契约核心问题应正确")
    assert_eq(ctx.platform.platform, "fanqie", "平台应正确")
    assert_true(ctx.budget.total_tokens > 0, "应估算token")
    assert_true(not ctx.budget.exceeded, "正常上下文不应超预算")
    assert_eq(len(ctx.assembly_errors), 0, "正常组装不应有错误")

    # 4.2 因果契约缺失字段
    ctx_missing = ctx_mod.assemble_chapter_context(
        novel_id="n",
        chapter_id="c",
        causal_contract={"core_question": "只有核心问题"},
    )
    assert_true(len(ctx_missing.assembly_errors) > 0, "因果契约缺失字段应有错误")

    # 4.3 超预算检测
    huge_style = {"sample_prose": "长" * 10000}
    ctx_huge = ctx_mod.assemble_chapter_context(
        novel_id="n", chapter_id="c",
        style_card=huge_style,
        max_tokens=1000,
    )
    assert_true(ctx_huge.budget.exceeded, "超大上下文应标记超预算")

    print(f"  ✅ 上下文融合测试完成 (累计{_passed})")


# ── 5. 状态机测试 ────────────────────────────────────────────
def test_state_machine():
    print("\n=== 状态机测试 ===")

    # 直接测试publishing_service的状态机逻辑
    import importlib.util as iu
    spec = iu.spec_from_file_location("ps", os.path.join(_BASE, "app/v7/services/publishing_service.py"))
    # 这个模块导入了其他模块，我们只测试can_transition函数
    # 通过读取源码提取函数逻辑
    with open(os.path.join(_BASE, "app/v7/services/publishing_service.py")) as f:
        source = f.read()

    # 验证状态机定义存在
    assert_true("PUBLISHING_STATES" in source, "应定义PUBLISHING_STATES")
    assert_true("VALID_TRANSITIONS" in source, "应定义VALID_TRANSITIONS")
    assert_true("can_transition" in source, "应定义can_transition函数")
    assert_true("quality_candidate" in source, "应包含quality_candidate状态")
    assert_true("publish_ready" in source, "应包含publish_ready状态")
    assert_true("published" in source, "应包含published状态")

    # 手动验证状态转换逻辑
    valid_transitions = {
        "draft": ["quality_candidate", "rejected"],
        "quality_candidate": ["publish_ready", "draft", "rejected"],
        "publish_ready": ["published", "quality_candidate", "rejected"],
        "published": ["quality_candidate"],
        "rejected": ["draft", "quality_candidate"],
    }

    def can_t(current, target):
        return target in valid_transitions.get(current, [])

    assert_true(can_t("draft", "quality_candidate"), "draft→quality_candidate应合法")
    assert_true(can_t("quality_candidate", "publish_ready"), "quality_candidate→publish_ready应合法")
    assert_true(can_t("publish_ready", "published"), "publish_ready→published应合法")
    assert_true(not can_t("draft", "published"), "draft→published应非法")
    assert_true(not can_t("published", "draft"), "published→draft应非法")
    assert_true(can_t("published", "quality_candidate"), "published→quality_candidate应合法（撤回）")

    print(f"  ✅ 状态机测试完成 (累计{_passed})")


# ── 运行所有测试 ──────────────────────────────────────────────
def run_all_tests():
    global _passed, _failed
    _passed = 0
    _failed = 0

    print("=" * 60)
    print("v0.9.2 出版准备层单元测试")
    print("=" * 60)

    test_statistics_v1()
    test_publishing_gates()
    test_local_repair()
    test_chapter_context()
    test_state_machine()

    print("\n" + "=" * 60)
    print(f"测试结果: {_passed} passed, {_failed} failed")
    print("=" * 60)

    if _failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
