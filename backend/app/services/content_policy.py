"""Generation-first content and fictional-world policy for web novels.

脏话检测策略调整（基于 39580 本网文扫描报告）：
- 所有脏话均设为 info 级别：只记录命中，不警告，不阻塞质量门
- 第一类（非脏话）：完全从脏话检测中移除
- 第二类（轻微口语）：info 级别，只记录
- 第三类（严重脏话）：info 级别，只记录（用户要求不阻塞）
- 真正拦截的只有：政治敏感、色情、暴力、毒品、赌博等违法违规内容
- 频率检测：保留统计，20 次以上提示"使用较多"，不阻塞
"""
from __future__ import annotations

import re
from typing import Any


# ═════════════════════════════════════════════════════════════
# 第一类：完全不是脏话，从脏话检测中移除（不检测）
# ═════════════════════════════════════════════════════════════
# 这些是网文常用表达，根本不算脏话：
# - 震惊、绝了、离谱、此子、脸色大变、倒吸一口凉气、瞳孔一缩
# - 恐怖如斯、不可战胜、吓尿了、我滴妈、心态崩了、卧槽无情
# - 老子（自称）
# - 大胆、放肆、小辈、匹夫、老贼（古风常用词）
# - 蝼蚁（比喻用法）
# - 不知死活、不自量力、不知天高地厚、不知好歹、岂有此理（成语/常用表达）


# ═════════════════════════════════════════════════════════════
# Info 级别脏话（第二类 + 第三类）
# 只记录命中，不警告，不阻塞质量门
# ═════════════════════════════════════════════════════════════
INFO_PROFANITY_PATTERNS: tuple[tuple[str, str], ...] = (
    # ── 第二类：轻微口语/骂人 ──
    # 口语感叹词
    (r"靠|我去|该死|妈的|找死|可恶|卧槽|尼玛|去死|特么", "mild_expletive"),
    (r"我靠|你妹|蠢货|混账|滚蛋|坑爹|蛋疼|放屁|扯淡|你大爷", "mild_insult"),
    # 口语化表达
    (r"该死的|他娘的|奶奶的|我日|天杀的|姥姥的", "mild_colloquial"),
    # 侮辱性称呼（轻微）
    (r"废物|畜生|贱人|他妈的|狐狸精", "mild_insult_term"),
    # 牛逼等口语
    (r"牛逼|牛B|牛批|牛掰", "mild_praise_colloquial"),

    # ── 第三类：严重脏话，但用户要求也只提示不阻塞 ──
    # 严重侮辱性称呼
    (r"傻逼|傻比|煞笔|煞筆|傻屌|草泥马|草泥馬", "severe_insult_term"),
    # 针对性辱骂
    (r"操你妈|操你媽|妈卖批|媽賣批|操他妈的|操他媽的", "severe_targeted_insult"),
    (r"操你|日你|干你", "targeted_insult"),
    # 第三人称辱骂
    (r"操他|操她|日他|日她|干他|干她", "third_person_insult"),
    # 狗日的等
    (r"狗日的|狗娘养的|狗孃養的", "medium_insult"),
    # 我操等
    (r"我操|我艹|我擦", "strong_expletive"),
    # 色情相关侮辱
    (r"婊子|淫贼|臭流氓|登徒子|贱货|荡妇|骚货|骚蹄子", "sexual_insult"),
    # 歧义单字（需要上下文判断）
    (r"(?:^|[\s，。！？、:：])草(?=[\s，。！？、:：]|$)", "ambiguous_expletive"),
    (r"(?:^|[\s，。！？、:：])操(?=[\s，。！？、:：]|$)", "ambiguous_expletive"),
    (r"(?:^|[\s，。！？、:：])日(?=[\s，。！？、:：]|$)", "ambiguous_expletive"),
)

# 保持向后兼容
PROFANITY_PATTERNS = INFO_PROFANITY_PATTERNS


# ═════════════════════════════════════════════════════════════
# 频率检测阈值
# ═════════════════════════════════════════════════════════════
PROFANITY_FREQUENCY_WARNING_THRESHOLD = 20  # 超过 20 次提示"脏话使用较多"，不阻塞


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

    注意：所有脏话均为 info 级别，只记录不阻塞。

    Args:
        text: 要检测的文本

    Returns:
        dict: 包含各级别命中详情的字典
    """
    info_hits: list[dict[str, Any]] = []

    # 检测 info 级别脏话（所有脏话都是 info 级别）
    for pattern, code in INFO_PROFANITY_PATTERNS:
        for match in re.finditer(pattern, text):
            start, end = match.span()
            in_dialogue = _is_in_dialogue(text, start, end)
            hit = {
                "match": match.group(),
                "code": code,
                "position": start,
                "in_dialogue": in_dialogue,
                "original_level": "info",
                "effective_level": "info",  # 所有脏话都是 info 级别，不再降级
            }
            info_hits.append(hit)

    # 计算总数
    total_info = len(info_hits)
    total_profanity = total_info

    # 频率检测（只提示，不阻塞）
    frequency_warning = False
    frequency_message = ""
    if total_profanity > PROFANITY_FREQUENCY_WARNING_THRESHOLD:
        frequency_warning = True
        frequency_message = f"本章脏话/口语出现 {total_profanity} 次，使用较多"

    return {
        "info_hits": info_hits,
        "total_info": total_info,
        "total_profanity": total_profanity,
        "frequency_warning": frequency_warning,
        "frequency_message": frequency_message,
        # 保持向后兼容的字段
        "high_hits": [],
        "medium_hits": [],
        "low_hits": info_hits,  # 把 info 放到 low 里，保持向后兼容
        "total_high": 0,
        "total_medium": 0,
        "total_low": total_info,
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

# Ordinary non-graphic conflict is part of fictional web-novel narration. It
# is still recorded for review, but it should not make every xuanhuan scene
# containing "杀人" fail before the author can inspect it. Political,
# sexual, drug, gambling, self-harm and all other sensitive categories remain
# hard blockers; projects can explicitly turn this allowance off.
FICTIONAL_VIOLENCE_GENRES = frozenset({
    "xuanhuan", "suspense", "science_fiction", "history", "game", "fengshen",
})


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

    注意：所有脏话均为 info 级别，只记录不阻塞。
    只有敏感词（政治、色情、暴力、毒品等）会导致不通过。

    Args:
        text: 要检测的文本
        quality_profile: 质量配置文件

    Returns:
        dict: 包含检测结果的字典
    """
    quality_profile = quality_profile or {}
    genre = quality_profile.get("genre", "")
    is_urban = genre in {"urban", "都市", "city", "modern"}
    fictional_setting_required = bool(quality_profile.get("fictional_setting_required", False))
    allow_fictional_violence = bool(
        quality_profile.get("allow_fictional_violence", genre in FICTIONAL_VIOLENCE_GENRES)
    )

    profanity_detail = _classify_profanity(text)

    # 检测敏感词
    sensitive_hits: list[dict[str, Any]] = []
    allowed_fictional_violence_hits: list[dict[str, Any]] = []
    blocking_sensitive_hits: list[dict[str, Any]] = []
    for pattern, code in SENSITIVE_TERMS:
        for match in re.finditer(pattern, text):
            hit = {
                "match": match.group(),
                "code": code,
                "position": match.start(),
            }
            sensitive_hits.append(hit)
            if code == "violence" and allow_fictional_violence:
                allowed_fictional_violence_hits.append(hit)
            else:
                blocking_sensitive_hits.append(hit)

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

    # 构建 failures/warnings 列表（脏话和架空非露骨冲突只提示）
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    # 敏感词 → 不通过
    if blocking_sensitive_hits:
        failures.append({
            "code": "sensitive_content",
            "message": f"检测到敏感内容 {len(blocking_sensitive_hits)} 处",
            "severity": "high",
        })

    if allowed_fictional_violence_hits:
        warnings.append({
            "code": "fictional_violence",
            "message": f"架空题材包含非露骨冲突词 {len(allowed_fictional_violence_hits)} 处，仅记录供作者复核",
            "severity": "low",
        })

    # 频率警告（只提示，不阻塞）
    if profanity_detail["frequency_warning"]:
        warnings.append({
            "code": "profanity_frequency",
            "message": profanity_detail["frequency_message"],
            "severity": "low",
        })

    # 现实实体默认只提醒，爽文可以使用现实地名作为叙事锚点；项目明确
    # 要求架空设定时才升级为硬失败。政治/敏感实体仍由 sensitive_hits 拦截。
    if real_world_entity_hits:
        entity_issue = {
            "code": "real_world_entity",
            "message": f"检测到现实世界实体 {len(real_world_entity_hits)} 个，建议使用架空设定",
            "severity": "high" if fictional_setting_required else "low",
        }
        if fictional_setting_required:
            failures.append(entity_issue)
        else:
            entity_issue["message"] = (
                f"检测到现实世界实体 {len(real_world_entity_hits)} 个；当前爽文模式仅提醒，"
                "可在项目配置中开启架空设定硬约束"
            )
            warnings.append(entity_issue)

    # 判断是否通过（只有敏感词会导致不通过）
    passed = len(failures) == 0

    # 构建摘要
    summary_parts = []
    if profanity_detail["total_info"] > 0:
        summary_parts.append(f"口语/脏话 {profanity_detail['total_info']} 处")
    if blocking_sensitive_hits:
        summary_parts.append(f"敏感内容 {len(blocking_sensitive_hits)} 处")
    elif allowed_fictional_violence_hits:
        summary_parts.append(f"架空冲突词 {len(allowed_fictional_violence_hits)} 处（仅提示）")
    if profanity_detail["frequency_warning"]:
        summary_parts.append("使用较多")

    summary = "；".join(summary_parts) if summary_parts else "内容合规"

    # 保持向后兼容的字段
    profanity_hits = profanity_detail["info_hits"]

    return {
        "passed": passed,
        "profile": genre or "default",
        "fictional_setting_required": fictional_setting_required,
        # Legacy field retained, but now reports the actual configured gate
        # instead of implying that every urban profile is fully fictional.
        "urban_fiction_required": fictional_setting_required,

        # 向后兼容字段
        "profanity_hits": profanity_hits,
        "sensitive_hits": sensitive_hits,
        "blocking_sensitive_hits": blocking_sensitive_hits,
        "allowed_fictional_violence_hits": allowed_fictional_violence_hits,
        "allow_fictional_violence": allow_fictional_violence,
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
    fictional_setting_required = bool(quality_profile.get("fictional_setting_required", False))
    allow_fictional_violence = bool(
        quality_profile.get("allow_fictional_violence", genre in FICTIONAL_VIOLENCE_GENRES)
    )

    lines = [
        "【内容安全与合规要求】",
        "1. 不得出现敏感、违法、色情、仇恨、极端或露骨暴力表达；禁止政治敏感、毒品、赌博等违法违规内容",
        "2. 角色对话中可以适当使用口语化表达和脏话，符合人物性格和场景",
        "3. 脏话使用应适度，符合人物身份和剧情需要",
    ]

    if allow_fictional_violence:
        lines.append("4. 架空题材允许为剧情服务的非露骨冲突和伤亡词，但不得描写现实违法操作、血腥细节或极端暴力；冲突必须符合世界观与人物因果")

    if is_urban and fictional_setting_required:
        lines.append("4. 都市题材采用完全架空的现代社会：所有人名、地名、公司、平台、品牌均为虚构，不得使用现实世界实体")
    elif is_urban:
        lines.append("4. 都市爽文可以使用现实地名作为叙事锚点，但不得涉及现实政治、敏感人物或现实事件的危险影射")

    return "\n".join(lines)
