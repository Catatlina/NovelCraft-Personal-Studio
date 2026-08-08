"""Generation-first content and fictional-world policy for web novels.

支持脏话分级 + 上下文感知：
- 严重脏话（high）：侮辱性强的脏话，质量门不通过
- 轻度口语（low）：常见口语化表达，只警告不拦截
- 上下文感知：对话中的脏话降低严重程度
"""
from __future__ import annotations

import re
from typing import Any


# ═════════════════════════════════════════════════════════════
# 严重脏话（high 级别）- 侮辱性强，质量门不通过
# ═════════════════════════════════════════════════════════════
HIGH_PROFANITY_PATTERNS: tuple[tuple[str, str], ...] = (
    # 严重辱骂
    (r"他妈的|他媽的|你妈的|你媽的|妈的|媽的|草泥马|草泥馬|妈卖批|媽賣批", "severe_profanity"),
    # 针对性辱骂
    (r"操你|操他|操她|日你|狗日的", "targeted_insult"),
    # 侮辱性称呼
    (r"傻逼|傻比|煞笔|煞筆", "insulting_term"),
)

# ═════════════════════════════════════════════════════════════
# 轻度口语（low 级别）- 常见口语化表达，只警告不拦截
# ═════════════════════════════════════════════════════════════
LOW_PROFANITY_PATTERNS: tuple[tuple[str, str], ...] = (
    # 口语感叹词
    (r"卧槽|臥槽|我操|我艹|我去|我靠", "mild_expletive"),
    # 口语化表达
    (r"尼玛|尼瑪|牛逼|牛B|牛批", "mild_colloquial"),
    # 歧义单字（需要上下文判断）
    (r"(?:^|[\s，。！？、:：])草(?=[\s，。！？、:：]|$)", "ambiguous_expletive"),
    (r"(?:^|[\s，。！？、:：])操(?=[\s，。！？、:：]|$)", "ambiguous_expletive"),
)

# 保持向后兼容
PROFANITY_PATTERNS = HIGH_PROFANITY_PATTERNS + LOW_PROFANITY_PATTERNS


# ═════════════════════════════════════════════════════════════
# 引号字符（用于判断是否在对话中）
# ═════════════════════════════════════════════════════════════
OPEN_QUOTES = {'"', '"', "'", "'", "「", "『", "《"}
CLOSE_QUOTES = {'"', '"', "'", "'", "」", "』", "》"}
ALL_QUOTES = OPEN_QUOTES | CLOSE_QUOTES

# 对话检测的搜索范围（前后各 100 字符）
DIALOGUE_CONTEXT_RANGE = 100


def _is_in_dialogue(text: str, start: int, end: int) -> bool:
    """
    判断匹配位置是否在对话中（引号内）。
    
    简单的启发式判断：
    1. 在匹配位置前后一定范围内搜索引号
    2. 如果前面有开引号，后面有闭引号，且中间没有其他不配对的引号，则认为在对话中
    
    Args:
        text: 完整文本
        start: 匹配起始位置
        end: 匹配结束位置
    
    Returns:
        bool: 是否在对话中
    """
    text_len = len(text)
    
    # 计算搜索范围
    search_start = max(0, start - DIALOGUE_CONTEXT_RANGE)
    search_end = min(text_len, end + DIALOGUE_CONTEXT_RANGE)
    
    # 统计前面的引号
    before_text = text[search_start:start]
    after_text = text[end:search_end]
    
    # 简单判断：前后都有引号，且数量大致平衡
    before_open = sum(1 for c in before_text if c in OPEN_QUOTES)
    before_close = sum(1 for c in before_text if c in CLOSE_QUOTES)
    after_open = sum(1 for c in after_text if c in OPEN_QUOTES)
    after_close = sum(1 for c in after_text if c in CLOSE_QUOTES)
    
    # 如果前面开引号比闭引号多（说明在引号内），且后面有闭引号
    # 或者后面闭引号比开引号多（说明在引号内）
    in_dialogue = False
    
    # 情况 1：前面开引号 > 闭引号，且后面有闭引号
    if before_open > before_close and after_close > 0:
        in_dialogue = True
    
    # 情况 2：后面闭引号 > 开引号，且前面有开引号
    if after_close > after_open and before_open > 0:
        in_dialogue = True
    
    # 情况 3：紧邻前后就是引号
    if start > 0 and text[start - 1] in ALL_QUOTES:
        in_dialogue = True
    if end < text_len and text[end] in ALL_QUOTES:
        in_dialogue = True
    
    return in_dialogue


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
        "正文不得出现敏感、违法、色情、仇恨、极端或露骨暴力表达，不得出现严重脏话、辱骂和侮辱性称呼。",
        "需要表达强烈情绪时，用动作、语气、停顿或干净的替代表达；角色对话中可以保留轻度口语化表达。",
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
    """
    Run a cheap local signal check after generation, without a provider call.
    
    支持脏话分级 + 上下文感知：
    - high 级别脏话：质量门不通过
    - medium 级别脏话：对话中的 high 脏话，降级，警告但通过
    - low 级别脏话：轻度口语，警告但通过
    - info 级别：对话中的 low 脏话，仅记录，不警告
    
    保持向后兼容：返回值包含原有的 profanity_hits、sensitive_hits、failures 等字段。
    """
    source = str(text or "")
    
    # ═════════════════════════════════════════════════════════════
    # 1. 脏话检测（分级 + 上下文感知）
    # ═════════════════════════════════════════════════════════════
    high_hits: list[dict[str, Any]] = []
    medium_hits: list[dict[str, Any]] = []  # 对话中的 high 脏话
    low_hits: list[dict[str, Any]] = []
    info_hits: list[dict[str, Any]] = []  # 对话中的 low 脏话
    
    # 检测严重脏话
    for pattern, category in HIGH_PROFANITY_PATTERNS:
        for match in re.finditer(pattern, source, flags=re.IGNORECASE | re.MULTILINE):
            term = match.group(0)
            start, end = match.span()
            in_dialogue = _is_in_dialogue(source, start, end)
            
            hit_info = {
                "term": term,
                "category": category,
                "severity": "high",
                "in_dialogue": in_dialogue,
                "position": start,
            }
            
            if in_dialogue:
                # 对话中的严重脏话，降级为 medium
                hit_info["severity"] = "medium"
                hit_info["original_severity"] = "high"
                medium_hits.append(hit_info)
            else:
                high_hits.append(hit_info)
    
    # 检测轻度口语
    for pattern, category in LOW_PROFANITY_PATTERNS:
        for match in re.finditer(pattern, source, flags=re.IGNORECASE | re.MULTILINE):
            term = match.group(0)
            start, end = match.span()
            in_dialogue = _is_in_dialogue(source, start, end)
            
            hit_info = {
                "term": term,
                "category": category,
                "severity": "low",
                "in_dialogue": in_dialogue,
                "position": start,
            }
            
            if in_dialogue:
                # 对话中的轻度口语，降级为 info
                hit_info["severity"] = "info"
                hit_info["original_severity"] = "low"
                info_hits.append(hit_info)
            else:
                low_hits.append(hit_info)
    
    # 合并所有脏话命中（用于向后兼容）
    all_profanity_hits = high_hits + medium_hits + low_hits + info_hits
    
    # ═════════════════════════════════════════════════════════════
    # 2. 敏感词检测（保持原样，严格检测）
    # ═════════════════════════════════════════════════════════════
    sensitive_hits = [term for term in SENSITIVE_TERMS if term in source]
    
    # ═════════════════════════════════════════════════════════════
    # 3. 现实实体检测（都市题材专用，保持原样）
    # ═════════════════════════════════════════════════════════════
    real_entity_hits: list[str] = []
    if isinstance(profile, dict) and profile.get("genre") == "urban":
        real_entity_hits = [term for term in REAL_WORLD_ENTITY_TOKENS if term in source]
    
    # ═════════════════════════════════════════════════════════════
    # 4. 构建失败列表和警告列表
    # ═════════════════════════════════════════════════════════════
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    
    # 严重脏话 → 失败
    if high_hits:
        failures.append({
            "code": "profanity_or_insult",
            "severity": "high",
            "message": "正文含未脱敏严重脏话或辱骂表达",
            "evidence": [h["term"] for h in high_hits[:8]],
            "details": high_hits[:8],
        })
    
    # 敏感词 → 失败
    if sensitive_hits:
        failures.append({
            "code": "sensitive_content",
            "severity": "high",
            "message": "正文命中敏感内容词表",
            "evidence": sensitive_hits[:8],
        })
    
    # 现实实体 → 失败
    if real_entity_hits:
        failures.append({
            "code": "urban_real_world_entity",
            "severity": "high",
            "message": "都市架空现实层中出现现实实体名称",
            "evidence": real_entity_hits[:8],
        })
    
    # 对话中的严重脏话 → 警告
    if medium_hits:
        warnings.append({
            "code": "dialogue_profanity",
            "severity": "medium",
            "message": "角色对话中含严重脏话，已降级处理",
            "evidence": [h["term"] for h in medium_hits[:8]],
            "details": medium_hits[:8],
        })
    
    # 轻度口语 → 警告
    if low_hits:
        warnings.append({
            "code": "mild_colloquial",
            "severity": "low",
            "message": "正文含轻度口语化表达",
            "evidence": [h["term"] for h in low_hits[:8]],
            "details": low_hits[:8],
        })
    
    # ═════════════════════════════════════════════════════════════
    # 5. 构建返回结果（保持向后兼容）
    # ═════════════════════════════════════════════════════════════
    result = {
        # 核心结果
        "passed": not failures,
        "profile": (profile or {}).get("profile_id") if isinstance(profile, dict) else None,
        "urban_fiction_required": isinstance(profile, dict) and profile.get("genre") == "urban",
        
        # 向后兼容字段
        "profanity_hits": [h["term"] for h in all_profanity_hits[:8]],
        "sensitive_hits": sensitive_hits[:8],
        "real_world_entity_hits": real_entity_hits[:8],
        "failures": failures,
        
        # 新增字段
        "warnings": warnings,
        "profanity_detail": {
            "high_hits": high_hits,
            "medium_hits": medium_hits,
            "low_hits": low_hits,
            "info_hits": info_hits,
            "total_high": len(high_hits),
            "total_medium": len(medium_hits),
            "total_low": len(low_hits),
            "total_info": len(info_hits),
        },
        "summary": _build_summary(failures, warnings),
    }
    
    return result


def _build_summary(failures: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> str:
    """构建人类可读的总结。"""
    if not failures and not warnings:
        return "内容检测通过，未发现问题。"
    
    parts = []
    
    if failures:
        failure_count = len(failures)
        parts.append(f"检测到 {failure_count} 项严重问题")
        for f in failures:
            parts.append(f"  - {f['message']}")
    
    if warnings:
        warning_count = len(warnings)
        parts.append(f"检测到 {warning_count} 项警告")
        for w in warnings:
            parts.append(f"  - {w['message']}")
    
    return "\n".join(parts)
