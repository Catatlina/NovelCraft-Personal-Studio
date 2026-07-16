"""TASK-001/M1: Real ranking source adapters — HTTP scraping for 番茄/起点/纵横.

Based on proven open-source approaches:
  - 番茄: Qbook approach — fetch __INITIAL_STATE__ for rank_version, then call public API
  - 起点: Qbook approach — mobile page HTML parsing + __INITIAL_STATE__
  - 纵横: regex HTML parsing (existing)
"""

import hashlib
import unicodedata
import re, json, urllib.request, urllib.error
from datetime import datetime, timezone
from urllib.parse import urljoin

# HTTP proxy — route through China IP to bypass geo-blocks
_PROXY_URL = __import__("os").getenv("RANKING_PROXY_URL", "")
_proxy_handler = None


def _get_opener():
    """Return urllib opener with HTTP proxy if configured."""
    global _proxy_handler
    if _proxy_handler is not None:
        return _proxy_handler
    if _PROXY_URL:
        try:
            _proxy_handler = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": _PROXY_URL, "https": _PROXY_URL}))
            return _proxy_handler
        except Exception:
            pass
    _proxy_handler = False
    return _proxy_handler


def _urlopen(req, timeout=15, use_proxy=False):
    """Open URL, optionally through HTTP proxy."""
    if use_proxy:
        opener = _get_opener()
        if opener and opener is not False:
            return opener.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX)


# ============================================================
# Source 1: 番茄小说 — Public API via rank_version from page
# ============================================================

_FANQIE_META_CACHE: dict | None = None
_FANQIE_META_TS: float = 0
_FANQIE_META_TTL = 3600  # 1 hour

# SSL context for Chinese sites (cert issues from non-China IPs)
_SSL_CTX = __import__("ssl").create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = __import__("ssl").CERT_NONE


def _decrypt_pua(text: str) -> str:
    """Decrypt 番茄小说 PUA font-encoded titles."""
    try:
        from app.services.pua_map import decrypt_pua
        return decrypt_pua(text)
    except Exception:
        return text


def _fanqie_meta() -> dict:
    """Fetch fanqie rank page to extract rank_version and categories."""
    global _FANQIE_META_CACHE, _FANQIE_META_TS
    import time as _time
    now = _time.time()
    if _FANQIE_META_CACHE and (now - _FANQIE_META_TS) < _FANQIE_META_TTL:
        return _FANQIE_META_CACHE

    url = "https://fanqienovel.com/rank"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with _urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return {"rank_version": "", "categories": {}}

    idx = html.find("__INITIAL_STATE__=")
    if idx < 0:
        return {"rank_version": "", "categories": {}}

    start = idx + len("__INITIAL_STATE__=")
    end = html.find("</script>", start)
    json_str = html[start:end].strip().rstrip(";").strip()
    json_str = re.sub(r"\bundefined\b", "null", json_str)

    try:
        state, _ = __import__("json").JSONDecoder().raw_decode(json_str)
    except json.JSONDecodeError:
        return {"rank_version": "", "categories": {}}

    rank = state.get("rank", {})
    meta = {
        "rank_version": rank.get("rankVersion", ""),
        "categories": rank.get("rankCategoryTypeList", {}),
    }
    _FANQIE_META_CACHE = meta
    _FANQIE_META_TS = now
    return meta


def _fanqie_api_call(category_id: str, gender: str = "1", rank_mold: str = "2",
                     offset: int = 0, limit: int = 30) -> list[dict]:
    """Call fanqie ranking API (uses rank_version from page, no a_bogus needed)."""
    import urllib.parse
    meta = _fanqie_meta()
    params = urllib.parse.urlencode({
        "app_id": "2503", "rank_list_type": "3",
        "offset": offset, "limit": limit,
        "category_id": category_id, "rank_version": meta["rank_version"],
        "gender": gender, "rankMold": rank_mold,
    })
    api_url = f"https://fanqienovel.com/api/rank/category/list?{params}"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://fanqienovel.com/rank",
        "User-Agent": "Mozilla/5.0",
    }
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with _urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        if data.get("code") != 0:
            return []
        return data.get("data", {}).get("book_list", [])
    except Exception:
        return []


def fetch_fanqie_ranking(category: str = "read", gender: str = "") -> list[dict]:
    """Fetch 番茄小说 ranking.

    category: 'read' (在读榜) or 'new' (新书榜)
    gender: 'male' / 'female' / '' (默认男频+女频各取前5分类)
    """
    mold_map = {"read": "2", "new": "1"}
    gender_map = {"male": "1", "female": "0"}
    rank_mold = mold_map.get(category, "2")

    meta = _fanqie_meta()
    categories = meta.get("categories", {})
    if not categories:
        return [{"source": "fanqie", "degraded": True,
                 "error": "Fanqie rank page unreachable — check network"}]

    targets = []
    if gender in ("male", "female"):
        g = gender_map[gender]
        for cat in categories.get(gender, []):
            targets.append((cat["id"], cat["name"], g))
    else:
        # Default: ALL categories (both genders)
        for gk in ["male", "female"]:
            g = gender_map[gk]
            for cat in categories.get(gk, []):
                targets.append((cat["id"], cat["name"], g))

    if not targets:
        targets = [("261", "都市日常", "1")]

    results = []
    seen = set()
    for cat_id, cat_name, g in targets:
        for offset in range(0, 30, 10):
            items = _fanqie_api_call(cat_id, g, rank_mold, offset, 10)
            for item in items:
                book_id = str(item.get("book_id", item.get("bookId", "")))
                if not book_id or book_id in seen:
                    continue
                seen.add(book_id)
                results.append({
                    "rank": len(results) + 1,
                    "title": _decrypt_pua(str(item.get("bookName", item.get("book_name", "")))),
                    "author": _decrypt_pua(str(item.get("author", item.get("author_name", "")))),
                    "category": cat_name,
                    "source": "fanqie",
                    "source_book_id": book_id,
                    "url": f"https://fanqienovel.com/page/{book_id}",
                    "read_count": item.get("read_count", item.get("readCount", 0)),
                    "word_count": item.get("wordCount", item.get("word_count", 0)),
                })
            if len(items) < 10:
                break

    if not results:
        return [{"source": "fanqie", "degraded": True,
                 "error": "Fanqie API returned no results"}]
    return results


# ============================================================
# Source 2: 起点中文网 — Mobile page + __INITIAL_STATE__
# ============================================================

_QIDIAN_MOBILE_URLS = {
    "hotsales":  "https://m.qidian.com/rank/hotsales/",
    "newbook":   "https://m.qidian.com/rank/newbook/",
    "finished":  "https://m.qidian.com/rank/finished/",
    "recommend": "https://m.qidian.com/rank/",
    "monthly":   "https://m.qidian.com/rank/yuepiao/",
    "collect":   "https://m.qidian.com/rank/collect/",
    "fans":      "https://m.qidian.com/rank/fans/",
}

_QIDIAN_LABELS = {
    "hotsales": "畅销榜", "newbook": "新书榜", "finished": "完本榜",
    "recommend": "推荐榜", "monthly": "月票榜", "collect": "收藏榜", "fans": "粉丝榜",
}


def fetch_qidian_ranking(rank_type: str = "hotsales") -> list[dict]:
    """Fetch 起点中文网 ranking.
    rank_type: 'hotsales'/'monthly'/'newbook'/'finished'/'recommend'/'collect'/'fans'
    Requires China IP proxy (set RANKING_PROXY_URL).
    """
    label = _QIDIAN_LABELS.get(rank_type, rank_type)
    url = _QIDIAN_MOBILE_URLS.get(rank_type, _QIDIAN_MOBILE_URLS["hotsales"])
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with _urlopen(req, timeout=15, use_proxy=True) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return [{"source": "qidian", "degraded": True,
                 "error": f"Qidian unreachable: {e}"}]

    # Extract JSON from <script> tag: {"pageContext":{..."records":[...]}}
    scripts = re.findall(
        r'<script[^>]*>\s*(\{.*?"records"\s*:\s*\[.*?\})\s*</script>',
        html, re.DOTALL,
    )
    if scripts:
        try:
            data = __import__("json").JSONDecoder().raw_decode(scripts[0])[0]
            records = (
                data.get("pageContext", {})
                .get("pageProps", {})
                .get("pageData", {})
                .get("records", [])
            )
        except Exception:
            records = []

        if records:
            results = []
            for r in records:
                if not isinstance(r, dict):
                    continue
                bid = str(r.get("bid", r.get("bookId", "")))
                if not bid:
                    continue
                results.append({
                    "rank": int(r.get("rankNum", len(results) + 1)),
                    "title": str(r.get("bName", r.get("bookName", ""))),
                    "author": str(r.get("bAuth", r.get("authorName", ""))),
                    "intro": str(r.get("desc", ""))[:300],
                    "word_count": str(r.get("cnt", "")),
                    "category": f"{r.get('cat', '')}|{r.get('subCat', '')}",
                    "rank_count": str(r.get("rankCnt", "")),
                    "source": "qidian",
                    "source_book_id": bid,
                    "url": f"https://m.qidian.com/book/{bid}/",
                })
            return results

    return [{"source": "qidian", "degraded": True,
             "error": "Qidian page script JSON not found"}]




# Source 3: 纵横中文网 — HTML regex
# ============================================================

def fetch_zongheng_ranking() -> list[dict]:
    """Fetch 纵横中文网排行榜 via HTML parsing."""
    url = "https://www.zongheng.com/rank"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with _urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        results = []
        matches = re.findall(
            r'<div data-id="(?P<id>\d+)" class="zh-modules-rank-book[^>]*>.*?'
            r'<p class="book-rank--title-text[^>]*>\s*<a title="(?P<title>[^"]+)" '
            r'href="(?P<url>[^"]+)"',
            html, re.DOTALL,
        )
        seen = set()
        for book_id, title, href in matches:
            if book_id in seen:
                continue
            seen.add(book_id)
            results.append({
                "rank": len(results) + 1, "title": title.strip(), "author": "",
                "source": "zongheng", "source_book_id": book_id,
                "url": urljoin(url, href),
            })
            if len(results) >= 20:
                break
        if not results:
            raise ValueError("Zongheng parser produced no items (schema drift)")
        return results
    except Exception as e:
        return [{"source": "zongheng", "error": str(e), "degraded": True}]


# ============================================================
# Unified ranking collector
# ============================================================

RANKING_FETCHERS = {
    "fanqie": fetch_fanqie_ranking,
    "qidian": fetch_qidian_ranking,
    "zongheng": fetch_zongheng_ranking,
}


def collect_all_rankings() -> dict:
    """Collect from all available sources."""
    return {
        "fanqie": fetch_fanqie_ranking(),
        "qidian": fetch_qidian_ranking("monthly"),
        "zongheng": fetch_zongheng_ranking(),
    }


def normalize_ranking_items(source: str, items: list[dict],
                            fetched_at: datetime | None = None) -> list[dict]:
    """Normalize and deduplicate one source response."""
    normalized: list[dict] = []
    seen: set[str] = set()
    fetched_at = fetched_at or datetime.now(timezone.utc)
    best_by_key: dict[str, dict] = {}
    for raw in items:
        if raw.get("error") or raw.get("degraded"):
            continue
        title = unicodedata.normalize("NFKC", re.sub(r"\s+", " ", str(raw.get("title", ""))).strip())
        if not title:
            continue
        author = unicodedata.normalize("NFKC", re.sub(r"\s+", " ", str(raw.get("author", ""))).strip())
        source_url = str(raw.get("url", "")).strip()
        external_raw = raw.get("external_id", raw.get("source_book_id", raw.get("book_id", raw.get("bookId"))))
        external_id = str(external_raw).strip() if external_raw not in (None, "") else None
        if not external_id and source_url:
            path_ids = re.findall(r"\d{4,}", source_url)
            external_id = path_ids[-1] if path_ids else None
        identity = external_id or f"{title.casefold()}|{author.casefold()}"
        dedupe_key = hashlib.sha256(f"{source}:{identity}".encode("utf-8")).hexdigest()
        metrics = {
            "readers": str(raw.get("readers", raw.get("read_count", ""))),
            "status": str(raw.get("status", "")),
            "last_update": str(raw.get("last_update", "")),
        }
        if raw.get("word_count") or raw.get("wordCount"):
            metrics["word_count"] = raw.get("word_count", raw.get("wordCount", 0))
        if raw.get("intro"):
            metrics["intro"] = str(raw.get("intro", ""))[:200]
        if any(key in raw for key in ("collector", "confidence", "evidence")):
            metrics.update({
                "collector": str(raw.get("collector", "http")),
                "confidence": float(raw.get("confidence", 1.0)),
                "evidence": raw.get("evidence", {}),
            })
        item = {
            "source_key": source,
            "external_id": external_id,
            "rank_no": int(raw.get("rank_no", raw.get("rank")) or len(normalized) + 1),
            "title": title,
            "author": author,
            "category": str(raw.get("category", "")),
            "source_url": source_url,
            "metrics": metrics,
            "dedupe_key": dedupe_key,
            "fetched_at": fetched_at,
        }
        previous = best_by_key.get(dedupe_key)
        if previous is None or item["rank_no"] < previous["rank_no"]:
            best_by_key[dedupe_key] = item
    return sorted(best_by_key.values(), key=lambda x: x["rank_no"])
