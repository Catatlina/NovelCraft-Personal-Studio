"""V3 §11.2 Pacing Engine visualization — queryable per-chapter time series.

The rhythm signals are already persisted per chapter (review dimensions,
chapter-function pacing gate, reader-experience scores). This module turns
them into a chapter_id-keyed time series consumed by the frontend pacing
curve. ``build_pacing_series`` is deterministic and unit-testable; the DB
query lives in ``get_pacing_series``.
"""

from __future__ import annotations

from typing import Any

# statuses from the chapter-function pacing gate rendered as 0-100 for the curve
_STATUS_SCORE = {"pass": 90.0, "warning": 65.0, "fail": 35.0}


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0.0, min(100.0, float(value)))
    return None


def build_pacing_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map chapter rows (id/title/meta[/pace]) to curve points ordered as given.

    Each point: chapter_id, seq, title, review_score, pace (7-dim pace score),
    pacing_status (+ derived pacing_score), reader_experience sub-scores
    (None when the chapter has no data yet — the frontend skips gaps).
    """
    series: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        seq = meta.get("seq")
        try:
            seq = int(seq) if seq is not None else None
        except (TypeError, ValueError):
            seq = None
        pacing_check = meta.get("pacing_check") if isinstance(meta.get("pacing_check"), dict) else {}
        pacing_status = str(pacing_check.get("status") or "") or None
        rx = meta.get("reader_experience") if isinstance(meta.get("reader_experience"), dict) else {}
        rx_scores = rx.get("scores") if isinstance(rx.get("scores"), dict) else {}
        series.append({
            "chapter_id": row.get("id"),
            "seq": seq,
            "title": row.get("title") or "",
            "review_score": _num(meta.get("review_score")),
            "pace": _num(row.get("pace")),
            "pacing_status": pacing_status,
            "pacing_score": _STATUS_SCORE.get(pacing_status or ""),
            "reader_experience": {k: _num(v) for k, v in rx_scores.items()} or None,
        })
    return series


def get_pacing_series(novel_id: str) -> dict[str, Any]:
    """Query chapters + latest review pace for one novel, ordered by seq."""
    from app.db import connect

    db = connect()
    rows = db.execute(
        """SELECT c.id, c.title, c.meta,
                  (SELECT (r.dimensions->>'pace')::float FROM reviews r
                    WHERE r.content_id = c.id ORDER BY r.created_at DESC LIMIT 1) AS pace
             FROM contents c
            WHERE c.parent_id = %s AND c.type = 'chapter' AND c.is_deleted = FALSE
            ORDER BY (c.meta->>'seq')::int NULLS LAST""",
        (novel_id,),
    ).fetchall()
    db.close()
    series = build_pacing_series([dict(row) for row in rows])
    return {"novel_id": novel_id, "count": len(series), "series": series}
