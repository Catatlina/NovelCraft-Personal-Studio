"""
Ten-Layer Book Analysis Model (十层分析模型)

Analyzes scanned books from ranking/import across 10 depth layers:

Layer 1  BookProfile     — local: parse metadata into structured JSON
Layer 2  GenreReport     — local: genre frequencies, co-occurrence, TOP100 tags
Layer 3  SellingPoints   — local: regex-based selling-point extraction
Layer 4  Golden3Chapter  — AI: first 3 chapters structural analysis
Layer 5  PlotRhythm      — AI: pacing, conflicts, reversals, suspense
Layer 6  Character       — AI: protagonist / antagonist / supporting cast
Layer 7  WorldBuilding   — AI: world setting, power systems, rules
Layer 8  StyleReport     — AI: writing style metrics
Layer 9  ReaderReport    — AI: reader feedback / comment patterns
Layer 10 AIInsight       — AI: synthesis → market trends, viral formulas, innovation

Layers 1-3 run local computation (fast, no AI cost).
Layers 4-10 call gateway.complete() with detailed prompts for deep analysis.
Each layer fails independently — errors are collected, not propagated.
"""

from __future__ import annotations

import collections
import concurrent.futures
import json
import logging
import re
import time
from typing import Any, Callable

from app.gateway import BudgetExceeded, ProviderError, complete

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────
_AI_LAYER_TIMEOUT_SECONDS = 60

# ── Selling-point hook patterns (Layer 3) ─────────────────────────────────
# Matched against book titles + descriptions to identify common viral hooks
_HOOK_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # (hook_category, hook_label, compiled_regex)
    ("系统流", "系统/面板", re.compile(r"系统|面板|属性|技能树|加点")),
    ("穿越流", "穿越", re.compile(r"穿越|穿到|穿成|魂穿|身穿")),
    ("重生流", "重生", re.compile(r"重生|重来|回到(过去|\d+年)|再活")),
    ("签到流", "签到/打卡", re.compile(r"签到|打卡|每日.*奖励")),
    ("抽奖流", "抽奖/彩票/转盘", re.compile(r"抽奖|彩票|转盘|随机.*奖励|幸运转盘")),
    ("末世流", "末世/末日", re.compile(r"末世|末日|丧尸|废土|灾变")),
    ("离婚流", "离婚/分手", re.compile(r"离婚|分手|退婚|悔婚|退亲")),
    ("赘婿流", "赘婿/逆袭", re.compile(r"赘婿|上门|入赘|废材|逆袭|打脸")),
    ("神医流", "神医/医术", re.compile(r"神医|医术|国医|妙手|回春|诊脉")),
    ("修仙流", "修仙/修真", re.compile(r"修仙|修真|仙侠|渡劫|飞升|金丹|元婴")),
    ("都市流", "都市/总裁", re.compile(r"都市|总裁|豪门|霸总|千金|继承")),
    ("玄幻流", "玄幻/异界", re.compile(r"玄幻|异界|异世|魔法|斗气|武魂")),
    ("游戏流", "游戏/虚拟现实", re.compile(r"游戏|网游|全息|VR|虚拟现实|副本|打怪")),
    ("种田流", "种田/基建", re.compile(r"种田|基建|种地|养殖|开荒|建设")),
    ("科技流", "科技/黑科技", re.compile(r"科技|黑科技|AI|人工智能|芯片|纳米")),
    ("学霸流", "学霸/学神", re.compile(r"学霸|学神|考试|高考|竞赛|保送")),
    ("悬疑流", "悬疑/推理", re.compile(r"悬疑|推理|侦探|案件|密室|失踪")),
    ("无限流", "无限流/副本", re.compile(r"无限流|无限.*世界|副本.*轮回|试炼")),
    ("娱乐圈", "娱乐圈/文娱", re.compile(r"娱乐圈|文娱|明星|偶像|导演|拍戏|出圈")),
    ("历史流", "历史/架空", re.compile(r"历史|架空|三国|唐宋|明清|穿越.*古")),
    ("异能流", "异能/超能力", re.compile(r"异能|超能|透视|读心|操控|进化")),
    ("空间流", "空间/随身", re.compile(r"空间|随身.*空间|储物|须弥|纳戒")),
    ("灵气复苏", "灵气复苏", re.compile(r"灵气复苏|灵气.*回归|天地.*异变")),
    ("虐恋流", "虐恋/追妻", re.compile(r"虐恋|追妻|火葬场|追夫|替身|白月光")),
    ("甜宠流", "甜宠/恋爱", re.compile(r"甜宠|恋爱|宠妻|宠夫|撒糖|HE")),
]


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any, default: str = "") -> str:
    """Safely convert a value to string."""
    if value is None:
        return default
    return str(value)


# ═══════════════════════════════════════════════════════════════════════════
# TenLayerAnalyzer
# ═══════════════════════════════════════════════════════════════════════════


class TenLayerAnalyzer:
    """Deep book analysis across 10 layers, producing structured JSON per layer.

    Layers 1-3 run locally (no AI cost).
    Layers 4-10 call gateway.complete() for real AI analysis.
    Each layer fails independently — a single failure does not break the batch.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id

    # ── Layer 1: BookProfile (LOCAL) ────────────────────────────────────
    def analyze_book_profile(self, book_profiles: list[dict]) -> dict:
        """Parse book_profiles into structured JSON with standard fields.

        Fields per book: 书名 / 作者 / 平台 / 分类 / 标签 / 字数 / 状态 / 排名 / 评分 / 阅读量
        """
        books: list[dict] = []
        for bp in book_profiles:
            books.append({
                "书名": _safe_str(bp.get("title") or bp.get("name") or bp.get("book_name")),
                "作者": _safe_str(bp.get("author") or bp.get("writer") or bp.get("author_name")),
                "平台": _safe_str(bp.get("platform") or bp.get("source")),
                "分类": _safe_str(bp.get("category") or bp.get("genre") or bp.get("type")),
                "标签": self._extract_tags(bp),
                "字数": _safe_int(bp.get("word_count") or bp.get("words") or bp.get("total_words")),
                "状态": _safe_str(bp.get("status") or bp.get("book_status") or bp.get("update_status"), "连载中"),
                "排名": _safe_int(bp.get("rank") or bp.get("rank_no")),
                "评分": _safe_float(bp.get("rating") or bp.get("score") or bp.get("star")),
                "阅读量": _safe_int(bp.get("views") or bp.get("read_count") or bp.get("total_views")),
            })
        return {
            "layer": "01_BookProfile",
            "status": "succeeded",
            "source": "local",
            "data": {
                "total_books": len(books),
                "books": books,
            },
        }

    @staticmethod
    def _extract_tags(bp: dict) -> list[str]:
        """Extract tags from various possible fields in book profile."""
        tags = bp.get("tags") or bp.get("labels") or bp.get("keywords") or []
        if isinstance(tags, str):
            # Try comma/slash/space separated
            tags = [t.strip() for t in re.split(r"[,/，、\s]+", tags) if t.strip()]
        if isinstance(tags, list):
            return [_safe_str(t) for t in tags if t]
        return []

    # ── Layer 2: GenreReport (LOCAL) ────────────────────────────────────
    def analyze_genre_report(self, book_profiles: list[dict]) -> dict:
        """Count genre frequencies, co-occurrence pairs, TOP100 tags, trends.

        Pure local computation — no AI call needed.
        """
        # ── Genre frequency ──
        genre_counter: collections.Counter = collections.Counter()
        for bp in book_profiles:
            cat = _safe_str(bp.get("category") or bp.get("genre") or bp.get("type")).strip()
            if cat:
                genre_counter[cat] += 1
        genre_freq = genre_counter.most_common()

        # ── Tag frequency (TOP100) ──
        tag_counter: collections.Counter = collections.Counter()
        for bp in book_profiles:
            tags = self._extract_tags(bp)
            for tag in tags:
                if tag:
                    tag_counter[tag] += 1
        top_tags = tag_counter.most_common(100)

        # ── Genre co-occurrence pairs ──
        co_occurrence: collections.Counter = collections.Counter()
        for bp in book_profiles:
            cats = set()
            cat = _safe_str(bp.get("category") or bp.get("genre") or "").strip()
            if cat:
                cats.add(cat)
            # Also check sub_category / tags for secondary genres
            sub = _safe_str(bp.get("sub_category") or bp.get("subgenre") or "").strip()
            if sub:
                cats.add(sub)
            if len(cats) >= 2:
                sorted_cats = sorted(cats)
                for i in range(len(sorted_cats)):
                    for j in range(i + 1, len(sorted_cats)):
                        co_occurrence[(sorted_cats[i], sorted_cats[j])] += 1
        co_occurrence_pairs = [
            {"pair": list(pair), "count": count}
            for pair, count in co_occurrence.most_common(50)
        ]

        # ── Platform distribution ──
        platform_counter: collections.Counter = collections.Counter()
        for bp in book_profiles:
            plat = _safe_str(bp.get("platform") or bp.get("source")).strip()
            if plat:
                platform_counter[plat] += 1

        # ── Status distribution ──
        status_counter: collections.Counter = collections.Counter()
        for bp in book_profiles:
            st = _safe_str(bp.get("status") or bp.get("book_status"), "未知").strip()
            status_counter[st] += 1

        return {
            "layer": "02_GenreReport",
            "status": "succeeded",
            "source": "local",
            "data": {
                "total_books": len(book_profiles),
                "genre_distribution": [{"genre": g, "count": c} for g, c in genre_freq],
                "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
                "co_occurrence_pairs": co_occurrence_pairs,
                "platform_distribution": dict(platform_counter.most_common()),
                "status_distribution": dict(status_counter.most_common()),
            },
        }

    # ── Layer 3: SellingPoints (LOCAL) ──────────────────────────────────
    def analyze_selling_points(self, book_profiles: list[dict]) -> dict:
        """Identify common selling points from titles/descriptions using regex patterns.

        Local computation — no AI call.
        """
        # ── Hook frequency ──
        hook_counter: collections.Counter = collections.Counter()
        book_hooks: list[dict] = []

        for bp in book_profiles:
            title = _safe_str(bp.get("title") or bp.get("name") or bp.get("book_name"))
            desc = _safe_str(bp.get("description") or bp.get("synopsis") or bp.get("intro") or "")
            combined = title + " " + desc

            matched_hooks: list[str] = []
            for category, label, pattern in _HOOK_PATTERNS:
                if pattern.search(combined):
                    hook_counter[(category, label)] += 1
                    matched_hooks.append(label)

            book_hooks.append({
                "书名": title,
                "匹配卖点": matched_hooks,
                "卖点数量": len(matched_hooks),
            })

        # ── Top hooks ──
        top_hooks = [
            {"类别": category, "标签": label, "频次": count}
            for (category, label), count in hook_counter.most_common(50)
        ]

        # ── Title pattern analysis ──
        title_lengths = []
        has_number = 0
        has_question = 0
        has_exclamation = 0
        for bp in book_profiles:
            title = _safe_str(bp.get("title") or bp.get("name") or "")
            if title:
                title_lengths.append(len(title))
                if re.search(r"\d", title):
                    has_number += 1
                if "?" in title or "？" in title:
                    has_question += 1
                if "!" in title or "！" in title:
                    has_exclamation += 1

        total = len(book_profiles) or 1

        return {
            "layer": "03_SellingPoints",
            "status": "succeeded",
            "source": "local",
            "data": {
                "total_books": len(book_profiles),
                "top_hooks": top_hooks,
                "hook_coverage": {
                    "至少一个卖点": sum(1 for bh in book_hooks if bh["卖点数量"] > 0),
                    "无卖点匹配": sum(1 for bh in book_hooks if bh["卖点数量"] == 0),
                },
                "title_patterns": {
                    "avg_title_length": round(sum(title_lengths) / len(title_lengths), 1) if title_lengths else 0,
                    "titles_with_numbers": has_number,
                    "titles_with_numbers_pct": round(has_number / total * 100, 1),
                    "titles_with_question": has_question,
                    "titles_with_exclamation": has_exclamation,
                },
                "book_hooks": book_hooks,
            },
        }

    # ── Layer 4: Golden3Chapter (AI) ────────────────────────────────────
    def analyze_golden_3_chapter(self, book_profiles: list[dict]) -> dict:
        """Analyze first 3 chapters: first sentence, paragraph, conflict, climax, reversal, hook.

        Calls gateway.complete() for deep structural analysis.
        """
        context = self._build_book_context(book_profiles, max_books=20)
        return self._call_ai(
            task_type="analysis_golden_3",
            prompt_name="analysis.golden_3_chapter",
            layer="04_Golden3Chapter",
            system_context=(
                "你是资深网文编辑，专精前三章结构分析。请基于提供的书籍列表，"
                "分析每本书前三章的关键结构要素，输出结构化 JSON。"
            ),
            analysis_instructions=f"""请分析以下书籍的前三章结构。对于每本书，请提取：
1. 开篇第一句 — 是否制造悬念/冲突/好奇
2. 第一段 — 信息密度和代入感
3. 前3000字 — 核心冲突是否建立
4. 第一个冲突点 — 位置和力度
5. 第一个高潮 — 是否在第三章内出现
6. 第一个反转 — 是否有意外/惊喜
7. 开篇钩子类型 — 悬念式/冲突式/设定式/情感式/幽默式
8. 读者留存预测 — 读完前三章后继续阅读的概率

书籍数据：
{context}

请输出 JSON 格式（不要额外文本）：
{{"books": [{{"书名": "...", "第一句分析": "...", "第一段评估": "...", "冲突建立": "是/否", "第一个冲突": "...", "第一个高潮": "...", "反转": "有/无", "钩子类型": "...", "留存预测": "高/中/低"}}], "总体评估": "..."}}""",
        )

    # ── Layer 5: PlotRhythm (AI) ────────────────────────────────────────
    def analyze_plot_rhythm(self, book_profiles: list[dict]) -> dict:
        """Analyze pacing, conflicts per chapter, reversals, suspense patterns.

        Calls gateway.complete() for rhythm analysis.
        """
        context = self._build_book_context(book_profiles, max_books=15)
        return self._call_ai(
            task_type="analysis_plot_rhythm",
            prompt_name="analysis.plot_rhythm",
            layer="05_PlotRhythm",
            system_context=(
                "你是资深网文节奏分析师。请基于书籍元数据，推断并分析每本书的情节节奏、"
                "冲突密度、反转频次和悬念布置策略。"
            ),
            analysis_instructions=f"""请分析以下书籍的情节节奏特征：
1. 每章平均矛盾/冲突数量
2. 反转频次 — 每几章出现一次意外转折
3. 悬念密度 — 每章结尾是否留钩子
4. 节奏类型 — 快节奏/慢热型/波浪型
5. 高潮间隔 — 大概几章一个高潮
6. 爽点分布 — 均匀还是有爆发点

书籍数据：
{context}

请输出 JSON 格式：
{{"books": [{{"书名": "...", "节奏类型": "...", "每章冲突数": N, "反转频次": "...", "悬念密度": "高/中/低", "高潮间隔": "...", "爽点模式": "..."}}], "节奏趋势": "..."}}""",
        )

    # ── Layer 6: Character (AI) ─────────────────────────────────────────
    def analyze_characters(self, book_profiles: list[dict]) -> dict:
        """Extract protagonist / antagonist profiles, supporting cast, relationships.

        Calls gateway.complete() for character analysis.
        """
        context = self._build_book_context(book_profiles, max_books=15)
        return self._call_ai(
            task_type="analysis_characters",
            prompt_name="analysis.characters",
            layer="06_Character",
            system_context=(
                "你是资深网文人设分析师。请基于书籍元数据（书名、分类、标签、简介），"
                "推断每本书的核心人物设定，包括主角、反派、配角体系。"
            ),
            analysis_instructions=f"""请分析以下书籍的人物设定：
对每本书提取：
1. 主角身份/年龄/性格/成长弧 — 从废材到强者？从平凡到传奇？
2. 主角能力/金手指 — 系统？重生记忆？特殊血脉？
3. 主角价值观/目标 — 复仇？守护？变强？赚钱？
4. 反派类型 — 宿敌型/利益冲突型/系统压制型/情感纠葛型
5. 配角体系 — 导师/红颜/兄弟/跟班
6. 人物关系张力 — 对手戏/师徒/爱恨

书籍数据：
{context}

请输出 JSON 格式：
{{"books": [{{"书名": "...", "主角": {{"身份": "...", "性格": "...", "能力": "...", "目标": "..."}}, "反派": "..."}}], "人设趋势": "..."}}""",
        )

    # ── Layer 7: WorldBuilding (AI) ──────────────────────────────────────
    def analyze_world_building(self, book_profiles: list[dict]) -> dict:
        """Analyze world setting, timeline, power systems, rules, organizations.

        Calls gateway.complete() for world-building analysis.
        """
        context = self._build_book_context(book_profiles, max_books=15)
        return self._call_ai(
            task_type="analysis_world_building",
            prompt_name="analysis.world_building",
            layer="07_WorldBuilding",
            system_context=(
                "你是资深网文世界观架构分析师。请基于书籍元数据，"
                "推断每本书的世界观体系、力量等级、社会结构和核心规则。"
            ),
            analysis_instructions=f"""请分析以下书籍的世界观设定：
对每本书提取：
1. 世界类型 — 现代都市/古代/异界/科幻/末世/混合
2. 力量体系 — 修仙等级/魔法体系/科技树/异能分类
3. 社会结构 — 家族/宗门/国家/势力分布
4. 核心规则 — 世界运行的基本法则
5. 货币/经济 — 交易体系
6. 时间线 — 是否有明确的历史/纪元
7. 组织/势力 — 主要阵营和派系

书籍数据：
{context}

请输出 JSON 格式：
{{"books": [{{"书名": "...", "世界类型": "...", "力量体系": "...", "社会结构": "...", "核心规则": "...", "阵营": []}}], "世界观趋势": "..."}}""",
        )

    # ── Layer 8: StyleReport (AI) ───────────────────────────────────────
    def analyze_style_report(self, book_profiles: list[dict]) -> dict:
        """Analyze writing style: sentence/paragraph length, dialogue ratio, density metrics.

        Calls gateway.complete() for style analysis.
        """
        context = self._build_book_context(book_profiles, max_books=20)
        return self._call_ai(
            task_type="analysis_style_report",
            prompt_name="analysis.style_report",
            layer="08_StyleReport",
            system_context=(
                "你是资深网文文风分析师，擅长从书籍元数据推断写作风格特征。"
            ),
            analysis_instructions=f"""请分析以下书籍的文风特征：
对每本书推断：
1. 平均句长 — 短句(10-20字)/中句(20-40字)/长句(40+字)
2. 段落长度 — 手机屏段落(<100字)/中段落(100-300字)/大段落(300+字)
3. 对话占比 — 高(>40%)/中(20-40%)/低(<20%)
4. 描写密度 — 形容词/名词比例推断
5. 文风类型 — 白描/华丽/幽默/冷峻/热血/细腻
6. 网络用语占比 — 高/中/低
7. AI感评分 — 是否有明显AI写作痕迹

书籍数据：
{context}

请输出 JSON 格式：
{{"books": [{{"书名": "...", "平均句长": "...", "段落风格": "...", "对话占比": "...", "文风类型": "...", "网络用语": "...", "AI感": "高/中/低"}}], "文风趋势": "..."}}""",
        )

    # ── Layer 9: ReaderReport (AI) ──────────────────────────────────────
    def analyze_reader_report(self, book_profiles: list[dict]) -> dict:
        """Analyze reader feedback: comments, reviews, chapter reactions.

        Calls gateway.complete() for reader-feedback analysis.
        """
        context = self._build_book_context(book_profiles, max_books=20)
        return self._call_ai(
            task_type="analysis_reader_report",
            prompt_name="analysis.reader_report",
            layer="09_ReaderReport",
            system_context=(
                "你是资深网文读者行为分析师。基于书籍的排名、评分、标签和分类，"
                "推断读者反馈模式和阅读行为。"
            ),
            analysis_instructions=f"""请分析以下书籍的读者反馈模式：
基于排名/评分/分类/标签数据推断：
1. 最受好评的章节类型 — 高潮章/反转章/日常章/战斗章
2. 读者流失点 — 第几章开始追读率下降
3. 催更强度 — 读者追更意愿
4. 情感触动点 — 虐心/热血/搞笑/温馨
5. 争议点 — 是否有设定/人物争议
6. 评论情感 — 正面/中性/负面比例
7. 粉丝粘性 — 是否有死忠粉/路人粉

书籍数据：
{context}

请输出 JSON 格式：
{{"books": [{{"书名": "...", "好评类型": "...", "流失推测": "...", "催更强度": "高/中/低", "情感触动": "...", "争议": "有/无"}}], "读者趋势": "..."}}""",
        )

    # ── Layer 10: AIInsight (AI) ────────────────────────────────────────
    def analyze_ai_insight(self, book_profiles: list[dict]) -> dict:
        """Synthesize all previous layers into market trends, viral formulas, innovation.

        Calls gateway.complete() for high-level synthesis.
        """
        context = self._build_book_context(book_profiles, max_books=30)
        return self._call_ai(
            task_type="analysis_ai_insight",
            prompt_name="analysis.ai_insight",
            layer="10_AIInsight",
            system_context=(
                "你是资深网文市场分析师和AI创作顾问。基于排行榜书籍数据，"
                "识别市场趋势、爆款公式和创新方向。"
            ),
            analysis_instructions=f"""请基于排行榜书籍数据进行综合分析：

1. 市场趋势（近30天）：
   - 崛起品类 — 哪些分类在增长
   - 热度变化 — 上升/下滑趋势
   - 新题材 — 是否有新兴子类型

2. 爆款公式：
   - 黄金开局模板 — 什么类型的开局最容易爆
   - 人设公式 — 什么主角设定最受欢迎
   - 节奏公式 — 什么更新频率/章节长度最有效

3. 创新建议：
   - 蓝海品类 — 竞争少但需求大的方向
   - 跨界融合 — 可尝试的元素组合
   - AI创作优化 — 标题/标签/简介/前三章/世界观/人设的生成建议

4. 平台策略：
   - 哪个平台适合什么品类
   - 推荐字数范围
   - 推荐更新频率

书籍数据：
{context}

请输出 JSON 格式：
{{"market_trends": [...], "viral_formulas": [...], "innovation_suggestions": [...], "platform_strategy": {{...}}, "generation_recommendations": {{...}}}}""",
        )

    # ── AI call helper ──────────────────────────────────────────────────
    def _call_ai(
        self,
        task_type: str,
        prompt_name: str,
        layer: str,
        system_context: str,
        analysis_instructions: str,
    ) -> dict:
        """Call gateway.complete() with timeout and error handling.

        Returns a structured layer result dict. Never raises — failures are
        captured in the result so the batch can continue.
        """
        start_time = time.monotonic()

        def _do_call() -> dict[str, Any]:
            try:
                return complete(
                    run_id=None,
                    node_key=None,
                    project_id=self.project_id,
                    task_type=task_type,
                    prompt_name=prompt_name,
                    variables={
                        "system_context": system_context,
                        "analysis_instructions": analysis_instructions,
                    },
                    client_mutation_id=f"ten-layer:{self.project_id}:{layer}:v1",
                )
            except Exception as e:
                # DB connection may fail in thread context — return error dict
                return {"error": str(e), "error_type": type(e).__name__}

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_do_call)
                output = future.result(timeout=_AI_LAYER_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            elapsed = round(time.monotonic() - start_time, 1)
            logger.warning(f"[{layer}] AI call timed out after {elapsed}s (limit: {_AI_LAYER_TIMEOUT_SECONDS}s)")
            return {
                "layer": layer,
                "status": "failed",
                "error": f"AI call timed out after {_AI_LAYER_TIMEOUT_SECONDS}s",
                "error_type": "TimeoutError",
                "data": None,
            }
        except (ProviderError, BudgetExceeded) as exc:
            elapsed = round(time.monotonic() - start_time, 1)
            logger.warning(f"[{layer}] AI call failed after {elapsed}s: {exc}")
            return {
                "layer": layer,
                "status": "failed",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "data": None,
            }
        except Exception as exc:
            elapsed = round(time.monotonic() - start_time, 1)
            logger.exception(f"[{layer}] Unexpected error after {elapsed}s")
            return {
                "layer": layer,
                "status": "failed",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "data": None,
            }

        elapsed = round(time.monotonic() - start_time, 1)
        return {
            "layer": layer,
            "status": "succeeded",
            "source": "ai",
            "latency_seconds": elapsed,
            "data": output,
        }

    # ── Book context builder ─────────────────────────────────────────────
    @staticmethod
    def _build_book_context(book_profiles: list[dict], max_books: int = 30) -> str:
        """Build a compact text summary of book profiles for AI prompts."""
        lines: list[str] = []
        for i, bp in enumerate(book_profiles[:max_books]):
            title = _safe_str(bp.get("title") or bp.get("name") or bp.get("book_name"))
            author = _safe_str(bp.get("author") or bp.get("writer"))
            category = _safe_str(bp.get("category") or bp.get("genre") or "")
            platform = _safe_str(bp.get("platform") or bp.get("source"))
            rank = _safe_int(bp.get("rank") or bp.get("rank_no"))
            rating = _safe_float(bp.get("rating") or bp.get("score"))
            words = _safe_int(bp.get("word_count") or bp.get("words"))
            status = _safe_str(bp.get("status") or bp.get("book_status"), "连载中")
            desc = _safe_str(bp.get("description") or bp.get("synopsis") or bp.get("intro") or "")[:200]
            tags = TenLayerAnalyzer._extract_tags(bp)

            lines.append(
                f"[{i + 1}] 《{title}》| 作者:{author} | 平台:{platform} | "
                f"分类:{category} | 排名:{rank} | 评分:{rating} | "
                f"字数:{words} | 状态:{status} | 标签:{', '.join(tags[:10])}"
            )
            if desc:
                lines.append(f"    简介: {desc}")

        if len(book_profiles) > max_books:
            lines.append(f"... (共 {len(book_profiles)} 本，仅展示前 {max_books} 本)")

        return "\n".join(lines)

    # ── Full batch analysis ─────────────────────────────────────────────
    def analyze(
        self,
        book_profiles: list[dict],
        platforms: list[str] | None = None,
        analysis_mode: str = "all",
    ) -> dict:
        """Run all 10 layers sequentially and collect results.

        Layers 1-3 run locally (fast, free).
        Layers 4-10 call gateway.complete() for deep AI analysis.

        Each layer fails independently — a single failure does not abort the batch.

        Args:
            book_profiles: list of book metadata dicts from scanned ranking
            platforms: source platforms (e.g. ["fanqie", "qidian"])
            analysis_mode: "single" | "multi" | "all"

        Returns:
            dict with ScanResult containing per-layer results + HeatMap + KeywordCloud + TrendReport
        """
        if not book_profiles:
            return {"status": "error", "message": "book_profiles is empty", "layers": {}}

        # ── Define layer registry ──
        layers_map: dict[str, tuple[Callable[..., Any], str]] = {
            "01_BookProfile":    (self.analyze_book_profile,    "local"),
            "02_GenreReport":    (self.analyze_genre_report,    "local"),
            "03_SellingPoints":  (self.analyze_selling_points,  "local"),
            "04_Golden3Chapter": (self.analyze_golden_3_chapter, "ai"),
            "05_PlotRhythm":     (self.analyze_plot_rhythm,     "ai"),
            "06_Character":      (self.analyze_characters,      "ai"),
            "07_WorldBuilding":  (self.analyze_world_building,  "ai"),
            "08_StyleReport":    (self.analyze_style_report,    "ai"),
            "09_ReaderReport":   (self.analyze_reader_report,   "ai"),
            "10_AIInsight":      (self.analyze_ai_insight,      "ai"),
        }

        # ── Select layers based on analysis_mode ──
        if analysis_mode == "single":
            selected = [
                "01_BookProfile", "03_SellingPoints",
                "06_Character", "10_AIInsight",
            ]
            layers_to_run = {k: v for k, v in layers_map.items() if k in selected}
        elif analysis_mode == "multi":
            selected = [
                "01_BookProfile", "02_GenreReport", "03_SellingPoints",
                "04_Golden3Chapter", "06_Character", "08_StyleReport", "10_AIInsight",
            ]
            layers_to_run = {k: v for k, v in layers_map.items() if k in selected}
        else:  # "all"
            layers_to_run = layers_map

        # ── Run layers sequentially ──
        results: dict[str, dict] = {}
        errors: list[dict] = []
        stats = {"local_ran": 0, "local_succeeded": 0, "ai_ran": 0, "ai_succeeded": 0}
        batch_start = time.monotonic()

        for layer_name, (method, layer_type) in layers_to_run.items():
            logger.info(f"[{layer_name}] Starting ({layer_type})...")
            try:
                result = method(book_profiles)
            except Exception as exc:
                logger.exception(f"[{layer_name}] Unexpected crash")
                result = {
                    "layer": layer_name,
                    "status": "failed",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "data": None,
                }

            results[layer_name] = result

            if result.get("status") == "failed":
                errors.append({
                    "layer": layer_name,
                    "error": result.get("error"),
                    "error_type": result.get("error_type"),
                })
            else:
                if layer_type == "local":
                    stats["local_succeeded"] += 1
                else:
                    stats["ai_succeeded"] += 1

            if layer_type == "local":
                stats["local_ran"] += 1
            else:
                stats["ai_ran"] += 1

        batch_elapsed = round(time.monotonic() - batch_start, 1)

        # ── Generate synthetic reports ──
        heat_map = self._generate_heat_map(results, book_profiles)
        keyword_cloud = self._generate_keyword_cloud(results)
        trend_report = self._generate_trend_report(results, platforms or [])

        all_layers_count = len(layers_to_run)
        succeeded_count = sum(1 for r in results.values() if r.get("status") == "succeeded")

        return {
            "status": "completed" if not errors else "partial",
            "total_layers": all_layers_count,
            "succeeded_layers": succeeded_count,
            "failed_layers": len(errors),
            "platforms": platforms or [],
            "analysis_mode": analysis_mode,
            "batch_latency_seconds": batch_elapsed,
            "stats": stats,
            "ScanResult": results,
            "HeatMap": heat_map,
            "KeywordCloud": keyword_cloud,
            "TrendReport": trend_report,
            "errors": errors,
        }

    # ── Report generators ────────────────────────────────────────────────
    def _generate_heat_map(self, results: dict, book_profiles: list[dict]) -> dict:
        """Generate a heat map from genre distribution and score data."""
        genres: dict[str, int] = {}
        scores: list[float] = []
        for bp in book_profiles:
            category = _safe_str(bp.get("category") or bp.get("genre"), "general")
            genres[category] = genres.get(category, 0) + 1
            score = _safe_float(bp.get("metrics", {}).get("confidence") or bp.get("rating") or bp.get("score"))
            if score > 0:
                scores.append(score)

        # Heat map intensity: normalize counts to 0-100
        max_count = max(genres.values()) if genres else 1
        heat_entries = [
            {"genre": g, "count": c, "intensity": round(c / max_count * 100, 1)}
            for g, c in sorted(genres.items(), key=lambda x: -x[1])
        ]

        return {
            "genre_distribution": genres,
            "heat_entries": heat_entries,
            "avg_rating": round(sum(scores) / len(scores), 2) if scores else 0,
            "total_books": len(book_profiles),
        }

    def _generate_keyword_cloud(self, results: dict) -> dict:
        """Extract keyword/tag frequency from layer results."""
        # From Layer 1 (BookProfile) — extract all tags
        profile_data = results.get("01_BookProfile", {}).get("data", {})
        tag_freq: dict[str, int] = {}
        if isinstance(profile_data, dict):
            for book in profile_data.get("books", []):
                for tag in book.get("标签", []):
                    tag_freq[tag] = tag_freq.get(tag, 0) + 1

        # From Layer 2 (GenreReport) — use computed top tags
        genre_data = results.get("02_GenreReport", {}).get("data", {})
        top_tags = []
        if isinstance(genre_data, dict):
            top_tags = genre_data.get("top_tags", [])[:50]

        # From Layer 3 (SellingPoints) — top hooks
        sp_data = results.get("03_SellingPoints", {}).get("data", {})
        top_hooks = []
        if isinstance(sp_data, dict):
            top_hooks = sp_data.get("top_hooks", [])[:20]

        return {
            "tag_cloud": [{"text": t, "weight": c} for t, c in sorted(
                tag_freq.items(), key=lambda x: -x[1]
            )[:100]],
            "top_tags_from_genre_report": top_tags,
            "top_selling_hooks": top_hooks,
        }

    def _generate_trend_report(self, results: dict, platforms: list[str]) -> dict:
        """Synthesize AIInsight into a trend report."""
        insight = results.get("10_AIInsight", {}).get("data", {})

        # Fallback: use locally-computed data from Layers 1-3
        genre_data = results.get("02_GenreReport", {}).get("data", {})
        sp_data = results.get("03_SellingPoints", {}).get("data", {})

        return {
            "platforms": platforms,
            "market_trends": (
                insight.get("market_trends", [])
                if isinstance(insight, dict)
                else []
            ),
            "viral_formulas": (
                insight.get("viral_formulas", [])
                if isinstance(insight, dict)
                else []
            ),
            "recommendations": (
                insight.get("generation_recommendations", {})
                if isinstance(insight, dict)
                else {}
            ),
            "top_genres": (
                genre_data.get("genre_distribution", [])[:10]
                if isinstance(genre_data, dict)
                else []
            ),
            "top_hooks": (
                sp_data.get("top_hooks", [])[:10]
                if isinstance(sp_data, dict)
                else []
            ),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
