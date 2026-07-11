"""TASK-001/M1: Real ranking source adapters — HTTP scraping, no API key needed."""

import hashlib
import unicodedata
import re, json, urllib.request
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse


# ============================================================
# Source 1: 番茄小说 (fanqienovel.com) — HTML 解析
# ============================================================

def fetch_fanqie_ranking(category: str = "novel_rank") -> list[dict]:
    """
    Scrape 番茄小说 mobile API (no auth required).
    Returns list of {rank, title, author, status, readers, last_update, url}.
    """
    url = f"https://fanqienovel.com/api/author/library/book_list/v0/rank/?page_size=20&rank_type=1&category_type=0"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://fanqienovel.com/",
        "Accept": "application/json",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        books = data.get("data", {}).get("book_list", data.get("data", []))
        if isinstance(books, dict):
            books = list(books.values())
        results = []
        for i, b in enumerate(books[:20], 1):
            if isinstance(b, dict):
                results.append({
                    "rank": i,
                    "title": b.get("book_name", b.get("title", "")),
                    "author": b.get("author", ""),
                    "status": "completed" if b.get("is_finish") else "ongoing",
                    "readers": str(b.get("read_count", "")),
                    "last_update": b.get("last_publish_time_desc", ""),
                    "source": "fanqie",
                    "url": f"https://fanqienovel.com/page/{b.get('book_id', '')}",
                })
        return results
    except Exception as e:
        return [{"source": "fanqie", "error": str(e), "degraded": True}]


# ============================================================
# Source 2: 起点 (Qidian) — JSONP 接口
# ============================================================

def fetch_qidian_ranking() -> list[dict]:
    """
    Fetch 起点排行榜 via JSONP API.
    Returns list of {rank, title, author, category, status, url}.
    """
    url = "https://www.qidian.com/ajax/rank/index?channelId=0&catId=0&style=1&page=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.qidian.com/rank/",
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        # Qidian returns JSONP: jQuery(...) — extract JSON
        match = re.search(r'\((\{.*\})\)', text, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
        else:
            data = json.loads(text) if text.startswith("{") else {}
        books = data.get("data", {}).get("books", data.get("data", []))
        if not books:
            raise ValueError("Qidian returned no ranking data (possible anti-bot or schema drift)")
        results = []
        for i, b in enumerate(books[:20], 1):
            results.append({
                "rank": i,
                "title": b.get("bName", b.get("bookName", "")),
                "author": b.get("bAuth", b.get("authorName", "")),
                "category": b.get("catName", ""),
                "status": b.get("bookStatus", ""),
                "readers": str(b.get("bScore", "")),
                "source": "qidian",
                "url": f"https://www.qidian.com/book/{b.get('bid', b.get('bookId', ''))}/",
            })
        return results
    except Exception as e:
        return [{"source": "qidian", "error": str(e), "degraded": True}]


# ============================================================
# Source 3: 纵横中文网 (Zongheng) — HTML 解析
# ============================================================

def fetch_zongheng_ranking() -> list[dict]:
    """Fetch 纵横中文网排行榜."""
    url = "https://www.zongheng.com/rank"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # The current page is server-rendered. Use the first visible rank block,
        # not the old /rank/details page which now returns an incompatible shell.
        results = []
        matches = re.findall(
            r'<div data-id="(?P<id>\d+)" class="zh-modules-rank-book[^>]*>.*?'
            r'<p class="book-rank--title-text[^>]*>\s*<a title="(?P<title>[^"]+)" '
            r'href="(?P<url>[^"]+)"',
            html,
            re.DOTALL,
        )
        seen = set()
        for book_id, title, href in matches:
            if book_id in seen:
                continue
            seen.add(book_id)
            results.append({"rank": len(results) + 1, "title": title.strip(), "author": "", "source": "zongheng",
                            "source_book_id": book_id, "url": urljoin(url, href)})
            if len(results) >= 20:
                break
        if not results:
            raise ValueError("Zongheng ranking parser produced no items (schema drift)")
        return results
    except Exception as e:
        return [{"source": "zongheng", "error": str(e), "degraded": True}]


# ============================================================
# Unified ranking collector
# ============================================================

def collect_all_rankings() -> dict:
    """Collect from all available sources. Returns {source: [book list]}."""
    return {
        "fanqie": fetch_fanqie_ranking(),
        "qidian": fetch_qidian_ranking(),
        "zongheng": fetch_zongheng_ranking(),
    }


RANKING_FETCHERS = {
    "fanqie": fetch_fanqie_ranking,
    "qidian": fetch_qidian_ranking,
    "zongheng": fetch_zongheng_ranking,
}


def normalize_ranking_items(source: str, items: list[dict], fetched_at: datetime | None = None) -> list[dict]:
    """Normalize and deduplicate one source response without hiding failures."""
    normalized: list[dict] = []
    seen: set[str] = set()
    fetched_at = fetched_at or datetime.now(timezone.utc)
    best_by_key: dict[str, dict] = {}
    for raw in items:
        if raw.get("error"):
            continue
        title = unicodedata.normalize("NFKC", re.sub(r"\s+", " ", str(raw.get("title", ""))).strip())
        if not title:
            continue
        author = unicodedata.normalize("NFKC", re.sub(r"\s+", " ", str(raw.get("author", ""))).strip())
        source_url = str(raw.get("url", "")).strip()
        external_raw = raw.get("external_id", raw.get("source_book_id", raw.get("book_id", raw.get("bookId"))))
        external_id = str(external_raw).strip() if external_raw not in (None, "") else None
        if not external_id and source_url:
            path_ids = re.findall(r"\d{4,}", urlparse(source_url).path)
            external_id = path_ids[-1] if path_ids else None
        identity = external_id or f"{title.casefold()}|{author.casefold()}"
        dedupe_key = hashlib.sha256(f"{source}:{identity}".encode("utf-8")).hexdigest()
        item = {
            "source_key": source,
            "external_id": external_id,
            "rank_no": int(raw.get("rank_no", raw.get("rank")) or len(normalized) + 1),
            "title": title,
            "author": author,
            "category": str(raw.get("category", "")),
            "source_url": source_url,
            "metrics": {"readers": str(raw.get("readers", "")), "status": str(raw.get("status", "")),
                        "last_update": str(raw.get("last_update", ""))},
            "dedupe_key": dedupe_key,
            "fetched_at": fetched_at,
        }
        previous = best_by_key.get(dedupe_key)
        if previous is None or item["rank_no"] < previous["rank_no"]:
            best_by_key[dedupe_key] = item
    return sorted(best_by_key.values(), key=lambda item: item["rank_no"])


def store_ranking_snapshot(rankings: dict) -> int:
    """Store ranking data as knowledge_items."""
    from app.db import connect, new_id, encode
    db = connect()
    count = 0
    for source, books in rankings.items():
        for book in books:
            if "error" in book:
                continue
            try:
                db.execute(
                    "INSERT INTO knowledge_items (id, kind, title, body, meta) VALUES (%s,%s,%s,%s,%s)",
                    (new_id(), "ranking", f"[{book['rank']}] {book['title'][:120]}",
                     json.dumps(book, ensure_ascii=False),
                     encode({"source": source, "rank": book["rank"], "author": book.get("author", ""), "url": book.get("url", "")})),
                )
                count += 1
            except Exception:
                pass
    db.commit(); db.close()
    return count
