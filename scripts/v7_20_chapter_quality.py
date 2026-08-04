#!/usr/bin/env python3
"""Run and evidence a real V7-only 20-chapter long run.

The product decision is that V7 is the only prose-generation chain.  This
harness therefore does not dual-write a second V6 prose track: V7 generates,
reviews, and bridges accepted chapters into the V6 contents model used by the
library/editor/export surfaces.

The server-side Provider key is intentionally not accepted from this script.
The production API owns the configured Provider credential; the client only
uses the authenticated user's token.  This keeps the key out of shell history
and makes the evidence describe the actual production path.

The generated report separates automatic evidence from human review.  It never
fills reviewer scores itself and never upgrades a run to ``accepted`` without
two independent reviewers covering every chapter.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONFIRMATION = "I_UNDERSTAND_REAL_API_COST_AND_V7_SINGLE_CHAIN"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _request(
    base_url: str,
    method: str,
    path: str,
    *,
    token: str = "",
    body: dict[str, Any] | None = None,
    timeout: int = 900,
) -> Any:
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
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"{method} {path} failed ({exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{method} {path} failed: {exc}") from exc
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    if isinstance(value, dict):
        content = value.get("content")
        if isinstance(content, list) and content:
            return _text(content)
        paragraphs = value.get("paragraphs")
        if isinstance(paragraphs, list) and paragraphs:
            return "\n".join(_text(item) for item in paragraphs)
        if isinstance(value.get("text"), str):
            return value["text"]
    return ""


def _paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text or "") if part.strip()]


def _duplicate_ratio(text: str) -> float:
    paragraphs = _paragraphs(text)
    if not paragraphs:
        return 0.0
    unique = len(dict.fromkeys(paragraphs))
    return round((len(paragraphs) - unique) / len(paragraphs), 4)


def _chapter_row(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    text = _text(row.get("body") or row.get("content") or row.get("text"))
    transition = meta.get("transition_contract")
    return {
        "id": row.get("id"),
        "chapter_number": int(row.get("seq") or meta.get("seq") or 0),
        "title": row.get("title") or "",
        "status": row.get("status") or "missing",
        "text": text,
        "chars": len(text.replace("\n", "")),
        "paragraphs": len(_paragraphs(text)),
        "duplicate_paragraph_ratio": _duplicate_ratio(text),
        "review_score": meta.get("review_score"),
        "quality_status": meta.get("quality_status"),
        "canonical_engine": meta.get("canonical_engine"),
        "transition_contract": transition if isinstance(transition, dict) else {},
        "continuity": meta.get("continuity") if isinstance(meta.get("continuity"), dict) else {},
        "dimension_scores": meta.get("dimension_scores") if isinstance(meta.get("dimension_scores"), dict) else {},
        "quality_gate": meta.get("quality_gate") if isinstance(meta.get("quality_gate"), dict) else {},
        "deai": meta.get("deai") if isinstance(meta.get("deai"), dict) else {},
        "reader_experience": meta.get("reader_experience") if isinstance(meta.get("reader_experience"), dict) else {},
        "review_issues": meta.get("review_issues") if isinstance(meta.get("review_issues"), list) else [],
    }


def _manual_summary() -> dict[str, Any]:
    return {
        "status": "pending",
        "cases": 20,
        "cases_with_two_reviewers": 0,
        "distinct_reviewer_count": 0,
        "minimum_reviewers_per_case": 2,
        "note": "未读取或生成任何人工分数；需两位独立评审填写评分表。",
    }


def _write_manual_packet(output_dir: Path, chapters: list[dict[str, Any]]) -> None:
    fields = ["case_id", "reviewer_id"] + [
        f"{dimension}_score"
        for dimension in ("continuity", "voice", "ai_feel", "fact_safety", "overall")
    ] + ["notes"]
    with (output_dir / "blind-scores.template.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, _chapter in enumerate(chapters, 1):
            writer.writerow({"case_id": f"sample-{index:02d}", "reviewer_id": ""})

    lines = [
        "# V7 20章人工盲评包",
        "",
        "> 本包只提供匿名样本编号，不提供生成链路、模型或 Prompt 信息。请将每个样本交给两位独立评审；不得由同一人代填两位评审。",
        "",
        "评分维度：",
        "- continuity：跨章衔接、因果与铺垫，越高越好；",
        "- voice：网文可读性、人物口吻与节奏，越高越好；",
        "- ai_feel：AI 腔风险，0 表示几乎没有，100 表示非常明显，越低越好；",
        "- fact_safety：人物、设定、资源、时间线是否自洽，越高越好；",
        "- overall：综合读者体验，越高越好。",
        "",
        "请把分数填写到同目录 `blind-scores.template.csv`，每个 sample 至少出现两行不同 reviewer_id；notes 必须写具体证据，不要只写‘可加强’。",
        "",
    ]
    for index, chapter in enumerate(chapters, 1):
        case_id = f"sample-{index:02d}"
        lines.extend([
            f"## {case_id}",
            "",
            f"章节序号：{chapter['chapter_number']}",
            f"章节名：{chapter['title']}",
            "",
            chapter["text"],
            "",
            "评审备注：",
            "",
        ])
    (output_dir / "blind-review-packet.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _metrics(chapters: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(item["review_score"]) for item in chapters if item["review_score"] is not None]
    status_counts: dict[str, int] = {}
    quality_counts: dict[str, int] = {}
    continuity_counts: dict[str, int] = {}
    for chapter in chapters:
        status = str(chapter["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
        quality = str(chapter["quality_status"] or "missing")
        quality_counts[quality] = quality_counts.get(quality, 0) + 1
        continuity = chapter["continuity"]
        continuity_status = str(continuity.get("status") or ("clean" if continuity.get("passed") is True else "missing"))
        continuity_counts[continuity_status] = continuity_counts.get(continuity_status, 0) + 1
    return {
        "chapters": len(chapters),
        "reviewed_chapters": sum(item["status"] == "reviewed" for item in chapters),
        "needs_review_chapters": sum(item["status"] == "needs_review" for item in chapters),
        "needs_rewrite_chapters": sum(item["status"] == "needs_rewrite" for item in chapters),
        "reviewed_scores": len(scores),
        "average_review_score": round(sum(scores) / len(scores), 2) if scores else None,
        "minimum_review_score": min(scores) if scores else None,
        "maximum_review_score": max(scores) if scores else None,
        "status_counts": status_counts,
        "quality_status_counts": quality_counts,
        "continuity_counts": continuity_counts,
        "max_duplicate_paragraph_ratio": max((item["duplicate_paragraph_ratio"] for item in chapters), default=0.0),
        "total_chars": sum(item["chars"] for item in chapters),
        "transition_contract_chapters": sum(bool(item["transition_contract"]) for item in chapters),
        "canonical_v7_chapters": sum(item["canonical_engine"] == "v7" for item in chapters),
        "first_person_policy_failures": sum(
            bool((item["deai"].get("pov_quality") or {}).get("passed") is False)
            or bool(item["deai"].get("first_person_count"))
            for item in chapters
        ),
    }


def _write_report(
    output_dir: Path,
    *,
    generated_at: str,
    project_id: str,
    novel_id: str,
    target: int,
    chapters: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> None:
    metrics = _metrics(chapters)
    evidence = {
        "schema_version": 1,
        "generated_at": generated_at,
        "engine": "v7",
        "project_id": project_id,
        "novel_id": novel_id,
        "target_chapters": target,
        "metrics": metrics,
        "errors": errors,
        "manual_review": _manual_summary(),
        "acceptance_status": "pending_manual_review" if len(chapters) >= target and not errors else "failed",
        "chapters": [
            {key: value for key, value in chapter.items() if key != "text"}
            for chapter in chapters
        ],
    }
    (output_dir / "v7-long-run-evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# V7 20章真实 Provider 长跑报告",
        "",
        f"- 生成时间：{generated_at}",
        f"- 引擎：`v7`（产品唯一正文生成链）",
        f"- Project：`{project_id}`",
        f"- Novel：`{novel_id}`",
        f"- 目标/实际章节：{target} / {len(chapters)}",
        f"- 已审核/待复核/待返工：{metrics['reviewed_chapters']} / {metrics['needs_review_chapters']} / {metrics['needs_rewrite_chapters']}",
        f"- 审核分平均/最低：{metrics['average_review_score']} / {metrics['minimum_review_score']}",
        f"- 总正文字符数：{metrics['total_chars']}",
        f"- 交接契约章节数：{metrics['transition_contract_chapters']}/{len(chapters)}",
        f"- 重复段落最大比例：{metrics['max_duplicate_paragraph_ratio']}",
        f"- 第三人称策略失败数：{metrics['first_person_policy_failures']}",
        f"- 自动运行状态：`{evidence['acceptance_status']}`",
        "",
        "## 自动证据",
        "",
        "```json",
        json.dumps(metrics, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 章节结果",
        "",
        "| 章 | 标题 | 状态 | 评分 | 质量状态 | 字符数 | 重复段落比例 | 交接契约 |",
        "|---:|---|---|---:|---|---:|---:|---|",
    ]
    for chapter in chapters:
        lines.append(
            f"| {chapter['chapter_number']} | {chapter['title']} | {chapter['status']} | "
            f"{chapter['review_score'] or '—'} | {chapter['quality_status'] or '—'} | {chapter['chars']} | "
            f"{chapter['duplicate_paragraph_ratio']} | {'是' if chapter['transition_contract'] else '否'} |"
        )
    if errors:
        lines.extend(["", "## 运行错误", ""])
        lines.extend(f"- 第 {item.get('chapter_number')} 章：{item.get('error')}" for item in errors)
    lines.extend([
        "",
        "## 人工验收边界",
        "",
        "本报告只记录生产 API 返回的真实 V7 结果。人工盲评包已经生成，但尚未填入任何人工分数；未完成两位独立评审覆盖前，不能把生成质量标记为最终达标。",
    ])
    (output_dir / "v7-long-run-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_manual_packet(output_dir, chapters)


def main() -> int:
    parser = argparse.ArgumentParser(description="V7-only real-provider 20-chapter long run")
    parser.add_argument("--api-base", default=os.getenv("NOVELCRAFT_API_BASE", "https://novel.xyjin.xyz/api/v1"))
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--novel-id", required=True)
    parser.add_argument("--chapters", type=int, default=20)
    parser.add_argument("--start-chapter", type=int, default=1)
    parser.add_argument("--output-dir", default="artifacts/v7-20-chapter")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if not 1 <= args.chapters <= 20:
        parser.error("--chapters must be between 1 and 20")
    if not 1 <= args.start_chapter <= args.chapters:
        parser.error("--start-chapter must be between 1 and --chapters")
    if not args.execute:
        print(f"DRY RUN: prepare chapters {args.start_chapter}-{args.chapters} of a V7 real-provider long run")
        print(f"Real execution requires --execute --confirm {CONFIRMATION}")
        return 0
    if args.confirm != CONFIRMATION:
        parser.error(f"real execution requires --confirm {CONFIRMATION}")
    email = os.getenv("T5_EMAIL", "")
    password = os.getenv("T5_PASSWORD", "")
    if not email or not password:
        parser.error("T5_EMAIL and T5_PASSWORD are required")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    login = _request(args.api_base, "POST", "/auth/login", body={"email": email, "password": password}, timeout=60)
    token = login.get("access_token") if isinstance(login, dict) else ""
    if not token:
        raise RuntimeError("login response did not contain access_token")

    generated_at = datetime.now(timezone.utc).isoformat()
    chapters: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for chapter_number in range(args.start_chapter, args.chapters + 1):
        try:
            _request(
                args.api_base.replace("/api/v1", ""),
                "POST",
                f"/api/v7/director/{args.novel_id}/generate-chapter",
                token=token,
                body={"chapter_number": chapter_number},
                timeout=900,
            )
        except RuntimeError as exc:
            errors.append({"chapter_number": chapter_number, "error": str(exc)})
            print(f"[FAIL] chapter {chapter_number}: {exc}", flush=True)
        else:
            print(f"[DONE] chapter {chapter_number}", flush=True)

        listing = _request(
            args.api_base,
            "GET",
            f"/contents?project_id={args.project_id}&parent_id={args.novel_id}&limit=200&offset=0",
            token=token,
            timeout=60,
        )
        rows = listing if isinstance(listing, list) else []
        chapters = sorted((_chapter_row(row) for row in rows), key=lambda item: item["chapter_number"])
        (output_dir / "checkpoint.json").write_text(
            json.dumps({"chapter_number": chapter_number, "chapters": chapters, "errors": errors}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    _write_report(
        output_dir,
        generated_at=generated_at,
        project_id=args.project_id,
        novel_id=args.novel_id,
        target=args.chapters,
        chapters=chapters,
        errors=errors,
    )
    print(json.dumps(_metrics(chapters), ensure_ascii=False, indent=2))
    return 0 if len(chapters) >= args.chapters and not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
