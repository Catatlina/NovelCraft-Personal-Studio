"""TASK-001/M1: Real ranking source adapters — HTTP scraping, no API key needed."""

import hashlib
import unicodedata
import re, json, urllib.request
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from app.services.ranking_capture import configured_capture


# ============================================================
# Source 1: 番茄小说 (fanqienovel.com) — HTML 解析
# ============================================================

def fetch_fanqie_ranking(category: str = "novel_rank") -> list[dict]:
    """Load a rendered browser/OCR capture of public Fanqie rank metadata."""
    capture = configured_capture("fanqie")
    if capture:
        return capture.as_adapter_items()
    return [{"source": "fanqie", "degraded": True,
             "error": "Fanqie requires a rendered browser/OCR capture; set RANKING_CAPTURE_FANQIE_PATH"}]


# ============================================================
# Source 2: 起点 (Qidian) — JSONP 接口
# ============================================================

def fetch_qidian_ranking() -> list[dict]:
    """Load public Qidian rank metadata captured in a user-controlled browser."""
    capture = configured_capture("qidian")
    if capture:
        return capture.as_adapter_items()
    return [{"source": "qidian", "degraded": True,
             "error": "Qidian requires a user-controlled browser capture; complete any challenge manually, "
                      "then set RANKING_CAPTURE_QIDIAN_PATH"}]


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
        metrics = {"readers": str(raw.get("readers", "")), "status": str(raw.get("status", "")),
                   "last_update": str(raw.get("last_update", ""))}
        if any(key in raw for key in ("collector", "confidence", "evidence")):
            metrics.update({"collector": str(raw.get("collector", "http")),
                            "confidence": float(raw.get("confidence", 1.0)),
                            "evidence": raw.get("evidence", {})})
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
    return sorted(best_by_key.values(), key=lambda item: item["rank_no"])
