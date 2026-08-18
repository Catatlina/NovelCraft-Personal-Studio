"""Generation-time readability checks for Chinese web-fiction prose.

These checks are deliberately narrow.  They do not try to estimate an
external detector score or force a house style; they catch high-confidence
signals that make a scene read like an explanation of a story instead of the
story happening on the page.  The generation engine uses the result as retry
feedback before accepting a scene.

The prompt protocol in this module is intentionally short.  A long list of
style prohibitions competes with the scene facts and often makes a Provider
produce the very template we are trying to avoid.  The protocol therefore
gives the writer one concrete delivery path, a small positive example of
information landing on the page, and a strict preflight baseline.
"""
from __future__ import annotations

import re
from typing import Any


_DIALOGUE_RE = re.compile(r"[“「『\"].*?[”」』\"]", re.S)
_EXPLANATION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("explicit_conclusion", r"真正的(?:问题|原因|答案)|也就是说|换句话说|这意味着|这说明"),
    ("mind_conclusion", r"(?:他|她|人物)(?:终于)?(?:明白|意识到|知道自己|心里清楚)"),
    ("denial_conclusion", r"(?:不是|并非)(?:梦|错觉|眼花|巧合)"),
    ("summary_conclusion", r"(?:现在|直到这时|这一刻)(?:他|她|人物)?(?:才)?(?:知道|明白|意识到).{0,18}(?:错|真相|原因)"),
)
_SIMILE_RE = re.compile(
    r"(?:好像|仿佛|如同|宛如|犹如|像)[^。！？!?\n，,]{0,18}"
)
_REPEATED_ACTION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("put_back_loop", r"(?:放回|放下|靠回|重新握起|重新拿起|收回).{0,80}(?:放回|放下|靠回|重新握起|重新拿起|收回)"),
)

GENERATION_STYLE_PROTOCOL_VERSION = "generation-style-protocol-v2"

_GENERATION_PATHS: dict[str, dict[str, str]] = {
    "event_action_dialogue": {
        "label": "动作与对白推进",
        "instruction": (
            "先让一个正在发生的动作改变现场，再让人物用不完整的对白或声音回应；"
            "对话之后必须出现一个可见物件变化、位置变化或新的选择。"
        ),
    },
    "object_consequence": {
        "label": "物件与后果推进",
        "instruction": (
            "先写一个具体物件、痕迹或声音发生变化，让人物试探或处理它；"
            "不要解释异常的意义，直接写处理动作带来的新限制或新压力。"
        ),
    },
    "plain_factual": {
        "label": "朴素现场推进",
        "instruction": (
            "只用准确的动作、位置、触感、对白和结果推进现场；"
            "把情绪藏在人物做了什么、没做什么以及说到一半停在哪里。"
        ),
    },
}


def select_generation_style_path(
    chapter_number: int,
    scene_index: int,
    attempt: int,
) -> str:
    """Select a deliberate prose route for an independent scene candidate.

    The first candidate follows the chapter/scene rotation.  Repairs use
    different routes rather than asking the Provider to keep polishing the
    same sentence pattern.  This is generation-time diversification, not an
    invitation to change plot facts.
    """
    if attempt == 1:
        return "event_action_dialogue"
    if attempt >= 2:
        return "plain_factual"
    names = tuple(_GENERATION_PATHS)
    return names[max(0, int(chapter_number) + int(scene_index) - 2) % len(names)]


def render_generation_style_protocol(path: str = "event_action_dialogue") -> str:
    """Render the compact writer protocol placed at the end of the prompt."""
    selected = _GENERATION_PATHS.get(path) or _GENERATION_PATHS["event_action_dialogue"]
    return (
        f"【出稿前正文协议 {GENERATION_STYLE_PROTOCOL_VERSION}】\n"
        f"本轮写法：{selected['label']}。{selected['instruction']}\n"
        "硬基线：非对白比喻为 0；旁白解释性总结为 0；不要用‘像、仿佛、如同、宛如、犹如’"
        "替代具体动作；不要用‘他明白了/他意识到/真正的问题/这意味着’替读者宣布结论。\n"
        "每个自然段只承担一个现场落点：动作、对白、物件变化、人物反应或结果，"
        "不要求每段都完整解释因果；段落长短随现场变化，不要把所有段落写成同样长度。\n"
        "只学习下面示例的信息落地方式，不复制词句：\n"
        "门栓先动了一下。苏长庚把手收回来，侧身挡住楼梯口。\n"
        "‘谁在里面？’\n"
        "门后没有回答，门缝下却漫出一线水。纸包的边角湿了，里面露出黑色的一截。\n"
        "他没有再推门，把纸包交给身后的人：‘拿稳。’\n"
        "出稿前只在内部检查：删掉非对白比喻和替读者下结论的句子；确认至少有一次具体选择改变现场；"
        "不要输出检查过程、规则、标题或说明。"
    )


def _remove_dialogue(text: str) -> str:
    return _DIALOGUE_RE.sub(" ", str(text or ""))


def inspect_generation_naturalness(text: Any) -> dict[str, Any]:
    """Return high-confidence prose risks for a single generation attempt."""
    source = str(text or "").strip()
    narrative = _remove_dialogue(source)
    compact = re.sub(r"\s+", "", narrative)
    size = len(compact)
    flags: list[dict[str, Any]] = []
    explanation_hits: list[dict[str, str]] = []
    for label, pattern in _EXPLANATION_PATTERNS:
        for match in re.finditer(pattern, narrative):
            explanation_hits.append({"kind": label, "evidence": match.group(0)[:60]})
    if explanation_hits:
        flags.append({
            "code": "scene_explanatory_narration",
            "severity": "high",
            "message": "旁白替读者下结论或解释人物已经知道的意义；改用具体动作、物件后果或未完成的念头",
            "evidence": explanation_hits[:4],
        })

    similes = [match.group(0)[:60] for match in _SIMILE_RE.finditer(narrative)]
    # The current generation baseline deliberately starts at zero non-dialogue
    # similes.  This is stricter than a general prose review because the real
    # Provider sample repeatedly emitted image chains even after being told to
    # keep them sparse.  A single image is therefore enough to trigger a
    # generation-time independent candidate; it is never rewritten after the
    # chapter is accepted.
    if size >= 500 and len(similes) >= 1:
        flags.append({
            "code": "scene_metaphor_density",
            "severity": "medium",
            "message": "非对白出现比喻；本轮基线为零比喻，改成可观察的动作、物件或结果",
            "evidence": {"count": len(similes), "examples": similes[:4], "narrative_chars": size},
        })

    repeated_actions: list[dict[str, str]] = []
    for label, pattern in _REPEATED_ACTION_PATTERNS:
        match = re.search(pattern, narrative)
        if match:
            repeated_actions.append({"kind": label, "evidence": match.group(0)[:100]})
    if repeated_actions:
        flags.append({
            "code": "scene_repeated_action_loop",
            "severity": "medium",
            "message": "同一物件或回身动作在短场景内重复，容易形成机械回环；保留一次，另一处改成新的选择或后果",
            "evidence": repeated_actions,
        })

    return {
        "schema_version": "generation-naturalness-v1",
        "passed": not flags,
        "narrative_chars": size,
        "explanation_count": len(explanation_hits),
        "metaphor_count": len(similes),
        "repeated_action_count": len(repeated_actions),
        "flags": flags,
    }
