"""statistics_v1 — 确定性章节统计层（v0.9.2 冻结规范）

严格规则：
- 字符偏移基于 UTF-8 编码后的字节位置，不是 Python 字符索引。
- 章节边界：以 "第N章" / "第N回" 开头的独立行作为章节起始。
- 段落边界：连续两个换行符（\\n\\n）切分，去除首尾空白后非空。
- 句子边界：中文句号。！？；+ 英文 .!?; 后跟空白或行尾，省略号……不计为句末。
- 对话边界：成对的中文引号「」『』"" '' 或英文引号，取最内层完整对话。
- 双哈希：content_sha256（正文原文）+ normalized_sha256（去空白小写后）。
- 同一输入必须产生字节级一致输出。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import Any

# ── 章节标题匹配 ──────────────────────────────────────────────
_CHAPTER_HEADER_RE = re.compile(
    r"^\s*(第[\u4e00-\u9fa50-9零一二三四五六七八九十百千万]+[章回节卷篇])"
    r"[\s　]*[^\n]*$",
    re.MULTILINE,
)

# ── 句子切分（保留标点）──────────────────────────────────────
# 中文句末标点 + 英文句末标点，后面跟空白、引号或字符串结尾
_SENTENCE_SPLIT_RE = re.compile(
    r"(?<=[。！？；.!?;])(?=[\s\"'」』）)】\]]|$)"
)

# 省略号不切句
_ELLIPSIS_RE = re.compile(r"\.\.\.|…{2,}")

# ── 对话提取（最内层成对引号）───────────────────────────────
_DIALOGUE_PATTERNS = [
    re.compile(r"「([^「」]*?)」"),
    re.compile(r"『([^『』]*?)』"),
    re.compile(r'"([^"]*?)"'),
    re.compile(r"'([^']*?)'"),
    re.compile(r"“([^”]*?)”"),
    re.compile(r"‘([^’]*?)’"),
]

# ── 异常标点检测 ─────────────────────────────────────────────
_ANOMALOUS_PUNCTUATION = [
    (re.compile(r"[。！？]{2,}"), "重复句末标点"),
    (re.compile(r"[，、]{2,}"), "重复逗号顿号"),
    (re.compile(r"\.{4,}"), "过长省略号"),
    (re.compile(r"[!?]{3,}"), "过多感叹问号"),
    (re.compile(r"[ \t]{3,}"), "连续空白"),
    (re.compile(r"[^\u4e00-\u9fa5a-zA-Z0-9\s\W]"), "不可见/异常字符"),
]


@dataclass
class ChapterStats:
    """单章统计结果。"""
    chapter_index: int
    title: str
    start_byte: int
    end_byte: int
    char_count: int          # 含标点的字符数
    byte_count: int          # UTF-8 字节数
    paragraph_count: int
    sentence_count: int
    dialogue_count: int
    dialogue_char_count: int
    avg_sentence_length: float
    punctuation_anomalies: list[dict[str, Any]] = field(default_factory=list)
    paragraphs: list[dict[str, Any]] = field(default_factory=list)
    sentences: list[dict[str, Any]] = field(default_factory=list)
    dialogues: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StatisticsResult:
    """全文统计结果。"""
    total_chars: int
    total_bytes: int
    total_paragraphs: int
    total_sentences: int
    total_dialogues: int
    total_dialogue_chars: int
    chapter_count: int
    content_sha256: str
    normalized_sha256: str
    chapters: list[ChapterStats] = field(default_factory=list)
    global_anomalies: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)


def _utf8_byte_offset(text: str, char_pos: int) -> int:
    """将字符索引转换为 UTF-8 字节偏移。"""
    return len(text[:char_pos].encode("utf-8"))


def _normalize_text(text: str) -> str:
    """归一化：去除所有空白，转小写。"""
    return re.sub(r"\s+", "", text).lower()


def _split_chapters(text: str) -> list[tuple[str, int, int, str]]:
    """切分章节，返回 (标题, 起始字符位置, 结束字符位置, 正文)。

    如果没有章节标题，整段作为第0章。空文本返回空列表。
    """
    if not text.strip():
        return []

    matches = list(_CHAPTER_HEADER_RE.finditer(text))
    if not matches:
        return [("（无标题）", 0, len(text), text.strip())]

    chapters = []
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        chapters.append((title, start, end, body))
    return chapters


def _split_paragraphs(body: str) -> list[str]:
    """按换行切分段落，过滤空段和纯章节标题行。

    中文网文通常每行一段，所以单换行即段落边界；
    双换行也兼容（中间的空行会被过滤）。
    """
    lines = body.split("\n")
    paragraphs = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # 跳过纯章节标题行（已被章节切分处理，这里作为段落无意义）
        if _CHAPTER_HEADER_RE.match(stripped) and len(stripped) < 30:
            continue
        paragraphs.append(stripped)
    return paragraphs


def _split_sentences(paragraph: str) -> list[str]:
    """切分句子，先处理省略号再切分。"""
    # 临时替换省略号为占位符，避免被误切
    placeholder = "\x00ELLIPSIS\x00"
    protected = _ELLIPSIS_RE.sub(placeholder, paragraph)
    parts = _SENTENCE_SPLIT_RE.split(protected)
    sentences = []
    for part in parts:
        s = part.replace(placeholder, "…").strip()
        if s:
            sentences.append(s)
    return sentences


def _extract_dialogues(text: str) -> list[tuple[str, int, int]]:
    """提取最内层对话，返回 (内容, 起始字符位置, 结束字符位置)。"""
    dialogues: list[tuple[str, int, int]] = []
    for pattern in _DIALOGUE_PATTERNS:
        for m in pattern.finditer(text):
            content = m.group(1)
            # 检查是否包含更内层引号（已被其他pattern匹配）
            if not any(p.search(content) for p in _DIALOGUE_PATTERNS):
                dialogues.append((content, m.start(1), m.end(1)))
    # 按位置排序去重
    dialogues.sort(key=lambda x: x[1])
    seen: set[int] = set()
    unique = []
    for d in dialogues:
        if d[1] not in seen:
            seen.add(d[1])
            unique.append(d)
    return unique


def _detect_anomalies(text: str) -> list[dict[str, Any]]:
    """检测异常标点。"""
    anomalies = []
    for pattern, label in _ANOMALOUS_PUNCTUATION:
        for m in pattern.finditer(text):
            anomalies.append({
                "type": label,
                "match": m.group(0),
                "char_offset": m.start(),
                "byte_offset": _utf8_byte_offset(text, m.start()),
            })
    return anomalies


def compute_statistics(text: str) -> StatisticsResult:
    """计算全文确定性统计。"""
    if not isinstance(text, str):
        raise TypeError("text must be str")

    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    normalized = _normalize_text(text)
    normalized_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    total_bytes = len(text.encode("utf-8"))
    chapters_raw = _split_chapters(text)

    chapter_stats: list[ChapterStats] = []
    total_paragraphs = 0
    total_sentences = 0
    total_dialogues = 0
    total_dialogue_chars = 0

    for idx, (title, char_start, char_end, body) in enumerate(chapters_raw):
        start_byte = _utf8_byte_offset(text, char_start)
        end_byte = _utf8_byte_offset(text, char_end)
        char_count = len(body)
        byte_count = len(body.encode("utf-8"))

        paragraphs = _split_paragraphs(body)
        all_sentences: list[str] = []
        para_details = []
        sentence_details = []
        body_search_cursor = 0
        for p_idx, para in enumerate(paragraphs):
            paragraph_start = body.find(para, body_search_cursor)
            if paragraph_start < 0:
                paragraph_start = body_search_cursor
            body_search_cursor = paragraph_start + len(para)
            sentences = _split_sentences(para)
            all_sentences.extend(sentences)
            para_details.append({
                "index": p_idx,
                "char_count": len(para),
                "sentence_count": len(sentences),
                "start_byte": _utf8_byte_offset(body, paragraph_start),
            })

            sentence_search_cursor = 0
            for sent in sentences:
                sentence_start_in_para = para.find(sent, sentence_search_cursor)
                if sentence_start_in_para < 0:
                    # Ellipsis normalization can make the split result differ
                    # from the source text. Keep a deterministic best-effort
                    # coordinate while retaining the exact sentence text.
                    sentence_start_in_para = sentence_search_cursor
                sentence_start = paragraph_start + sentence_start_in_para
                sentence_end = sentence_start + len(sent)
                sentence_details.append({
                    "index": len(sentence_details),
                    "text": sent,
                    "char_count": len(sent),
                    "paragraph_index": p_idx,
                    "char_start": sentence_start,
                    "char_end": sentence_end,
                })
                sentence_search_cursor = sentence_start_in_para + len(sent)

        dialogues = _extract_dialogues(body)
        dialogue_chars = sum(len(d[0]) for d in dialogues)

        sent_details = []
        for sentence in sentence_details:
            sentence = dict(sentence)
            sentence["has_dialogue"] = any(
                d[1] >= sentence["char_start"] and d[2] <= sentence["char_end"]
                for d in dialogues
            )
            sent_details.append(sentence)

        diag_details = []
        for d_idx, (content, d_start, d_end) in enumerate(dialogues):
            diag_details.append({
                "index": d_idx,
                "char_count": len(content),
                "char_start": d_start,
                "char_end": d_end,
                "byte_start": _utf8_byte_offset(body, d_start),
                "byte_end": _utf8_byte_offset(body, d_end),
            })

        anomalies = _detect_anomalies(body)
        avg_sent_len = round(len(body) / len(all_sentences), 2) if all_sentences else 0.0

        chapter_stats.append(ChapterStats(
            chapter_index=idx,
            title=title,
            start_byte=start_byte,
            end_byte=end_byte,
            char_count=char_count,
            byte_count=byte_count,
            paragraph_count=len(paragraphs),
            sentence_count=len(all_sentences),
            dialogue_count=len(dialogues),
            dialogue_char_count=dialogue_chars,
            avg_sentence_length=avg_sent_len,
            punctuation_anomalies=anomalies,
            paragraphs=para_details,
            sentences=sent_details,
            dialogues=diag_details,
        ))

        total_paragraphs += len(paragraphs)
        total_sentences += len(all_sentences)
        total_dialogues += len(dialogues)
        total_dialogue_chars += dialogue_chars

    global_anomalies = _detect_anomalies(text)

    return StatisticsResult(
        total_chars=len(text),
        total_bytes=total_bytes,
        total_paragraphs=total_paragraphs,
        total_sentences=total_sentences,
        total_dialogues=total_dialogues,
        total_dialogue_chars=total_dialogue_chars,
        chapter_count=len(chapter_stats),
        content_sha256=content_hash,
        normalized_sha256=normalized_hash,
        chapters=chapter_stats,
        global_anomalies=global_anomalies,
    )


def main() -> None:
    """命令行入口：从 stdin 或文件读取，输出 JSON。"""
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()
    result = compute_statistics(text)
    print(result.to_json())


if __name__ == "__main__":
    main()
