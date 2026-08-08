"""Generation-first content and fictional-world policy for web novels.

支持脏话三级分级 + 上下文感知 + 频率检测：
- 严重脏话（high）：直接人身攻击，叙述中拦截，对话中警告
- 中等脏话（medium）：较强脏话，叙述中警告，对话中通过
- 轻微口语（low）：常见口语化表达，叙述中不拦截，对话中直接通过
- 上下文感知：对话中的脏话降低一级严重程度
- 频率检测：脏话过于密集时警告
"""
from __future__ import annotations

import re
from typing import Any


# ═════════════════════════════════════════════════════════════
# 严重脏话（high 级别）- 直接人身攻击，叙述中拦截，对话中警告
# ═════════════════════════════════════════════════════════════
HIGH_PROFANITY_PATTERNS: tuple[tuple[str, str], ...] = (
    # 直接人身攻击（操你妈、草泥马、妈卖批等）
    (r"操你妈|操你媽|草泥马|草泥馬|妈卖批|媽賣批|操他妈的|操他媽的", "severe_insult"),
    # 侮辱性称呼（傻逼、煞笔等）
    (r"傻逼|傻比|煞笔|煞筆|傻屌", "insulting_term"),
    # 针对性辱骂（第二人称）
    (r"操你|日你|干你", "targeted_insult"),
)

# ═════════════════════════════════════════════════════════════
# 中等脏话（medium 级别）- 较强脏话，叙述中警告，对话中通过
# ═════════════════════════════════════════════════════════════
MEDIUM_PROFANITY_PATTERNS: tuple[tuple[str, str], ...] = (
    # 他妈的、你妈的等
    (r"他妈的|他媽的|你妈的|你媽的|妈的|媽的|TMD|tmd", "medium_profanity"),
    # 狗日的等
    (r"狗日的|狗娘养的|狗孃養的", "medium_insult"),
    # 第三人称辱骂
    (r"操他|操她|日他|日她|干他|干她", "third_person_insult"),
    # 卧槽（加强版）
    (r"我操|我艹|我擦", "strong_expletive"),
)

# ═════════════════════════════════════════════════════════════
# 轻微口语（low 级别）- 常见口语化表达，叙述中不拦截，对话中直接通过
# ═════════════════════════════════════════════════════════════
LOW_PROFANITY_PATTERNS: tuple[tuple[str, str], ...] = (
    # 口语感叹词
    (r"卧槽|臥槽|我去|我靠|我去", "mild_expletive"),
    # 口语化表达
    (r"尼玛|尼瑪|牛逼|牛B|牛批|牛掰", "mild_colloquial"),
    # 歧义单字（需要上下文判断）
    (r"(?:^|[\s，。！？、:：])草(?=[\s，。！？、:：]|$)", "ambiguous_expletive"),
    (r"(?:^|[\s，。！？、:：])操(?=[\s，。！？、:：]|$)", "ambiguous_expletive"),
    (r"(?:^|[\s，。！？、:：])日(?=[\s，。！？、:：]|$)", "ambiguous_expletive"),
)

# 保持向后兼容
PROFANITY_PATTERNS = HIGH_PROFANITY_PATTERNS + MEDIUM_PROFANITY_PATTERNS + LOW_PROFANITY_PATTERNS


# ═════════════════════════════════════════════════════════════
# 频率检测阈值
# ═════════════════════════════════════════════════════════════
PROFANITY_FREQUENCY_WARNING_THRESHOLD = 10  # 超过 10 次警告"脏话过于密集"


# ═════════════════════════════════════════════════════════════
# 引号字符（用于判断是否在对话中）
# ═════════════════════════════════════════════════════════════
OPEN_QUOTES = {'"', '"', "'", "'", "「", "『", "《"}
CLOSE_QUOTES = {'"', '"', "'", "'", "」", "』", "》"}
ALL_QUOTES = OPEN_QUOTES | CLOSE_QUOTES

# 对话检测的搜索范围（前后各 100 字符）
DIALOGUE_CONTEXT_RANGE = 100

# 动作+脏话的模式（如"他低骂：'艹！'"）
ACTION_PROFANITY_PATTERNS = (
    r"(?:骂|低骂|暗骂|啐|嘟囔|嘀咕|忍不住|脱口而出)[^，。！？：:]{0,20}[：:]['\"]",
    r"['\"][^'\"]{0,10}(?:草|操|日|靠)[^'\"]{0,10}['\"]",
)


def _is_in_dialogue(text: str, start: int, end: int) -> bool:
    """
    判断匹配位置是否在对话中（引号内）。

    简单的启发式判断：
    1. 在匹配位置前后一定范围内搜索引号
    2. 如果前面有开引号，后面有闭引号，且中间没有其他不配对的引号，则认为在对话中
    3. 动作+脏话（如"他低骂：'艹！'"）也视为对话

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

    # 情况 4：动作+脏话模式（如"他低骂：'艹！'"）
    # 检查前面 50 字符内有没有"骂：""、"暗道：""等模式
    action_check_start = max(0, start - 50)
    action_check_text = text[action_check_start:start]
    for pattern in ACTION_PROFANITY_PATTERNS:
        if re.search(pattern, action_check_text):
            in_dialogue = True
            break

    return in_dialogue


def _classify_profanity(text: str) -> dict[str, Any]:
    """
    分类脏话，返回各级别的命中情况。

    Args:
        text: 要检测的文本

    Returns:
        dict: 包含各级别命中详情的字典
    """
    high_hits: list[dict[str, Any]] = []
    medium_hits: list[dict[str, Any]] = []
    low_hits: list[dict[str, Any]] = []

    # 检测 high 级别脏话
    for pattern, code in HIGH_PROFANITY_PATTERNS:
        for match in re.finditer(pattern, text):
            start, end = match.span()
            in_dialogue = _is_in_dialogue(text, start, end)
            hit = {
                "match": match.group(),
                "code": code,
                "position": start,
                "in_dialogue": in_dialogue,
                "original_level": "high",
            }
            # 对话中的 high 级别脏话，降级为 medium
            if in_dialogue:
                hit["effective_level"] = "medium"
                medium_hits.append(hit)
            else:
                hit["effective_level"] = "high"
                high_hits.append(hit)

    # 检测 medium 级别脏话
    for pattern, code in MEDIUM_PROFANITY_PATTERNS:
        for match in re.finditer(pattern, text):
            start, end = match.span()
            in_dialogue = _is_in_dialogue(text, start, end)
            hit = {
                "match": match.group(),
                "code": code,
                "position": start,
                "in_dialogue": in_dialogue,
                "original_level": "medium",
            }
            # 对话中的 medium 级别脏话，降级为 low
            if in_dialogue:
                hit["effective_level"] = "low"
                low_hits.append(hit)
            else:
                hit["effective_level"] = "medium"
                medium_hits.append(hit)

    # 检测 low 级别脏话
    for pattern, code in LOW_PROFANITY_PATTERNS:
        for match in re.finditer(pattern, text):
            start, end = match.span()
            in_dialogue = _is_in_dialogue(text, start, end)
            hit = {
                "match": match.group(),
                "code": code,
                "position": start,
                "in_dialogue": in_dialogue,
                "original_level": "low",
                "effective_level": "low",  # low 级别不再降级
            }
            low_hits.append(hit)

    # 计算总数
    total_high = len(high_hits)
    total_medium = len(medium_hits)
    total_low = len(low_hits)
    total_profanity = total_high + total_medium + total_low

    # 频率检测
    frequency_warning = False
    frequency_message = ""
    if total_profanity > PROFANITY_FREQUENCY_WARNING_THRESHOLD:
        frequency_warning = True
        frequency_message = f"本章脏话出现 {total_profanity} 次，过于密集，建议适当减少"

    return {
        "high_hits": high_hits,
        "medium_hits": medium_hits,
        "low_hits": low_hits,
        "total_high": total_high,
        "total_medium": total_medium,
        "total_low": total_low,
        "total_profanity": total_profanity,
        "frequency_warning": frequency_warning,
        "frequency_message": frequency_message,
    }


# ═════════════════════════════════════════════════════════════
# 敏感词（政治、色情、暴力、毒品、赌博等）- 继续严格检测
# ═════════════════════════════════════════════════════════════
SENSITIVE_TERMS: tuple[tuple[str, str], ...] = (
    # 政治敏感
    (r"习近平|习大大", "political_leader"),
    (r"天安门事件|六四", "political_event"),
    (r"法轮功|法轮大法", "political_org"),
    # 色情
    (r"色情|黄片|AV|三级片", "pornography"),
    (r"强奸|性侵|猥亵", "sexual_violence"),
    # 暴力
    (r"杀人|放火|爆炸|恐怖袭击", "violence"),
    (r"自杀|自残", "self_harm"),
    # 毒品
    (r"海洛因|冰毒|摇头丸|K粉", "drugs"),
    (r"吸毒|贩毒", "drug_use"),
    # 赌博
    (r"赌博|赌钱|下注", "gambling"),
)


# ═════════════════════════════════════════════════════════════
# 现实实体（仅都市题材检测）
# ═════════════════════════════════════════════════════════════
REAL_WORLD_ENTITY_TOKENS: tuple[tuple[str, str], ...] = (
    ("阿里巴巴", "company"),
    ("腾讯", "company"),
    ("百度", "company"),
    ("字节跳动", "company"),
    ("华为", "company"),
    ("小米", "company"),
    ("京东", "company"),
    ("美团", "company"),
    ("抖音", "platform"),
    ("微信", "platform"),
    ("微博", "platform"),
    ("知乎", "platform"),
    ("B站", "platform"),
    ("哔哩哔哩", "platform"),
    ("淘宝", "platform"),
    ("天猫", "platform"),
    ("拼多多", "platform"),
    ("北京", "city"),
    ("上海", "city"),
    ("广州", "city"),
    ("深圳", "city"),
    ("杭州", "city"),
    ("成都", "city"),
    ("清华", "school"),
    ("北大", "school"),
    ("复旦大学", "school"),
    ("浙江大学", "school"),
    ("习近平", "person"),
    ("毛泽东", "person"),
    ("邓小平", "person"),
    ("李克强", "person"),
    ("中国共产党", "party"),
    ("国务院", "gov"),
    ("中央政府", "gov"),
    ("人民银行", "gov"),
    ("证监会", "gov"),
    ("银保监会", "gov"),
    ("新冠", "virus"),
    ("疫情", "event"),
)


def analyze_content_policy(
    text: str,
    quality_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    分析内容策略，返回检测结果。

    Args:
        text: 要检测的文本
        quality_profile: 质量配置文件

    Returns:
        dict: 包含检测结果的字典
    """
    quality_profile = quality_profile or {}
    genre = quality_profile.get("genre", "")
    is_urban = genre in {"urban", "都市", "city", "modern"}

    profanity_detail = _classify_profanity(text)

    # 检测敏感词
    sensitive_hits: list[dict[str, Any]] = []
    for pattern, code in SENSITIVE_TERMS:
        for match in re.finditer(pattern, text):
            sensitive_hits.append({
                "match": match.group(),
                "code": code,
                "position": match.start(),
            })

    # 检测现实实体（仅都市题材）
    real_world_entity_hits: list[dict[str, Any]] = []
    if is_urban:
        for token, entity_type in REAL_WORLD_ENTITY_TOKENS:
            count = text.count(token)
            if count > 0:
                real_world_entity_hits.append({
                    "token": token,
                    "type": entity_type,
                    "count": count,
                })

    # 构建 failures 列表（只有 high 级别的脏话和敏感词会导致不通过）
    failures: list[dict[str, Any]] = []

    # high 级别脏话 → 不通过
    if profanity_detail["total_high"] > 0:
        failures.append({
            "code": "profanity_high",
            "message": f"检测到严重脏话 {profanity_detail['total_high']} 处",
            "severity": "high",
        })

    # 敏感词 → 不通过
    if sensitive_hits:
        failures.append({
            "code": "sensitive_content",
            "message": f"检测到敏感内容 {len(sensitive_hits)} 处",
            "severity": "high",
        })

    # 构建 warnings 列表（medium、low 级别脏话和频率警告）
    warnings: list[dict[str, Any]] = []

    # medium 级别脏话 → 警告
    if profanity_detail["total_medium"] > 0:
        warnings.append({
            "code": "profanity_medium",
            "message": f"检测到中等脏话 {profanity_detail['total_medium']} 处（多为对话中的口语表达）",
            "severity": "medium",
        })

    # low 级别脏话 → 提示
    if profanity_detail["total_low"] > 0:
        warnings.append({
            "code": "profanity_low",
            "message": f"检测到口语化表达 {profanity_detail['total_low']} 处",
            "severity": "low",
        })

    # 频率警告
    if profanity_detail["frequency_warning"]:
        warnings.append({
            "code": "profanity_frequency",
            "message": profanity_detail["frequency_message"],
            "severity": "medium",
        })

    # 现实实体 → 警告（仅都市题材）
    if real_world_entity_hits:
        warnings.append({
            "code": "real_world_entity",
            "message": f"检测到现实世界实体 {len(real_world_entity_hits)} 个，建议使用架空设定",
            "severity": "low",
        })

    # 判断是否通过
    passed = len(failures) == 0

    # 构建摘要
    summary_parts = []
    if profanity_detail["total_high"] > 0:
        summary_parts.append(f"严重脏话 {profanity_detail['total_high']} 处")
    if profanity_detail["total_medium"] > 0:
        summary_parts.append(f"中等脏话 {profanity_detail['total_medium']} 处")
    if profanity_detail["total_low"] > 0:
        summary_parts.append(f"口语表达 {profanity_detail['total_low']} 处")
    if sensitive_hits:
        summary_parts.append(f"敏感内容 {len(sensitive_hits)} 处")
    if profanity_detail["frequency_warning"]:
        summary_parts.append("脏话过于密集")

    summary = "；".join(summary_parts) if summary_parts else "内容合规"

    # 保持向后兼容的字段
    profanity_hits = profanity_detail["high_hits"] + profanity_detail["medium_hits"] + profanity_detail["low_hits"]

    return {
        "passed": passed,
        "profile": genre or "default",
        "urban_fiction_required": is_urban,

        # 向后兼容字段
        "profanity_hits": profanity_hits,
        "sensitive_hits": sensitive_hits,
        "real_world_entity_hits": real_world_entity_hits,
        "failures": failures,

        # 新增字段
        "warnings": warnings,
        "profanity_detail": profanity_detail,
        "summary": summary,
    }


def content_generation_contract(quality_profile: dict[str, Any] | None = None) -> str:
    """
    返回生成安全约束的 Prompt 文本。

    Args:
        quality_profile: 质量配置文件

    Returns:
        str: 安全约束 Prompt
    """
    quality_profile = quality_profile or {}
    genre = quality_profile.get("genre", "")
    is_urban = genre in {"urban", "都市", "city", "modern"}

    lines = [
        "【内容安全与合规要求】",
        "1. 禁止出现政治敏感、色情、暴力、毒品、赌博等违法违规内容",
        "2. 角色对话中可以适当使用口语化表达（如卧槽、牛逼等），但不得使用严重侮辱性脏话",
        "3. 叙述部分应保持文明，避免使用脏话",
        "4. 脏话使用应适度，不得过于密集",
    ]

    if is_urban:
        lines.append("5. 都市题材采用完全架空设定，所有人名、地名、公司、平台、品牌均为虚构，不得使用现实世界实体")

    return "\n".join(lines)
