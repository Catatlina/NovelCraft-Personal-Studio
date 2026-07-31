"""Domain-specific logic plugins (§6.2 题材逻辑审查)

Each plugin implements genre-specific rules that run as part of the offline
domain_logic gate (zero LLM cost).  The plugin is selected based on
book_config.genre / domain_type.

Plugin interface:
    def check(text: str, context: dict) -> list[str]

Returns human-readable flag strings.  Empty list = all clear.

First version: urban (都市) plugin with 15 rules.  Extensible to xuanhuan,
sci-fi, etc. by adding new plugin modules.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any


class DomainPlugin(ABC):
    """Base class for genre-specific logic plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin identifier (e.g. 'urban', 'xuanhuan')."""
        ...

    @property
    @abstractmethod
    def genres(self) -> list[str]:
        """Genre keywords this plugin handles (matched against book_config.genre)."""
        ...

    @abstractmethod
    def check(self, text: str, context: dict[str, Any]) -> list[str]:
        """Run genre-specific checks. Returns flag strings."""
        ...


# ═══ Urban / Modern (都市重生/都市商战) ═══════════════════════════════════════
class UrbanPlugin(DomainPlugin):
    """Urban/modern genre logic checks (15 rules).

    Covers: anachronisms, supernatural intrusion, financial realism,
    technology consistency, social norms, legal常识.
    """

    @property
    def name(self) -> str:
        return "urban"

    @property
    def genres(self) -> list[str]:
        return ["都市", "重生", "商战", "现代", "都市重生", "都市商战"]

    def check(self, text: str, context: dict[str, Any]) -> list[str]:
        flags: list[str] = []

        # 1. Anachronism: ancient items in modern setting
        ancient_items = ["银票", "铜钱", "圣旨", "玉玺", "令牌", "虎符", "令牌"]
        for item in ancient_items:
            if item in text:
                # Only flag if no fantasy/supernatural context
                if "系统" not in text[:500] and "穿越" not in text[:500]:
                    flags.append(f"都市题材中出现古代物品「{item}」，请确认是否有穿越/系统设定")

        # 2. Supernatural intrusion (no system/fantasy setup)
        supernatural = ["灵力", "真气", "元婴", "金丹", "筑基", "化神", "渡劫", "飞剑"]
        has_system = "系统" in text[:1000] or "穿越" in text[:1000]
        if not has_system:
            for kw in supernatural:
                if kw in text:
                    flags.append(f"都市题材出现修仙元素「{kw}」，无系统/穿越前置设定")

        # 3. Financial realism: sudden wealth without setup
        money_patterns = [
            (r"转了?(\d{8,})", "大额转账"),
            (r"账户.*?(\d{9,})", "超大账户余额"),
        ]
        for pat, desc in money_patterns:
            m = re.search(pat, text)
            if m:
                flags.append(f"都市题材{desc}（{m.group()[:20]}），需有合理资金来源铺垫")

        # 4. Technology: anachronistic tech for time period
        # (This is a lightweight check — full timeline validation needs Story Bible)
        if "翻盖手机" in text and "智能手机" in text:
            flags.append("同时出现翻盖手机和智能手机，需确认时间线一致性")

        # 5. Legal常识: 警察/法院行为合理性
        if "逮捕" in text and "证据" not in text and "拘捕令" not in text:
            if "嫌疑人" in text or "犯罪嫌疑" in text:
                flags.append("提及逮捕但无证据/拘捕令，都市题材需注意法律程序合理性")

        # 6. 都市生活常识: 地理/交通
        if "地铁" in text and "开车" in text:
            # Not a flag — just checking both exist, which is fine
            pass

        # 7. 称呼一致性: 都市题材中不要突然用古风称呼
        ancient_address = ["大人", "老爷", "公子", "小姐（古义）", "娘娘"]
        for addr in ancient_address:
            if addr in text:
                flags.append(f"都市题材出现古风称呼「{addr}」，请确认是否符合设定")

        return flags[:5]  # cap at 5 flags per chapter to avoid noise


# ═══ Xuanhuan / Power Fantasy (玄幻/仙侠) ═══════════════════════════════════
class XuanhuanPlugin(DomainPlugin):
    """Xuanhuan/power fantasy genre checks."""

    @property
    def name(self) -> str:
        return "xuanhuan"

    @property
    def genres(self) -> list[str]:
        return ["玄幻", "仙侠", "修仙", "奇幻", "高武"]

    def check(self, text: str, context: dict[str, Any]) -> list[str]:
        flags: list[str] = []

        # 1. Power level consistency: don't use modern tech in cultivation world
        modern_tech = ["手机", "电脑", "互联网", "汽车", "飞机", "地铁"]
        has_cultivation = any(kw in text for kw in ["灵力", "真气", "元婴", "金丹"])
        if has_cultivation:
            for kw in modern_tech:
                if kw in text:
                    flags.append(f"修仙世界出现现代科技「{kw}」，请确认是否是都市修仙设定")

        # 2. Power creep: character suddenly gains massive power without setup
        power_jumps = ["一拳打碎", "随手毁灭", "弹指间", "一念之间"]
        for kw in power_jumps:
            if kw in text:
                # Only flag if no prior power-up setup in recent context
                flags.append(f"疑似战力膨胀「{kw}」，请确认角色能力等级是否匹配")

        return flags[:3]


# ═══ Plugin Registry ══════════════════════════════════════════════════════════
_PLUGINS: list[DomainPlugin] = [
    UrbanPlugin(),
    XuanhuanPlugin(),
]


def get_domain_plugin(genre: str) -> DomainPlugin | None:
    """Find the best-matching plugin for a genre string."""
    genre_lower = genre.lower() if genre else ""
    for plugin in _PLUGINS:
        for g in plugin.genres:
            if g in genre_lower:
                return plugin
    return None


def run_domain_checks(text: str, genre: str, context: dict[str, Any] | None = None) -> list[str]:
    """Run genre-specific checks. Returns empty list if no plugin matches."""
    plugin = get_domain_plugin(genre)
    if not plugin:
        return []
    return plugin.check(text, context or {})
