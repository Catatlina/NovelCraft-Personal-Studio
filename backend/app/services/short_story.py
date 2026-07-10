"""M3: Short story generation system — 5 templates + workflow."""
from __future__ import annotations

SHORT_STORY_TEMPLATES = {
    "flash": {"name": "微小说", "max_words": 2000, "structure": "hook→conflict→twist"},
    "emotional": {"name": "情感故事", "max_words": 5000, "structure": "setup→conflict→resolution"},
    "suspense": {"name": "悬疑短篇", "max_words": 8000, "structure": "mystery→clues→reveal"},
    "viral": {"name": "爆款短篇", "max_words": 5000, "structure": "hook→escalation→climax→resolution"},
    "dialogue": {"name": "对话体", "max_words": 3000, "structure": "dialogue-driven narrative"},
}

SHORT_STORY_NODES = [
    ("s1", "agent", "ShortStory", "生成标题候选", "gen_short_titles"),
    ("s2", "human", None, "选定标题", None),
    ("s3", "agent", "ShortStory", "生成短篇全文", "gen_short_story"),
    ("s4", "agent", "Reviewer", "质量审核", "review_short"),
]

SHORT_PROMPTS = [
    ("shortstory.gen_titles", "1.0.0", "deepseek",
     "为以下短篇创意生成3个标题。\\n灵感：$idea\\n题材：$genre\\n模板：$template\\n输出JSON: {\\\"titles\\\":[\\\"标题1\\\",\\\"标题2\\\",\\\"标题3\\\"]}"),
    ("shortstory.gen_story", "1.0.0", "deepseek",
     "按照「$template」模板写短篇。\\n标题：$title\\n灵感：$idea\\n风格：$style\\n字数：$max_words字以内\\n输出JSON: {\\\"story\\\":{\\\"title\\\":\\\"\\\",\\\"body\\\":[\\\"段落一\\\",\\\"段落二\\\"]}}"),
    ("shortstory.review", "1.0.0", "deepseek",
     "审核短篇质量。输出JSON: {\\\"score\\\":80,\\\"hooks\\\":\\\"开头评价\\\",\\\"pacing\\\":\\\"节奏评价\\\",\\\"ending\\\":\\\"结尾评价\\\",\\\"issues\\\":[\\\"问题\\\"]}"),
]

SHORT_CONTRACTS = {
    "gen_short_titles": '{"titles":["标题1","标题2","标题3"]}',
    "gen_short_story": '{"story":{"title":"标题","body":["段落一","段落二"]}}',
    "review_short": '{"score":80,"hooks":"开头评价","pacing":"节奏评价","ending":"结尾评价","issues":["问题"]}',
}
