#!/usr/bin/env python3
"""Capture public ranking metadata in a visible, user-controlled browser.

Usage:
  backend/.venv/bin/python backend/scripts/capture_ranking.py qidian --output var/qidian.json
  backend/.venv/bin/python backend/scripts/capture_ranking.py fanqie --output var/fanqie.json

The command can pause for manual login/challenge completion. It does not solve
CAPTCHAs or bypass access controls. Fanqie private-use glyphs trigger a local
OCR attempt when a real OCR engine is installed; otherwise the screenshot is
retained and the artifact is marked ``ocr_required``.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin


URLS = {
    "fanqie": "https://fanqienovel.com/rank/all",
    "qidian": "https://www.qidian.com/rank/",
    "zongheng": "https://www.zongheng.com/rank",
}
BODY_CHALLENGE_MARKERS = ("安全验证", "验证码", "访问过于频繁", "verify", "captcha")
HTML_CHALLENGE_MARKERS = ("TencentCaptcha", "captcha.qq.com", "__captcha")
MIN_OCR_CONFIDENCE = 0.62


def has_private_use_glyph(value: str) -> bool:
    return any(0xE000 <= ord(char) <= 0xF8FF for char in value)


def looks_like_public_book_title(value: str) -> bool:
    text = re.sub(r"\s+", "", value)
    if len(text) < 2 or len(text) > 40:
        return False
    if not re.search(r"[\u4e00-\u9fffA-Za-z]", text):
        return False
    blocked = ("排行榜", "小说", "书架", "登录", "注册", "分类", "完本", "免费", "更多", "作品")
    return not any(marker == text or text.endswith(marker) for marker in blocked)


def extract_public_cards(page, source: str) -> list[dict]:
    selectors = {
        "qidian": ("a[href*='/book/']", "a[href*='//book.qidian.com/info/']"),
        "fanqie": ("a[href*='/page/']",),
        "zongheng": ("a[href*='/detail/'][title]", "a[href*='/book/']", "a[href*='/book/'][title]"),
    }
    items: list[dict] = []
    seen: set[str] = set()
    for selector in selectors[source]:
        for anchor in page.locator(selector).all():
            try:
                title = (anchor.get_attribute("title") or anchor.inner_text()).strip()
                href = urljoin(page.url, anchor.get_attribute("href") or "")
            except Exception:
                continue
            if not title or href in seen:
                continue
            seen.add(href)
            items.append({"rank": len(items) + 1, "title": title, "author": "", "url": href,
                          "confidence": 1.0, "collector": "visible_browser_dom"})
            if len(items) >= 50:
                return items
    return items


def parse_tesseract_tsv(tsv: str) -> list[dict]:
    """Turn Tesseract TSV into conservative ranking title candidates."""
    rows = [line.split("\t") for line in tsv.splitlines() if line.strip()]
    if not rows:
        return []
    header = rows[0]
    required = {"block_num", "par_num", "line_num", "conf", "text"}
    if not required.issubset(set(header)):
        raise ValueError("tesseract TSV output missing required columns")
    index = {name: header.index(name) for name in header}
    grouped: dict[tuple[str, str, str], list[tuple[str, float]]] = {}
    for row in rows[1:]:
        if len(row) <= max(index.values()):
            continue
        text = row[index["text"]].strip()
        if not text:
            continue
        try:
            confidence = float(row[index["conf"]])
        except ValueError:
            continue
        if confidence < 0:
            continue
        key = (row[index["block_num"]], row[index["par_num"]], row[index["line_num"]])
        grouped.setdefault(key, []).append((text, confidence / 100))
    candidates: list[dict] = []
    seen: set[str] = set()
    for words in grouped.values():
        line = re.sub(r"\s+", "", "".join(word for word, _confidence in words)).strip("·|-—_ ")
        if not looks_like_public_book_title(line) or line in seen:
            continue
        seen.add(line)
        confidence = sum(confidence for _word, confidence in words) / max(len(words), 1)
        candidates.append({
            "rank": len(candidates) + 1,
            "title": line,
            "author": "",
            "confidence": round(confidence, 3),
            "collector": "browser_ocr",
            "evidence": {"ocr_line": line},
        })
        if len(candidates) >= 50:
            break
    return candidates


def run_tesseract_ocr(screenshot: Path, languages: str = "chi_sim+eng") -> tuple[list[dict], dict, str | None]:
    """Run a local OCR engine if present; never invent text when OCR is absent."""
    binary = shutil.which("tesseract")
    if not binary:
        return [], {"ocr_engine": "tesseract", "ocr_available": False}, "tesseract binary not found"
    command = [binary, str(screenshot), "stdout", "-l", languages, "tsv"]
    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=120)
    evidence = {"ocr_engine": "tesseract", "ocr_available": True, "ocr_languages": languages}
    if completed.returncode != 0:
        return [], evidence, completed.stderr.strip() or "tesseract returned non-zero exit"
    try:
        items = parse_tesseract_tsv(completed.stdout)
    except Exception as exc:
        return [], evidence, str(exc)
    if not items:
        return [], evidence, "OCR produced no conservative title candidates"
    min_confidence = min(float(item.get("confidence", 0)) for item in items)
    evidence["ocr_min_confidence"] = round(min_confidence, 3)
    if min_confidence < MIN_OCR_CONFIDENCE:
        evidence["ocr_review_required"] = True
    return items, evidence, None


def is_challenge_page(body: str, html: str = "") -> bool:
    body_folded = body.casefold()
    if any(marker.casefold() in body_folded for marker in BODY_CHALLENGE_MARKERS):
        return True
    return any(marker.casefold() in html.casefold() for marker in HTML_CHALLENGE_MARKERS)


def build_artifact(source: str, page_url: str, body: str, items: list[dict], screenshot: Path,
                   profile: Path, ocr_mode: str = "auto", html_snapshot: Path | None = None) -> dict:
    status, error = "succeeded", None
    evidence = {"screenshot": str(screenshot), "browser_profile": str(profile)}
    if html_snapshot:
        evidence["html_snapshot"] = str(html_snapshot)
    html = html_snapshot.read_text(encoding="utf-8", errors="replace") if html_snapshot and html_snapshot.exists() else ""
    if is_challenge_page(body, html):
        status, error, items = "user_action_required", "browser still shows a challenge page", []
    elif source == "fanqie" and any(has_private_use_glyph(str(item.get("title", ""))) for item in items):
        if ocr_mode == "none":
            status, error, items = "ocr_required", "rendered titles contain private-use glyphs", []
        else:
            ocr_items, ocr_evidence, ocr_error = run_tesseract_ocr(screenshot)
            evidence.update(ocr_evidence)
            if ocr_items:
                items = ocr_items
            else:
                status, error, items = "ocr_required", ocr_error or "rendered titles contain private-use glyphs", []
    elif not items:
        status, error = "schema_changed", "no public ranking cards matched known selectors"
    collector = "browser_ocr" if evidence.get("ocr_available") and items else "visible_browser"
    return {
        "schema_version": 1,
        "source": source,
        "status": status,
        "collector": collector,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source_url": page_url,
        "items": items,
        "error": error,
        "evidence": evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", choices=URLS)
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile", default="var/ranking-browser-profile")
    parser.add_argument("--headless", action="store_true", help="Run browser headlessly; useful for scheduled public pages.")
    parser.add_argument("--no-pause", action="store_true", help="Do not wait for manual login/challenge completion.")
    parser.add_argument("--ocr", choices=("auto", "none"), default="auto", help="Use local OCR for Fanqie private-use glyph pages when available.")
    args = parser.parse_args()
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    screenshot = output.with_suffix(".png")
    html_snapshot = output.with_suffix(".html")
    profile = Path(args.profile).expanduser().resolve()
    profile.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(str(profile), headless=args.headless, channel="chrome")
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(URLS[args.source], wait_until="domcontentloaded", timeout=60_000)
        if not args.no_pause:
            print("请在浏览器中完成必要的登录或安全验证，然后回到终端按 Enter。", file=sys.stderr)
            input()
        page.screenshot(path=str(screenshot), full_page=True)
        html_snapshot.write_text(page.content(), encoding="utf-8")
        body = page.locator("body").inner_text(timeout=10_000)
        items = extract_public_cards(page, args.source)
        artifact = build_artifact(args.source, page.url, body, items, screenshot, profile, args.ocr, html_snapshot)
        output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        context.close()
    print(output)
    return 0 if artifact["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
