"""V3 Prompt Compiler (§6.4) — assemble the Writer's final directive.

Pure, deterministic logic. No LLM calls here. Combines the existing layers
(system/platform/genre rules, 7-layer context, Novel DNA) with the new
strategy library and chapter_function, producing a directive string that is
injected into the Writer prompt.

Graceful degradation: when the strategy library has no match for the current
chapter, `compile_strategy_directive` returns "" and `compile_prompt` returns
the base prompt unchanged — generation is never blocked by a missing strategy.
"""

from __future__ import annotations

from typing import Any


_GOLDEN_THREE_MAX_SEQ = 3
_FACE_SLAP_FUNCS = {"爽点", "冲突", "打脸"}
_REVERSAL_FUNC = "身份反转"
# Skill layer (§6.3): only the two that map to Writer's existing capabilities.
SKILL_GENERATE_CONFLICT = "generate_conflict"
SKILL_GENERATE_HOOK = "generate_hook"

# Map a matched strategy to the Writer skill hint it should trigger. Skills are
# NOT new model calls — they are reusable capability hints compiled into the
# prompt (e.g. "generate a face-slap conflict beat", "open with a hook").
_STRATEGY_SKILL_MAP = {
    "打脸策略": SKILL_GENERATE_CONFLICT,
    "黄金三章": SKILL_GENERATE_HOOK,
    "身份反转": SKILL_GENERATE_HOOK,
}


def skill_hints_for_strategies(strategies: Any) -> list[str]:
    """Return the Writer skill hints (human-readable Chinese) triggered by the
    matched strategies. Skills are reusable capability prompts, not new calls."""
    if not isinstance(strategies, list):
        return []
    labels: list[str] = []
    for s in strategies:
        if not isinstance(s, dict):
            continue
        sk = _STRATEGY_SKILL_MAP.get(s.get("name", ""))
        if sk:
            label = _SKILL_LABEL.get(sk, sk)
            if label not in labels:
                labels.append(label)
    return labels


_SKILL_LABEL = {
    SKILL_GENERATE_CONFLICT: "本章应设计一个清晰的冲突/打脸张力（压制 → 反转）",
    SKILL_GENERATE_HOOK: "本章开头用强钩子（立人设或抛悬念，留住读者）",
}


def select_strategies(strategies: Any, chapter_seq: int, function_type: str = "") -> list[dict]:
    """Pick the built-in strategies applicable to the current chapter.

    Rules are keyed off the seeded strategy names (MVP: 3-5 human-curated
    strategies, not a general matcher). Returns an ordered list.
    """
    if not isinstance(strategies, list):
        return []
    selected: list[dict] = []
    ft = (function_type or "").strip()
    for s in strategies:
        if not isinstance(s, dict):
            continue
        name = s.get("name", "")
        if name == "黄金三章" and chapter_seq and chapter_seq <= _GOLDEN_THREE_MAX_SEQ:
            selected.append(s)
        elif name == "打脸策略" and ft in _FACE_SLAP_FUNCS:
            selected.append(s)
        elif name == "身份反转" and (ft == _REVERSAL_FUNC or "反转" in ft):
            selected.append(s)
    return selected


def compile_strategy_directive(strategies: Any) -> str:
    """Flatten matched strategies into a Chinese directive block for the Writer."""
    if not isinstance(strategies, list) or not strategies:
        return ""
    blocks: list[str] = []
    for s in strategies:
        if not isinstance(s, dict):
            continue
        stages = s.get("stages") or []
        if isinstance(stages, list) and stages:
            stage_text = " → ".join(str(x) for x in stages)
            desc = str(s.get("description", "") or "")
            blocks.append(f"【{s.get('name', '')}】按节奏推进：{stage_text}。{desc}")
    return "\n".join(blocks)


# ═══════════════════════════════════════════════════════
# V3-P3-⑫: Prompt Compiler 通用引擎扩展

def render_template(template: str, variables: dict[str, str]) -> str:
    """安全替换模板中的 $variable 占位符。

    Prompt Compiler 模块内使用；委托 prompt_registry.render_prompt 做注入清洗。
    """
    from app.prompt_registry import render_prompt
    return render_prompt(template, variables)


def compile_generic_prompt(
    base_prompt: str,
    layers: dict[str, str] | None = None,
    priorities: dict[str, int] | None = None,
) -> str:
    """通用 Prompt 编译：将任意结构化层（layer→text）按优先级组装为最终 Prompt。

    layers:
        {"策略指引": "本章应含强钩子", "创作红线": "不碰历史虚无主义"}
    priorities:
        {"策略指引": 1, "创作红线": 3}  → 数字越小越优先（排前面）
        未指定的层默认为 999（低优先）
    Degrades gracefully: 无 layers 或全空则返回 base_prompt 不动。
    """
    if not layers:
        return base_prompt
    pri = dict(priorities) if priorities else {}

    def _label(layer: str) -> str:
        # 加【】包装但保留原有 raw key
        return f"【{layer}】" if not layer.startswith("【") else layer

    items: list[tuple[int, str]] = []
    for name, text in (layers or {}).items():
        content = text.strip() if isinstance(text, str) and text.strip() else ""
        if not content:
            continue
        p = pri.get(name, 999)
        items.append((p, f"{_label(name)}\n{content}"))
    if not items:
        return base_prompt
    items.sort(key=lambda x: x[0])
    return base_prompt.rstrip() + "\n\n" + "\n\n".join(i[1] for i in items)


def compile_prompt(
    base_prompt: str,
    *,
    strategy_directive: str = "",
    novel_dna: Any = None,
    chapter_function: Any = None,
    skill_hints: Any = None,
    extra_layers: dict[str, str] | None = None,
) -> str:
    """Assemble the final Writer directive（兼容旧签名 + 通用层扩展）。

    Degrades gracefully: any missing/enabled layer is simply omitted; if nothing
    is added the base prompt is returned untouched.
    """
    extras: list[str] = []
    if strategy_directive and strategy_directive.strip():
        extras.append("【本章策略指引】\n" + strategy_directive.strip())
    if isinstance(novel_dna, dict):
        fd = novel_dna.get("forbidden_deviations")
        if isinstance(fd, list) and fd:
            items = [str(x).strip() for x in fd if str(x).strip()]
            if items:
                extras.append("【创作红线】不得违背：" + "；".join(items))
    if isinstance(chapter_function, dict):
        goal = chapter_function.get("chapter_goal")
        exp = chapter_function.get("reader_expectation")
        parts = []
        if goal and str(goal).strip():
            parts.append(f"目标：{goal}")
        if exp and str(exp).strip():
            parts.append(f"读者期待：{exp}")
        if parts:
            extras.append("【本章功能】" + "；".join(parts) + "。")
    if isinstance(skill_hints, list):
        hints = [str(h).strip() for h in skill_hints if str(h).strip()]
        if hints:
            extras.append("【技巧提示】" + "；".join(hints))
    # ── V3-P3-⑫: 通用层扩展 ──
    if extra_layers:
        for name, text in extra_layers.items():
            content = text.strip() if isinstance(text, str) and text.strip() else ""
            if content:
                extras.append(f"【{name}】\n{content}")
    if not extras:
        return base_prompt
    return base_prompt.rstrip() + "\n\n" + "\n\n".join(extras)
