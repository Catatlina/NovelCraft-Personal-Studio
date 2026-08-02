#!/usr/bin/env python3
"""Verify the V7 -> V6 editor/library/export product chain.

The script records only response metadata and counts. Access tokens and
chapter text are never written to the evidence file.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _request(
    base_url: str,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    token: str = "",
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        method=method,
        headers=headers,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
            payload = json.loads(raw.decode("utf-8")) if "json" in content_type else None
            return {
                "status": response.status,
                "content_type": content_type,
                "headers": dict(response.headers),
                "raw_bytes": len(raw),
                "raw": raw,
                "payload": payload,
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {"message": raw.decode("utf-8", errors="replace")[:300]}
        return {
            "status": exc.code,
            "content_type": exc.headers.get("Content-Type", ""),
            "headers": dict(exc.headers),
            "raw_bytes": len(raw),
            "raw": raw,
            "payload": payload,
        }


def _data(response: dict[str, Any]) -> dict[str, Any] | list[dict[str, Any]]:
    payload = response.get("payload") or {}
    return payload.get("data", payload) if isinstance(payload, dict) else payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the V7/V6 editor and export chain")
    parser.add_argument("--api-base", default=os.getenv("NOVELCRAFT_API_BASE", "http://127.0.0.1:8000/api/v1"))
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--novel-id", required=True)
    parser.add_argument("--output", default="artifacts/v6v7-product-chain-evidence.json")
    args = parser.parse_args()

    email = os.getenv("T5_EMAIL", "")
    password = os.getenv("T5_PASSWORD", "")
    if not email or not password:
        parser.error("T5_EMAIL and T5_PASSWORD are required")

    login = _request(args.api_base, "POST", "/auth/login", body={"email": email, "password": password})
    login_data = _data(login)
    token = login_data.get("access_token") if isinstance(login_data, dict) else ""
    if login.get("status") != 200 or not token:
        raise RuntimeError("product-chain login failed")

    listing = _request(
        args.api_base,
        "GET",
        f"/contents?project_id={args.project_id}&parent_id={args.novel_id}&limit=200&offset=0",
        token=token,
    )
    chapters = _data(listing)
    chapters = chapters if isinstance(chapters, list) else []
    first_id = chapters[0].get("id") if chapters else ""
    editor_novel = _request(args.api_base, "GET", f"/contents/{args.novel_id}", token=token)
    editor_chapter = _request(args.api_base, "GET", f"/contents/{first_id}", token=token) if first_id else {}
    completion = _request(args.api_base, "GET", f"/novels/{args.novel_id}/completion", token=token)
    txt = _request(args.api_base, "GET", f"/novels/{args.novel_id}/export/txt", token=token)
    markdown = _request(args.api_base, "GET", f"/novels/{args.novel_id}/export/markdown", token=token)
    epub = _request(args.api_base, "GET", f"/novels/{args.novel_id}/export/epub", token=token)

    chapter_data = _data(editor_chapter) if editor_chapter else {}
    chapter_meta = chapter_data.get("meta", {}) if isinstance(chapter_data, dict) else {}
    completion_data = _data(completion)
    txt_data = _data(txt)
    markdown_data = _data(markdown)
    epub_payload = epub.get("payload") or {}
    ready_header = next(
        (value for key, value in epub.get("headers", {}).items()
         if key.lower() == "x-novelcraft-ready-for-release"),
        None,
    )
    evidence = {
        "schema_version": 1,
        "project_id": args.project_id,
        "novel_id": args.novel_id,
        "editor": {
            "novel_http_status": editor_novel.get("status"),
            "chapter_http_status": editor_chapter.get("status"),
            "chapter_seq": chapter_meta.get("seq"),
            "chapter_source": chapter_meta.get("source"),
            "has_transition_contract": bool(chapter_meta.get("transition_contract")),
            "has_project_mapping": bool(chapter_meta.get("project_mapping")),
            "chapter_body_bytes": len(json.dumps(chapter_data.get("body", {}), ensure_ascii=False).encode("utf-8"))
            if isinstance(chapter_data, dict) else 0,
        },
        "completion": {
            "http_status": completion.get("status"),
            "total_chapters": completion_data.get("total_chapters"),
            "reviewed_chapters": completion_data.get("reviewed_chapters"),
            "average_review_score": completion_data.get("average_review_score"),
            "ready_for_release": completion_data.get("ready_for_release"),
            "exportable": completion_data.get("exportable"),
        },
        "txt": {
            "http_status": txt.get("status"),
            "chapter_count": txt_data.get("chapter_count"),
            "content_bytes": len((txt_data.get("content") or "").encode("utf-8")),
        },
        "markdown": {
            "http_status": markdown.get("status"),
            "chapter_count": markdown_data.get("chapter_count"),
            "content_bytes": len((markdown_data.get("content") or "").encode("utf-8")),
        },
        "epub": {
            "http_status": epub.get("status"),
            "content_type": epub.get("content_type"),
            "bytes": epub.get("raw_bytes"),
            "zip_magic": epub.get("raw", b"")[:2].hex(),
            "ready_header": ready_header,
            "error_code": epub_payload.get("code") if isinstance(epub_payload, dict) else None,
        },
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))

    passed = (
        evidence["editor"]["novel_http_status"] == 200
        and evidence["editor"]["chapter_http_status"] == 200
        and evidence["editor"]["chapter_source"] == "v7"
        and evidence["editor"]["has_transition_contract"]
        and evidence["completion"]["total_chapters"] == evidence["completion"]["reviewed_chapters"] == 20
        and evidence["completion"]["ready_for_release"] is True
        and evidence["txt"]["chapter_count"] == 20
        and evidence["markdown"]["chapter_count"] == 20
        and evidence["epub"]["http_status"] == 200
        and evidence["epub"]["zip_magic"] == "504b"
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
