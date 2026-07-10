#!/usr/bin/env python3
"""TASK-030: 30万字 stress test — generates N chapters and validates consistency.
Run: python scripts/stress_test.py --novel-id <id> --chapters 30 --target-words 10000
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

DB = "postgresql://genius@localhost/novelcraft_dev"


def stress_test(novel_id: str, num_chapters: int = 30, target_words: int = 10000) -> dict:
    """Generate N chapters and measure quality metrics."""
    conn = psycopg2.connect(DB, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    # Verify novel exists
    cur.execute("SELECT id, title, project_id FROM contents WHERE id = %s AND type='novel'", (novel_id,))
    novel = cur.fetchone()
    if not novel:
        print(f"Novel not found: {novel_id}")
        sys.exit(1)

    print(f"📖 Novel: {novel['title']}")
    print(f"🎯 Generating {num_chapters} chapters (~{num_chapters * target_words} words total)...")
    print()

    start_time = time.time()
    results = []
    total_words = 0
    errors = 0
    costs = []

    for i in range(num_chapters):
        chapter_start = time.time()
        try:
            # Call API to generate next chapter
            import urllib.request
            req = urllib.request.Request(
                f"http://127.0.0.1:8000/api/v1/novels/{novel_id}/continue",
                data=b"{}", method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                task_data = json.loads(r.read())["data"]

            # Wait for Celery to complete
            time.sleep(3)

            # Check result
            cur.execute(
                "SELECT id, title, meta, body FROM contents WHERE parent_id = %s AND type='chapter' ORDER BY (meta->>'seq')::int DESC LIMIT 1",
                (novel_id,),
            )
            chapter = cur.fetchone()
            if chapter:
                body = chapter["body"] if isinstance(chapter["body"], dict) else json.loads(chapter["body"])
                texts = [p.get("text", "") for p in body.get("content", [])]
                word_count = sum(len(t) for t in texts)
                total_words += word_count

                # Check entity states
                cur.execute("SELECT count(*) as cnt FROM entity_states")
                entity_count = cur.fetchone()["cnt"]

                # Check foreshadowing
                cur.execute("SELECT count(*) as cnt FROM foreshadowings WHERE status='planted'")
                f_count = cur.fetchone()["cnt"]

                # Check AI call cost
                cur.execute(
                    "SELECT sum(cost_cny) as total_cost FROM ai_calls WHERE created_at > %s",
                    (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0),),
                )
                cost_row = cur.fetchone()
                cost = float(cost_row["total_cost"] or 0)
                costs.append(cost)

                chapter_time = time.time() - chapter_start
                results.append({
                    "ch": i + 1,
                    "title": chapter["title"][:30],
                    "words": word_count,
                    "entities": entity_count,
                    "foreshadowing": f_count,
                    "time_s": round(chapter_time, 1),
                    "cost_¥": round(cost, 4),
                })
                print(f"  Ch{i+1:2d}: {chapter['title'][:25]:25s} {word_count:5d}字 {chapter_time:4.1f}s  entities:{entity_count}  foreshadowing:{f_count}")
            else:
                errors += 1
                print(f"  Ch{i+1:2d}: FAILED — no chapter returned")
        except Exception as e:
            errors += 1
            print(f"  Ch{i+1:2d}: ERROR — {e}")

    elapsed = time.time() - start_time

    # Final checks
    cur.execute("SELECT count(*) as cnt FROM contents WHERE parent_id = %s AND type='chapter'", (novel_id,))
    total_chapters = cur.fetchone()["cnt"]
    cur.execute("SELECT count(*) as cnt FROM foreshadowings WHERE status='planted'")
    unfulfilled = cur.fetchone()["cnt"]
    cur.execute("SELECT sum(cost_cny) as total FROM ai_calls")
    total_cost = float((cur.fetchone()["total"] or 0))
    cur.execute("SELECT count(*) as cnt FROM ai_calls WHERE status != 'succeeded'")
    failed_calls = cur.fetchone()["cnt"]

    conn.close()

    summary = {
        "novel": novel["title"],
        "chapters_generated": len(results),
        "errors": errors,
        "total_words": total_words,
        "total_time_s": round(elapsed, 1),
        "avg_time_per_chapter_s": round(elapsed / max(len(results), 1), 1),
        "total_chapters": total_chapters,
        "unfulfilled_foreshadowing": unfulfilled,
        "failed_ai_calls": failed_calls,
        "total_cost_¥": round(total_cost, 4),
        "results": results[:5] + (results[-5:] if len(results) > 10 else []),
    }

    print(f"\n{'='*50}")
    print(f"Chapters: {len(results)}/{num_chapters} (errors: {errors})")
    print(f"Words: {total_words:,}")
    print(f"Time: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"Avg/chapter: {elapsed/max(len(results),1):.1f}s")
    print(f"Cost: ¥{total_cost:.4f}")
    print(f"Failed AI calls: {failed_calls}")
    print(f"Unfulfilled foreshadowing: {unfulfilled}")
    print(f"{'='*50}")

    result = "PASS" if errors <= num_chapters * 0.1 and total_words >= num_chapters * target_words * 0.5 else "FAIL"
    print(f"\nStress test: {result}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="30万字 stress test")
    parser.add_argument("--novel-id", required=True)
    parser.add_argument("--chapters", type=int, default=30)
    parser.add_argument("--target-words", type=int, default=10000)
    parser.add_argument("--output", help="Save results to JSON file")
    args = parser.parse_args()

    result = stress_test(args.novel_id, args.chapters, args.target_words)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"\nResults saved to {args.output}")
