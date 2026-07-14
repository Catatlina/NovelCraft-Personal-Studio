"""M3: Social media content types + fan-out system."""
from __future__ import annotations

PLATFORMS = {
    "wechat": {"name": "微信公众号", "type": "wechat_article", "style": "深度长文，排版精美，引导关注"},
    "toutiao": {"name": "今日头条", "type": "toutiao_article", "style": "SEO标题，关键词优化，推荐算法适配"},
    "xiaohongshu": {"name": "小红书", "type": "xhs_note", "style": "短笔记，emoji风格，标签系统，封面建议"},
    "douyin": {"name": "抖音", "type": "douyin_video", "style": "短视频脚本，强开头，口播化，适合 30-60 秒"},
    "zhihu": {"name": "知乎", "type": "zhihu_answer", "style": "深度分析，专业引用，问答格式"},
    "baijia": {"name": "百家号", "type": "baijia_article", "style": "百度SEO，关键词密度优化"},
    "dayu": {"name": "大鱼号", "type": "dayu_article", "style": "UC推荐适配"},
    "wangyi": {"name": "网易号", "type": "wangyi_article", "style": "跟帖引导"},
    "medium": {"name": "Medium", "type": "medium_article", "style": "英文长文，SEO优化"},
    "substack": {"name": "Substack", "type": "substack_newsletter", "style": "邮件标题优化，订阅引导"},
    "twitter": {"name": "X/Twitter", "type": "x_thread", "style": "线程拆分，hook开头"},
}

PLATFORM_META_FIELDS = {
    "wechat": ["title","summary","tags","cover_text","cta"],
    "toutiao": ["seo_title","keywords","summary","tags"],
    "xiaohongshu": ["title","tags","cover_text","cta"],
    "zhihu": ["question","answer_summary","tags"],
    "baijia": ["seo_title","keywords","summary"],
    "medium": ["seo_title","summary","tags","cta"],
    "substack": ["email_subject","summary","cta"],
    "twitter": ["hook","thread_text","hashtags"],
}

FANOUT_PROMPT = """将以下内容改写为{platform_name}格式。
源内容：{source_content}
风格要求：{style_guide}
输出JSON: {{"title":"","body":["段落"],"meta":{{"tags":["标签"],"summary":"摘要"}}}}"""

VIDEO_PLATFORMS = {
    "douyin": {"name": "抖音", "max_duration": 60, "style": "快节奏，强反转，口语化，前3秒定生死"},
    "xiaohongshu_video": {"name": "小红书视频", "max_duration": 120, "style": "精致，生活方式，清单体"},
    "bilibili": {"name": "B站", "max_duration": 600, "style": "深度，弹幕互动，中二风格"},
}

VIDEO_SCRIPT_FIELDS = ["hook_3s", "scenes", "narration", "dialogue", "camera_tips", "title", "cover_text", "cta"]
