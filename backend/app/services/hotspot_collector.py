"""NC-HM-001: Hotspot ingestion — fetch, dedup, trend, freshness scoring."""
from __future__ import annotations
import json, os, urllib.request, hashlib, urllib.parse
from datetime import date, datetime, time, timedelta
from app.db import connect, encode, new_id

HOTSPOT_SOURCES = {
    "baidu": {"name": "百度热搜", "url": "https://top.baidu.com/board?tab=realtime", "history_url_env": "HOTSPOT_BAIDU_HISTORY_URL", "kind": "baidu_html"},
    "zhihu": {"name": "知乎热榜", "url": "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=20", "history_url_env": "HOTSPOT_ZHIHU_HISTORY_URL", "kind": "zhihu_json"},
    "weibo": {"name": "微博热搜", "url": "https://weibo.com/ajax/side/hotSearch", "history_url_env": "HOTSPOT_WEIBO_HISTORY_URL", "kind": "weibo_json"},
    "xiaohongshu": {"name": "小红书热点", "url_env": "HOTSPOT_XIAOHONGSHU_URL", "history_url_env": "HOTSPOT_XIAOHONGSHU_HISTORY_URL", "kind": "xiaohongshu_html",
                    "fallback_url": "https://www.xiaohongshu.com/explore"},
    "douyin": {"name": "抖音热点", "url_env": "HOTSPOT_DOUYIN_URL", "history_url_env": "HOTSPOT_DOUYIN_HISTORY_URL", "kind": "douyin_html",
               "fallback_url": "https://www.douyin.com/hot"},
    "toutiao": {"name": "今日头条", "url_env": "HOTSPOT_TOUTIAO_URL", "history_url_env": "HOTSPOT_TOUTIAO_HISTORY_URL", "kind": "toutiao_html",
                "fallback_url": "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"},
    "kuaishou": {"name": "快手热榜", "url_env": "HOTSPOT_KUAISHOU_URL", "history_url_env": "HOTSPOT_KUAISHOU_HISTORY_URL", "kind": "kuaishou_html",
                 "fallback_url": "https://www.kuaishou.com/?isHome=1"},
    "bilibili": {"name": "B站热门", "url_env": "HOTSPOT_BILIBILI_URL", "history_url_env": "HOTSPOT_BILIBILI_HISTORY_URL", "kind": "bilibili_json",
                 "fallback_url": "https://api.bilibili.com/x/web-interface/popular?ps=20"},
    "google_trends_cn": {"name": "Google Trends中国", "url_env": "HOTSPOT_GOOGLE_TRENDS_CN_URL", "history_url_env": "HOTSPOT_GOOGLE_TRENDS_CN_HISTORY_URL", "kind": "google_trends_json",
                         "fallback_url": "https://trends.google.com/trending?geo=CN"},
    "x": {"name": "X Trends", "url_env": "HOTSPOT_X_URL", "history_url_env": "HOTSPOT_X_HISTORY_URL", "kind": "generic_json"},
}

# Platform display names for overview
PLATFORM_DISPLAY = {k: v["name"] for k, v in HOTSPOT_SOURCES.items()}
PLATFORM_CATEGORIES = {
    "tech": ["科技", "AI", "人工智能", "互联网", "数码", "5G", "芯片", "新能源"],
    "entertainment": ["娱乐", "明星", "综艺", "电影", "音乐", "电视剧", "动漫", "游戏"],
    "society": ["社会", "民生", "法制", "教育", "医疗", "交通", "天气"],
    "finance": ["财经", "股市", "基金", "房产", "经济", "商业"],
    "sports": ["体育", "足球", "篮球", "奥运", "电竞", "F1"],
    "lifestyle": ["生活", "美食", "旅游", "时尚", "健身", "宠物", "家居"],
    "international": ["国际", "外交", "军事", "地缘"],
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
    url = os.getenv(env_name, "").strip() if env_name else ""
    if not url:
        url = str(cfg.get("fallback_url", ""))
    return url


def _configured_history_url(cfg: dict, collection_date: str, connection: dict | None = None) -> str:
    """Return a real configured historical hotspot URL for one date.

    Many public trend endpoints expose only the current list. We therefore only
    backfill dates from an explicitly configured official/authorized archive URL;
    if absent, callers must surface ``unsupported_history`` instead of inventing
    historical data.
    """
    raw = ""
    if connection and str(connection.get("history_url", "")).strip():
        raw = str(connection["history_url"]).strip()
    elif cfg.get("history_url"):
        raw = str(cfg["history_url"])
    else:
        env_name = str(cfg.get("history_url_env", ""))
        raw = os.getenv(env_name, "").strip() if env_name else ""
    if not raw:
        return ""
    return raw.replace("{date}", collection_date).replace("{yyyy-mm-dd}", collection_date)


def _html_extract_titles(html_text: str, source_name: str, base_url: str) -> list[dict]:
    """Extract hotspot titles from HTML pages using multiple regex strategies.

    Chinese SPA platforms embed JSON state in <script> tags; we extract
    title-like fields from those blobs. Falls back to <title> tags and
    generic word/name patterns.
    """
    import html as _html
    import re
    results: list[dict] = []
    seen: set[str] = set()

    # Strategy 1: Extract JSON blobs from <script> tags
    json_blobs: list[str] = []
    for m in re.finditer(
        r'<script[^>]*?(?:id="(?:__NEXT_DATA__|RENDER_DATA|__INITIAL_STATE__|SSR_DATA)"[^>]*?|'
        r'type="application/json"[^>]*?)>(.*?)</script>',
        html_text, re.DOTALL | re.IGNORECASE,
    ):
        json_blobs.append(m.group(1))
    # Also try window.__DATA__ = ... patterns
    for m in re.finditer(r'window\.\w+\s*=\s*(\{.*?\});', html_text, re.DOTALL):
        json_blobs.append(m.group(1))

    # Combine all blobs for title extraction
    search_text = html_text + "\n" + "\n".join(json_blobs)

    # Strategy 2a: Look for title/word/name in JSON-like structures
    title_patterns = [
        (r'"title"\s*:\s*"([^"]{2,200})"', None),
        (r'"word"\s*:\s*"([^"]{2,200})"', None),
        (r'"name"\s*:\s*"([^"]{2,200})"', None),
        (r'"query"\s*:\s*"([^"]{2,200})"', None),
        (r'"noteTitle"\s*:\s*"([^"]{2,200})"', None),
        (r'"ClusterIdStr"[^}]*?"title"\s*:\s*"([^"]{2,200})"', None),
    ]
    # Platform-specific scoring patterns
    hot_score_patterns = [
        r'"hotScore"\s*:\s*(\d+(?:\.\d+)?)',
        r'"hotValue"\s*:\s*(\d+(?:\.\d+)?)',
        r'"hot_value"\s*:\s*(\d+(?:\.\d+)?)',
        r'"HotValue"\s*:\s*(\d+(?:\.\d+)?)',
        r'"score"\s*:\s*(\d+(?:\.\d+)?)',
        r'"view_count"\s*:\s*(\d+(?:\.\d+)?)',
    ]

    for pattern, _group_name in title_patterns:
        for m in re.finditer(pattern, search_text):
            title = _html.unescape(m.group(1)).strip()
            if not title or len(title) < 2 or len(title) > 200:
                continue
            # Filter out non-content titles (URLs, JSON keys, etc.)
            if title.startswith("{") or title.startswith("[") or title.startswith("http"):
                continue
            norm = title.lower()
            if norm in seen:
                continue
            # Try to find associated hot score in nearby context
            ctx_start = max(0, m.start() - 500)
            ctx_end = min(len(search_text), m.end() + 500)
            ctx = search_text[ctx_start:ctx_end]
            hot_score = 0
            for sp in hot_score_patterns:
                sm = re.search(sp, ctx)
                if sm:
                    hot_score = _safe_score(sm.group(1))
                    break
            seen.add(norm)
            results.append({
                "title": title,
                "category": "general",
                "raw_score": hot_score,
                "url": base_url,
            })
            if len(results) >= 20:
                break
        if len(results) >= 20:
            break

    # Strategy 2b: Look for <a> tags with titles (desktop HTML pages)
    if not results:
        for m in re.finditer(r'<a[^>]*?title="([^"]{2,200})"[^>]*?>', html_text, re.IGNORECASE):
            title = _html.unescape(m.group(1)).strip()
            if title and title not in seen and not title.startswith("http"):
                seen.add(title)
                results.append({
                    "title": title,
                    "category": "general",
                    "raw_score": 0,
                    "url": base_url,
                })
                if len(results) >= 20:
                    break

    # Strategy 3: Extract from <title> tag (fallback)
    if not results:
        tm = re.search(r'<title>(.*?)</title>', html_text, re.IGNORECASE)
        if tm:
            page_title = _html.unescape(tm.group(1)).strip()
            if page_title and page_title not in seen:
                results.append({
                    "title": page_title,
                    "category": "general",
                    "raw_score": 0,
                    "url": base_url,
                })

    return results


def _parse_hotspot_payload(source: str, cfg: dict, payload: bytes) -> list[dict]:
    kind = cfg.get("kind", "generic_json")

    # ── HTML parsers ──────────────────────────────────────────────
    if kind == "baidu_html":
        import html
        import re
        text = payload.decode("utf-8", errors="replace")
        titles = re.findall(r'"word":"(.*?)"', text) or re.findall(r'class="c-single-text-ellipsis">(.*?)<', text)
        return [{"title": html.unescape(title), "category": "general", "raw_score": 0, "url": cfg.get("url", "")}
                for title in titles[:20] if title.strip()]

    if kind in ("toutiao_html", "xiaohongshu_html", "douyin_html", "kuaishou_html"):
        text = payload.decode("utf-8", errors="replace")
        base_url = _configured_url(cfg) or ""
        return _html_extract_titles(text, source, base_url)

    # ── JSON parsers ──────────────────────────────────────────────
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

    if kind == "bilibili_json":
        # B站公开热门API: api.bilibili.com/x/web-interface/popular
        if data.get("code") != 0:
            return []
        raw = data.get("data", {}).get("list", [])
        if not raw:
            raw = data.get("data", [])
        if isinstance(raw, dict):
            raw = raw.get("list", [])
        parsed = []
        for item in (raw if isinstance(raw, list) else [])[:20]:
            if not isinstance(item, dict):
                continue
            title = item.get("title", "")
            stat = item.get("stat", {}) or {}
            url = item.get("short_link_v2") or item.get("short_link") or item.get("url", "")
            if url and not url.startswith("http"):
                url = "https://www.bilibili.com/video/" + str(item.get("bvid", ""))
            parsed.append({
                "title": str(title),
                "category": item.get("tname", "general"),
                "raw_score": stat.get("view", stat.get("play", 0)),
                "url": url,
            })
        return parsed

    # ── Google Trends multi-format parser ──────────────────────────
    if kind == "google_trends_json":
        import re as _gt_re
        import xml.etree.ElementTree as ET
        text = payload.decode("utf-8", errors="replace")
        parsed: list[dict] = []

        # Format 1: RSS/XML (for env-provided RSS URLs)
        if text.strip().startswith("<?xml") or text.strip().startswith("<rss"):
            try:
                root = ET.fromstring(text)
                ns = {"ht": "https://trends.google.com/trends/trendingsearches"}
                for item_el in root.iter("item"):
                    title_el = item_el.find("title")
                    traffic_el = item_el.find("ht:approx_traffic", ns)
                    title = (title_el.text or "").strip() if title_el is not None else ""
                    traffic = traffic_el.text.strip() if traffic_el is not None and traffic_el.text else "0"
                    if title:
                        traffic_upper = traffic.upper().replace(",", "")
                        score = 0
                        try:
                            if "M" in traffic_upper:
                                score = float(traffic_upper.replace("M", "").replace("+", "")) * 1000000
                            elif "K" in traffic_upper:
                                score = float(traffic_upper.replace("K", "").replace("+", "")) * 1000
                            else:
                                score = float(_gt_re.sub(r'[^\d.]', '', traffic) or "0")
                        except ValueError:
                            score = 0
                        parsed.append({"title": title, "category": "general", "raw_score": score, "url": ""})
                        if len(parsed) >= 20:
                            break
                if parsed:
                    return parsed
            except ET.ParseError:
                pass  # fall through to regex

        # Format 2: )]}', prefix JSON (Google Trends dailytrends API)
        json_text = text
        if text.startswith(")]}',"):
            json_text = text[text.index("\n") + 1:] if "\n" in text else text[5:]
        try:
            data = json.loads(json_text)
            # dailytrends API structure
            default = data.get("default", {})
            trending_days = default.get("trendingSearchesDays", [])
            for day in trending_days[:3]:  # take latest 1 day's searches, up to 3 days as fallback
                searches = day.get("trendingSearches", [])
                for s in searches:
                    title = (s.get("title", {}) or {}).get("query", "")
                    if not title:
                        title = s.get("title", "")
                    traffic = s.get("formattedTraffic", "0")
                    # Parse formattedTraffic like "200K+" or "1M+"
                    traffic_upper = str(traffic).upper().replace(",", "")
                    score = 0
                    try:
                        if "M" in traffic_upper:
                            score = float(traffic_upper.replace("M", "").replace("+", "")) * 1000000
                        elif "K" in traffic_upper:
                            score = float(traffic_upper.replace("K", "").replace("+", "")) * 1000
                        else:
                            score = float(_gt_re.sub(r'[^\d.]', '', str(traffic)) or "0")
                    except ValueError:
                        score = 0
                    url = ""
                    articles = s.get("articles", [])
                    if articles and isinstance(articles, list) and len(articles) > 0:
                        url = articles[0].get("url", "")
                    parsed.append({"title": title, "category": "general", "raw_score": score, "url": url})
                    if len(parsed) >= 20:
                        break
                if parsed:
                    break
            if parsed:
                return parsed
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # fall through to HTML

        # Format 3: HTML fallback — try regex extraction
        parsed = _html_extract_titles(text, source, _configured_url(cfg) or "")
        if parsed:
            return parsed

        # Format 4: RSS regex fallback (last resort)
        titles = _gt_re.findall(r'<title>(.*?)</title>', text)
        for t in titles[1:21]:  # skip channel title
            t = t.strip()
            if t and "Google Trends" not in t and "Daily Search" not in t:
                parsed.append({"title": t, "category": "general", "raw_score": 0, "url": ""})
        return parsed

    # ── Generic JSON fallback ─────────────────────────────────────
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


def _fetch_source_items(source_key: str, cfg: dict, url: str, connection: dict | None = None) -> list[dict]:
    timeout = int(os.getenv("HOTSPOT_FETCH_TIMEOUT", "10"))
    try:
        opener = _hotspot_opener(str((connection or {}).get("proxy", "")))
    except TypeError as exc:
        if "positional" not in str(exc) and "argument" not in str(exc):
            raise
        opener = _hotspot_opener()

    kind = cfg.get("kind", "generic_json")
    is_html_kind = kind.endswith("_html") or kind == "baidu_html" or kind == "google_trends_json"
    is_rss_kind = kind == "google_trends_json"

    headers = {
        "User-Agent": _BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" if (is_html_kind or is_rss_kind) else "application/json",
    }
    # Build Referer from source or URL
    if source_key == "bilibili":
        headers["Referer"] = "https://www.bilibili.com/"
    elif source_key == "google_trends_cn":
        headers["Referer"] = "https://trends.google.com/"
    elif source_key == "toutiao":
        headers["Referer"] = "https://www.toutiao.com/"
    elif source_key == "xiaohongshu":
        headers["Referer"] = "https://www.xiaohongshu.com/"
    elif source_key == "douyin":
        headers["Referer"] = "https://www.douyin.com/"
    elif source_key == "kuaishou":
        headers["Referer"] = "https://www.kuaishou.com/"
    else:
        headers["Referer"] = "https://www." + source_key + ".com/"

    # B站 API requires specific Origin/Referer headers
    if source_key == "bilibili":
        headers["Origin"] = "https://www.bilibili.com"

    cookie = _source_cookie(source_key, connection)
    if cookie:
        if source_key == "x" and (connection or {}).get("bearer_token"):
            headers["Authorization"] = f"Bearer {cookie}"
        else:
            headers["Cookie"] = cookie

    req = urllib.request.Request(url, headers=headers)
    with opener.open(req, timeout=timeout) as resp:
        return _parse_hotspot_payload(source_key, cfg, resp.read())


def fetch_hotspots(user_id: str = "") -> tuple[list[dict], dict[str, str]]:
    """Fetch all sources; per-source failures are reported, never swallowed (docs/23 §4)."""
    results: list[dict] = []
    source_status: dict[str, str] = {}
    for key, cfg in HOTSPOT_SOURCES.items():
        try:
            connection = _connection_for_source(key, user_id)
            url = _configured_url(cfg, connection)
            if not url:
                source_status[key] = f"error: {cfg.get('url_env') or 'visual connection'} is not configured"
                continue
            parsed_items = _fetch_source_items(key, cfg, url, connection)
            count = 0
            for item in parsed_items:
                title = item.get("title", "")
                if not title: continue
                fetched_at = datetime.utcnow().isoformat()
                results.append({
                    "source": key, "title": title.strip(),
                    "category": item.get("category", "general"),
                    "raw_score": item.get("raw_score", item.get("detail_text", item.get("raw_hot", 0))),
                    "url": item.get("url", item.get("target", {}).get("url", "")),
                    "fetched_at": fetched_at,
                    "collection_date": fetched_at[:10],
                    "dedup_key": _dedup_key(title, key),
                })
                count += 1
            source_status[key] = "ok" if count else "empty"
        except Exception as exc:
            source_status[key] = f"error: {exc}"
    return results, source_status


def backfill_hotspot_history(days: int = 7, user_id: str = "") -> dict:
    """Collect historical hotspot snapshots from configured archive URLs.

    This is intentionally evidence-first: dates without a configured historical
    endpoint are reported as ``unsupported_history`` and no synthetic rows are
    created. If a source exposes a current endpoint only, today's current
    snapshot can still be collected by ``fetch_hotspots``; it is not treated as
    proof that past dates were available.
    """
    if days < 1 or days > 30:
        raise ValueError("days must be between 1 and 30")
    today = date.today()
    run_id = new_id()
    by_date: dict[str, dict[str, str]] = {}
    inserted_total = 0
    fetched_total = 0
    dates_with_rows: set[str] = set()
    for offset in range(days - 1, -1, -1):
        collection_day = today - timedelta(days=offset)
        collection_date = collection_day.isoformat()
        by_date[collection_date] = {}
        fetched_at = datetime.combine(collection_day, time(hour=12)).isoformat()
        for key, cfg in HOTSPOT_SOURCES.items():
            try:
                connection = _connection_for_source(key, user_id)
                url = _configured_history_url(cfg, collection_date, connection)
                if not url:
                    by_date[collection_date][key] = "unsupported_history: configure history_url with {date}"
                    continue
                parsed_items = _fetch_source_items(key, cfg, url, connection)
                items: list[dict] = []
                for item in parsed_items:
                    title = str(item.get("title", "")).strip()
                    if not title:
                        continue
                    items.append({
                        "source": key,
                        "title": title,
                        "category": item.get("category", "general"),
                        "raw_score": item.get("raw_score", item.get("detail_text", item.get("raw_hot", 0))),
                        "url": item.get("url", item.get("target", {}).get("url", "")),
                        "fetched_at": fetched_at,
                        "collection_date": collection_date,
                        "collection_run_id": run_id,
                        "dedup_key": _dedup_key(title, key),
                    })
                fetched_total += len(items)
                inserted = store_hotspots(items, fetched_at=fetched_at, collection_date=collection_date, collection_run_id=run_id)
                inserted_total += inserted
                if items:
                    dates_with_rows.add(collection_date)
                by_date[collection_date][key] = f"ok: fetched={len(items)}, inserted={inserted}" if items else "empty"
            except Exception as exc:
                by_date[collection_date][key] = f"error: {exc}"
    unsupported_sources = sorted({
        key
        for statuses in by_date.values()
        for key, status in statuses.items()
        if status.startswith("unsupported_history")
    })
    return {
        "run_id": run_id,
        "days_requested": days,
        "date_range": [(today - timedelta(days=days - 1)).isoformat(), today.isoformat()],
        "dates_with_rows": sorted(dates_with_rows),
        "fetched": fetched_total,
        "inserted": inserted_total,
        "sources": by_date,
        "unsupported_sources": unsupported_sources,
        "status": "ok" if len(dates_with_rows) == days else ("partial" if dates_with_rows else "unsupported"),
    }


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


def store_hotspots(items: list[dict], fetched_at: str | None = None, collection_date: str | None = None, collection_run_id: str = "") -> int:
    db = connect()
    count = 0
    now_str = fetched_at or datetime.utcnow().isoformat()
    default_collection_date = collection_date or now_str[:10]
    for item in items:
        item_collection_date = str(item.get("collection_date") or default_collection_date)
        item_dedup_key = item.get("dedup_key", "")
        # Dedup current snapshots by the 24h window, and historical snapshots by
        # source/title/date so the same topic can legitimately appear on multiple days.
        existing = db.execute(
            """SELECT id FROM knowledge_items
               WHERE kind='hotspot' AND meta->>'dedup_key'=%s
               AND COALESCE(meta->>'collection_date', left(meta->>'fetched_at', 10))=%s
               AND (%s <> %s OR created_at > now() - interval '24 hours')""",
            (item_dedup_key, item_collection_date, item_collection_date, datetime.utcnow().date().isoformat()),
        ).fetchone()
        if existing:
            # Update trend + freshness
            db.execute(
                "UPDATE knowledge_items SET meta = meta || %s, updated_at = now() WHERE id = %s",
                (encode({"last_seen": now_str}), existing["id"]),
            )
            continue

        trend = compute_trend(item.get("title", ""), item.get("source", ""), _safe_score(item.get("raw_score", 0)))
        item_fetched_at = str(item.get("fetched_at") or now_str)
        freshness = compute_freshness_score(item_fetched_at)

        db.execute(
            "INSERT INTO knowledge_items (id, kind, title, body, meta) VALUES (%s,%s,%s,%s,%s)",
            (new_id(), "hotspot", item.get("title", "")[:200],
             json.dumps({**item, "collection_date": item_collection_date, "fetched_at": item_fetched_at}, ensure_ascii=False),
             encode({
                 "source": item.get("source", ""), "score": item.get("raw_score", 0),
                 "dedup_key": item_dedup_key,
                 "trend": trend, "freshness": round(freshness, 3),
                 "title": item.get("title", ""), "url": item.get("url", ""),
                 "fetched_at": item_fetched_at,
                 "collection_date": item_collection_date,
                 "collection_run_id": item.get("collection_run_id") or collection_run_id,
             })),
        )
        count += 1
    db.commit(); db.close()
    return count


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


def get_hotspot_history_report(days: int = 7) -> dict:
    """Return stored historical evidence for the last N calendar days."""
    if days < 1 or days > 30:
        raise ValueError("days must be between 1 and 30")
    db = connect()
    rows = db.execute(
        """SELECT COALESCE(meta->>'collection_date', left(meta->>'fetched_at', 10)) AS collection_date,
                  meta->>'source' AS source,
                  COUNT(*) AS cnt
           FROM knowledge_items
           WHERE kind='hotspot'
             AND COALESCE(meta->>'collection_date', left(meta->>'fetched_at', 10)) >= to_char((CURRENT_DATE - (%s::int - 1)), 'YYYY-MM-DD')
           GROUP BY collection_date, source
           ORDER BY collection_date DESC, source ASC""",
        (days,),
    ).fetchall()
    db.close()
    by_date: dict[str, dict[str, int]] = {}
    for row in rows:
        collection_date = row["collection_date"] or "unknown"
        by_date.setdefault(collection_date, {})[row["source"] or "unknown"] = int(row["cnt"])
    return {
        "days_requested": days,
        "dates": by_date,
        "dates_with_rows": sorted(by_date.keys()),
        "total_rows": sum(sum(sources.values()) for sources in by_date.values()),
    }


def _fuzzy_title_similarity(title_a: str, title_b: str) -> float:
    """Simple fuzzy match ratio for title dedup (0-1)."""
    if not title_a or not title_b:
        return 0.0
    set_a = set(title_a)
    set_b = set(title_b)
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def _normalize_hotness(raw_score, source: str) -> float:
    """Convert platform-specific raw score to unified 0-100 hotness."""
    score = _safe_score(raw_score)
    if source in ("baidu",):
        return min(100, max(1, score / 100000 * 100)) if score > 0 else 10
    if source in ("zhihu",):
        return min(100, max(1, score / 20000000 * 100)) if score > 0 else 10
    if source in ("weibo",):
        return min(100, max(1, score / 5000000 * 100)) if score > 0 else 10
    # Generic: cap at 100
    return min(100, max(1, float(score) / 10000 * 100)) if score > 0 else 10


def get_hotspots_paginated(
    user_id: str = "",
    platforms: list[str] | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "hotness",
) -> dict:
    """Fetch hotspots with pagination and unified scoring.

    Returns deduped, sorted hotspots from recent fetches (last 24h).
    """
    db = connect()
    source_filter = ""
    params: list = []
    if platforms:
        placeholders = ",".join(["%s"] * len(platforms))
        source_filter = f"AND meta->>'source' IN ({placeholders})"
        params = list(platforms)

    total_row = db.execute(
        f"SELECT COUNT(*) as cnt FROM knowledge_items WHERE kind='hotspot' "
        f"AND created_at > now() - interval '24 hours' {source_filter}",
        tuple(params),
    ).fetchone()
    total = total_row["cnt"] if total_row else 0

    offset = (page - 1) * page_size
    rows = db.execute(
        f"""SELECT meta, created_at FROM knowledge_items
            WHERE kind='hotspot' AND created_at > now() - interval '24 hours'
            {source_filter}
            ORDER BY (meta->>'freshness')::float DESC, created_at DESC
            LIMIT %s OFFSET %s""",
        tuple(params) + (page_size, offset),
    ).fetchall()
    db.close()

    items = []
    seen = set()
    for row in rows:
        meta = row.get("meta") or {}
        title = str(meta.get("title", "")).strip()
        source = str(meta.get("source", ""))
        dedup_sig = f"{source}:{title}"
        if dedup_sig in seen:
            continue
        seen.add(dedup_sig)
        raw_score = meta.get("score", 0)
        hotness = _normalize_hotness(raw_score, source)
        trend = meta.get("trend", "stable")
        items.append({
            "title": title,
            "source": source,
            "source_name": PLATFORM_DISPLAY.get(source, source),
            "category": meta.get("category", "general"),
            "hotness": round(hotness, 1),
            "trend": trend,
            "url": meta.get("url", ""),
            "freshness": meta.get("freshness", 1.0),
            "fetched_at": meta.get("fetched_at", ""),
        })

    # Sort by hotness
    items.sort(key=lambda x: x["hotness"], reverse=True)

    # Cross-platform dedup by title similarity
    deduped = []
    for item in items:
        dup = False
        for existing in deduped:
            if _fuzzy_title_similarity(item["title"], existing["title"]) > 0.75:
                dup = True
                break
        if not dup:
            deduped.append(item)

    return {
        "items": deduped,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


def get_hotspot_overview(
    user_id: str = "",
    project_id: str = "",
    platforms: list[str] | None = None,
) -> dict:
    """Generate a hotspot overview with AI summary, categories, trends, predictions.

    Calls gateway.complete() for AI analysis. Returns structured overview data.
    """
    # Get raw hotspots first
    paginated = get_hotspots_paginated(
        user_id=user_id,
        platforms=platforms,
        page=1,
        page_size=50,
    )
    items = paginated.get("items", [])

    if not items:
        return {
            "summary": "暂无热点数据，请先刷新热点采集。",
            "categories": {},
            "trends": [],
            "predicted_viral": [],
            "recommended_angles": [],
            "total_hotspots": 0,
            "sources_active": [],
        }

    # Categorize hotspots
    categories: dict[str, list[dict]] = {}
    for item in items:
        cat = "general"
        for cat_key, keywords in PLATFORM_CATEGORIES.items():
            if any(kw in str(item.get("category", "")) or kw in str(item.get("title", ""))
                   for kw in keywords):
                cat = cat_key
                break
        categories.setdefault(cat, []).append(item)

    # Trend analysis
    trends = []
    trend_counts = {"rising": 0, "new": 0, "stable": 0, "cooling": 0}
    for item in items:
        t = item.get("trend", "stable")
        trend_counts[t] = trend_counts.get(t, 0) + 1
    for trend_name, count in trend_counts.items():
        if count > 0:
            trends.append({
                "name": trend_name,
                "label": {"rising": "📈 上升", "new": "🆕 新热点", "stable": "➡️ 稳定", "cooling": "📉 降温"}.get(trend_name, trend_name),
                "count": count,
            })

    # Sort by hotness for predictions
    top_items = sorted(items, key=lambda x: x["hotness"], reverse=True)[:10]
    rising_items = [it for it in items if it.get("trend") == "rising"]

    predicted_viral = [
        {
            "title": it["title"],
            "source": it["source_name"],
            "hotness": it["hotness"],
            "reason": "上升趋势 + 高热度" if it["trend"] == "rising" else "跨平台分布",
        }
        for it in (rising_items[:5] or top_items[:5])
    ]

    recommended_angles = [
        {
            "title": it["title"][:40],
            "source": it["source_name"],
            "angle": f"从{it.get('category', '热点')}角度切入，结合{it['source_name']}平台特点创作内容",
            "hotness": it["hotness"],
        }
        for it in top_items[:8]
    ]

    # AI summary via gateway when project_id provided
    summary = ""
    if project_id:
        try:
            from app.gateway import complete
            titles_text = "\n".join(
                f"- [{it['source_name']}] {it['title']}" for it in top_items[:20]
            )
            output = complete(
                run_id=None,
                node_key=None,
                project_id=project_id,
                task_type="hotspot_overview_summary",
                prompt_name="hotspot.overview_summary",
                variables={
                    "hotspot_titles": titles_text,
                    "total_count": str(len(items)),
                    "trends": json.dumps(trends, ensure_ascii=False),
                },
                client_mutation_id=f"hotspot-overview:{project_id}:v1",
            )
            summary = output.get("summary", "") or output.get("text", "")
        except Exception:
            summary = f"今日共采集 {len(items)} 条热点，来自 {len(set(it['source'] for it in items))} 个平台。" + \
                       f"热度最高话题：{top_items[0]['title'][:30] if top_items else '暂无'}。"

    return {
        "summary": summary,
        "categories": {k: len(v) for k, v in sorted(categories.items(), key=lambda x: -len(x[1]))},
        "category_items": categories,
        "trends": trends,
        "predicted_viral": predicted_viral,
        "recommended_angles": recommended_angles,
        "total_hotspots": len(items),
        "sources_active": list(set(it["source"] for it in items)),
        "generated_at": datetime.utcnow().isoformat(),
    }
