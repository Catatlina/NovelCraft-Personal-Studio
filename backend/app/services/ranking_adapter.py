"""TASK-001/M1: Real ranking source adapters — HTTP scraping for 番茄/起点/纵横.

Based on proven open-source approaches:
  - 番茄: Qbook approach — fetch __INITIAL_STATE__ for rank_version, then call public API
  - 起点: Qbook approach — mobile page HTML parsing + __INITIAL_STATE__
  - 纵横: regex HTML parsing (existing)

Expanded coverage (M5):
  - 番茄: full leaderboard coverage (主榜/新书榜/分类榜/etc), pagination, retry, concurrency
  - 起点: multi-page pagination → 100+ books
  - 纵横: multi-page pagination → 100+ books
"""

import hashlib
import unicodedata
import re, json, urllib.request, urllib.error
import time as _time_module
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urljoin

from typing import Optional


# ---------------------------------------------------------------------------
# Configurable env vars
# ---------------------------------------------------------------------------
_os = __import__("os")
_PROXY_URL = _os.getenv("RANKING_PROXY_URL", "")
_RANKING_FANQIE_COUNT = int(_os.getenv("RANKING_FANQIE_COUNT", "100"))
# Validate: must be one of 50/100/200/500/1000
_VALID_COUNTS = {50, 100, 200, 500, 1000}
if _RANKING_FANQIE_COUNT not in _VALID_COUNTS:
    _RANKING_FANQIE_COUNT = 100

_RANKING_QIDIAN_COUNT = int(_os.getenv("RANKING_QIDIAN_COUNT", "100"))
_RANKING_ZONGHENG_COUNT = int(_os.getenv("RANKING_ZONGHENG_COUNT", "100"))

# Retry config
_RETRY_MAX = 3
_RETRY_BACKOFF = 2.0  # seconds

# Proxy handler (lazy init)
_proxy_handler = None

# SSL context for Chinese sites (cert issues from non-China IPs)
_SSL_CTX = __import__("ssl").create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = __import__("ssl").CERT_NONE


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


def _retry_call(fn, *args, max_retries=_RETRY_MAX, backoff=_RETRY_BACKOFF, **kwargs):
    """Call fn with retry logic: up to max_retries attempts with exponential backoff."""
    last_err: Exception = RuntimeError("_retry_call: no attempts made")
    for attempt in range(1, max_retries + 1):
        try:
            result = fn(*args, **kwargs)
            return result
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                _time_module.sleep(backoff * (2 ** (attempt - 1)))
    raise last_err


# ============================================================
# Source 1: 番茄小说 — Public API via rank_version from page
# ============================================================

_FANQIE_META_CACHE: Optional[dict] = None
_FANQIE_META_TS: float = 0
_FANQIE_META_TTL = 3600  # 1 hour


def _decrypt_pua(text: str) -> str:
    """Decrypt 番茄小说 PUA font-encoded titles."""
    try:
        from app.services.pua_map import decrypt_pua
        return decrypt_pua(text)
    except Exception:
        return text


def _fanqie_meta() -> dict:
    """Fetch fanqie rank page to extract rank_version and categories.

    Returns dict with keys:
      - rank_version: str
      - categories: dict like {"male": [{id, name}, ...], "female": [...]}
    """
    global _FANQIE_META_CACHE, _FANQIE_META_TS
    now = _time_module.time()
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
        with _retry_call(_urlopen, req, timeout=15) as resp:
            data = json.loads(resp.read())
        if data.get("code") != 0:
            return []
        return data.get("data", {}).get("book_list", [])
    except Exception:
        return []


def _build_category_targets(meta: dict, leaderboard: str) -> list[tuple[str, str, str]]:
    """Build list of (category_id, category_name, gender) tuples for a leaderboard.

    leaderboard values:
      - 'all' / 'main' / 'hotsales' / 'recommend' / 'monthly' / 'weekly' / 'daily' / 'completed' / 'category':
          All categories, both genders, rankMold=2 (阅读榜)
      - 'newbook': All categories, both genders, rankMold=1 (新书榜)
      - 'male' / 'female': gender-specific, rankMold=2
    """
    gender_map = {"male": "1", "female": "0"}
    categories = meta.get("categories", {})
    if not categories:
        return [("261", "都市日常", "1")]  # fallback

    targets = []
    if leaderboard in ("male",):
        for cat in categories.get("male", []):
            targets.append((cat["id"], cat["name"], "1"))
    elif leaderboard in ("female",):
        for cat in categories.get("female", []):
            targets.append((cat["id"], cat["name"], "0"))
    else:
        # All leaderboards: both genders, all categories
        for gk, gv in [("male", "1"), ("female", "0")]:
            for cat in categories.get(gk, []):
                targets.append((cat["id"], cat["name"], gv))

    if not targets:
        targets = [("261", "都市日常", "1")]
    return targets


# Leaderboard type → rankMold mapping
_FANQIE_MOLD_MAP = {
    "newbook": "1",  # 新书榜
    "all": "2", "main": "2", "hotsales": "2", "recommend": "2",
    "monthly": "2", "weekly": "2", "daily": "2", "completed": "2",
    "category": "2", "male": "2", "female": "2",
}

# Leaderboard labels
_FANQIE_LABELS = {
    "all": "全站榜", "main": "主榜", "newbook": "新书榜",
    "hotsales": "热销榜", "completed": "完结榜", "recommend": "推荐榜",
    "monthly": "月榜", "weekly": "周榜", "daily": "日榜",
    "category": "分类榜", "male": "男频榜", "female": "女频榜",
}


def _parse_fanqie_item(item: dict, cat_name: str, rank: int) -> Optional[dict]:
    """Parse a single fanqie API item into a normalized dict. Returns None if invalid."""
    book_id = str(item.get("book_id", item.get("bookId", "")))
    if not book_id:
        return None
    title = _decrypt_pua(str(item.get("bookName", item.get("book_name", ""))))
    author = _decrypt_pua(str(item.get("author", item.get("author_name", ""))))
    if not title:
        return None
    creation_status = item.get("creationStatus", "")
    return {
        "rank": rank,
        "title": title,
        "author": author,
        "category": cat_name,
        "source": "fanqie",
        "source_book_id": book_id,
        "url": f"https://fanqienovel.com/page/{book_id}",
        "read_count": item.get("read_count", item.get("readCount", 0)),
        "word_count": item.get("wordNumber", item.get("word_count", 0)),
        "creation_status": str(creation_status),
    }


def _make_dedup_key(title: str, author: str) -> str:
    """Create a dedup key from title+author (NFKC normalized)."""
    t = unicodedata.normalize("NFKC", re.sub(r"\s+", " ", title).strip())
    a = unicodedata.normalize("NFKC", re.sub(r"\s+", " ", author).strip())
    return hashlib.sha256(f"{t.casefold()}|{a.casefold()}".encode("utf-8")).hexdigest()


def _fetch_fanqie_one_category(cat_id: str, cat_name: str, gender: str,
                                rank_mold: str, max_count: int) -> list[dict]:
    """Fetch all pages for a single fanqie category. Returns up to max_count items."""
    results = []
    limit = 30  # API max per page
    pages = max(1, (max_count + limit - 1) // limit)  # ceiling division
    seen = set()
    for offset_idx in range(pages):
        offset = offset_idx * limit
        items = _fanqie_api_call(cat_id, gender, rank_mold, offset, limit)
        for item in items:
            book_id = str(item.get("book_id", item.get("bookId", "")))
            if not book_id or book_id in seen:
                continue
            seen.add(book_id)
            parsed = _parse_fanqie_item(item, cat_name, len(results) + 1)
            if parsed:
                results.append(parsed)
        if len(items) < limit:
            break  # no more pages
    return results


def fetch_fanqie_ranking(leaderboard: str = "all", max_count: Optional[int] = None) -> list[dict]:
    """Fetch 番茄小说 ranking with full leaderboard coverage.

    Args:
        leaderboard: Leaderboard type. One of:
            'all' (全站榜), 'main' (主榜), 'newbook' (新书榜),
            'hotsales' (热销榜), 'completed' (完结榜), 'recommend' (推荐榜),
            'monthly' (月榜), 'weekly' (周榜), 'daily' (日榜),
            'category' (分类榜), 'male' (男频), 'female' (女频)
        max_count: Max books to collect (default: RANKING_FANQIE_COUNT env var, 100).

    Features:
      - Expands to ALL categories (both genders) for most leaderboard types
      - Auto-paginates to hit target count
      - Deduplicates by title+author hash
      - Uses ThreadPoolExecutor for concurrent category fetching
      - Retry logic: 3 attempts with exponential backoff
    """
    target = max_count or _RANKING_FANQIE_COUNT
    rank_mold = _FANQIE_MOLD_MAP.get(leaderboard, "2")
    label = _FANQIE_LABELS.get(leaderboard, leaderboard)

    meta = _fanqie_meta()
    if not meta.get("rank_version"):
        return [{"source": "fanqie", "degraded": True,
                 "error": "Fanqie rank page unreachable — check network"}]

    targets = _build_category_targets(meta, leaderboard)
    # Distribute target count across categories (at least 30 per category)
    per_cat = max(30, (target + len(targets) - 1) // len(targets))

    all_results: list[dict] = []
    seen_dedup: set[str] = set()

    # Concurrent fetching across categories
    with ThreadPoolExecutor(max_workers=min(8, len(targets))) as executor:
        futures = {}
        for cat_id, cat_name, g in targets:
            fut = executor.submit(
                _fetch_fanqie_one_category, cat_id, cat_name, g, rank_mold, per_cat)
            futures[fut] = (cat_id, cat_name)

        for fut in as_completed(futures):
            cat_id, cat_name = futures[fut]
            try:
                items = fut.result()
            except Exception:
                items = []
            for item in items:
                dk = _make_dedup_key(item["title"], item["author"])
                if dk in seen_dedup:
                    continue
                seen_dedup.add(dk)
                # Re-rank
                item["rank"] = len(all_results) + 1
                item["leaderboard"] = label
                all_results.append(item)

    # If 完结榜, filter to only completed books
    if leaderboard == "completed":
        all_results = [b for b in all_results if b.get("creation_status") == "0"]
        for i, b in enumerate(all_results):
            b["rank"] = i + 1

    # Truncate to target
    all_results = all_results[:target]

    if not all_results:
        return [{"source": "fanqie", "degraded": True,
                 "error": "Fanqie API returned no results"}]
    return all_results


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

_QIDIAN_PAGE_SIZE = 20  # qidian mobile returns ~20 per page


def _fetch_qidian_one_page(rank_type: str, page: int) -> list[dict]:
    """Fetch a single page of qidian ranking. Returns list of normalized book dicts."""
    label = _QIDIAN_LABELS.get(rank_type, rank_type)
    base_url = _QIDIAN_MOBILE_URLS.get(rank_type, _QIDIAN_MOBILE_URLS["hotsales"])
    if page > 1:
        url = f"{base_url}?page={page}"
    else:
        url = base_url

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with _retry_call(_urlopen, req, timeout=15, use_proxy=True) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    # Extract JSON from <script> tag: {"pageContext":{...\"records\":[...]}}
    scripts = re.findall(
        r'<script[^>]*>\s*(\{.*?"records"\s*:\s*\[.*?\})\s*</script>',
        html, re.DOTALL,
    )
    if not scripts:
        return []

    try:
        data = __import__("json").JSONDecoder().raw_decode(scripts[0])[0]
        records = (
            data.get("pageContext", {})
            .get("pageProps", {})
            .get("pageData", {})
            .get("records", [])
        )
    except Exception:
        return []

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
            "leaderboard": label,
        })
    return results


def fetch_qidian_ranking(rank_type: str = "hotsales",
                         max_count: Optional[int] = None) -> list[dict]:
    """Fetch 起点中文网 ranking with multi-page pagination.

    Args:
        rank_type: 'hotsales'/'monthly'/'newbook'/'finished'/'recommend'/'collect'/'fans'
        max_count: Max books to collect (default: RANKING_QIDIAN_COUNT env var, 100).

    Requires China IP proxy (set RANKING_PROXY_URL).

    Fetches up to 5+ pages (100+ books) by paginating through ?page=N.
    """
    target = max_count or _RANKING_QIDIAN_COUNT
    label = _QIDIAN_LABELS.get(rank_type, rank_type)
    pages_needed = max(1, (target + _QIDIAN_PAGE_SIZE - 1) // _QIDIAN_PAGE_SIZE)
    # Cap at 10 pages to be safe (200 books max)
    pages_needed = min(pages_needed, 10)

    all_results: list[dict] = []
    seen_ids: set[str] = set()
    seen_dedup: set[str] = set()

    for page in range(1, pages_needed + 1):
        page_items = _fetch_qidian_one_page(rank_type, page)
        if not page_items:
            break
        for item in page_items:
            bid = item.get("source_book_id", "")
            if bid in seen_ids:
                continue
            seen_ids.add(bid)
            dk = _make_dedup_key(item["title"], item["author"])
            if dk in seen_dedup:
                continue
            seen_dedup.add(dk)
            item["rank"] = len(all_results) + 1
            item["leaderboard"] = label
            all_results.append(item)
        if len(page_items) < _QIDIAN_PAGE_SIZE:
            break  # last page

    all_results = all_results[:target]
    if not all_results:
        return [{"source": "qidian", "degraded": True,
                 "error": "Qidian page script JSON not found"}]
    return all_results


# ============================================================
# Source 3: 纵横中文网 — HTML regex with pagination
# ============================================================

_ZONGHENG_PAGE_SIZE = 30  # approximate per page


def _fetch_zongheng_one_page(page: int = 1) -> list[dict]:
    """Fetch one page of 纵横中文网 rankings."""
    url = "https://www.zongheng.com/rank"
    if page > 1:
        url = f"{url}?page={page}"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with _retry_call(_urlopen, req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    results = []
    # Extract book blocks with id, title, url, and author
    # Each book entry is a div with class zh-modules-rank-book containing data-id
    book_blocks = re.findall(
        r'<div[^>]*data-id="(?P<id>\d+)"[^>]*class="[^"]*zh-modules-rank-book[^"]*"[^>]*>'
        r'(.*?)'
        r'(?=<div[^>]*data-id="\d+"[^>]*class="[^"]*zh-modules-rank-book|$)',
        html, re.DOTALL,
    )

    seen = set()
    for book_id, block_html in book_blocks:
        if book_id in seen:
            continue
        seen.add(book_id)

        # Extract title and URL
        title_match = re.search(
            r'<a[^>]*title="([^"]*)"[^>]*href="([^"]*)"[^>]*class="[^"]*global-hover[^"]*"[^>]*>\s*\1\s*</a>',
            block_html,
        )
        if not title_match:
            # Try alternative pattern
            title_match = re.search(
                r'<a[^>]*title="([^"]*)"[^>]*href="([^"]*)"[^>]*>',
                block_html,
            )

        title = title_match.group(1).strip() if title_match else ""
        href = title_match.group(2) if title_match else ""

        # Extract author
        author = ""
        author_match = re.search(
            r'<a[^>]*href="[^"]*userInfo[^"]*"[^>]*class="[^"]*global-hover[^"]*"[^>]*>([^<]+)</a>',
            block_html,
        )
        if author_match:
            author = author_match.group(1).strip()

        if title:
            results.append({
                "rank": len(results) + 1,
                "title": title,
                "author": author,
                "source": "zongheng",
                "source_book_id": book_id,
                "url": urljoin(url, href),
            })

    return results


def fetch_zongheng_ranking(max_count: Optional[int] = None) -> list[dict]:
    """Fetch 纵横中文网排行榜 via HTML parsing with pagination.

    Args:
        max_count: Max books to collect (default: RANKING_ZONGHENG_COUNT env var, 100).

    Fetches multiple pages to reach target count (100+ books).
    """
    target = max_count or _RANKING_ZONGHENG_COUNT
    pages_needed = max(1, (target + _ZONGHENG_PAGE_SIZE - 1) // _ZONGHENG_PAGE_SIZE)
    pages_needed = min(pages_needed, 10)  # cap

    all_results: list[dict] = []
    seen_ids: set[str] = set()
    seen_dedup: set[str] = set()

    for page in range(1, pages_needed + 1):
        page_items = _fetch_zongheng_one_page(page)
        if not page_items:
            break
        for item in page_items:
            bid = item.get("source_book_id", "")
            if bid in seen_ids:
                continue
            seen_ids.add(bid)
            dk = _make_dedup_key(item["title"], item["author"])
            if dk in seen_dedup:
                continue
            seen_dedup.add(dk)
            item["rank"] = len(all_results) + 1
            item["leaderboard"] = "纵横榜"
            all_results.append(item)
        if len(page_items) < _ZONGHENG_PAGE_SIZE * 0.5:
            break  # likely last page

    all_results = all_results[:target]
    if not all_results:
        return [{"source": "zongheng", "error": "No results from zongheng", "degraded": True}]
    return all_results


# ============================================================
# Unified ranking collector
# ============================================================

RANKING_FETCHERS = {
    "fanqie": fetch_fanqie_ranking,
    "qidian": fetch_qidian_ranking,
    "zongheng": fetch_zongheng_ranking,
}


def collect_all_rankings() -> dict:
    """Collect from all available sources with expanded coverage."""
    return {
        "fanqie": fetch_fanqie_ranking("all"),
        "qidian": fetch_qidian_ranking("monthly"),
        "zongheng": fetch_zongheng_ranking(),
    }


def normalize_ranking_items(source: str, items: list[dict],
                            fetched_at: Optional[datetime] = None) -> list[dict]:
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
