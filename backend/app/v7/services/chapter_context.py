"""chapter_context — v0.9.2 ChapterContext 五类上下文融合

融合关系（冻结规范）：
  现有 GenrePack
+ 现有 style_cards
+ CharacterVoiceCard（经人工确认的人物台词样本）
+ StoryState start/end 双快照
+ writing_workflow 因果契约
+ PlatformPublicationProfile
+ 现有 context_package
= 新 ChapterContext

关键状态超预算会直接停止，不再静默切掉。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class GenrePackContext:
    """品类包上下文。"""
    genre_id: str = ""
    genre_name: str = ""
    parent_genre: str = ""
    style_rules: dict[str, Any] = field(default_factory=dict)
    payoff_contract: dict[str, Any] = field(default_factory=dict)
    knowledge_items: list[dict[str, Any]] = field(default_factory=list)
    prompt_seeds: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StyleCardContext:
    """作者文风卡。"""
    style_id: str = ""
    style_name: str = ""
    tone: str = ""
    pace: str = ""
    opening_style: str = ""
    payoff_density: str = ""
    vocabulary_hints: list[str] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)
    sample_prose: str = ""


@dataclass
class CharacterVoiceCard:
    """人物台词样本卡（经人工确认）。"""
    character_id: str = ""
    character_name: str = ""
    role: str = ""
    speech_pattern: str = ""
    vocabulary: list[str] = field(default_factory=list)
    confirmed_samples: list[str] = field(default_factory=list)  # 人工确认的台词样本
    personality_traits: list[str] = field(default_factory=list)
    human_confirmed: bool = False


@dataclass
class StoryStateSnapshot:
    """故事状态快照（章首/章末双快照）。"""
    chapter_seq: int = 0
    character_states: dict[str, Any] = field(default_factory=dict)  # 人物位置/状态
    item_states: dict[str, Any] = field(default_factory=dict)       # 物品持有状态
    timeline_position: str = ""
    world_state: dict[str, Any] = field(default_factory=dict)
    unresolved_foreshadowings: list[dict[str, Any]] = field(default_factory=list)
    active_goals: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CausalContract:
    """写作工作流因果契约（五列因果账本）。"""
    core_question: str = ""
    visible_payoff: str = ""
    cost_or_sacrifice: str = ""
    next_pressure: str = ""
    causal_ledger: list[dict[str, Any]] = field(default_factory=list)  # 五列账本
    state_anchors: list[dict[str, Any]] = field(default_factory=list)
    workflow_state: str = ""  # 工作流状态机当前状态


@dataclass
class PlatformContext:
    """平台发布配置上下文。"""
    platform: str = ""
    profile_name: str = ""
    policy_status: str = "unknown"  # confirmed/stale/unknown
    policy_version: str = ""
    ai_usage_policy: str = "unknown"  # allowed/allowed_with_human_editing/required_disclosure/unknown/prohibited
    word_count_min: Optional[int] = None
    word_count_max: Optional[int] = None
    chapter_word_min: Optional[int] = None
    chapter_word_max: Optional[int] = None
    title_rules: dict[str, Any] = field(default_factory=dict)
    prohibited_content: list[str] = field(default_factory=list)


@dataclass
class BudgetState:
    """上下文预算状态（超预算直接停止）。"""
    total_tokens: int = 0
    max_tokens: int = 8000
    genre_tokens: int = 0
    style_tokens: int = 0
    character_tokens: int = 0
    state_tokens: int = 0
    causal_tokens: int = 0
    platform_tokens: int = 0
    existing_context_tokens: int = 0
    exceeded: bool = False
    exceeded_components: list[str] = field(default_factory=list)


@dataclass
class ChapterContext:
    """融合后的章节上下文（v0.9.2 单一真相源）。"""
    novel_id: str = ""
    chapter_id: str = ""
    chapter_seq: int = 0

    genre_pack: GenrePackContext = field(default_factory=GenrePackContext)
    style_card: StyleCardContext = field(default_factory=StyleCardContext)
    character_voices: list[CharacterVoiceCard] = field(default_factory=list)
    state_start: StoryStateSnapshot = field(default_factory=StoryStateSnapshot)  # 章首快照
    state_end: StoryStateSnapshot = field(default_factory=StoryStateSnapshot)    # 章末快照
    causal_contract: CausalContract = field(default_factory=CausalContract)
    platform: PlatformContext = field(default_factory=PlatformContext)
    existing_context: dict[str, Any] = field(default_factory=dict)  # 兼容旧context_package

    budget: BudgetState = field(default_factory=BudgetState)
    assembled_at: str = ""
    assembly_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_prompt_context(self) -> str:
        """序列化为生成用的上下文文本。"""
        parts = []
        if self.genre_pack.genre_name:
            parts.append(f"【品类】{self.genre_pack.genre_name}")
            if self.genre_pack.style_rules:
                parts.append(f"  风格规则：{json.dumps(self.genre_pack.style_rules, ensure_ascii=False)}")
        if self.style_card.tone:
            parts.append(f"【文风】语气={self.style_card.tone}, 节奏={self.style_card.pace}")
        if self.character_voices:
            parts.append("【人物声音】")
            for cv in self.character_voices:
                if cv.human_confirmed:
                    parts.append(f"  {cv.character_name}({cv.role}): {cv.speech_pattern}")
        if self.causal_contract.core_question:
            parts.append(f"【因果契约】核心问题={self.causal_contract.core_question}")
            parts.append(f"  可见兑现={self.causal_contract.visible_payoff}")
            parts.append(f"  代价={self.causal_contract.cost_or_sacrifice}")
            parts.append(f"  下一章压力={self.causal_contract.next_pressure}")
        if self.platform.platform:
            parts.append(f"【平台】{self.platform.platform}, AI政策={self.platform.ai_usage_policy}")
        if self.state_start.character_states:
            parts.append(f"【章首状态】{json.dumps(self.state_start.character_states, ensure_ascii=False)[:200]}")
        return "\n".join(parts)


def _estimate_tokens(text: str) -> int:
    """粗略估算token数（中文1字≈1.5token，英文1词≈1.3token）。"""
    if not text:
        return 0
    chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other = len(text) - chinese
    return int(chinese * 1.5 + other * 0.5)


def assemble_chapter_context(
    novel_id: str,
    chapter_id: str,
    chapter_seq: int = 0,
    genre_pack: Optional[dict[str, Any]] = None,
    style_card: Optional[dict[str, Any]] = None,
    character_voices: Optional[list[dict[str, Any]]] = None,
    state_start: Optional[dict[str, Any]] = None,
    state_end: Optional[dict[str, Any]] = None,
    causal_contract: Optional[dict[str, Any]] = None,
    platform_profile: Optional[dict[str, Any]] = None,
    existing_context: Optional[dict[str, Any]] = None,
    max_tokens: int = 8000,
) -> ChapterContext:
    """组装ChapterContext，超预算直接停止并标记。

    关键状态超预算会直接停止，不再静默切掉。
    """
    from datetime import datetime, timezone

    ctx = ChapterContext(
        novel_id=novel_id,
        chapter_id=chapter_id,
        chapter_seq=chapter_seq,
        assembled_at=datetime.now(timezone.utc).isoformat(),
    )
    ctx.budget.max_tokens = max_tokens

    # 1. 品类包
    if genre_pack:
        ctx.genre_pack = GenrePackContext(
            genre_id=genre_pack.get("id", ""),
            genre_name=genre_pack.get("name", ""),
            parent_genre=genre_pack.get("parent_name", ""),
            style_rules=genre_pack.get("style_rules", {}),
            payoff_contract=genre_pack.get("payoff_contract", {}),
            knowledge_items=genre_pack.get("knowledge_items", []),
        )
    ctx.budget.genre_tokens = _estimate_tokens(json.dumps(ctx.genre_pack.__dict__, ensure_ascii=False))

    # 2. 文风卡
    if style_card:
        ctx.style_card = StyleCardContext(
            style_id=style_card.get("id", ""),
            style_name=style_card.get("name", ""),
            tone=style_card.get("tone", ""),
            pace=style_card.get("pace", ""),
            opening_style=style_card.get("opening_style", ""),
            payoff_density=style_card.get("payoff_density", ""),
            vocabulary_hints=style_card.get("vocabulary_hints", []),
            forbidden_patterns=style_card.get("forbidden_patterns", []),
            sample_prose=style_card.get("sample_prose", ""),
        )
    ctx.budget.style_tokens = _estimate_tokens(json.dumps(ctx.style_card.__dict__, ensure_ascii=False))

    # 3. 人物声音卡（只保留经人工确认的）
    if character_voices:
        for cv in character_voices:
            card = CharacterVoiceCard(
                character_id=cv.get("id", ""),
                character_name=cv.get("name", ""),
                role=cv.get("role", ""),
                speech_pattern=cv.get("speech_pattern", ""),
                vocabulary=cv.get("vocabulary", []),
                confirmed_samples=cv.get("confirmed_samples", []),
                personality_traits=cv.get("personality_traits", []),
                human_confirmed=cv.get("human_confirmed", False),
            )
            ctx.character_voices.append(card)
    ctx.budget.character_tokens = _estimate_tokens(json.dumps([c.__dict__ for c in ctx.character_voices], ensure_ascii=False))

    # 4. 章首/章末双快照
    if state_start:
        ctx.state_start = StoryStateSnapshot(
            chapter_seq=state_start.get("chapter_seq", chapter_seq),
            character_states=state_start.get("character_states", {}),
            item_states=state_start.get("item_states", {}),
            timeline_position=state_start.get("timeline_position", ""),
            world_state=state_start.get("world_state", {}),
            unresolved_foreshadowings=state_start.get("unresolved_foreshadowings", []),
            active_goals=state_start.get("active_goals", []),
        )
    if state_end:
        ctx.state_end = StoryStateSnapshot(
            chapter_seq=state_end.get("chapter_seq", chapter_seq),
            character_states=state_end.get("character_states", {}),
            item_states=state_end.get("item_states", {}),
            timeline_position=state_end.get("timeline_position", ""),
            world_state=state_end.get("world_state", {}),
            unresolved_foreshadowings=state_end.get("unresolved_foreshadowings", []),
            active_goals=state_end.get("active_goals", []),
        )
    ctx.budget.state_tokens = _estimate_tokens(
        json.dumps(ctx.state_start.__dict__, ensure_ascii=False) +
        json.dumps(ctx.state_end.__dict__, ensure_ascii=False)
    )

    # 5. 因果契约
    if causal_contract:
        ctx.causal_contract = CausalContract(
            core_question=causal_contract.get("core_question", ""),
            visible_payoff=causal_contract.get("visible_payoff", ""),
            cost_or_sacrifice=causal_contract.get("cost_or_sacrifice", ""),
            next_pressure=causal_contract.get("next_pressure", ""),
            causal_ledger=causal_contract.get("causal_ledger", []),
            state_anchors=causal_contract.get("state_anchors", []),
            workflow_state=causal_contract.get("workflow_state", ""),
        )
    ctx.budget.causal_tokens = _estimate_tokens(json.dumps(ctx.causal_contract.__dict__, ensure_ascii=False))

    # 6. 平台配置
    if platform_profile:
        ctx.platform = PlatformContext(
            platform=platform_profile.get("platform", ""),
            profile_name=platform_profile.get("profile_name", ""),
            policy_status=platform_profile.get("policy_status", "unknown"),
            policy_version=platform_profile.get("policy_version", ""),
            ai_usage_policy=platform_profile.get("ai_usage_policy", "unknown"),
            word_count_min=platform_profile.get("word_count_min"),
            word_count_max=platform_profile.get("word_count_max"),
            chapter_word_min=platform_profile.get("chapter_word_min"),
            chapter_word_max=platform_profile.get("chapter_word_max"),
            title_rules=platform_profile.get("title_rules", {}),
            prohibited_content=platform_profile.get("prohibited_content", []),
        )
    ctx.budget.platform_tokens = _estimate_tokens(json.dumps(ctx.platform.__dict__, ensure_ascii=False))

    # 7. 现有上下文（兼容）
    if existing_context:
        ctx.existing_context = existing_context
    ctx.budget.existing_context_tokens = _estimate_tokens(json.dumps(ctx.existing_context, ensure_ascii=False))

    # 预算汇总
    ctx.budget.total_tokens = (
        ctx.budget.genre_tokens + ctx.budget.style_tokens + ctx.budget.character_tokens +
        ctx.budget.state_tokens + ctx.budget.causal_tokens + ctx.budget.platform_tokens +
        ctx.budget.existing_context_tokens
    )

    # 超预算检测 — 关键状态超预算直接停止，不再静默切掉
    if ctx.budget.total_tokens > max_tokens:
        ctx.budget.exceeded = True
        components = [
            ("genre_pack", ctx.budget.genre_tokens),
            ("style_card", ctx.budget.style_tokens),
            ("character_voices", ctx.budget.character_tokens),
            ("state_snapshots", ctx.budget.state_tokens),
            ("causal_contract", ctx.budget.causal_tokens),
            ("platform", ctx.budget.platform_tokens),
            ("existing_context", ctx.budget.existing_context_tokens),
        ]
        # 标记超过各自合理预算的组件
        per_component_max = max_tokens // 7
        for name, tokens in components:
            if tokens > per_component_max * 2:
                ctx.budget.exceeded_components.append(name)
        ctx.assembly_errors.append(
            f"上下文总token={ctx.budget.total_tokens}超过上限{max_tokens}，"
            f"超预算组件: {ctx.budget.exceeded_components}。必须裁剪后才能继续生成。"
        )

    # 因果契约完整性校验
    if causal_contract:
        required = ["core_question", "visible_payoff", "cost_or_sacrifice", "next_pressure"]
        missing = [f for f in required if not getattr(ctx.causal_contract, f)]
        if missing:
            ctx.assembly_errors.append(f"因果契约缺少必填字段: {missing}，生成质量标记为失败。")

    return ctx
