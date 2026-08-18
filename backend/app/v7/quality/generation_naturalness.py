"""Generation-time readability checks for Chinese web-fiction prose.

These checks are deliberately narrow.  They do not try to estimate an
external detector score or force a house style; they catch high-confidence
signals that make a scene read like an explanation of a story instead of the
story happening on the page.  The generation engine uses the result as retry
feedback before accepting a scene.
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
    ("turn_back_loop", r"(?:转身|回头|退后|走开).{0,80}(?:转身|回头|退后|走开)"),
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
    # A necessary image is fine.  Repeated similes in a short scene are the
    # stronger signal, especially when the surrounding prose is explanatory.
    if size >= 500 and len(similes) >= 2:
        flags.append({
            "code": "scene_metaphor_density",
            "severity": "medium",
            "message": "非对白比喻/类比过密；保留最必要的一处，其余改成可观察的动作、物件或结果",
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
