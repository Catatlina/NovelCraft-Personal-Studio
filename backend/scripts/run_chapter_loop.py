"""Smoke-test the V6.1.2 chapter closed loop on a real novel.

Runs chapters LOOP_FROM..LOOP_TO sequentially so each chapter sees the
Story Bible + recent summaries produced by the previous ones.

Usage:
  DEEPSEEK_API_KEY=... DATABASE_URL=... \
  LOOP_FROM=1 LOOP_TO=10 python backend/scripts/run_chapter_loop.py
"""
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.chapter_loop import REVIEW_SCORE_THRESHOLD, run_single_chapter

NOVEL = os.getenv("LOOP_NOVEL_ID", "58051d25-c719-489d-a34c-e65fb2b15abe")
PROJECT = os.getenv("LOOP_PROJECT_ID", "06445add-098d-4a80-b657-ff99fd7262b0")
FROM = int(os.getenv("LOOP_FROM", os.getenv("LOOP_CHAPTER_SEQ", "1")))
TO = int(os.getenv("LOOP_TO", str(FROM)))
OUT = os.getenv("LOOP_REPORT", "")


def main() -> None:
    print(f"[loop] novel={NOVEL} project={PROJECT} chapters={FROM}..{TO} "
          f"threshold={REVIEW_SCORE_THRESHOLD}")
    reports = []
    t0 = time.time()
    for seq in range(FROM, TO + 1):
        started = time.time()
        try:
            rep = run_single_chapter(PROJECT, NOVEL, chapter_seq=seq, user_id=None)
        except Exception as exc:  # keep going: a mid-run failure must be visible
            traceback.print_exc()
            rep = {"chapter_seq": seq, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
        rep["elapsed_s"] = round(time.time() - started, 1)
        reports.append(rep)
        steps = {s.get("step"): s for s in rep.get("steps", [])}
        repair = steps.get("repair_local", {})
        print(
            f"  ch{seq:>2}  ok={str(rep.get('ok')):<5} score={rep.get('final_score')} "
            f"chars={rep.get('chars')} repairs={rep.get('repairs_done')} "
            f"rollback={repair.get('rolled_back')} "
            f"cost={(rep.get('cost') or {}).get('cost_cny')} {rep['elapsed_s']}s"
        )

    ok = [r for r in reports if r.get("ok")]
    scores = [r["final_score"] for r in ok if r.get("final_score") is not None]
    summary = {
        "chapters_attempted": len(reports),
        "chapters_ok": len(ok),
        "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
        "min_score": min(scores) if scores else None,
        "total_chars": sum(r.get("chars", 0) for r in ok),
        "total_repairs": sum(r.get("repairs_done", 0) for r in ok),
        "total_cost_cny": round(sum((r.get("cost") or {}).get("cost_cny", 0) for r in ok), 6),
        "total_tokens": sum((r.get("cost") or {}).get("tokens", 0) for r in ok),
        "elapsed_s": round(time.time() - t0, 1),
    }
    print("\n[summary] " + json.dumps(summary, ensure_ascii=False))
    if OUT:
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "reports": reports}, f,
                      ensure_ascii=False, indent=2, default=str)
        print(f"[report] {OUT}")
    if len(ok) != len(reports):
        sys.exit(1)


if __name__ == "__main__":
    main()
