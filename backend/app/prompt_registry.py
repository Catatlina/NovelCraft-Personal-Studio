from __future__ import annotations

from string import Template
from typing import Any


PROMPT_SEEDS = [
    ("bootstrap.gen_titles", "1.0.0", "mock", "请基于灵感生成 3 个小说书名候选。\\n灵感：$idea\\n题材：$genre\\n风格：$style"),
    ("bootstrap.gen_synopsis", "1.0.0", "mock", "请为书名 $selected_title 生成简介和卖点。\\n灵感：$idea"),
    ("bootstrap.gen_worldview", "1.0.0", "mock", "请为 $selected_title 构建可连载长篇世界观。"),
    ("bootstrap.gen_characters", "1.0.0", "mock", "请为 $selected_title 生成 3 到 6 位核心人物。"),
    ("bootstrap.gen_outline", "1.0.0", "mock", "请为 $selected_title 生成三卷总纲。"),
    ("bootstrap.gen_chapter1", "1.0.0", "mock", "请按 $style 写 $selected_title 第一章。"),
    ("bootstrap.review_7dim", "1.0.0", "mock", "请对第一章做七维审核并输出 JSON。"),
    ("editor.polish", "1.0.0", "mock", "请润色选中文本，保持含义和风格。\\n$selection"),
    ("editor.rewrite", "1.0.0", "mock", "请按要求改写选中文本。\\n要求：$instruction\\n$selection"),
    ("editor.continue", "1.0.0", "mock", "请续写选中文本。\\n要求：$instruction\\n$selection"),
    # M2: narrative engine
    ("narrative.summarize_chapter", "1.0.0", "deepseek", "总结章节内容。$instructions\\n\\n$body"),
    ("narrative.summarize_volume", "1.0.0", "deepseek", "汇总卷内容。$instructions\\n\\n$body"),
    ("narrative.summarize_book", "1.0.0", "deepseek", "总结全书状态。$instructions\\n\\n$body"),
    ("narrative.gen_next_chapter", "1.0.0", "deepseek", "根据上下文写下一章。\\n$context\\n\\n请输出JSON: {\\\"chapter\\\":{\\\"title\\\":\\\"\\\",\\\"body\\\":[\\\"段落\\\"]}}"),
]


OUTPUT_CONTRACTS: dict[str, str] = {
    "gen_titles": '{"title_candidates":["《书名一》","《书名二》","《书名三》"]}',
    "gen_synopsis": '{"synopsis":"一句简介","selling_points":["卖点一","卖点二"]}',
    "gen_worldview": '{"worldview":{"name":"世界观名称","rules":["规则一","规则二","规则三"]}}',
    "gen_characters": '{"characters":[{"name":"姓名","role":"角色定位","arc":"人物弧线"}]}',
    "gen_outline": '{"outline":["第一卷：...","第二卷：...","第三卷：..."]}',
    "gen_chapter1": '{"chapter":{"title":"第一章 标题","body":["段落一","段落二"]}}',
    "review_7dim": '{"score":80,"dimensions":{"hook":80,"character":80,"world":80,"pace":80,"emotion":80,"clarity":80,"serial_potential":80},"issues":["问题一"]}',
    "editor_polish": '{"text":"润色后的文本"}',
    "editor_rewrite": '{"text":"改写后的文本"}',
    "editor_continue": '{"text":"续写后的文本"}',
    "summarize_chapter": '{"summary":"章节摘要"}',
    "summarize_volume": '{"summary":"卷摘要"}',
    "summarize_book": '{"summary":"全书摘要"}',
    "gen_next_chapter": '{"chapter":{"title":"第N章 标题","body":["段落一"]}}',
}


def render_prompt(template: str, variables: dict[str, Any]) -> str:
    safe_values = {key: _stringify(value) for key, value in variables.items()}
    return Template(template).safe_substitute(safe_values)


def _stringify(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return str(value)
    return "" if value is None else str(value)
