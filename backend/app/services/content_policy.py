"""Generation-first content and fictional-world policy for web novels."""
from __future__ import annotations

import re
from typing import Any


# These are deliberately phrase-level checks.  A single character such as
# “草” is not blocked because it may genuinely mean grass; the surrounding
# context must make an expletive unambiguous before it is rejected.
PROFANITY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"他妈的|他媽的|你妈的|你媽的|妈的|媽的|草泥马|草泥馬|妈卖批|媽賣批", "profanity"),
    (r"卧槽|臥槽|我操|我艹|操你|操他|操她|日你|狗日的", "profanity"),
    (r"傻逼|傻比|煞笔|煞筆|尼玛|尼瑪|牛逼|牛B", "profanity"),
    (r"(?:^|[\s，。！？、:：])草(?=[\s，。！？、:：]|$)", "ambiguous_expletive"),
    (r"(?:^|[\s，。！？、:：])操(?=[\s，。！？、:：]|$)", "ambiguous_expletive"),
)

# Common real-world entities that accidentally leak into a fictional urban
# setting.  The prompt contract remains the primary control; this list is a
# cheap last-mile signal, not a claim that a finite dictionary covers every
# real entity.
REAL_WORLD_ENTITY_TOKENS: tuple[str, ...] = (
    "北京", "上海", "广州", "深圳", "天津", "重庆", "杭州", "南京", "苏州", "成都",
    "武汉", "西安", "郑州", "济南", "沈阳", "大连", "青岛", "厦门", "福州", "昆明",
    "长沙", "合肥", "南昌", "贵阳", "太原", "石家庄", "哈尔滨", "长春", "乌鲁木齐",
    "海口", "三亚", "香港", "澳门", "台北", "阿里巴巴", "淘宝", "天猫", "京东",
    "拼多多", "腾讯", "微信", "抖音", "快手", "字节跳动", "百度", "小米", "华为",
    "苹果公司", "微软", "谷歌", "特斯拉", "起点中文网", "番茄小说",
)

SENSITIVE_TERMS: tuple[str, ...] = (
    "政治敏感", "色情", "暴力恐怖", "极端主义", "仇恨言论", "赌博", "毒品", "枪支", "诈骗",
    "传销", "邪教", "侵权", "隐私泄露", "违禁内容", "分裂国家", "颠覆政权", "民族仇恨",
    "宗教极端", "淫秽", "凶杀", "校园暴力", "自杀", "假币", "假发票", "人体器官",
    "间谍器材", "非法集资", "高利贷", "套路贷", "迷药", "催情", "窃听", "偷拍",
    "考试作弊", "代孕", "代写论文", "刷单", "刷粉", "删帖", "水军", "网络攻击", "木马",
    "病毒",
)


def content_generation_contract(profile: dict[str, Any] | None) -> str:
    """Build the content policy that must be sent before any prose request."""
    profile = profile if isinstance(profile, dict) else {}
    lines = [
        "【生成安全与原创化硬约束】",
        "正文不得出现敏感、违法、色情、仇恨、极端或露骨暴力表达，不得出现脏话、辱骂和侮辱性称呼。",
        "需要表达强烈情绪时，用动作、语气、停顿或干净的替代表达；不要原样输出脏话。",
        "允许保留普通词义，但必须让语境明确不是脏话：例如‘草’只能明确指植物/草地，不能单独作为情绪脏话；"
        "‘TMD’等仅可作为已脱敏的替代表达，不得再扩写成原脏话。",
    ]
    if profile.get("genre") == "urban":
        lines.extend(
            [
                "【都市题材专属：架空现实层】",
                "本书发生在完全架空的现代社会。人名、地名、公司/机构、平台、品牌、媒体、学校、医院、法律政策和现实事件全部原创虚构，"
                "不得直接使用或影射现实实体，不得把现实城市、企业和公众人物换个字继续套用。",
                "可以保留读者熟悉的生活逻辑和行业质感，但必须重写实体名称、组织关系和事件背景；先在脑中建立本书的虚构实体表，"
                "正文只使用实体表中的原创名称。不要出现真实平台、品牌、城市或现实新闻作为快捷说明。",
            ]
        )
    return "\n".join(lines)


def analyze_content_policy(text: Any, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run a cheap local signal check after generation, without a provider call."""
    source = str(text or "")
    profanity_hits: list[dict[str, str]] = []
    for pattern, category in PROFANITY_PATTERNS:
        for match in re.finditer(pattern, source, flags=re.IGNORECASE | re.MULTILINE):
            profanity_hits.append({"term": match.group(0), "category": category})

    sensitive_hits = [term for term in SENSITIVE_TERMS if term in source]
    real_entity_hits: list[str] = []
    if isinstance(profile, dict) and profile.get("genre") == "urban":
        real_entity_hits = [term for term in REAL_WORLD_ENTITY_TOKENS if term in source]

    failures: list[dict[str, Any]] = []
    if profanity_hits:
        failures.append({
            "code": "profanity_or_insult",
            "severity": "high",
            "message": "正文含未脱敏脏话或辱骂表达",
            "evidence": profanity_hits[:8],
        })
    if sensitive_hits:
        failures.append({
            "code": "sensitive_content",
            "severity": "high",
            "message": "正文命中敏感内容词表",
            "evidence": sensitive_hits[:8],
        })
    if real_entity_hits:
        failures.append({
            "code": "urban_real_world_entity",
            "severity": "high",
            "message": "都市架空现实层中出现现实实体名称",
            "evidence": real_entity_hits[:8],
        })

    return {
        "passed": not failures,
        "profile": (profile or {}).get("profile_id") if isinstance(profile, dict) else None,
        "urban_fiction_required": isinstance(profile, dict) and profile.get("genre") == "urban",
        "profanity_hits": profanity_hits[:8],
        "sensitive_hits": sensitive_hits[:8],
        "real_world_entity_hits": real_entity_hits[:8],
        "failures": failures,
    }
