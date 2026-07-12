"""NC-HM-002 + NC-HM-003: Platform matching, audience, compliance risk + content generation pipeline.
⚠️ DEPRECATED — No active callers (audit 2026-07-12). Preserved for reference."""
from __future__ import annotations
import json, os
from app.db import connect, new_id, encode

# ===== NC-HM-002: Platform matching / audience / risk =====

PLATFORM_AUDIENCE = {
    "wechat": {"age_range": "25-45", "interests": ["深度阅读", "职场", "生活"], "tone": "专业可信"},
    "toutiao": {"age_range": "30-55", "interests": ["新闻", "社会", "娱乐"], "tone": "直白有力"},
    "xiaohongshu": {"age_range": "18-35", "interests": ["生活方式", "美妆", "旅行"], "tone": "亲切分享"},
    "zhihu": {"age_range": "20-40", "interests": ["知识", "观点", "深度分析"], "tone": "理性思辨"},
    "baijia": {"age_range": "25-50", "interests": ["百科", "科技", "教育"], "tone": "专业科普"},
    "dayu": {"age_range": "20-40", "interests": ["娱乐", "搞笑", "奇闻"], "tone": "轻松有趣"},
    "wangyi": {"age_range": "25-45", "interests": ["社会", "娱乐", "体育"], "tone": "跟帖互动"},
    "medium": {"age_range": "25-50", "interests": ["科技", "创业", "文化"], "tone": "深度叙事"},
    "substack": {"age_range": "25-55", "interests": ["独立观点", "深度分析", "小众领域"], "tone": "个人化"},
    "twitter": {"age_range": "18-45", "interests": ["时事", "科技", "吐槽"], "tone": "短平快/幽默"},
}

COMPLIANCE_RULES = {
    "wechat": ["禁止诱导分享", "禁止虚假信息", "金融需资质"],
    "toutiao": ["禁止标题党", "禁止低俗内容", "禁止政治敏感"],
    "xiaohongshu": ["禁止虚假种草", "禁止医疗宣传", "需标明广告"],
    "zhihu": ["禁止人身攻击", "禁止抄袭", "禁止垃圾广告"],
    "baijia": ["禁止伪原创", "禁止低质内容", "禁止违规推广"],
}


def match_platforms_for_topic(topic: str, category: str = "") -> list[dict]:
    """NC-HM-002: Score each platform's suitability for a given topic."""
    results = []
    for key, audience in PLATFORM_AUDIENCE.items():
        score = 50
        # Category matching
        if category == "tech" and key in ("zhihu", "medium", "baijia"): score += 20
        if category == "entertainment" and key in ("dayu", "twitter", "xiaohongshu"): score += 20
        if category == "lifestyle" and key == "xiaohongshu": score += 25
        if category == "politics" and key in ("toutiao", "wechat"): score += 15
        # Compliance pre-check
        risks = get_compliance_risks(key, topic)
        if risks: score -= len(risks) * 10
        results.append({
            "platform": key, "name": audience.get("name", key),
            "suitability": min(100, max(0, score)),
            "audience": audience, "risks": risks,
        })
    return sorted(results, key=lambda x: x["suitability"], reverse=True)


def get_compliance_risks(platform: str, content: str) -> list[str]:
    """NC-HM-002: Check content against platform-specific rules."""
    from app.services.fusion_browseract_insprira import check_compliance
    rules = COMPLIANCE_RULES.get(platform, [])
    risks = []
    # General violation check
    check = check_compliance(content)
    if not check.get("safe_to_publish"): risks.append("违禁词命中")
    # Platform-specific
    if platform == "wechat" and "分享" in content: risks.append("小心诱导分享")
    if platform == "toutiao" and len(content.split()) < 50: risks.append("内容过短")
    return risks


# ===== NC-HM-003: Content generation pipeline =====

def generate_article_variants(topic: dict, platform: str) -> dict:
    """NC-HM-003: Generate multi-platform article drafts from a hot topic."""
    from app.services.social_media import PLATFORMS
    p = PLATFORMS.get(platform, {})
    if not p: return {"status": "error", "message": f"unknown platform: {platform}"}
    return {
        "status": "ok", "platform": platform,
        "draft": f"# {topic.get('title','')}\n\n风格: {p['style']}\n受众: {p['name']}",
        "meta_fields": ["title", "summary", "tags", "cover_text", "cta"],
    }


def generate_title_variants(topic: str, count: int = 5) -> list[str]:
    """NC-HM-003: Generate multiple title variants for A/B testing."""
    variants = [
        f"震惊！{topic}背后的真相",
        f"{topic}，你不知道的5个秘密",
        f"为什么人人都该关注{topic}",
        f"深度解析：{topic}将如何改变我们的生活",
        f"{topic}：一个被忽视的底层逻辑",
    ]
    return variants[:count]


def generate_video_script(topic: str, platform: str = "douyin") -> dict:
    """NC-HM-003: Generate short video script (douyin/xiaohongshu/bilibili)."""
    from app.services.social_media import VIDEO_PLATFORMS, VIDEO_SCRIPT_FIELDS
    p = VIDEO_PLATFORMS.get(platform, {})
    if not p: return {"status": "error", "message": f"unknown video platform: {platform}"}

    max_dur = p.get("max_duration", 60)
    scenes = [
        {"time": "0-3s", "action": "hook开头", "text": f"关于'{topic}'，99%的人都不知道的真相"},
        {"time": f"3-{max_dur//3}s", "action": "核心内容", "text": f"深入解析{topic}"},
        {"time": f"{max_dur//3}-{max_dur*2//3}s", "action": "案例/论证", "text": "真实案例与数据支撑"},
        {"time": f"{max_dur*2//3}-{max_dur}s", "action": "结尾CTA", "text": "关注我，每天分享更多干货"},
    ]
    return {
        "status": "ok", "platform": platform, "max_duration_sec": max_dur,
        "title": f"{topic} — {p['style']}", "scenes": scenes,
        "narration_style": p["style"], "cover_text": f"#{topic} #短视频",
        "fields": VIDEO_SCRIPT_FIELDS,
    }


def generate_material_suggestions(topic: str, content: str) -> dict:
    """NC-HM-003: Suggest cover images, charts, data sources."""
    return {
        "cover_image_prompt": f"Minimalist illustration about {topic}, dark theme, neon orange accents",
        "suggested_charts": ["趋势对比图", "受众画像图"] if "trend" in content.lower() else ["概念图", "流程图"],
        "data_sources": ["百度指数", "微信指数", "微博热搜趋势"],
        "recommended_tags": [topic[:8], "热点", "分析"],
    }
