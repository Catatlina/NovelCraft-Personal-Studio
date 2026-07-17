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

_RANKING_QIDIAN_COUNT = int(_os.getenv("RANKING_QIDIAN_COUNT", "200"))
_RANKING_ZONGHENG_COUNT = int(_os.getenv("RANKING_ZONGHENG_COUNT", "200"))

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
        "leaderboard": f"分类榜-{cat_name}",
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


def _fetch_fanqie_rank_list(rv: str, max_count: int = 10) -> list[dict]:
    """Fetch the real default leaderboard from /api/rank/list (跨分类综合排行)."""
    try:
        u = f"https://fanqienovel.com/api/rank/list?app_id=2503&rank_version={rv}&rank_type=peak&offset=0&limit={max_count}"
        req = urllib.request.Request(u, headers={
            "Accept": "application/json", "Referer": "https://fanqienovel.com/rank",
            "User-Agent": "Mozilla/5.0"})
        with _retry_call(_urlopen, req, timeout=15) as resp:
            data = json.loads(resp.read())
        items = []
        for b in data.get("data", {}).get("list", []):
            bid = str(b.get("bookId", ""))
            if not bid: continue
            title = _decrypt_pua(str(b.get("bookName", "")))
            if not title: continue
            items.append({
                "rank": len(items) + 1, "title": title,
                "author": _decrypt_pua(str(b.get("author", ""))),
                "source": "fanqie", "source_book_id": bid,
                "url": f"https://fanqienovel.com/page/{bid}",
                "leaderboard": "巅峰榜",
            })
        return items
    except Exception:
        return []


def _fetch_fanqie_via_browser() -> list[dict]:
    """Use Playwright to scrape the rendered rank page for full leaderboard data.
    Fallback when /api/rank/list only returns 7 books."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    results: list[dict] = []
    rank_urls = [
        ("https://fanqienovel.com/rank/all", "巅峰榜"),
        ("https://fanqienovel.com/rank/hotsales", "热销榜"),
        ("https://fanqienovel.com/rank/newbook", "新书榜"),
        ("https://fanqienovel.com/rank/read", "阅读榜"),
    ]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            seen = set()

            for url, label in rank_urls:
                try:
                    page = context.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)  # Wait for JS render

                    # Extract book cards — tomato uses a[href*='/page/'] for book links
                    anchors = page.locator("a[href*='/page/']").all()
                    for a in anchors[:30]:  # Max 30 per leaderboard
                        try:
                            title = (a.get_attribute("title") or a.inner_text()).strip()
                            href = a.get_attribute("href") or ""
                        except Exception:
                            continue
                        if not title or len(title) < 2 or len(title) > 40:
                            continue
                        # Skip non-book links
                        if any(w in title for w in ["排行榜", "更多", "全部", "分类"]):
                            continue
                        dk = hashlib.sha256(title.encode()).hexdigest()
                        if dk in seen:
                            continue
                        seen.add(dk)
                        bid = href.rsplit("/", 1)[-1] if "/page/" in href else ""
                        results.append({
                            "rank": len(results) + 1,
                            "title": title,
                            "author": "",
                            "source": "fanqie",
                            "source_book_id": bid,
                            "url": f"https://fanqienovel.com{href}" if href.startswith("/") else href,
                            "leaderboard": label,
                        })
                    page.close()
                except Exception:
                    pass

            browser.close()
    except Exception:
        pass

    return results


def fetch_fanqie_ranking(leaderboard: str = "all", max_count: Optional[int] = None) -> list[dict]:
    """Fetch 番茄小说: 巅峰榜API + 全分类排名.

    Data sources:
    1. /api/rank/list — real cross-category default leaderboard (~7-10 books)
    2. /api/rank/category/list — per-category rankings (37 cats × both genders)
    """
    target = max_count or _RANKING_FANQIE_COUNT
    meta = _fanqie_meta()
    rv = meta.get("rank_version", "")
    if not rv:
        return [{"source": "fanqie", "degraded": True,
                 "error": "Fanqie unreachable"}]

    all_results: list[dict] = []
    seen: set[str] = set()

    # Phase 1: Real leaderboard API + browser scraping
    for item in _fetch_fanqie_rank_list(rv):
        dk = _make_dedup_key(item["title"], item["author"])
        if dk not in seen:
            seen.add(dk)
            all_results.append(item)

    # Phase 1b: Browser scraping (Playwright) — optional, skipped if unavailable
    try:
        browser_items = _fetch_fanqie_via_browser()
    except Exception:
        browser_items = []
    for item in browser_items:
        dk = _make_dedup_key(item["title"], item["author"])
        if dk not in seen:
            seen.add(dk)
            all_results.append(item)

    # Phase 2: Category rankings (3 per category, ~37×2×3 = ~222 books)
    targets = _build_category_targets(meta, leaderboard)
    per_cat = max(2, target // len(targets))
    rank_mold = _FANQIE_MOLD_MAP.get(leaderboard, "2")

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {}
        for cid, cname, g in targets:
            futs[ex.submit(_fetch_fanqie_one_category, cid, cname, g, rank_mold, per_cat)] = cname
        for fut in as_completed(futs):
            for item in fut.result() or []:
                dk = _make_dedup_key(item["title"], item["author"])
                if dk not in seen:
                    seen.add(dk)
                    item["rank"] = len(all_results) + 1
                    all_results.append(item)

    return all_results if all_results else [{"source": "fanqie", "degraded": True, "error": "No results"}]


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
        url = f"{base_url}?pageNum={page}"
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


def fetch_qidian_ranking(rank_type: str = "all",
                         max_count: Optional[int] = None) -> list[dict]:
    """Fetch 起点中文网: all 7 rank types combined (140+ books).

    Since pagination doesn't work (same page returned for all params),
    we combine all 7 rank types for enough unique books.
    """
    target = max_count or _RANKING_QIDIAN_COUNT
    if rank_type == "all":
        # Fetch all types, dedup across them
        all_types = list(_QIDIAN_LABELS.keys())
        all_results: list[dict] = []
        seen: set[str] = set()
        for rt in all_types:
            for item in _fetch_qidian_one_page(rt, 1):
                dk = _make_dedup_key(item["title"], item["author"])
                if dk not in seen:
                    seen.add(dk)
                    item["rank"] = len(all_results) + 1
                    all_results.append(item)
        return all_results[:target] if all_results else [{"source": "qidian", "degraded": True, "error": "No results from any rank type"}]

    # Single rank type
    label = _QIDIAN_LABELS.get(rank_type, rank_type)
    all_results: list[dict] = []
    seen_dedup: set[str] = set()
    for page in range(1, 11):
        page_items = _fetch_qidian_one_page(rank_type, page)
        if not page_items:
            break
        for item in page_items:
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
# Source 4: 七猫小说 — HTML scraping via regex
# ============================================================

def _fetch_qimao_page_html(url: str) -> str:
    """Fetch raw HTML from qimao.com."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with _urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def fetch_qimao_ranking(max_count: int = 50) -> list[dict]:
    """Fetch 七猫小说排行榜 via HTML scraping.

    Tries to extract book cards from the rank page using regex patterns
    matching the typical qimao.com page structure.
    """
    try:
        html = _fetch_qimao_page_html("https://www.qimao.com/rank/")
    except Exception:
        return []

    if not html:
        return []

    results: list[dict] = []
    seen_titles: set[str] = set()

    try:
        # Strategy 1: Look for __NUXT__ or __INITIAL_STATE__ JSON
        nuxt_match = re.search(r'window\.__NUXT__\s*=\s*({.*?});\s*</script>', html, re.DOTALL)
        if nuxt_match:
            try:
                nuxt_data = json.loads(nuxt_match.group(1))
                # Walk into state.data for book lists
                state = nuxt_data.get("state", {})
                rank_data = state.get("paihang", {}).get("data", [])
                for item in rank_data[:max_count]:
                    title = str(item.get("title", "")).strip()
                    author = str(item.get("author", "")).strip()
                    book_id = str(item.get("book_id", item.get("bookId", "")))
                    if not title:
                        continue
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)
                    results.append({
                        "rank": len(results) + 1,
                        "title": title,
                        "author": author,
                        "source": "qimao",
                        "source_book_id": book_id,
                        "url": f"https://www.qimao.com/book/{book_id}/" if book_id else "",
                        "leaderboard": "七猫热榜",
                    })
                if results:
                    return results[:max_count]
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
    except Exception:
        pass

    try:
        # Strategy 2: Regex scrape book links with title attributes
        # Match patterns like <a ... title="书名" href="/book/123/"
        book_pattern = re.findall(
            r'<a[^>]*title="([^"]{2,80})"[^>]*href="(/book/\d+[^"]*)"[^>]*>',
            html,
        )
        for title, href in book_pattern:
            title = title.strip()
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            book_id = re.search(r'/book/(\d+)', href)
            bid = book_id.group(1) if book_id else ""
            results.append({
                "rank": len(results) + 1,
                "title": title,
                "author": "",
                "source": "qimao",
                "source_book_id": bid,
                "url": f"https://www.qimao.com{href}" if href.startswith("/") else href,
                "leaderboard": "七猫热榜",
            })
            if len(results) >= max_count:
                break
    except Exception:
        pass

    if not results:
        try:
            # Strategy 3: Try API endpoint
            api_url = "https://www.qimao.com/qimaoapi/rank/book/list?rank_type=1&offset=0&limit=50"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Referer": "https://www.qimao.com/rank/",
            }
            req = urllib.request.Request(api_url, headers=headers)
            with _urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            books = data.get("data", {}).get("list", [])
            for item in books[:max_count]:
                title = str(item.get("title", "")).strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                book_id = str(item.get("book_id", item.get("bookId", "")))
                results.append({
                    "rank": len(results) + 1,
                    "title": title,
                    "author": str(item.get("author", "")).strip(),
                    "source": "qimao",
                    "source_book_id": book_id,
                    "url": f"https://www.qimao.com/book/{book_id}/" if book_id else "",
                    "leaderboard": "七猫热榜",
                })
        except Exception:
            pass

    return results[:max_count]


# ============================================================
# Source 5: QQ阅读 — HTML scraping via regex
# ============================================================

def fetch_qqread_ranking(max_count: int = 50) -> list[dict]:
    """Fetch QQ阅读排行榜 via HTML scraping.

    Scrapes the rank page using regex to extract book links with titles.
    """
    url = "https://book.qq.com/rank.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://book.qq.com/",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with _urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    if not html:
        return []

    results: list[dict] = []
    seen: set[str] = set()

    try:
        # Strategy 1: Look for window.__INITIAL_STATE__ or similar JSON
        json_matches = re.findall(
            r'window\.__(?:INITIAL_STATE__|DATA__|PREFETCH_DATA__)\s*=\s*({.*?});\s*(?:</script>|window\.)',
            html, re.DOTALL,
        )
        for json_str in json_matches:
            try:
                data = json.loads(json_str.replace("undefined", "null"))
                # Try common paths for book lists
                for path in ["rankList", "rank.list", "data.list", "data.rankList", "list"]:
                    books = data
                    for part in path.split("."):
                        books = books.get(part, {}) if isinstance(books, dict) else {}
                    if isinstance(books, list) and books:
                        for item in books:
                            if not isinstance(item, dict):
                                continue
                            title = str(item.get("title", item.get("bookName", item.get("name", "")))).strip()
                            if not title or title in seen:
                                continue
                            seen.add(title)
                            book_id = str(item.get("bookId", item.get("book_id", item.get("id", ""))))
                            results.append({
                                "rank": len(results) + 1,
                                "title": title,
                                "author": str(item.get("author", item.get("authorName", ""))).strip(),
                                "source": "qqread",
                                "source_book_id": book_id,
                                "url": f"https://book.qq.com/book-detail/{book_id}" if book_id else "",
                                "leaderboard": "QQ阅读榜",
                            })
                        if results:
                            return results[:max_count]
            except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
                continue
    except Exception:
        pass

    try:
        # Strategy 2: Regex scrape book links
        # Match common book detail link patterns
        link_patterns = [
            r'<a[^>]*href="([^"]*(?:book-detail|/book/|/detail/)\d+[^"]*)"[^>]*title="([^"]{2,100})"',
            r'<a[^>]*href="[^"]*book-detail/(\d+)[^"]*"[^>]*>[\s\S]*?<span[^>]*>([^<]{2,100})</span>',
            r'<h3[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>([^<]{2,100})</a>',
        ]
        for pattern in link_patterns:
            matches = re.findall(pattern, html)
            for href, title in matches:
                title = title.strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                bid_match = re.search(r'(\d{5,})', href)
                book_id = bid_match.group(1) if bid_match else ""
                results.append({
                    "rank": len(results) + 1,
                    "title": title,
                    "author": "",
                    "source": "qqread",
                    "source_book_id": book_id,
                    "url": href if href.startswith("http") else f"https://book.qq.com{href}",
                    "leaderboard": "QQ阅读榜",
                })
                if len(results) >= max_count:
                    break
            if results:
                break
    except Exception:
        pass

    return results[:max_count]


# ============================================================
# Source 6: 17K小说 — HTML scraping via regex
# ============================================================

def fetch_17k_ranking(max_count: int = 50) -> list[dict]:
    """Fetch 17K小说排行榜 via HTML scraping.

    Scrapes https://www.17k.com/top/ for book rankings.
    """
    url = "https://www.17k.com/top/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with _urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    if not html:
        return []

    results: list[dict] = []
    seen: set[str] = set()

    try:
        # Strategy 1: 17K uses <li> with data-rid/book links
        # Match book entries with book links and title
        book_entries = re.findall(
            r'<a[^>]*href="(/book/\d+\.html)"[^>]*title="([^"]{2,100})"[^>]*>',
            html,
        )
        for href, title in book_entries:
            title = title.strip()
            if not title or title in seen:
                continue
            seen.add(title)
            bid_match = re.search(r'/book/(\d+)', href)
            book_id = bid_match.group(1) if bid_match else ""
            results.append({
                "rank": len(results) + 1,
                "title": title,
                "author": "",
                "source": "17k",
                "source_book_id": book_id,
                "url": f"https://www.17k.com{href}",
                "leaderboard": "17K热榜",
            })
    except Exception:
        pass

    # Strategy 2: Try alternative patterns if needed
    if not results:
        try:
            # Match broader patterns: book link + adjacent text
            alt_matches = re.findall(
                r'<a[^>]*href="([^"]*17k\.com/book/\d+[^"]*)"[^>]*>(?:<[^>]*>)*([^<]{2,100})(?:</[^>]*>)*</a>',
                html,
            )
            for href, title in alt_matches:
                title = re.sub(r'<[^>]*>', '', title).strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                bid_match = re.search(r'(\d{4,})', href)
                book_id = bid_match.group(1) if bid_match else ""
                results.append({
                    "rank": len(results) + 1,
                    "title": title,
                    "author": "",
                    "source": "17k",
                    "source_book_id": book_id,
                    "url": href,
                    "leaderboard": "17K热榜",
                })
        except Exception:
            pass

    # Strategy 3: Try API
    if not results:
        try:
            api_url = "https://www.17k.com/top/refactor/top100/06/v7_impv1_049_100_0_0_1_0_0_0.html"
            req = urllib.request.Request(api_url, headers=headers)
            with _urlopen(req, timeout=15) as resp:
                api_html = resp.read().decode("utf-8", errors="replace")
            items = re.findall(
                r'<a[^>]*href="(/book/\d+\.html)"[^>]*title="([^"]{2,100})"[^>]*>',
                api_html,
            )
            for href, title in items:
                title = title.strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                bid_match = re.search(r'/book/(\d+)', href)
                book_id = bid_match.group(1) if bid_match else ""
                results.append({
                    "rank": len(results) + 1,
                    "title": title,
                    "author": "",
                    "source": "17k",
                    "source_book_id": book_id,
                    "url": f"https://www.17k.com{href}",
                    "leaderboard": "17K热榜",
                })
        except Exception:
            pass

    return results[:max_count]


# ============================================================
# Source 7: 晋江文学城 — HTML scraping via regex
# ============================================================

def fetch_jjwxc_ranking(max_count: int = 50) -> list[dict]:
    """Fetch 晋江文学城排行榜 via HTML scraping.

    Scrapes https://www.jjwxc.net/bookbase.php for book rankings.
    晋江 uses gb2312/gbk encoding.
    """
    url = "https://www.jjwxc.net/bookbase.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with _urlopen(req, timeout=15) as resp:
            raw = resp.read()
            # 晋江 uses gbk/gb2312 encoding
            html = None
            for enc in ["gbk", "gb2312", "gb18030", "utf-8"]:
                try:
                    html = raw.decode(enc)
                    if "晋江" in html or "book" in html.lower():
                        break
                except Exception:
                    continue
            if html is None:
                html = raw.decode("utf-8", errors="replace")
    except Exception:
        return []

    if not html:
        return []

    results: list[dict] = []
    seen: set[str] = set()

    try:
        # 晋江 bookbase uses table rows with links like <a href="onebook.php?novelid=123">
        book_links = re.findall(
            r'<a[^>]*href="(onebook\.php\?novelid=(\d+))"[^>]*>([^<]{2,200})</a>',
            html,
        )
        for href, book_id, title in book_links:
            title = title.strip()
            # Filter out non-book links
            if not title or len(title) < 2 or len(title) > 80:
                continue
            if any(w in title for w in ["排行榜", "更多", "下一页", "首页", "末页"]):
                continue
            if title in seen:
                continue
            seen.add(title)
            results.append({
                "rank": len(results) + 1,
                "title": title,
                "author": "",
                "source": "jjwxc",
                "source_book_id": book_id,
                "url": f"https://www.jjwxc.net/{href}",
                "leaderboard": "晋江书库榜",
            })
            if len(results) >= max_count:
                break
    except Exception:
        pass

    # Also try the rank page
    if len(results) < 20:
        try:
            rank_url = "https://www.jjwxc.net/bookbase.php?fw0=0&fbsj0=0&ycx0=0&xx0=0&mainview0=0&sd0=0&lx0=0&fg0=0&sortType=3&isfinish=0&collectiontypes=ors&page=1"
            req2 = urllib.request.Request(rank_url, headers=headers)
            with _urlopen(req2, timeout=15) as resp2:
                raw2 = resp2.read()
                html2 = None
                for enc in ["gbk", "gb2312", "gb18030", "utf-8"]:
                    try:
                        html2 = raw2.decode(enc)
                        break
                    except Exception:
                        continue
                if html2 is None:
                    html2 = raw2.decode("utf-8", errors="replace")
            book_links2 = re.findall(
                r'<a[^>]*href="(onebook\.php\?novelid=(\d+))"[^>]*>([^<]{2,200})</a>',
                html2,
            )
            for href, book_id, title in book_links2:
                title = title.strip()
                if not title or len(title) < 2 or len(title) > 80 or title in seen:
                    continue
                if any(w in title for w in ["排行榜", "更多", "下一页", "首页", "末页"]):
                    continue
                seen.add(title)
                results.append({
                    "rank": len(results) + 1,
                    "title": title,
                    "author": "",
                    "source": "jjwxc",
                    "source_book_id": book_id,
                    "url": f"https://www.jjwxc.net/{href}",
                    "leaderboard": "晋江书库榜",
                })
                if len(results) >= max_count:
                    break
        except Exception:
            pass

    return results[:max_count]


# ============================================================
# Source 8: 刺猬猫 — HTML scraping via regex
# ============================================================

def fetch_ciweimao_ranking(max_count: int = 50) -> list[dict]:
    """Fetch 刺猬猫排行榜 via HTML scraping.

    Scrapes https://www.ciweimao.com/book-list for book rankings.
    """
    url = "https://www.ciweimao.com/book-list"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with _urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    if not html:
        return []

    results: list[dict] = []
    seen: set[str] = set()

    try:
        # Strategy 1: Look for embedded JSON data
        json_patterns = [
            r'window\.__NUXT__\s*=\s*({.*?});\s*</script>',
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});\s*</script>',
            r'"bookList"\s*:\s*(\[.*?\])',
        ]
        for pattern in json_patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match.replace("undefined", "null")) if isinstance(match, str) else match
                    if not data:
                        continue
                    # Handle different data shapes
                    books = data if isinstance(data, list) else data.get("data", data.get("list", []))
                    if isinstance(books, dict):
                        books = books.get("list", books.get("data", []))
                    if not isinstance(books, list):
                        continue
                    for item in books:
                        if not isinstance(item, dict):
                            continue
                        title = str(item.get("title", item.get("book_name", item.get("name", "")))).strip()
                        if not title or title in seen:
                            continue
                        seen.add(title)
                        book_id = str(item.get("book_id", item.get("id", item.get("novel_id", ""))))
                        results.append({
                            "rank": len(results) + 1,
                            "title": title,
                            "author": str(item.get("author", item.get("author_name", ""))).strip(),
                            "source": "ciweimao",
                            "source_book_id": book_id,
                            "url": f"https://www.ciweimao.com/book/{book_id}" if book_id else "",
                            "leaderboard": "刺猬猫榜单",
                        })
                    if results:
                        return results[:max_count]
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
    except Exception:
        pass

    try:
        # Strategy 2: Regex scrape book cards
        # 刺猬猫 uses book cards with title links
        book_cards = re.findall(
            r'<a[^>]*href="(/book(?:-detail)?/(\d+))"[^>]*>[\s\S]*?<h\d[^>]*>([^<]{2,100})</h\d>',
            html, re.DOTALL,
        )
        for href, book_id, title in book_cards:
            title = title.strip()
            if not title or title in seen:
                continue
            seen.add(title)
            results.append({
                "rank": len(results) + 1,
                "title": title,
                "author": "",
                "source": "ciweimao",
                "source_book_id": book_id,
                "url": f"https://www.ciweimao.com{href}",
                "leaderboard": "刺猬猫榜单",
            })
            if len(results) >= max_count:
                break
    except Exception:
        pass

    if not results:
        try:
            # Broader link matching
            links = re.findall(
                r'<a[^>]*href="(/book(?:-detail)?/\d+)"[^>]*>([^<]{2,100})</a>',
                html,
            )
            for href, title in links:
                title = title.strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                bid_match = re.search(r'(\d+)', href)
                book_id = bid_match.group(1) if bid_match else ""
                results.append({
                    "rank": len(results) + 1,
                    "title": title,
                    "author": "",
                    "source": "ciweimao",
                    "source_book_id": book_id,
                    "url": f"https://www.ciweimao.com{href}",
                    "leaderboard": "刺猬猫榜单",
                })
        except Exception:
            pass

    return results[:max_count]


# ============================================================
# Unified ranking collector
# ============================================================

RANKING_FETCHERS = {
    "fanqie": fetch_fanqie_ranking,
    "qidian": fetch_qidian_ranking,
    "zongheng": fetch_zongheng_ranking,
    "qimao": fetch_qimao_ranking,
    "qqread": fetch_qqread_ranking,
    "17k": fetch_17k_ranking,
    "jjwxc": fetch_jjwxc_ranking,
    "ciweimao": fetch_ciweimao_ranking,
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
