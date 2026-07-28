"""V3-P3-⑩: Author Style Card 强化。

在现有 style_learn.learn_style（样本→特征提取→style_card）之上，扩展学习来源：
- 编辑器 diff 信号：修改记录 / 删除内容 / 保留内容
- 喜欢表达：用户主动标记的偏好表达

所有统计特征均为确定性纯函数，便于单元测试；Learning Agent（m3_tasks）异步消费。
"""
from __future__ import annotations

from collections import Counter

from app.db import connect, encode, new_id
from app.services.style_learn import _extract_motifs, learn_style

_MAX_LEN = 4000  # 单条信号文本上限，防止巨量正文写库


def _clip(text: str, limit: int = _MAX_LEN) -> str:
    if not isinstance(text, str):
        return ""
    return text[:limit]


def normalize_signals(raw_signals: list) -> list[dict]:
    """将原始信号列表清洗为统一结构，过滤非法条目。"""
    out: list[dict] = []
    for s in raw_signals or []:
        if not isinstance(s, dict):
            continue
        sig_type = s.get("signal_type", "edit")
        if sig_type not in {"edit", "like"}:
            sig_type = "edit"
        out.append({
            "signal_type": sig_type,
            "kept_text": _clip(s.get("kept_text", "")),
            "deleted_text": _clip(s.get("deleted_text", "")),
            "edited_text": _clip(s.get("edited_text", "")),
            "liked_text": _clip(s.get("liked_text", "")),
        })
    return out


def summarize_signals(signals: list[dict]) -> dict:
    """对归一化信号做聚合统计，产出可解释的风格偏好特征。"""
    if not signals:
        return {
            "signal_count": 0,
            "total_kept": 0,
            "total_deleted": 0,
            "total_edited": 0,
            "keep_ratio": None,
            "deletion_ratio": None,
            "edit_preference": "insufficient_data",
            "liked_phrases": [],
        }

    total_kept = sum(len(s["kept_text"]) for s in signals)
    total_deleted = sum(len(s["deleted_text"]) for s in signals)
    total_edited = sum(len(s["edited_text"]) for s in signals)
    total_basis = total_kept + total_deleted + total_edited

    keep_ratio = round(total_kept / max(total_basis, 1), 3)
    deletion_ratio = round(total_deleted / max(total_basis, 1), 3)
    if deletion_ratio >= 0.5:
        edit_preference = "aggressive_editor"
    elif deletion_ratio <= 0.1 and keep_ratio >= 0.6:
        edit_preference = "faithful_keeper"
    else:
        edit_preference = "moderate_editor"

    liked_texts = [s["liked_text"] for s in signals if s["signal_type"] == "like" and s["liked_text"]]
    liked_phrases = _extract_motifs(liked_texts, top_n=10) if liked_texts else []

    return {
        "signal_count": len(signals),
        "total_kept": total_kept,
        "total_deleted": total_deleted,
        "total_edited": total_edited,
        "keep_ratio": keep_ratio,
        "deletion_ratio": deletion_ratio,
        "edit_preference": edit_preference,
        "liked_phrases": liked_phrases,
    }


def merge_style_card(base: dict, summary: dict) -> dict:
    """把编辑器信号摘要合并进现有 style_card，不破坏原字段。"""
    merged = dict(base) if isinstance(base, dict) else {}
    merged["author_signals"] = summary
    if summary.get("liked_phrases"):
        merged["liked_phrases"] = summary["liked_phrases"]
        existing = merged.get("common_motifs") or []
        merged["common_motifs"] = (existing + summary["liked_phrases"])[:10]
    if summary.get("edit_preference") and summary["edit_preference"] != "insufficient_data":
        merged["edit_preference"] = summary["edit_preference"]
    return merged


def learn_from_signals(samples: list[str], raw_signals: list) -> dict:
    """Learning Agent 的确定性核心：样本统计特征 + 编辑器信号 → 强化后的 style_card。"""
    base = learn_style(samples or [])
    signals = normalize_signals(raw_signals)
    summary = summarize_signals(signals)
    return merge_style_card(base, summary)


# ── DB 持久化（供 Learning Agent / API 调用）──

def persist_card(project_id: str, card: dict, samples_count: int) -> None:
    db = connect()
    db.execute(
        """INSERT INTO style_cards (id, project_id, card, samples_count, updated_at)
           VALUES (%s, %s, %s, %s, now())
           ON CONFLICT (project_id)
           DO UPDATE SET card = EXCLUDED.card, samples_count = EXCLUDED.samples_count, updated_at = now()""",
        (new_id(), project_id, encode(card), int(samples_count)),
    )
    db.close()


def get_card(project_id: str) -> dict:
    db = connect()
    row = db.execute("SELECT card FROM style_cards WHERE project_id = %s", (project_id,)).fetchone()
    db.close()
    if row and isinstance(row.get("card"), dict):
        return row["card"]
    return {}


def record_signals(project_id: str, content_id: str | None, author_id: str | None,
                   signals: list[dict]) -> int:
    """批量写入编辑器 diff 信号，返回写入条数。"""
    normalized = normalize_signals(signals)
    if not normalized:
        return 0
    db = connect()
    for sig in normalized:
        db.execute(
            """INSERT INTO author_style_signals
               (id, project_id, content_id, author_id, signal_type,
                kept_text, deleted_text, edited_text, liked_text)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (new_id(), project_id, content_id, author_id, sig["signal_type"],
             sig["kept_text"], sig["deleted_text"], sig["edited_text"], sig["liked_text"]),
        )
    db.close()
    return len(normalized)


def _phrase_counter(texts: list[str], top_n: int = 10) -> list[str]:
    return _extract_motifs(texts, top_n=top_n)


def run_style_learning(project_id: str) -> dict:
    """Learning Agent 主体：聚合知识库样本 + 编辑器信号，重建并持久化 style_card。"""
    db = connect()
    samples_rows = db.execute(
        "SELECT body FROM knowledge_items WHERE project_id = %s AND kind = 'reference' AND is_deleted = FALSE LIMIT 50",
        (project_id,),
    ).fetchall()
    sig_rows = db.execute(
        "SELECT signal_type, kept_text, deleted_text, edited_text, liked_text FROM author_style_signals WHERE project_id = %s",
        (project_id,),
    ).fetchall()
    db.close()

    samples = [r["body"] for r in samples_rows if r.get("body")]
    raw_signals = [
        {
            "signal_type": r.get("signal_type", "edit"),
            "kept_text": r.get("kept_text", "") or "",
            "deleted_text": r.get("deleted_text", "") or "",
            "edited_text": r.get("edited_text", "") or "",
            "liked_text": r.get("liked_text", "") or "",
        }
        for r in sig_rows
    ]
    card = learn_from_signals(samples, raw_signals)
    persist_card(project_id, card, len(samples))
    return card
