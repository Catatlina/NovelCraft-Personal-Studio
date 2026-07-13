"""NC-HM-001: Hotspot ingestion — fetch, dedup, trend, freshness scoring."""
from __future__ import annotations
import json, os, urllib.request, hashlib
from datetime import datetime, timedelta
from app.db import connect, encode, new_id

HOTSPOT_SOURCES = {
    "zhihu": {"name": "知乎热榜", "url": "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=10"},
    "weibo": {"name": "微博热搜", "url": "https://weibo.com/ajax/side/hotSearch"},
}

DUPLICATE_WINDOW_HOURS = 24

# A browser-like UA reduces anti-bot rejections from the Chinese source APIs.
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _hotspot_opener() -> "urllib.request.OpenerDirector":
    """Route hotspot fetches through HOTSPOT_HTTP_PROXY when set (e.g. an xray HTTP
    inbound at http://127.0.0.1:10809). Scoped to hotspots only — the AI gateway and
    everything else keep their direct route. Overseas hosts (e.g. the Singapore VPS)
    often cannot reach zhihu/weibo directly; this lets that traffic go via a proxy."""
    proxy = os.getenv("HOTSPOT_HTTP_PROXY", "").strip()
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    return urllib.request.build_opener()


def _dedup_key(title: str, source: str) -> str:
    return hashlib.sha256(f"{source}:{title}".encode()).hexdigest()[:32]


def fetch_hotspots() -> tuple[list[dict], dict[str, str]]:
    """Fetch all sources; per-source failures are reported, never swallowed (docs/23 §4)."""
    results: list[dict] = []
    source_status: dict[str, str] = {}
    opener = _hotspot_opener()
    timeout = int(os.getenv("HOTSPOT_FETCH_TIMEOUT", "10"))
    for key, cfg in HOTSPOT_SOURCES.items():
        try:
            req = urllib.request.Request(
                cfg["url"], headers={"User-Agent": _BROWSER_UA, "Accept": "application/json"}
            )
            with opener.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            items = data.get("data", data.get("realtime", []))[:15]
            count = 0
            for item in items:
                title = item.get("target", {}).get("title", item.get("word", ""))
                if not title: continue
                results.append({
                    "source": key, "title": title.strip(),
                    "category": item.get("category", "general"),
                    "raw_score": item.get("detail_text", item.get("raw_hot", 0)),
                    "url": item.get("target", {}).get("url", ""),
                    "fetched_at": datetime.utcnow().isoformat(),
                    "dedup_key": _dedup_key(title, key),
                })
                count += 1
            source_status[key] = "ok" if count else "empty"
        except Exception as exc:
            source_status[key] = f"error: {exc}"
    return results, source_status


def compute_freshness_score(fetched_at: str) -> float:
    """Decay score: 1.0 at fetch time, decays to 0.5 after 24h."""
    if not fetched_at:
        return 0.5
    try:
        age = (datetime.utcnow() - datetime.fromisoformat(fetched_at)).total_seconds()
        return max(0.1, 1.0 - (age / (24 * 3600)) * 0.5)
    except Exception:
        return 0.5


def compute_trend(item_title: str, source: str, current_score: float) -> str:
    """Compare with previous snapshot to determine trend: rising/stable/cooling."""
    db = connect()
    prev = db.execute(
        """SELECT meta FROM knowledge_items 
           WHERE kind='hotspot' AND meta->>'title' = %s AND meta->>'source' = %s 
           AND created_at > now() - interval '24 hours' 
           ORDER BY created_at DESC LIMIT 1""",
        (item_title, source),
    ).fetchone()
    db.close()
    if not prev:
        return "new"
    prev_score = float((prev.get("meta") or {}).get("score", 0))
    diff = current_score - prev_score
    if diff > 5: return "rising"
    if diff < -5: return "cooling"
    return "stable"


def store_hotspots(items: list[dict]) -> int:
    db = connect()
    count = 0
    now_str = datetime.utcnow().isoformat()
    for item in items:
        # Dedup: check if same title+source within window
        existing = db.execute(
            "SELECT id FROM knowledge_items WHERE kind='hotspot' AND meta->>'dedup_key'=%s AND created_at > now() - interval '24 hours'",
            (item.get("dedup_key", ""),),
        ).fetchone()
        if existing:
            # Update trend + freshness
            db.execute(
                "UPDATE knowledge_items SET meta = meta || %s, updated_at = now() WHERE id = %s",
                (encode({"last_seen": now_str}), existing["id"]),
            )
            continue

        trend = compute_trend(item.get("title", ""), item.get("source", ""), float(item.get("raw_score", 0)))
        freshness = compute_freshness_score(now_str)

        db.execute(
            "INSERT INTO knowledge_items (id, kind, title, body, meta) VALUES (%s,%s,%s,%s,%s)",
            (new_id(), "hotspot", item.get("title", "")[:200],
             json.dumps(item, ensure_ascii=False),
             encode({
                 "source": item.get("source", ""), "score": item.get("raw_score", 0),
                 "dedup_key": item.get("dedup_key", ""),
                 "trend": trend, "freshness": round(freshness, 3),
                 "title": item.get("title", ""), "url": item.get("url", ""),
                 "fetched_at": now_str,
             })),
        )
        count += 1
    db.commit(); db.close()
    return count


def analyze_hotspots(items: list[dict]) -> list[dict]:
    angles = []
    templates = [
        ("如果「{title}」发生在虚构世界里会怎样？", "fiction"),
        ("「{title}」背后的故事，比新闻更精彩", "narrative"),
        ("从「{title}」看人性的复杂", "human_nature"),
        ("「{title}」揭示的系统性真相", "analysis"),
    ]
    for item in items[:8]:
        for tpl, atype in templates:
            angles.append({
                "topic": item.get("title", ""),
                "angle": tpl.format(title=item.get("title", "")),
                "category": item.get("category", ""),
                "angle_type": atype,
            })
    return angles


def get_hotspot_trend_report() -> dict:
    """NC-HM-001: Aggregated trend report — counts by trend and freshness."""
    db = connect()
    trends = db.execute(
        "SELECT meta->>'trend' as trend, COUNT(*) as cnt FROM knowledge_items "
        "WHERE kind='hotspot' AND created_at > now() - interval '24 hours' GROUP BY trend"
    ).fetchall()
    fresh = db.execute(
        "SELECT AVG((meta->>'freshness')::float) as avg_fresh FROM knowledge_items "
        "WHERE kind='hotspot' AND created_at > now() - interval '24 hours'"
    ).fetchone()
    total = db.execute(
        "SELECT COUNT(*) as total FROM knowledge_items WHERE kind='hotspot' AND created_at > now() - interval '24 hours'"
    ).fetchone()
    db.close()
    return {
        "total_hotspots_24h": total["total"] if total else 0,
        "avg_freshness": round(float(fresh["avg_fresh"] or 0), 3) if fresh else 0,
        "trends": {t["trend"]: t["cnt"] for t in trends},
    }
