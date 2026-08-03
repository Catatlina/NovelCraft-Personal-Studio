#!/usr/bin/env python3
"""V6/V7 20-chapter dual-track quality acceptance harness.

The harness separates three kinds of evidence:

* real API/Provider output for an old V6 track and a V7 track;
* deterministic continuity/AI-pattern smoke metrics;
* an anonymised reviewer packet whose scores are reconciled only when filled.

Dry run is safe and requires no credentials.  Real generation is deliberately
guarded because it consumes Provider quota and writes chapters to the supplied
novels.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.t5_long_run import (  # noqa: E402
    ApiClient,
    Checkpoint,
    LongRunRunner,
    T5Config,
    adjacent_repeat_scores,
    build_evidence,
)

CONFIRMATION = "I_UNDERSTAND_REAL_API_COST_AND_DUAL_WRITE"
KEY_DIMENSIONS = ("continuity", "voice", "ai_feel", "fact_safety", "overall")
BLIND_MINIMUMS = {
    "continuity": 85.0,
    "voice": 80.0,
    "fact_safety": 85.0,
    "overall": 85.0,
}


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
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
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    return ""


def _normalise_chapters(rows: list[dict[str, Any]], *, track: str) -> list[dict[str, Any]]:
    result = []
    for index, row in enumerate(rows, 1):
        meta = row.get("meta") or {}
        number = int(meta.get("seq") or row.get("chapter_number") or index)
        result.append(
            {
                "chapter_number": number,
                "title": row.get("title") or row.get("chapter_title") or f"第{number}章",
                "text": _text(row.get("body") or row.get("content") or row.get("text")),
                "status": row.get("status") or meta.get("status"),
                "review_score": meta.get("review_score", row.get("review_score")),
                "dimension_scores": meta.get("dimension_scores") or row.get("dimension_scores") or {},
                "transition_contract": meta.get("transition_contract") or row.get("transition_contract") or {},
                "source": track,
            }
        )
    return sorted(result, key=lambda item: item["chapter_number"])


def _v7_request(root_url: str, token: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{root_url.rstrip('/')}{path}",
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"V7 request failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("V7 response is not an object")
    return payload.get("data", payload)


def _metrics(chapters: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(chapters, key=lambda item: item["chapter_number"])
    pseudo_rows = [
        {"id": str(item["chapter_number"]), "body": item["text"], "meta": {"seq": item["chapter_number"]}}
        for item in ordered
    ]
    repeats = adjacent_repeat_scores(pseudo_rows)
    scores = [float(item["review_score"]) for item in ordered if item["review_score"] is not None]
    statuses = [str(item["status"] or "missing") for item in ordered]
    contracts = sum(bool(item["transition_contract"]) for item in ordered)
    return {
        "chapters": len(ordered),
        "reviewed_scores": len(scores),
        "average_review_score": round(sum(scores) / len(scores), 2) if scores else None,
        "minimum_review_score": min(scores) if scores else None,
        "needs_review": statuses.count("needs_review"),
        "missing_status": statuses.count("missing"),
        "transition_contract_chapters": contracts,
        "max_adjacent_5gram_jaccard": max((row["jaccard_5gram"] for row in repeats), default=0.0),
        "adjacent_repeat_scores": repeats,
    }


def _blind_packet(old: list[dict[str, Any]], new: list[dict[str, Any]], seed: int = 20260802) -> tuple[list[dict[str, Any]], dict[str, str]]:
    old_by_number = {item["chapter_number"]: item for item in old}
    new_by_number = {item["chapter_number"]: item for item in new}
    rng = random.Random(seed)
    packet: list[dict[str, Any]] = []
    private_map: dict[str, str] = {}
    for number in sorted(set(old_by_number) & set(new_by_number)):
        case_id = hashlib.sha256(f"{seed}:{number}".encode()).hexdigest()[:12]
        samples = [("old", old_by_number[number]["text"]), ("new", new_by_number[number]["text"])]
        rng.shuffle(samples)
        private_map[case_id] = "sample_a=new" if samples[0][0] == "new" else "sample_a=old"
        packet.append(
            {
                "case_id": case_id,
                "chapter_number": number,
                "sample_a": samples[0][1],
                "sample_b": samples[1][1],
                "scores": {dimension: "" for dimension in KEY_DIMENSIONS},
                "notes": "",
            }
        )
    return packet, private_map


def _read_scores(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.exists():
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            case_id = str(row.get("case_id") or "").strip()
            reviewer = str(row.get("reviewer_id") or "").strip()
            if not case_id or not reviewer:
                continue
            sample_values: dict[str, dict[str, float]] = {}
            for sample in ("sample_a", "sample_b"):
                values = {}
                for dimension in KEY_DIMENSIONS:
                    raw = row.get(f"{sample}_{dimension}")
                    if raw in (None, ""):
                        break
                    values[dimension] = float(raw)
                if len(values) != len(KEY_DIMENSIONS):
                    break
                sample_values[sample] = values
            if len(sample_values) == 2:
                result.setdefault(case_id, []).append({"reviewer_id": reviewer, "scores": sample_values})
    return result


def _manual_summary(
    packet: list[dict[str, Any]],
    score_file: Path | None,
    private_map: dict[str, str],
) -> dict[str, Any]:
    scores = _read_scores(score_file) if score_file else {}
    complete_cases = [
        case_id for case_id, rows in scores.items()
        if len({str(row.get("reviewer_id") or "") for row in rows}) >= 2
    ]
    reviewer_ids = sorted({
        str(row.get("reviewer_id") or "")
        for case_id in complete_cases
        for row in scores[case_id]
        if row.get("reviewer_id")
    })
    averages: dict[str, dict[str, float]] = {}
    if complete_cases:
        for sample in ("sample_a", "sample_b"):
            averages[sample] = {}
            for dimension in KEY_DIMENSIONS:
                values = [
                    row["scores"][sample][dimension]
                    for case_id in complete_cases
                    for row in scores[case_id]
                ]
                averages[sample][dimension] = round(sum(values) / len(values), 3)
    comparison: dict[str, dict[str, float]] = {}
    if complete_cases:
        for dimension in KEY_DIMENSIONS:
            old_values = []
            new_values = []
            for case_id in complete_cases:
                sample_a_is_new = private_map.get(case_id) == "sample_a=new"
                for row in scores[case_id]:
                    new_values.append(row["scores"]["sample_a" if sample_a_is_new else "sample_b"][dimension])
                    old_values.append(row["scores"]["sample_b" if sample_a_is_new else "sample_a"][dimension])
            comparison[dimension] = {
                "old": round(sum(old_values) / len(old_values), 3),
                "new": round(sum(new_values) / len(new_values), 3),
            }
    return {
        "status": "complete" if len(complete_cases) == len(packet) and packet else "pending",
        "cases": len(packet),
        "cases_with_two_reviewers": len(complete_cases),
        "reviewer_ids": reviewer_ids,
        "distinct_reviewer_count": len(reviewer_ids),
        "averages": averages,
        "minimum_reviewers_per_case": 2,
        "comparison_old_vs_new": comparison,
    }


def _write_outputs(output_dir: Path, evidence: dict[str, Any], packet: list[dict[str, Any]], private_map: dict[str, str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dual-track-evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "blind-review-packet.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Keep the mapping separate from the reviewer packet so the comparison is
    # genuinely blind during review.
    (output_dir / "blind-review-private-map.json").write_text(
        json.dumps(private_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "blind-review-instructions.md").write_text(
        "# 双轨人工盲评填写说明\n\n"
        "1. 将 `blind-review-packet.json` 和评分表分别交给两位独立评审；评审者不得接触 `blind-review-private-map.json`。\n"
        "2. 两位评审必须使用不同的 `reviewer_id`，每个 case 都要各填一行，不能由同一人补齐第二行。\n"
        "3. 每个 sample 按 0-100 分填写：continuity、voice、fact_safety、overall 越高越好；ai_feel 按 AI 腔风险强度评分，越低越好。\n"
        "4. notes 写具体证据：哪一段断裂、哪一个转折缺铺垫、哪一句有 AI 腔。不要只写“可加强”。\n"
        "5. 填完后再运行带 `--score-file` 的脚本；脚本只有在 20 个 case 都有两位不同评审、且达到目标线时才会给出 accepted。\n",
        encoding="utf-8",
    )
    with (output_dir / "blind-scores.template.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["case_id", "reviewer_id"] + [
            f"{sample}_{dimension}"
            for sample in ("sample_a", "sample_b")
            for dimension in KEY_DIMENSIONS
        ] + ["notes"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for case in packet:
            writer.writerow({"case_id": case["case_id"], "reviewer_id": ""})
    lines = [
        "# V6/V7 20章双轨质量证据",
        "",
        f"生成时间：{evidence['generated_at']}",
        f"目标章节：{evidence['target_chapters']}",
        f"旧链路自动指标：`{json.dumps(evidence['old_metrics'], ensure_ascii=False)}`",
        f"新链路自动指标：`{json.dumps(evidence['new_metrics'], ensure_ascii=False)}`",
        f"人工盲评：`{json.dumps(evidence['manual_review'], ensure_ascii=False)}`",
        f"验收状态：**{evidence['acceptance_status']}**",
        "",
        "> 只有真实 Provider/数据库结果、20 个 case 均有两位不同评审、并达到目标分数，才会把状态推进为 accepted。",
    ]
    (output_dir / "dual-track-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="V6/V7 20-chapter dual-track quality acceptance")
    parser.add_argument("--api-base", default=os.getenv("NOVELCRAFT_API_BASE", "http://127.0.0.1:8000/api/v1"))
    parser.add_argument("--old-project-id", required=False)
    parser.add_argument("--old-novel-id", required=False)
    parser.add_argument("--new-project-id", required=False)
    parser.add_argument("--new-novel-id", required=False)
    parser.add_argument("--chapters", type=int, default=20)
    parser.add_argument("--output-dir", default="artifacts/v6v7-20-chapter")
    parser.add_argument("--score-file", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()

    if not 1 <= args.chapters <= 20:
        parser.error("--chapters must be between 1 and 20")
    if not args.execute:
        print(f"DRY RUN: prepare a {args.chapters}-chapter V6/V7 dual-track run and blind-review packet")
        print(f"Real execution requires --execute --confirm {CONFIRMATION}")
        print("Required: two same-setting project/novel pairs, API credentials, database migrations and a real Provider key.")
        return 0
    if args.confirm != CONFIRMATION:
        parser.error(f"real execution requires --confirm {CONFIRMATION}")
    required = (args.old_project_id, args.old_novel_id, args.new_project_id, args.new_novel_id)
    if not all(required):
        parser.error("real execution requires old/new project and novel ids")
    email = os.getenv("T5_EMAIL", "")
    password = os.getenv("T5_PASSWORD", "")
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not email or not password or not api_key:
        parser.error("T5_EMAIL, T5_PASSWORD and DEEPSEEK_API_KEY are required")

    output_dir = Path(args.output_dir)
    old_client = ApiClient(args.api_base, api_key=api_key)
    old_client.login(email, password)
    config = T5Config(
        args.old_project_id,
        args.old_novel_id,
        target_new_chapters=args.chapters,
        batch_size=1,
        allow_needs_review=True,
        cost_cap_cny=float(os.getenv("V6V7_COST_CAP_CNY", "5.0")),
    )
    runner = LongRunRunner(old_client, config, output_dir / "old-checkpoint.json")
    checkpoint, old_rows, batches = runner.run()
    old = _normalise_chapters(old_rows[checkpoint.baseline_chapters:], track="old")

    root_url = args.api_base[:-len("/api/v1")] if args.api_base.endswith("/api/v1") else args.api_base
    new: list[dict[str, Any]] = []
    for chapter_number in range(1, args.chapters + 1):
        payload = _v7_request(
            root_url,
            old_client.token,
            f"/api/v7/director/{args.new_novel_id}/generate-chapter",
            {"chapter_number": chapter_number},
        )
        new.append(_normalise_chapters([payload], track="new")[0])

    packet, private_map = _blind_packet(old, new)
    score_path = Path(args.score_file) if args.score_file else None
    old_metrics = _metrics(old)
    new_metrics = _metrics(new)
    manual = _manual_summary(packet, score_path, private_map)
    automated_ok = (
        old_metrics["chapters"] >= args.chapters
        and new_metrics["chapters"] >= args.chapters
        and new_metrics["needs_review"] == 0
        and new_metrics["missing_status"] == 0
        and new_metrics["transition_contract_chapters"] >= max(1, args.chapters - 1)
    )
    comparison = manual.get("comparison_old_vs_new") or {}
    manual_ok = (
        manual["status"] == "complete"
        and manual.get("distinct_reviewer_count", 0) >= 2
        and comparison.get("overall", {}).get("new", 0) >= BLIND_MINIMUMS["overall"]
        and comparison.get("continuity", {}).get("new", 0) >= BLIND_MINIMUMS["continuity"]
        and comparison.get("voice", {}).get("new", 0) >= BLIND_MINIMUMS["voice"]
        and comparison.get("fact_safety", {}).get("new", 0) >= BLIND_MINIMUMS["fact_safety"]
        and comparison.get("overall", {}).get("new", 0)
        >= comparison.get("overall", {}).get("old", 0)
        and comparison.get("ai_feel", {}).get("new", 99)
        <= comparison.get("ai_feel", {}).get("old", 99)
    )
    acceptance = "accepted" if automated_ok and manual_ok else "pending_manual_or_failed"
    evidence = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_chapters": args.chapters,
        "old_metrics": old_metrics,
        "new_metrics": new_metrics,
        "batches": batches,
        "manual_review": manual,
        "automated_gates_passed": automated_ok,
        "acceptance_status": acceptance,
    }
    _write_outputs(output_dir, evidence, packet, private_map)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if acceptance == "accepted" else 2


if __name__ == "__main__":
    raise SystemExit(main())
