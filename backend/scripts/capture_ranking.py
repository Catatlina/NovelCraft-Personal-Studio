#!/usr/bin/env python3
"""Capture public ranking metadata in a visible, user-controlled browser.

Usage:
  backend/.venv/bin/python backend/scripts/capture_ranking.py qidian --output var/qidian.json
  backend/.venv/bin/python backend/scripts/capture_ranking.py fanqie --output var/fanqie.json

The command pauses for manual login/challenge completion. It does not solve
CAPTCHAs or bypass access controls. Fanqie private-use glyphs are explicitly
reported as ``ocr_required`` and the screenshot is retained for an OCR worker.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


URLS = {"fanqie": "https://fanqienovel.com/rank/all", "qidian": "https://www.qidian.com/rank/"}
CHALLENGE_MARKERS = ("安全验证", "验证码", "访问过于频繁", "verify", "captcha")


def has_private_use_glyph(value: str) -> bool:
    return any(0xE000 <= ord(char) <= 0xF8FF for char in value)


def extract_public_cards(page, source: str) -> list[dict]:
    selectors = {
        "qidian": ("a[href*='/book/']", "a[href*='//book.qidian.com/info/']"),
        "fanqie": ("a[href*='/page/']",),
    }
    items: list[dict] = []
    seen: set[str] = set()
    for selector in selectors[source]:
        for anchor in page.locator(selector).all():
            try:
                title = (anchor.get_attribute("title") or anchor.inner_text()).strip()
                href = anchor.get_attribute("href") or ""
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", choices=URLS)
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile", default="var/ranking-browser-profile")
    args = parser.parse_args()
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    screenshot = output.with_suffix(".png")
    profile = Path(args.profile).expanduser().resolve()
    profile.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(str(profile), headless=False, channel="chrome")
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(URLS[args.source], wait_until="domcontentloaded", timeout=60_000)
        print("请在浏览器中完成必要的登录或安全验证，然后回到终端按 Enter。", file=sys.stderr)
        input()
        page.screenshot(path=str(screenshot), full_page=True)
        body = page.locator("body").inner_text(timeout=10_000)
        items = extract_public_cards(page, args.source)
        status, error = "succeeded", None
        if any(marker.casefold() in body.casefold() for marker in CHALLENGE_MARKERS):
            status, error, items = "user_action_required", "browser still shows a challenge page", []
        elif args.source == "fanqie" and any(has_private_use_glyph(item["title"]) for item in items):
            status, error, items = "ocr_required", "rendered titles contain private-use glyphs", []
        elif not items:
            status, error = "schema_changed", "no public ranking cards matched known selectors"
        artifact = {
            "schema_version": 1,
            "source": args.source,
            "status": status,
            "collector": "visible_browser",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source_url": page.url,
            "items": items,
            "error": error,
            "evidence": {"screenshot": str(screenshot), "browser_profile": str(profile)},
        }
        output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        context.close()
    print(output)
    return 0 if status == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
