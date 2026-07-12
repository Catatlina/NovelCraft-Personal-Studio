"""Delivery-claim gate for strict progress documents.

Docs opting in via the `delivery-claims: strict` marker are checked for:
1. contradiction — a line that claims ✅/已交付/已验收 while also containing
   negation words (未实现/未实测/仅骨架…);
2. evidence binding — any ✅/已交付/已验收 line must carry at least one
   concrete evidence token (test id, commit, file path, T-level, 实测/E2E),
   per《23-AI开发边界与交付真实性规范》§6/§8;
3. the deprecated《22-全功能跟踪表》must stay marked 已废止.

This is a documentation-consistency gate. It does not replace test execution:
CI runs the real pytest suite in a separate step.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKER = "delivery-claims: strict"
DONE_CLAIM = re.compile(r"✅|已交付|已验收")
CONTRADICTIONS = re.compile(r"未实现|待实现|待开发|未实测|未测试|未验证|仅骨架|代码骨架|未接|缺少|尚未|部分完成|0\s*代码", re.I)
EVIDENCE = re.compile(
    r"T[0-5]\b|\btests?\b|测试|passed|E2E|实测|commit|[0-9a-f]{7,40}\b|\.py\b|\.tsx?\b|迁移|alembic|浏览器",
    re.I,
)


def main() -> int:
    errors: list[str] = []
    for path in [ROOT / "PROJECT_PROGRESS.md", *ROOT.glob("docs/**/*.md")]:
        text = path.read_text(encoding="utf-8")
        if MARKER not in text:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if not DONE_CLAIM.search(line):
                continue
            where = f"{path.relative_to(ROOT)}:{line_no}"
            if CONTRADICTIONS.search(line):
                errors.append(f"{where}: 完成声明与否定说明同行冲突: {line.strip()[:120]}")
            elif not EVIDENCE.search(line):
                errors.append(f"{where}: 完成声明缺少证据标记(测试/commit/文件/T级/实测): {line.strip()[:120]}")
    deprecated = ROOT / "docs/NovelCraft-开发文档/22-全功能跟踪表(256项).md"
    if deprecated.exists() and "状态：已废止" not in deprecated.read_text(encoding="utf-8"):
        errors.append(f"{deprecated.relative_to(ROOT)}: 缺少‘状态：已废止’")
    if errors:
        print("Delivery claim verification failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Delivery claim verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
