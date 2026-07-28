"""V3 §12 Author Style Card 强化：确定性纯函数单元测试（不依赖 DB / AI）。"""
from app.services.author_style import (
    learn_from_signals,
    merge_style_card,
    normalize_signals,
    summarize_signals,
)


# ── normalize_signals ───────────────────────────────────────────────────

def test_normalize_filters_non_dict_and_invalid_type():
    raw = [
        {"signal_type": "edit", "kept_text": "保留", "deleted_text": "删掉", "edited_text": "改成"},
        "garbage",
        {"signal_type": "weird", "liked_text": "喜欢"},  # 非法 type → 默认 edit
        {"signal_type": "like", "liked_text": "这句意境好"},
    ]
    out = normalize_signals(raw)
    assert len(out) == 3
    assert out[1]["signal_type"] == "edit"
    assert out[2]["signal_type"] == "like"
    assert out[2]["liked_text"] == "这句意境好"


def test_normalize_clips_overlong_text():
    big = "x" * 9999
    out = normalize_signals([{"signal_type": "edit", "kept_text": big}])
    assert len(out[0]["kept_text"]) == 4000


# ── summarize_signals ───────────────────────────────────────────────────

def test_summarize_empty():
    s = summarize_signals([])
    assert s["signal_count"] == 0
    assert s["edit_preference"] == "insufficient_data"
    assert s["liked_phrases"] == []


def test_summarize_aggressive_editor():
    sigs = normalize_signals([
        {"signal_type": "edit", "kept_text": "短", "deleted_text": "很长很长很长很长很长",
         "edited_text": "短"},
    ])
    s = summarize_signals(sigs)
    assert s["deletion_ratio"] >= 0.5
    assert s["edit_preference"] == "aggressive_editor"


def test_summarize_faithful_keeper():
    sigs = normalize_signals([
        {"signal_type": "edit", "kept_text": "很长很长很长很长很长", "deleted_text": "",
         "edited_text": ""},
    ])
    s = summarize_signals(sigs)
    assert s["keep_ratio"] >= 0.6
    assert s["edit_preference"] == "faithful_keeper"


def test_summarize_liked_phrases_extracted():
    sigs = normalize_signals([
        {"signal_type": "like", "liked_text": "剑气纵横三万里剑气纵横三万里"},
    ])
    s = summarize_signals(sigs)
    assert len(s["liked_phrases"]) > 0


# ── merge_style_card ───────────────────────────────────────────────────

def test_merge_keeps_base_and_adds_signals():
    base = {"avg_sentence_length": 22.0, "common_motifs": ["江湖"]}
    summary = summarize_signals(normalize_signals([
        {"signal_type": "like", "liked_text": "月色凉"},
    ]))
    merged = merge_style_card(base, summary)
    assert merged["avg_sentence_length"] == 22.0
    assert merged["author_signals"]["signal_count"] == 1
    assert "月色" in merged["common_motifs"]


# ── learn_from_signals（Learning Agent 确定性核心）─────────────────────

def test_learn_from_signals_combines_samples_and_signals():
    samples = ["他说：「你来了。」夜色很静。", "她说：「走吧。」风很轻。"]
    raw = [
        {"signal_type": "edit", "kept_text": "保", "deleted_text": "删掉删掉删掉删掉删掉删掉", "edited_text": "保"},
        {"signal_type": "like", "liked_text": "星辰大海星辰大海"},
    ]
    card = learn_from_signals(samples, raw)
    assert card["avg_sentence_length"] > 0
    assert card["author_signals"]["signal_count"] == 2
    assert card["edit_preference"] == "aggressive_editor"
    assert "星辰" in card.get("liked_phrases", [])


def test_learn_from_signals_no_data_returns_base_only():
    card = learn_from_signals([], [])
    assert card["author_signals"]["signal_count"] == 0
    assert card["author_signals"]["edit_preference"] == "insufficient_data"
