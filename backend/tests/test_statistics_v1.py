"""statistics_v1 黄金样例测试 — 确定性输出必须字节级一致。"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.v7.quality.statistics_v1 import compute_statistics, _normalize_text

GOLDEN_TEXT = """第一章 觉醒

林辰睁开眼睛，发现自己躺在一片废墟之中。「这是哪里？」他喃喃自语。

远处传来爆炸声。天空中，巨大的飞船正在缓缓降落。

「人类，你们的时代结束了。」一个冰冷的声音响起。林辰握紧拳头，他知道自己必须活下去。

第二章 反击

三天后，林辰找到了一处废弃的军事基地。「这里应该有武器。」他说。

基地里，他发现了一套外骨骼装甲。穿上装甲后，他的力量提升了十倍。「这就是希望吗？」

他走出基地，望向天空中的飞船。这一次，他不再恐惧。
"""


def test_chapter_count():
    result = compute_statistics(GOLDEN_TEXT)
    assert result.chapter_count == 2


def test_chapter_titles():
    result = compute_statistics(GOLDEN_TEXT)
    assert result.chapters[0].title == "第一章"
    assert result.chapters[1].title == "第二章"


def test_paragraph_count():
    result = compute_statistics(GOLDEN_TEXT)
    assert result.chapters[0].paragraph_count == 3
    assert result.chapters[1].paragraph_count == 3


def test_dialogue_count():
    result = compute_statistics(GOLDEN_TEXT)
    # 第一章有2段对话，第二章有2段对话
    assert result.chapters[0].dialogue_count == 2
    assert result.chapters[1].dialogue_count == 2


def test_deterministic_output():
    """同一输入必须产生完全一致的哈希和统计。"""
    r1 = compute_statistics(GOLDEN_TEXT)
    r2 = compute_statistics(GOLDEN_TEXT)
    assert r1.content_sha256 == r2.content_sha256
    assert r1.normalized_sha256 == r2.normalized_sha256
    assert r1.to_json() == r2.to_json()


def test_hash_values():
    """验证哈希计算正确性。"""
    result = compute_statistics(GOLDEN_TEXT)
    expected_content = hashlib.sha256(GOLDEN_TEXT.encode("utf-8")).hexdigest()
    expected_normalized = hashlib.sha256(_normalize_text(GOLDEN_TEXT).encode("utf-8")).hexdigest()
    assert result.content_sha256 == expected_content
    assert result.normalized_sha256 == expected_normalized


def test_byte_offsets():
    """验证字节偏移是 UTF-8 字节数，不是字符数。"""
    result = compute_statistics(GOLDEN_TEXT)
    # 中文字符在 UTF-8 中占3字节
    assert result.total_bytes > result.total_chars


def test_anomaly_detection():
    """检测异常标点。"""
    text = "这是测试。。。有重复标点！！！还有过长省略号。。。。"
    result = compute_statistics(text)
    assert len(result.global_anomalies) > 0


def test_no_chapter_header():
    """没有章节标题时整段作为第0章。"""
    text = "这是一段没有章节标题的正文。只有一个段落。"
    result = compute_statistics(text)
    assert result.chapter_count == 1
    assert result.chapters[0].title == "（无标题）"


def test_sentence_count_positive():
    result = compute_statistics(GOLDEN_TEXT)
    assert result.total_sentences > 0
    assert result.chapters[0].sentence_count > 0


def test_avg_sentence_length():
    result = compute_statistics(GOLDEN_TEXT)
    assert result.chapters[0].avg_sentence_length > 0


def test_empty_string():
    result = compute_statistics("")
    assert result.total_chars == 0
    assert result.chapter_count == 1  # 无标题空段


def test_json_serializable():
    result = compute_statistics(GOLDEN_TEXT)
    d = result.to_dict()
    assert json.dumps(d, ensure_ascii=False)  # 不抛异常


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
