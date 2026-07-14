"""NC-HM-001: Hotspot ingestion — fetch, dedup, trend, freshness scoring."""
from __future__ import annotations
import json, os, urllib.request, hashlib, urllib.parse
from datetime import datetime, timedelta
from app.db import connect, encode, new_id

HOTSPOT_SOURCES = {
    "baidu": {"name": "百度热搜", "url": "https://top.baidu.com/board?tab=realtime", "kind": "baidu_html"},
    "zhihu": {"name": "知乎热榜", "url": "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=20", "kind": "zhihu_json"},
    "weibo": {"name": "微博热搜", "url": "https://weibo.com/ajax/side/hotSearch", "kind": "weibo_json"},
    "xiaohongshu": {"name": "小红书热点", "url_env": "HOTSPOT_XIAOHONGSHU_URL", "kind": "generic_json"},
    "douyin": {"name": "抖音热点", "url_env": "HOTSPOT_DOUYIN_URL", "kind": "generic_json"},
    "x": {"name": "X Trends", "url_env": "HOTSPOT_X_URL", "kind": "generic_json"},
}

DUPLICATE_WINDOW_HOURS = 24

# A browser-like UA reduces anti-bot rejections from the Chinese source APIs.
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _hotspot_opener(proxy_override: str = "") -> "urllib.request.OpenerDirector":
    """Route hotspot fetches through HOTSPOT_HTTP_PROXY when set (e.g. an xray HTTP
    inbound at http://127.0.0.1:10809). Scoped to hotspots only — the AI gateway and
    everything else keep their direct route. Overseas hosts (e.g. the Singapore VPS)
    often cannot reach zhihu/weibo directly; this lets that traffic go via a proxy."""
    proxy = proxy_override.strip() or os.getenv("HOTSPOT_HTTP_PROXY", "").strip()
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    return urllib.request.build_opener()

def _source_cookie(source_key: str, connection: dict | None = None) -> str:
    """Read per-source cookie from env HOTSPOT_<SOURCE>_COOKIE."""
    if connection:
        return str(connection.get("cookie") or connection.get("bearer_token") or "").strip()
    return os.getenv(f"HOTSPOT_{source_key.upper()}_COOKIE", "").strip()


def _dedup_key(title: str, source: str) -> str:
    return hashlib.sha256(f"{source}:{title}".encode()).hexdigest()[:32]


def _connection_for_source(source_key: str, user_id: str = "") -> dict:
    if not user_id:
        return {}
    try:
        from app.services.publish_hub import get_platform_credentials
        return get_platform_credentials(user_id, f"hotspot_{source_key}") or {}
    except Exception:
        return {}


def _configured_url(cfg: dict, connection: dict | None = None) -> str:
    if connection and str(connection.get("url", "")).strip():
        return str(connection["url"]).strip()
    if cfg.get("url"):
        return str(cfg["url"])
    env_name = str(cfg.get("url_env", ""))
    return os.getenv(env_name, "").strip() if env_name else ""


def _parse_hotspot_payload(source: str, cfg: dict, payload: bytes) -> list[dict]:
    kind = cfg.get("kind", "generic_json")
    if kind == "baidu_html":
        import html
        import re
        text = payload.decode("utf-8", errors="replace")
        titles = re.findall(r'"word":"(.*?)"', text) or re.findall(r'class="c-single-text-ellipsis">(.*?)<', text)
        return [{"title": html.unescape(title), "category": "general", "raw_score": 0, "url": cfg.get("url", "")}
                for title in titles[:20] if title.strip()]

    data = json.loads(payload)
    if kind == "zhihu_json":
        raw = data.get("data", [])
        return [{
            "title": item.get("target", {}).get("title", ""),
            "category": item.get("category", "general"),
            "raw_score": item.get("detail_text", item.get("raw_hot", 0)),
            "url": item.get("target", {}).get("url", ""),
        } for item in raw[:20]]
    if kind == "weibo_json":
        raw = data.get("data", data).get("realtime", []) if isinstance(data.get("data", data), dict) else []
        return [{
            "title": item.get("word", ""),
            "category": item.get("category", "general"),
            "raw_score": item.get("num", item.get("raw_hot", 0)),
            "url": "https://s.weibo.com/weibo?q=" + urllib.parse.quote(item.get("word", "")),
        } for item in raw[:20]]

    raw = data.get("data", data.get("items", data.get("trends", [])))
    if isinstance(raw, dict):
        raw = raw.get("list", raw.get("items", raw.get("trends", [])))
    items = raw if isinstance(raw, list) else []
    parsed = []
    for item in items[:20]:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("word") or item.get("name") or item.get("query") or ""
        parsed.append({
            "title": str(title),
            "category": item.get("category", "general"),
            "raw_score": item.get("score", item.get("hot", item.get("raw_hot", 0))),
            "url": item.get("url", ""),
        })
    return parsed


def fetch_hotspots(user_id: str = "") -> tuple[list[dict], dict[str, str]]:
    """Fetch all sources; per-source failures are reported, never swallowed (docs/23 §4)."""
    results: list[dict] = []
    source_status: dict[str, str] = {}
    timeout = int(os.getenv("HOTSPOT_FETCH_TIMEOUT", "10"))
    for key, cfg in HOTSPOT_SOURCES.items():
        try:
            connection = _connection_for_source(key, user_id)
            try:
                opener = _hotspot_opener(str(connection.get("proxy", "")))
            except TypeError as exc:
                if "positional" not in str(exc) and "argument" not in str(exc):
                    raise
                opener = _hotspot_opener()
            url = _configured_url(cfg, connection)
            if not url:
                source_status[key] = f"error: {cfg.get('url_env') or 'visual connection'} is not configured"
                continue
            headers = {"User-Agent": _BROWSER_UA, "Accept": "application/json", "Referer": "https://www." + key + ".com/"}
            cookie = _source_cookie(key, connection)
            if cookie:
                if key == "x" and connection.get("bearer_token"):
                    headers["Authorization"] = f"Bearer {cookie}"
                else:
                    headers["Cookie"] = cookie
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=timeout) as resp:
                parsed_items = _parse_hotspot_payload(key, cfg, resp.read())
            count = 0
            for item in parsed_items:
                title = item.get("title", "")
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


def _safe_score(raw: str) -> float:
    """Extract numeric score from Chinese-format strings like '1181 万热度'."""
    if isinstance(raw, (int, float)):
        return float(raw)
    import re
    m = re.search(r"(\d+(?:\.\d+)?)\s*万", str(raw))
    if m:
        return float(m.group(1)) * 10000
    m = re.search(r"(\d+(?:\.\d+)?)", str(raw))
    return float(m.group(1)) if m else 0.0

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

        trend = compute_trend(item.get("title", ""), item.get("source", ""), _safe_score(item.get("raw_score", 0)))
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
