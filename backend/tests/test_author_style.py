"""V3 §12 Author Style Card 强化：确定性纯函数单元测试（不依赖 DB / AI）。"""
from app.services.author_style import (
    learn_from_signals,
    merge_style_card,
    normalize_signals,
    persist_card,
    record_signals,
    summarize_signals,
)
from app.services import author_style


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


def test_style_signal_and_card_writes_commit(monkeypatch):
    class FakeDb:
        def __init__(self):
            self.executions = []
            self.commits = 0
            self.closed = False

        def execute(self, sql, params):
            self.executions.append((sql, params))
            return self

        def commit(self):
            self.commits += 1

        def close(self):
            self.closed = True

    signal_db = FakeDb()
    monkeypatch.setattr(author_style, "connect", lambda: signal_db)
    assert record_signals(
        "project-1",
        "chapter-1",
        "user-1",
        [{"signal_type": "like", "liked_text": "雨落在旧巷青石上"}],
    ) == 1
    assert signal_db.commits == 1
    assert signal_db.closed is True

    card_db = FakeDb()
    monkeypatch.setattr(author_style, "connect", lambda: card_db)
    persist_card("project-1", {"avg_sentence_length": 18.0}, 1)
    assert card_db.commits == 1
    assert card_db.closed is True


def test_author_feedback_dispatches_real_learning_task(monkeypatch):
    from app.api.v1 import author_style as author_style_api
    from app.workers import m3_tasks

    class Queued:
        id = "learning-task-1"

    monkeypatch.setattr(
        m3_tasks.run_author_style_learning,
        "delay",
        lambda project_id: Queued(),
    )

    assert author_style_api._dispatch_style_learning("project-1") == "learning-task-1"
