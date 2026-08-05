"""Deterministic contracts for long-form planning and future-simulation stories.

The provider may write the creative material, but it must not be allowed to
silently change the project's length, route, or the rules of a core cheat.
This module keeps those checks independent from the prompt so a malformed
plan is retried before it can seed the blueprint or prose chain.
"""
from __future__ import annotations

import re
from typing import Any


_TOTAL_WORD_RE = re.compile(
    r"(?:目标总字数|总字数|全书总字数|目标篇幅|全书篇幅)"
    r"[^。；;\n]{0,28}?"
    r"(\d[\d,，_]*)\s*(万)?\s*字"
)
_WORD_RANGE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*[-—至]\s*(\d+(?:\.\d+)?)\s*万字"
)


def _number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip().replace(",", "").replace("，", "").replace("_", "")
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _target_in_text(value: str) -> list[int]:
    targets: list[int] = []
    for raw, wan in _TOTAL_WORD_RE.findall(value or ""):
        parsed = _number(raw)
        if parsed is None:
            continue
        targets.append(parsed * 10000 if wan else parsed)
    return targets


def _idea_requires_simulator(idea: str) -> bool:
    text = str(idea or "")
    return any(marker in text for marker in ("模拟器", "人生模拟", "模拟未来", "推演未来"))


def _idea_requires_core_mechanic(idea: str) -> bool:
    text = str(idea or "")
    return any(
        marker in text
        for marker in (
            "金手指", "系统", "签到", "模拟器", "人生模拟", "重生", "空间",
            "随身", "面板", "传承", "血脉", "灵泉", "商城", "时间循环",
            "时间回溯", "属性", "能力",
        )
    )


def validate_core_mechanic_contract(
    contract: Any,
    *,
    required: bool = False,
) -> list[str]:
    """Validate the shared contract used by every cheat/core story mechanic.

    A mechanic is only useful when it creates a repeatable reader-facing loop:
    trigger -> protagonist choice -> visible payoff -> cost/limit -> state
    change -> a new problem.  This keeps system, rebirth, space, inheritance,
    and simulator stories on the same quality rails without forcing them into
    one fictional implementation.
    """
    if not isinstance(contract, dict):
        return ["必须提供结构化 core_mechanic_contract"] if required else []
    enabled = contract.get("enabled")
    if required and enabled is False:
        return ["原始需求包含核心金手指，core_mechanic_contract.enabled 不能为 false"]
    if not required and enabled is not True:
        return []

    required_fields = {
        "mechanic_type": "机制类型",
        "reader_promise": "读者承诺",
        "trigger_and_loop": "触发到新冲突的闭环",
        "capability_loop": "能力循环",
        "choice_surface": "主角选择面",
        "visible_payoff": "可见收益",
        "limits_and_costs": "边界与代价",
        "failure_and_risks": "失败与风险",
        "state_writeback": "状态写回",
        "plot_coupling": "主线耦合",
        "progression": "成长升级",
    }
    defects: list[str] = []
    for field, label in required_fields.items():
        value = contract.get(field)
        if value in (None, "", [], {}):
            defects.append(f"core_mechanic_contract 缺少{label}（{field}）")

    loop = str(contract.get("capability_loop", ""))
    loop_markers = ("触发", "选择", "行动", "结果", "收益", "代价", "新问题", "冲突")
    if sum(marker in loop for marker in loop_markers) < 5:
        defects.append("能力循环必须写清触发、选择、行动、可见结果、代价和新问题")
    choice = str(contract.get("choice_surface", ""))
    if not any(marker in choice for marker in ("选择", "取舍", "放弃", "风险")):
        defects.append("金手指必须让主角做选择和取舍，不能替主角自动通关")
    costs = str(contract.get("limits_and_costs", ""))
    if len(costs.strip()) < 12:
        defects.append("金手指必须有可执行的使用边界和代价")
    writeback = str(contract.get("state_writeback", ""))
    if not any(marker in writeback for marker in ("现实", "状态", "改变", "写回", "后果")):
        defects.append("金手指收益必须写回人物、资源、关系或风险状态，并产生后果")
    coupling = str(contract.get("plot_coupling", ""))
    if not any(marker in coupling for marker in ("主线", "冲突", "新问题", "升级", "不能跳过")):
        defects.append("金手指必须服务主线冲突，收益后要产生新问题或升级")
    return defects


def validate_simulator_contract(
    contract: Any,
    *,
    required: bool = False,
) -> list[str]:
    """Return actionable defects for a fictional future-simulation mechanic.

    This is a story-rule contract, not an instruction to invent arbitrary
    powers.  It requires the minimum loop that makes a simulator satisfying:
    simulate to a terminal fate, expose branches and rewards, let the lead
    choose what to bring back, and record the cost/causal change.
    """
    if not isinstance(contract, dict):
        return ["必须提供结构化 simulator_contract"] if required else []
    enabled = contract.get("enabled")
    if required and enabled is False:
        return ["原始需求明确包含模拟器，simulator_contract.enabled 不能为 false"]
    if not required and enabled is not True:
        return []

    defects: list[str] = []
    required_fields = {
        "horizon": "模拟范围",
        "terminal_condition": "终局条件",
        "branches": "分支展示规则",
        "observable_state": "模拟中可观察的状态",
        "harvestable_rewards": "可回收收益",
        "selection_rules": "收益选择规则",
        "costs_and_risks": "模拟与回收代价",
        "reality_writeback": "回写现实规则",
        "causal_recalculation": "回收后的因果重算规则",
        "plot_guardrails": "不跳过主线的剧情护栏",
    }
    for field, label in required_fields.items():
        value = contract.get(field)
        if value in (None, "", [], {}):
            defects.append(f"simulator_contract 缺少{label}（{field}）")

    horizon = f"{contract.get('horizon', '')} {contract.get('terminal_condition', '')}"
    if not any(marker in horizon for marker in ("死亡", "身死", "终局", "寿终", "道消", "结局")):
        defects.append("模拟范围必须明确从当前状态推演到死亡或终局，不能只看未来几天")

    branches = contract.get("branches")
    branch_text = str(branches)
    if isinstance(branches, list) and len(branches) < 2:
        defects.append("模拟器至少要展开两条可比较的未来分支")
    elif not isinstance(branches, list) and not any(
        marker in branch_text for marker in ("两条", "多条", "分支")
    ):
        defects.append("branches 必须说明至少两条可比较的未来分支")

    rewards = str(contract.get("harvestable_rewards", ""))
    if not any(marker in rewards for marker in ("机缘", "修为", "功法", "资源", "能力")):
        defects.append("模拟收益必须至少允许选择回收机缘、修为、功法、资源或能力中的一类")

    selection = str(contract.get("selection_rules", ""))
    if not any(marker in selection for marker in ("选择", "取舍", "组合", "放弃")):
        defects.append("收益选择规则必须允许选择、取舍、组合或放弃，不能默认全量领取")
    if any(marker in selection for marker in ("全部带回", "无条件全拿", "全部获得")):
        defects.append("收益选择规则不能允许无条件全量带回，否则会直接破坏剧情张力")

    writeback = str(contract.get("reality_writeback", ""))
    if not any(marker in writeback for marker in ("带回", "回收", "现实", "选择", "改写", "改变")):
        defects.append("必须说明主角如何选择模拟收益并将其带回现实，以及选择如何改变现实")

    recalculation = str(contract.get("causal_recalculation", ""))
    if not any(marker in recalculation for marker in ("重算", "重新模拟", "重新推演", "分支", "因果")):
        defects.append("回收收益后必须重新计算受影响的因果和未来分支")
    guardrails = str(contract.get("plot_guardrails", ""))
    if not any(marker in guardrails for marker in ("主线", "冲突", "代价", "新问题", "不能跳过")):
        defects.append("剧情护栏必须说明收益不能跳过主线冲突，并要带来新问题、代价或升级")

    costs = str(contract.get("costs_and_risks", ""))
    cost_markers = ("次数", "寿元", "资源", "因果", "失败", "暴露", "代价", "冷却")
    if len(costs.strip()) < 12 or sum(marker in costs for marker in cost_markers) < 2:
        defects.append("模拟器必须有可执行的次数、寿元、资源、因果或失败代价，不能无条件全拿")
    return defects


def validate_longform_contract(
    output: dict[str, Any],
    *,
    idea: str,
    target_words: int,
) -> list[str]:
    """Validate the plan/bible as one closed word-and-rule ledger."""
    defects: list[str] = []
    target = int(target_words or 0)
    bible = str(output.get("creative_bible") or "")
    if target >= 500_000:
        minimum = 2200 if target >= 1_000_000 else 1600
        if len(bible.replace("\n", "")) < minimum:
            defects.append(
                f"长篇创作圣经过短：当前约 {len(bible.replace(chr(10), ''))} 字，至少需要 {minimum} 字，"
                "必须覆盖黄金三章、能力边界、阶段路线、人物关系、篇幅账本和校验清单"
            )

    if target > 0:
        text_targets = _target_in_text(bible)
        wrong_targets = [value for value in text_targets if value != target]
        if wrong_targets:
            defects.append(
                f"创作圣经出现与项目目标不一致的总字数：{wrong_targets}；项目目标是 {target} 字"
            )
        for _low, high in _WORD_RANGE_RE.findall(bible):
            high_words = int(float(high) * 10000)
            if high_words > target:
                defects.append(
                    f"长篇路线阶段上限 {high} 万字超过项目目标 {target} 字；路线不能规划到项目之外"
                )
                break

    contract = output.get("longform_contract")
    if target >= 500_000:
        if not isinstance(contract, dict):
            defects.append("必须提供结构化 longform_contract，统一管理目标字数、卷账和路线里程碑")
        else:
            contract_target = _number(contract.get("target_words"))
            if contract_target != target:
                defects.append(
                    f"longform_contract.target_words 为 {contract_target}，必须等于项目目标 {target}"
                )
            volume_targets = contract.get("volume_word_targets")
            if not isinstance(volume_targets, list) or not volume_targets:
                defects.append("longform_contract.volume_word_targets 不能为空")
            else:
                parsed = [_number(value) for value in volume_targets]
                if any(value is None or value <= 0 for value in parsed):
                    defects.append("每卷必须有正整数 word_target")
                elif sum(parsed) != target:
                    defects.append(
                        f"各卷字数合计为 {sum(parsed)}，必须精确闭合到项目目标 {target}"
                    )
            milestones = contract.get("route_milestones")
            if not isinstance(milestones, list) or not milestones:
                defects.append("longform_contract.route_milestones 不能为空")
            else:
                ends = [_number(item.get("end_words")) for item in milestones if isinstance(item, dict)]
                if any(value is None or value > target for value in ends):
                    defects.append("路线里程碑不能超过项目目标总字数")
                if ends and ends[-1] != target:
                    defects.append("最后一个路线里程碑必须落在项目目标总字数")

    core_defects = validate_core_mechanic_contract(
        output.get("core_mechanic_contract"),
        required=_idea_requires_core_mechanic(idea),
    )
    defects.extend(core_defects)
    simulator_defects = validate_simulator_contract(
        output.get("simulator_contract"),
        required=_idea_requires_simulator(idea),
    )
    defects.extend(simulator_defects)

    required_sections = (
        ("黄金三章", "开局节奏"),
        ("能力边界", "代价和风险"),
        ("长篇路线", "阶段路线"),
        ("篇幅与内容配比", "篇幅账本"),
        ("人物关系", "角色关系"),
        ("持续校验", "校验清单"),
    )
    for labels in required_sections:
        if not any(label in bible for label in labels):
            defects.append(f"创作圣经缺少可执行章节：{'/'.join(labels)}")
    return defects


def validate_volume_plan_contract(
    output: dict[str, Any],
    *,
    target_words: int,
) -> list[str]:
    """Validate the second planning ledger before it can seed chapter outlines."""
    target = int(target_words or 0)
    if target <= 0:
        return []
    volumes = output.get("volumes") if isinstance(output, dict) else None
    if not isinstance(volumes, list) or not volumes:
        return ["分卷规划必须提供 volumes"]
    defects: list[str] = []
    declared_total = _number(output.get("total_word_target"))
    if declared_total is None:
        defects.append("分卷规划必须声明 total_word_target")
    elif declared_total != target:
        defects.append(
            f"分卷规划 total_word_target 为 {declared_total}，必须等于项目目标 {target}"
        )
    word_targets: list[int] = []
    previous_end = 0
    for index, volume in enumerate(volumes, start=1):
        if not isinstance(volume, dict):
            defects.append(f"第 {index} 卷不是对象")
            continue
        target_value = _number(
            volume.get("word_target", volume.get("target_words", volume.get("word_count_target")))
        )
        if target_value is None or target_value <= 0:
            defects.append(f"第 {index} 卷缺少正整数 word_target")
        else:
            word_targets.append(target_value)
        start = _number(volume.get("start_chapter"))
        end = _number(volume.get("end_chapter"))
        if start is None or end is None or end < start:
            defects.append(f"第 {index} 卷章节区间无效")
        elif index == 1 and start != 1:
            defects.append("第一卷必须从第 1 章开始")
        elif index > 1 and start != previous_end + 1:
            defects.append("各卷章节区间必须连续，不能有空档或重叠")
        if end is not None:
            previous_end = end
    total = sum(word_targets)
    if word_targets and total != target:
        defects.append(f"分卷字数合计为 {total}，必须精确等于项目目标 {target}")
    return defects
