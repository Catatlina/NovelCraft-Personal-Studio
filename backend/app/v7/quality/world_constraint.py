"""
世界观硬约束模块

用于检查小说正文是否违反特定品类的世界观硬约束。
例如：封神小说不能出现"金丹期""筑基期"等修真概念。

设计原则：
- 增量开发，不破坏现有架构
- 可扩展，支持多品类
- 纯规则检查，不需要AI调用
- 可作为质量门禁的一部分
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import re


@dataclass
class WorldConstraintRule:
    """单条世界观约束规则"""
    rule_id: str
    category: str  # 规则分类：forbidden_concept, naming, structure, combat, etc.
    description: str
    forbidden_patterns: List[str] = field(default_factory=list)  # 禁止出现的模式（正则）
    required_patterns: List[str] = field(default_factory=list)   # 必须出现的模式（可选）
    severity: str = "high"  # high/medium/low


@dataclass
class WorldConstraintPack:
    """一个品类的完整世界观约束包"""
    genre: str  # 品类标识，如 "fengshen"
    name: str   # 品类名称，如 "封神举国"
    rules: List[WorldConstraintRule] = field(default_factory=list)

    def check_text(self, text: str) -> Dict:
        """
        检查文本是否违反世界观约束
        
        Args:
            text: 要检查的正文文本
            
        Returns:
            {
                "passed": bool,
                "violations": [
                    {
                        "rule_id": str,
                        "category": str,
                        "description": str,
                        "severity": str,
                        "matched": [str, ...],  # 匹配到的具体内容
                        "count": int
                    }
                ],
                "summary": {
                    "total_violations": int,
                    "high_severity": int,
                    "medium_severity": int,
                    "low_severity": int
                }
            }
        """
        violations = []
        high_count = 0
        medium_count = 0
        low_count = 0

        for rule in self.rules:
            matched = []
            for pattern in rule.forbidden_patterns:
                try:
                    matches = re.findall(pattern, text)
                    if matches:
                        matched.extend(matches)
                except re.error:
                    # 如果正则表达式有问题，跳过
                    continue

            if matched:
                violation = {
                    "rule_id": rule.rule_id,
                    "category": rule.category,
                    "description": rule.description,
                    "severity": rule.severity,
                    "matched": list(set(matched)),  # 去重
                    "count": len(matched)
                }
                violations.append(violation)

                if rule.severity == "high":
                    high_count += 1
                elif rule.severity == "medium":
                    medium_count += 1
                else:
                    low_count += 1

        total = len(violations)
        passed = total == 0 or high_count == 0  # 没有high级违规就算通过

        return {
            "passed": passed,
            "violations": violations,
            "summary": {
                "total_violations": total,
                "high_severity": high_count,
                "medium_severity": medium_count,
                "low_severity": low_count
            }
        }


# ============== 内置品类约束包 ==============

def get_fengshen_constraint_pack() -> WorldConstraintPack:
    """
    获取封神举国品类的世界观约束包
    
    封神世界观核心规则：
    - 修炼体系：炼气士→地仙→天仙→金仙→大罗→混元→圣人
    - 禁止：筑基/金丹/元婴/灵根/灵石/储物袋（后世修真概念）
    - 截教结构：外门→四大亲传→随侍七仙→通天
    - 战斗方式：法宝为主，阵法为核心，因果>修为
    - 时间流速：100:1，通讯需数据包压缩
    - 名称变体：华夏/米国/帝京/华威
    """
    pack = WorldConstraintPack(
        genre="fengshen",
        name="封神举国",
        rules=[
            WorldConstraintRule(
                rule_id="forbidden_cultivation_terms",
                category="forbidden_concept",
                description="禁止后世修真概念（筑基/金丹/元婴等）",
                forbidden_patterns=[
                    r"筑基[期层]?",
                    r"金丹[期层]?",
                    r"元婴[期层]?",
                    r"化神[期层]?",
                    r"炼虚[期层]?",
                    r"合体[期层]?",
                    r"大乘[期层]?",
                    r"渡劫[期层]?",
                    r"灵根",
                    r"灵石",
                    r"储物袋",
                    r"储物戒指",
                    r"功法玉简",
                    r"玉简",
                    r"纳戒",
                    r"修仙者",
                    r"修真者",
                ],
                severity="high"
            ),
            WorldConstraintRule(
                rule_id="forbidden_modern_terms",
                category="forbidden_concept",
                description="禁止现代词汇（封神世界不应出现）",
                forbidden_patterns=[
                    r"手机",
                    r"电脑",
                    r"互联网",
                    r"微信",
                    r"QQ",
                    r"汽车",
                    r"飞机",
                    r"火车",
                    r"地铁",
                    r"电视",
                    r"电影",
                ],
                severity="medium"
            ),
            WorldConstraintRule(
                rule_id="fengshen_cultivation_system",
                category="naming",
                description="封神修炼体系应该使用正确的境界名称",
                forbidden_patterns=[
                    # 这些是错误的境界名称，不应该出现在封神小说中
                    r"炼气[期层]",  # 应该是"炼气士"
                ],
                severity="low"
            ),
        ]
    )
    return pack


# ============== 约束包注册表 ==============

_CONSTRAINT_PACKS: Dict[str, WorldConstraintPack] = {}


def register_constraint_pack(pack: WorldConstraintPack):
    """注册一个世界观约束包"""
    _CONSTRAINT_PACKS[pack.genre] = pack


def get_constraint_pack(genre: str) -> Optional[WorldConstraintPack]:
    """
    获取指定品类的世界观约束包
    
    Args:
        genre: 品类标识，如 "fengshen"
        
    Returns:
        WorldConstraintPack 或 None（如果该品类没有约束包）
    """
    return _CONSTRAINT_PACKS.get(genre)


def list_available_packs() -> List[str]:
    """列出所有可用的约束包"""
    return list(_CONSTRAINT_PACKS.keys())


# ============== 初始化内置约束包 ==============

def _init_builtin_packs():
    """初始化内置的约束包"""
    register_constraint_pack(get_fengshen_constraint_pack())


# 模块加载时自动初始化
_init_builtin_packs()
