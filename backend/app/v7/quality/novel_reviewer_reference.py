"""Bounded adapter for the user-provided ``novel-reviewer`` reference.

The reference is useful as an editorial vocabulary and a report taxonomy, but
it is not a second scoring engine.  This module therefore has two deliberately
small responsibilities:

* expose context-aware, deterministic candidate signals for the existing
  de-AI metrics; and
* project the canonical V7 result into a 12-facet editor view without creating
  another overall score or another provider call.

Candidate signals are advisory.  They must be validated against the submitted
text before an issue is shown and cannot independently block a chapter.
"""
from __future__ import annotations

import copy
import re
import threading
import time
from collections import Counter
from typing import Any, Iterable


NOVEL_REVIEWER_SOURCE_ID = "novel-reviewer-reference"
NOVEL_REVIEWER_SOURCE_VERSION = "1.1.0"
EDITORIAL_REVIEW_VIEW_SCHEMA_VERSION = "novel-reviewer-view-v1"
AI_FLAVOR_LEXICON_SETTING_KEY = "quality.ai_flavor_lexicon"
AI_FLAVOR_LEXICON_SCHEMA_VERSION = "ai-flavor-lexicon-v2"
_LEXICON_CACHE_TTL_SECONDS = 20.0
_LEXICON_CACHE: tuple[float, dict[str, Any], str] | None = None
_LEXICON_CACHE_LOCK = threading.RLock()


# These are intentionally observations rather than a banned-word list.  A
# phrase can be natural in a particular scene, character voice or genre.
_DEFAULT_CATEGORY_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": "classic_description",
        "label": "经典神态模板",
        "description": "反复用同一组眉眼、嘴角和目光动作替代具体反应。",
        "phrases": (
            "嘴角微扬", "嘴角勾起", "嘴角微微上扬", "眉头微皱", "眉头一挑",
            "眼神一凝", "眼中闪过", "眼底闪过", "眸光一闪", "目光一沉",
            "神色微变", "脸色微变", "心中一震", "心头一震", "心中一动",
            "心头一紧", "呼吸一滞", "身形一顿", "身形一闪",
        ),
    },
    {
        "key": "body_tic",
        "label": "重复动作口癖",
        "description": "单一微动作在多段落反复出现，挤占人物的真实选择和场景后果。",
        "phrases": (
            "笑了笑", "点了点头", "深吸一口气", "不由得", "不禁", "下意识地",
            "本能地", "不由自主地", "没有说话", "沉默了片刻", "抿了抿嘴",
            "揉了揉眉心", "捏了捏拳", "喉结滚动", "指节发白", "手指轻敲",
            "缓缓吐出一口气", "轻轻摇头", "轻轻点头",
        ),
    },
    {
        "key": "filler",
        "label": "填充与模糊表达",
        "description": "本身不一定错误，但连续密集时会让文字变软、变空。",
        "phrases": (
            "似乎", "仿佛", "好像", "宛若", "莫名", "隐隐", "一股", "一丝",
            "片刻后", "一时间", "顿时", "随即", "旋即", "当即", "缓缓", "轻轻",
            "默默", "悄然", "不知不觉", "某种程度上", "从某种意义上",
        ),
    },
    {
        "key": "transition",
        "label": "机械转场词",
        "description": "转场词集中重复，容易形成每段同拍的推进感。",
        "phrases": (
            "就在这时", "突然", "猛地", "正要", "恰在此时", "话音未落",
            "就在此刻", "下一刻", "紧接着", "与此同时", "转眼间", "随后",
            "很快", "就在这之后", "就在这一刻", "说时迟那时快",
        ),
    },
    {
        "key": "summary_lecture",
        "label": "总结说教腔",
        "description": "把已经写出的动作和因果重新总结成作者讲解。",
        "phrases": (
            "值得一提的是", "综上所述", "总而言之", "不得不说", "显而易见",
            "由此可见", "不难看出", "毋庸置疑", "不言而喻", "换句话说",
            "简单来说", "归根结底", "这意味着", "也就是说", "从根本上",
            "可以说", "事实上", "众所周知", "毫无疑问",
        ),
    },
    {
        "key": "cliche_metaphor",
        "label": "空泛比喻与套景",
        "description": "宏大但不可验证的比喻反复出现，替代了人物动作、物件和具体后果。",
        "phrases": (
            "命运的齿轮", "故事才刚刚开始", "新的篇章", "一场腥风血雨",
            "空气仿佛凝固", "时间仿佛停止", "像一柄出鞘的利剑", "宛如天神下凡",
            "仿佛来自地狱", "毁天灭地的气势", "一股无形的压力", "某种不可名状的",
            "充满了未知", "迎来了新的挑战", "踏上了新的征程",
        ),
    },
    {
        "key": "mechanical_reaction",
        "label": "群像反应模板",
        "description": "用统一的惊讶、寂静和目光描写替代不同人物的利益、态度或行动。",
        "phrases": (
            "众人皆惊", "在场众人", "全场一片哗然", "空气中弥漫着", "气氛顿时",
            "场面一片寂静", "所有人都", "众人纷纷", "周围陷入沉默", "一道道目光",
            "无数道目光", "让人不寒而栗", "令人心悸", "全场鸦雀无声",
        ),
    },
    {
        "key": "direct_emotion",
        "label": "直接情绪标签",
        "description": "直接宣布人物情绪，缺少触发它的动作、记忆、利益或身体反应。",
        "phrases": (
            "他感到", "她感到", "内心深处", "心中充满了", "心底涌起",
            "情绪复杂", "心情沉重", "感到一阵", "不知为何", "说不清是什么滋味",
            "内心十分", "心里充满了",
        ),
    },
    {
        "key": "dialogue_template",
        "label": "套路对白模板",
        "description": "角色对话高度依赖固定挑衅、反问和揭底句式。",
        "phrases": (
            "你以为这样就结束了吗", "我倒要看看", "这不可能", "怎么会这样",
            "没想到吧", "看来是我小看你了", "你究竟是什么人", "这就是你的底牌",
            "你还要继续吗", "现在知道后悔了吧", "给我一个解释",
        ),
    },
    {
        "key": "ending_scaffold",
        "label": "章尾脚手架",
        "description": "用固定的‘更大危机/故事开始’收尾，替代具体发现、选择或新压力。",
        "phrases": (
            "而这一切只是开始", "真正的考验才刚刚开始", "更大的危机还在后面",
            "这一夜注定不平静", "没人知道的是", "至于后来", "一切尽在掌握",
            "新的危机正在逼近", "命运将会如何",
        ),
    },
    {
        "key": "system_terms",
        "label": "系统/面板术语",
        "description": "系统流、模拟器等题材的正常词汇；只有脱离题材或机械重复时才复核。",
        "phrases": (
            "系统", "面板", "弹窗", "【叮】", "叮！", "金光提示", "提示音",
            "系统提示", "系统面板", "任务完成", "奖励发放", "宿主", "虚拟面板",
            "模拟结束", "未来画面", "人生模拟器",
        ),
    },
)

_SYSTEM_PHRASES: tuple[str, ...] = tuple(
    phrase
    for spec in _DEFAULT_CATEGORY_SPECS
    if spec["key"] == "system_terms"
    for phrase in spec["phrases"]
)

_SYSTEM_CONTEXT_TOKENS: tuple[str, ...] = (
    "系统",
    "系统流",
    "模拟器",
    "人生模拟",
    "未来推演",
    "面板",
    "签到",
    "金手指",
    "simulator",
    "system",
)


def novel_reviewer_reference_metadata() -> dict[str, Any]:
    """Return provenance for the absorbed reference, not a quality score."""
    return {
        "source_id": NOVEL_REVIEWER_SOURCE_ID,
        "version": NOVEL_REVIEWER_SOURCE_VERSION,
        "role": "candidate_signals_and_editorial_view",
        "hard_gate": False,
        "scoring_authority": "v7.review.33_dimension",
        "lexicon_setting_key": AI_FLAVOR_LEXICON_SETTING_KEY,
        "lexicon_schema_version": AI_FLAVOR_LEXICON_SCHEMA_VERSION,
    }


def _normalise_phrase_item(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        phrase, enabled, note = value, True, ""
    elif isinstance(value, dict):
        phrase = value.get("phrase")
        enabled = bool(value.get("enabled", True))
        note = str(value.get("note") or "").strip()[:240]
    else:
        return None
    phrase = re.sub(r"\s+", "", str(phrase or "").strip())[:80]
    if not phrase or not re.search(r"[\u3400-\u9fffA-Za-z]", phrase):
        return None
    return {"phrase": phrase, "enabled": enabled, "note": note}


def default_ai_flavor_lexicon() -> dict[str, Any]:
    """Return a copy of the versioned built-in vocabulary for the UI/API."""
    return {
        "schema_version": AI_FLAVOR_LEXICON_SCHEMA_VERSION,
        "version": 2,
        "mode": "advisory",
        "hard_gate": False,
        "categories": [
            {
                "key": str(spec["key"]),
                "label": str(spec["label"]),
                "description": str(spec["description"]),
                "enabled": True,
                "phrases": [
                    {"phrase": phrase, "enabled": True, "note": ""}
                    for phrase in spec["phrases"]
                ],
            }
            for spec in _DEFAULT_CATEGORY_SPECS
        ],
    }


def normalize_ai_flavor_lexicon(value: Any) -> dict[str, Any]:
    """Validate/normalize editable lexicon data without turning it into bans."""
    defaults = default_ai_flavor_lexicon()
    raw_categories = value.get("categories") if isinstance(value, dict) else None
    submitted: dict[str, dict[str, Any]] = {}
    if isinstance(raw_categories, dict):
        raw_categories = [dict(item, key=key) if isinstance(item, dict) else {"key": key, "phrases": item}
                          for key, item in raw_categories.items()]
    if isinstance(raw_categories, list):
        for item in raw_categories[:32]:
            if not isinstance(item, dict):
                continue
            key = re.sub(r"[^a-zA-Z0-9_\-]", "", str(item.get("key") or ""))[:64]
            if key:
                submitted[key] = item

    categories: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for default in defaults["categories"]:
        current = submitted.get(default["key"], {})
        raw_phrases = current.get("phrases") if isinstance(current, dict) else None
        phrases: list[dict[str, Any]] = []
        if isinstance(raw_phrases, dict):
            raw_phrases = [dict(item, phrase=phrase) if isinstance(item, dict) else {"phrase": phrase, "enabled": bool(item)}
                           for phrase, item in raw_phrases.items()]
        if isinstance(raw_phrases, list):
            for item in raw_phrases[:160]:
                normalised = _normalise_phrase_item(item)
                if normalised and normalised["phrase"] not in {row["phrase"] for row in phrases}:
                    phrases.append(normalised)
        if not phrases:
            phrases = copy.deepcopy(default["phrases"])
        categories.append({
            "key": default["key"],
            "label": str(current.get("label") or default["label"])[:80],
            "description": str(current.get("description") or default["description"])[:240],
            "enabled": bool(current.get("enabled", True)),
            "phrases": phrases,
        })
        seen_keys.add(default["key"])

    # Preserve user-created categories so the editor is extensible without a
    # code release. They remain advisory and are never a hard quality gate.
    for key, current in submitted.items():
        if key in seen_keys or not isinstance(current, dict):
            continue
        raw_phrases = current.get("phrases") if isinstance(current.get("phrases"), list) else []
        phrases = []
        for item in raw_phrases[:160]:
            normalised = _normalise_phrase_item(item)
            if normalised and normalised["phrase"] not in {row["phrase"] for row in phrases}:
                phrases.append(normalised)
        if phrases:
            categories.append({
                "key": key,
                "label": str(current.get("label") or key)[:80],
                "description": str(current.get("description") or "自定义 AI 味候选信号")[:240],
                "enabled": bool(current.get("enabled", True)),
                "phrases": phrases,
            })

    return {
        "schema_version": AI_FLAVOR_LEXICON_SCHEMA_VERSION,
        "version": int(value.get("version") or 2) if isinstance(value, dict) else 2,
        "mode": "advisory",
        "hard_gate": False,
        "categories": categories,
    }


def _cache_lexicon(value: dict[str, Any], source: str) -> dict[str, Any]:
    global _LEXICON_CACHE
    normalised = normalize_ai_flavor_lexicon(value)
    with _LEXICON_CACHE_LOCK:
        _LEXICON_CACHE = (time.monotonic(), copy.deepcopy(normalised), source)
    return normalised


def invalidate_ai_flavor_lexicon_cache() -> None:
    global _LEXICON_CACHE
    with _LEXICON_CACHE_LOCK:
        _LEXICON_CACHE = None


def load_ai_flavor_lexicon(*, force: bool = False) -> dict[str, Any]:
    """Load the editable global lexicon with a short process-local cache."""
    now = time.monotonic()
    with _LEXICON_CACHE_LOCK:
        if _LEXICON_CACHE and not force and now - _LEXICON_CACHE[0] < _LEXICON_CACHE_TTL_SECONDS:
            result = copy.deepcopy(_LEXICON_CACHE[1])
            result["source"] = _LEXICON_CACHE[2]
            return result
    payload: Any = None
    source = "builtin"
    try:
        from ...db import connect, decode
        db = connect()
        try:
            row = db.execute(
                "SELECT value FROM settings WHERE key = %s",
                (AI_FLAVOR_LEXICON_SETTING_KEY,),
            ).fetchone()
            payload = decode(row.get("value"), None) if row else None
        finally:
            db.close()
        if payload:
            source = "database"
    except Exception:
        # Quality analysis must remain available when a local test process has
        # no database. Production configuration is still read when available.
        payload = None
    result = _cache_lexicon(payload or default_ai_flavor_lexicon(), source)
    result["source"] = source
    return result


def store_ai_flavor_lexicon(value: Any) -> dict[str, Any]:
    """Persist a validated lexicon; the caller owns authorization/transaction."""
    result = _cache_lexicon(normalize_ai_flavor_lexicon(value), "database")
    result["source"] = "database"
    return result


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _profile_context(profile: dict[str, Any] | None) -> str:
    profile = profile if isinstance(profile, dict) else {}
    keys = (
        "genre",
        "subgenre",
        "style_plugin",
        "style",
        "mechanic",
        "golden_finger",
        "golden_finger_type",
        "theme",
    )
    return _compact(" ".join(str(profile.get(key) or "") for key in keys)).lower()


def _is_system_context(profile: dict[str, Any] | None) -> bool:
    context = _profile_context(profile)
    return any(token.lower() in context for token in _SYSTEM_CONTEXT_TOKENS)


def _evidence(text: str, phrase: str, *, limit: int = 3) -> list[dict[str, Any]]:
    """Return bounded, line-addressable evidence for a candidate signal."""
    result: list[dict[str, Any]] = []
    for match in re.finditer(re.escape(phrase), text):
        start = match.start()
        line = text.count("\n", 0, start) + 1
        left = max(0, start - 18)
        right = min(len(text), match.end() + 24)
        excerpt = re.sub(r"\s+", " ", text[left:right]).strip()
        result.append({"phrase": phrase, "line": line, "excerpt": excerpt})
        if len(result) >= limit:
            break
    return result


def _category(
    text: str,
    phrases: Iterable[str],
    *,
    size: int,
    active: bool = True,
    suppressed_reason: str = "",
) -> dict[str, Any]:
    hits: Counter[str] = Counter()
    evidence: list[dict[str, Any]] = []
    for phrase in phrases:
        count = text.count(phrase)
        if count:
            hits[phrase] = count
            evidence.extend(_evidence(text, phrase))
    evidence.sort(key=lambda item: (int(item.get("line") or 0), str(item.get("phrase") or "")))
    total = sum(hits.values())
    return {
        "active": active,
        "hit_count": total,
        "density_per_1000": round(total / max(size, 1) * 1000, 3),
        "phrases": dict(hits),
        "evidence": evidence[:8],
        "suppressed_reason": suppressed_reason,
    }


def analyze_novel_reviewer_lexicon(
    text: str,
    *,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect advisory lexicon signals with genre-aware exceptions.

    The returned ``candidate_risks`` are intentionally not folded into the
    canonical de-AI ``risk_score``.  They are passed to the same V7 reviewer,
    which must still provide a verified excerpt before showing an issue.
    """
    text = str(text or "")
    compact_size = len(re.sub(r"\s+", "", text))
    system_context = _is_system_context(profile)
    lexicon = (
        profile.get("ai_flavor_lexicon")
        if isinstance(profile, dict) and isinstance(profile.get("ai_flavor_lexicon"), dict)
        else load_ai_flavor_lexicon()
    )
    lexicon_source = lexicon.get("source") if isinstance(lexicon, dict) else None
    lexicon = normalize_ai_flavor_lexicon(lexicon)
    categories: dict[str, dict[str, Any]] = {}
    for definition in lexicon["categories"]:
        key = str(definition.get("key") or "custom")
        phrases = [
            str(item.get("phrase"))
            for item in definition.get("phrases") or []
            if isinstance(item, dict) and item.get("enabled", True) and str(item.get("phrase") or "").strip()
        ]
        is_system_terms = key == "system_terms"
        active = bool(definition.get("enabled", True)) and not (is_system_terms and system_context)
        suppressed_reason = ""
        if is_system_terms:
            suppressed_reason = (
                "当前题材/金手指包含系统、模拟器或面板语境，系统词按题材表达保留，不作为 AI 味风险。"
                if system_context
                else "系统词仅作为题材信号，需结合正文模板化程度判断。"
            )
        categories[key] = _category(
            text,
            phrases,
            size=compact_size,
            active=active,
            suppressed_reason=suppressed_reason,
        )

    candidates: list[dict[str, Any]] = []
    classic = categories.get("classic_description") or {}
    if classic.get("active") and classic.get("hit_count", 0) >= 3:
        candidates.append({
            "code": "classic_description_stacking",
            "category": "classic_description",
            "severity": "low",
            "count": classic["hit_count"],
            "reason": "经典神态/心理短语出现堆叠，需要结合人物反应和场景后果复核。",
        })
    filler = categories.get("filler") or {}
    if filler.get("active") and filler.get("density_per_1000", 0) > 1.5:
        candidates.append({
            "code": "filler_density_candidate",
            "category": "filler",
            "severity": "low",
            "density_per_1000": filler["density_per_1000"],
            "reason": "填充性表达密度偏高，只能作为复核线索，不能单凭词语判定 AI 腔。",
        })
    transition = categories.get("transition") or {}
    repeated_transition = max(transition.get("phrases", {}).values(), default=0)
    if transition.get("active") and (transition.get("hit_count", 0) >= 5 or repeated_transition >= 3):
        candidates.append({
            "code": "transition_stacking_candidate",
            "category": "transition",
            "severity": "low",
            "count": transition["hit_count"],
            "reason": "转场词出现集中，需检查是否形成同构节拍。",
        })

    candidate_rules = (
        ("summary_lecture", "summary_lecture_stacking", 2, "总结/说教表达出现堆叠，需检查是否遮蔽了动作和因果。"),
        ("cliche_metaphor", "cliche_metaphor_stacking", 2, "空泛比喻集中出现，需换成可观察的动作、物件或后果。"),
        ("mechanical_reaction", "mechanical_reaction_stacking", 3, "群像反应模板重复，需让不同角色给出不同利益或行动反馈。"),
        ("direct_emotion", "direct_emotion_labeling", 3, "直接情绪标签偏多，需用人物选择、身体反应或细节承载情绪。"),
        ("dialogue_template", "dialogue_template_stacking", 3, "对白模板集中出现，需检查角色是否拥有具体目的和潜台词。"),
        ("ending_scaffold", "ending_scaffold_repetition", 2, "章尾脚手架重复，需把钩子落到具体发现、选择或新压力。"),
    )
    for category_key, code, minimum, reason in candidate_rules:
        category = categories.get(category_key) or {}
        if category.get("active") and category.get("hit_count", 0) >= minimum:
            candidates.append({
                "code": code,
                "category": category_key,
                "severity": "low",
                "count": category.get("hit_count", 0),
                "reason": reason,
            })
    system_terms = categories.get("system_terms") or {}
    if system_terms.get("active") and system_terms.get("hit_count", 0) >= 3:
        candidates.append({
            "code": "system_term_template_candidate",
            "category": "system_terms",
            "severity": "low",
            "count": system_terms.get("hit_count", 0),
            "reason": "系统/面板术语脱离明确题材语境或重复成固定模板，需结合正文复核。",
        })

    return {
        "schema_version": AI_FLAVOR_LEXICON_SCHEMA_VERSION,
        "reference": novel_reviewer_reference_metadata(),
        "mode": "candidate_only",
        "hard_gate": False,
        "system_context": system_context,
        "configuration": {
            "source": lexicon_source or lexicon.get("source") or "profile_or_builtin",
            "version": lexicon.get("version", 2),
            "category_count": len(lexicon.get("categories") or []),
            "active_phrase_count": sum(
                1
                for category in lexicon.get("categories") or []
                if category.get("enabled", True)
                for item in category.get("phrases") or []
                if item.get("enabled", True)
            ),
        },
        "categories": categories,
        "candidate_risks": candidates,
        "rule": "单个词、单个标点或题材正常术语不构成问题；必须结合密度、重复、语境和正文证据。词库只产生候选信号，不直接改变 V7 总分或质量门。",
    }


def render_ai_flavor_guidance(
    profile: dict[str, Any] | None = None,
    *,
    max_samples_per_category: int = 3,
) -> str:
    """Render compact pre-generation guidance from the editable lexicon."""
    lexicon = (
        profile.get("ai_flavor_lexicon")
        if isinstance(profile, dict) and isinstance(profile.get("ai_flavor_lexicon"), dict)
        else load_ai_flavor_lexicon()
    )
    lexicon = normalize_ai_flavor_lexicon(lexicon)
    system_context = _is_system_context(profile)
    rows: list[str] = []
    for category in lexicon.get("categories") or []:
        key = str(category.get("key") or "")
        if not category.get("enabled", True) or (key == "system_terms" and system_context):
            continue
        samples = [
            str(item.get("phrase"))
            for item in category.get("phrases") or []
            if item.get("enabled", True) and str(item.get("phrase") or "").strip()
        ][:max_samples_per_category]
        if samples:
            rows.append(f"- {category.get('label') or key}：{'、'.join(samples)}")
    return (
        "词库是 AI 味候选观察表，不是禁词表。不要为了躲避单个词而换成同义套话；"
        "只有同类表达在整章集中重复、替代了动作/选择/后果时才改写。系统流、模拟器、"
        "面板等题材术语按题材语境保留。优先把模板表达换成具体人物反应、物件细节、"
        "利益变化或新的压力。\n" + "\n".join(rows)
    )


_EDITORIAL_FACETS: tuple[dict[str, Any], ...] = (
    {"key": "logic", "label": "剧情逻辑", "audit": ("causality", "choice_consequence", "plot_progress", "logic_exposition"), "macro": ("plot_logic",)},
    {"key": "canon", "label": "设定自洽", "audit": ("world_rules", "ability_system", "terminology", "resource_ledger"), "macro": ("consistency",)},
    {"key": "lint", "label": "连续性检查", "audit": ("timeline", "space_location", "foreshadowing_state", "knowledge_boundary"), "continuity": True},
    {"key": "fact", "label": "事实核对", "audit": ("world_rules", "timeline", "resource_ledger"), "macro": ("consistency",)},
    {"key": "character", "label": "人物塑造", "audit": ("motivation_consistency", "character_arc_progress", "behavior_credibility", "relationship_change"), "macro": ("character_voice",)},
    {"key": "consistency", "label": "人设一致", "audit": ("personality_consistency", "capability_consistency", "knowledge_boundary", "character_voice"), "macro": ("character_voice", "consistency")},
    {"key": "pace", "label": "节奏张力", "audit": ("sentence_rhythm", "stakes", "plot_progress"), "macro": ("pacing",)},
    {"key": "hook_density", "label": "爽感密度", "audit": ("payoff", "ending_hook", "emotion_shift"), "reader": ("payoff",)},
    {"key": "retention", "label": "追读引力", "audit": ("ending_hook", "continuation_intent", "expectation"), "reader": ("worth_continuing", "expectation")},
    {"key": "bridge", "label": "叙事衔接", "audit": ("causality", "space_location", "ending_hook"), "continuity": True},
    {"key": "prose", "label": "文笔风貌", "audit": ("sentence_rhythm", "character_voice"), "macro": ("writing_quality",)},
    {"key": "ai_flavor", "label": "AI味风险", "deai": True},
)


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(max(0.0, min(100.0, float(value))), 1)
    return None


def _mean(values: Iterable[Any]) -> float | None:
    numbers = [number for value in values if (number := _number(value)) is not None]
    return round(sum(numbers) / len(numbers), 1) if numbers else None


def _audit_items(review: dict[str, Any]) -> dict[str, dict[str, Any]]:
    report = review.get("audit_report") if isinstance(review.get("audit_report"), dict) else {}
    items = report.get("items") if isinstance(report.get("items"), dict) else {}
    return {key: value for key, value in items.items() if isinstance(value, dict)}


def _facet_evidence(
    items: dict[str, dict[str, Any]],
    keys: Iterable[str],
) -> tuple[list[str], list[str], list[str]]:
    evidence: list[str] = []
    repairs: list[str] = []
    sources: list[str] = []
    for key in keys:
        item = items.get(key) or {}
        if item.get("evidence"):
            evidence.append(f"{item.get('label') or key}：{item['evidence']}")
        if item.get("repair"):
            repairs.append(f"{item.get('label') or key}：{item['repair']}")
        if item.get("source"):
            sources.append(str(item["source"]))
    return evidence[:3], repairs[:3], sorted(set(sources))


def build_editorial_review_view(review: dict[str, Any] | None) -> dict[str, Any]:
    """Build the 12-facet editor view from an existing V7 review result.

    This function never calls a model and never computes a new overall score.
    Missing facts remain ``not_scored`` instead of being filled with a guess.
    """
    review = review if isinstance(review, dict) else {}
    items = _audit_items(review)
    macro = review.get("dimension_scores") if isinstance(review.get("dimension_scores"), dict) else {}
    reader = review.get("reader_experience") if isinstance(review.get("reader_experience"), dict) else {}
    continuity = review.get("continuity") if isinstance(review.get("continuity"), dict) else {}
    deai = review.get("deai_metrics") if isinstance(review.get("deai_metrics"), dict) else {}
    facets: list[dict[str, Any]] = []

    for definition in _EDITORIAL_FACETS:
        key = str(definition["key"])
        audit_keys = tuple(definition.get("audit") or ())
        evidence, repairs, sources = _facet_evidence(items, audit_keys)
        scores = [items[item].get("score") for item in audit_keys if item in items]
        score = _mean(scores)
        source = "v7.audit_33" if score is not None else ""
        status = "scored" if score is not None else "not_scored"

        if score is None:
            score = _mean(macro.get(item) for item in definition.get("macro") or ())
            if score is not None:
                source = "v7.macro_review"
                status = "macro_fallback"
        reader_score = _mean(reader.get(item) for item in definition.get("reader") or ())
        if reader_score is not None:
            score = reader_score if score is None else round((score + reader_score) / 2, 1)
            source = "v7.audit_33+reader_experience" if source else "v7.reader_experience"
            status = "scored"

        raw_metrics: dict[str, Any] = {}
        if definition.get("continuity"):
            continuity_score = _number(continuity.get("model_score"))
            if continuity_score is not None:
                score = continuity_score
                source = "v7.continuity"
                status = "scored"
            elif continuity.get("checked") is True:
                source = "v7.continuity"
                status = "evidence_only"
                raw_metrics = {"status": continuity.get("status"), "checked": True}

        if definition.get("deai"):
            risk = _number(deai.get("risk_score"))
            if risk is not None:
                score = round(100.0 - risk, 1)
                source = "v7.deai_metrics"
                status = "scored"
                raw_metrics = {"risk_score": risk, "flags": deai.get("flags") or []}
            else:
                source = "v7.deai_metrics"
                status = "not_scored"

        facets.append({
            "key": key,
            "label": definition["label"],
            "score": score,
            "status": status,
            "direction": "higher_is_better",
            "source": source or "unknown",
            "source_dimensions": list(audit_keys),
            "evidence": evidence,
            "repairs": repairs,
            "raw_metrics": raw_metrics,
            "source_detail": sorted(set(sources)),
        })

    return {
        "schema_version": EDITORIAL_REVIEW_VIEW_SCHEMA_VERSION,
        "reference": novel_reviewer_reference_metadata(),
        "facets": facets,
        "scoring_note": "编辑视图不重新计算总分；产品唯一总分仍为 V7 review.overall_score。",
        "overall_score_source": "v7.review.33_dimension",
    }
