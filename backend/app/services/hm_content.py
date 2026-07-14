"""NC-HM-002 + NC-HM-003: Platform matching, audience, compliance risk + content generation pipeline.

Generation helpers in this module must use the real AI gateway. They must not
return fixed templates or deterministic "viral title" strings, because that
would look like AI output without creating ai_calls provenance.
"""
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

def _require_project(project_id: str) -> str:
    if not project_id:
        raise ValueError("project_id is required for real AI generation")
    return project_id


def generate_article_variants(topic: dict, platform: str, project_id: str = "") -> dict:
    """NC-HM-003: Generate multi-platform article drafts from a hot topic via real AI."""
    from app.gateway import complete
    from app.prompt_registry import sanitize_untrusted
    from app.services.social_media import PLATFORMS

    project_id = _require_project(project_id)
    p = PLATFORMS.get(platform, {})
    if not p: return {"status": "error", "message": f"unknown platform: {platform}"}
    output = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="gen_daily_brief", prompt_name="social.gen_hotspot_content",
        variables={
            "hotspot_title": sanitize_untrusted(str(topic.get("title", "")), 200),
            "hotspot_source": sanitize_untrusted(str(topic.get("source", "")), 80),
            "hotspot_url": sanitize_untrusted(str(topic.get("url", "")), 1000),
            "platform": p.get("name", platform),
            "style": p.get("style", ""),
        },
    )
    return {"status": "ok", "platform": platform, "draft": output,
            "meta_fields": ["title", "summary", "tags", "cover_text", "cta"]}


def generate_title_variants(topic: str, count: int = 5, project_id: str = "") -> list[str]:
    """NC-HM-003: Generate multiple title variants for A/B testing via real AI."""
    from app.gateway import complete
    from app.prompt_registry import sanitize_untrusted

    project_id = _require_project(project_id)
    output = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="hm_title_variants", prompt_name="social.hm_title_variants",
        variables={"topic": sanitize_untrusted(topic, 200), "count": min(max(count, 1), 20)},
    )
    titles = output.get("titles", [])
    return [str(title) for title in titles][:count]


def generate_video_script(topic: str, platform: str = "douyin", project_id: str = "") -> dict:
    """NC-HM-003: Generate short video script via real AI."""
    from app.gateway import complete
    from app.prompt_registry import sanitize_untrusted
    from app.services.social_media import VIDEO_PLATFORMS, VIDEO_SCRIPT_FIELDS

    project_id = _require_project(project_id)
    p = VIDEO_PLATFORMS.get(platform, {})
    if not p: return {"status": "error", "message": f"unknown video platform: {platform}"}
    output = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="gen_video_script", prompt_name="social.gen_video_script",
        variables={"topic": sanitize_untrusted(topic, 200), "platform": platform,
                   "max_duration": p.get("max_duration", 60), "style": p.get("style", "")},
    )
    return {"status": "ok", "platform": platform, **output, "fields": VIDEO_SCRIPT_FIELDS}


def generate_material_suggestions(topic: str, content: str, project_id: str = "") -> dict:
    """NC-HM-003: Suggest cover images, charts and data sources via real AI."""
    from app.gateway import complete
    from app.prompt_registry import sanitize_untrusted

    project_id = _require_project(project_id)
    return complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="hm_material_suggestions", prompt_name="social.hm_material_suggestions",
        variables={"topic": sanitize_untrusted(topic, 200), "content": sanitize_untrusted(content, 4000)},
    )
