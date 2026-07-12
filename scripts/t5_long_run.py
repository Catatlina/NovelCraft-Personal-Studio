#!/usr/bin/env python3
"""Run a guarded T5 chapter-generation soak against an already running stack."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.t5_long_run import ApiClient, LongRunRunner, T5Config, build_evidence, write_evidence  # noqa: E402

CONFIRMATION = "I_UNDERSTAND_REAL_API_COST"


def main() -> int:
    parser = argparse.ArgumentParser(description="NovelCraft T5 real-provider long run")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--novel-id", required=True)
    parser.add_argument("--chapters", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--cost-cap-cny", type=float, default=5.0)
    parser.add_argument("--output-dir", default="artifacts/t5-long-run")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--allow-needs-review", action="store_true")
    args = parser.parse_args()
    config = T5Config(args.project_id, args.novel_id, args.chapters, args.batch_size,
                      allow_needs_review=args.allow_needs_review, cost_cap_cny=args.cost_cap_cny)
    config.validate()
    estimated = config.target_new_chapters * config.estimated_cost_per_chapter_cny
    if not args.execute:
        print(f"DRY RUN: {args.chapters} chapters in batches of {args.batch_size}; estimated ceiling ¥{estimated:.2f}")
        print(f"To execute, add --execute --confirm {CONFIRMATION} and configure T5_EMAIL/T5_PASSWORD/DEEPSEEK_API_KEY")
        return 0
    if args.confirm != CONFIRMATION:
        parser.error(f"real execution requires --confirm {CONFIRMATION}")
    email, password, api_key = os.getenv("T5_EMAIL", ""), os.getenv("T5_PASSWORD", ""), os.getenv("DEEPSEEK_API_KEY", "")
    if not email or not password or not api_key:
        parser.error("T5_EMAIL, T5_PASSWORD and DEEPSEEK_API_KEY are required")
    output_dir = Path(args.output_dir)
    client = ApiClient(os.getenv("NOVELCRAFT_API_BASE", "http://127.0.0.1:8000/api/v1"), api_key=api_key)
    client.login(email, password)
    runner = LongRunRunner(client, config, output_dir / "checkpoint.json")
    checkpoint, chapters, batches = runner.run()
    evidence = build_evidence(chapters, checkpoint, batches)
    json_path, md_path = write_evidence(evidence, output_dir)
    print(f"Evidence: {json_path} / {md_path}")
    return 0 if evidence["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
