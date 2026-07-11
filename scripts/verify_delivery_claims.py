"""Reject contradictory delivery claims in strict progress documents."""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKER = "delivery-claims: strict"
CONTRADICTIONS = re.compile(r"未实现|待实现|待开发|未实测|未测试|未验证|仅骨架|代码骨架|未接|缺少|尚未|部分完成|0\s*代码", re.I)


def main() -> int:
    errors: list[str] = []
    for path in [ROOT / "PROJECT_PROGRESS.md", *ROOT.glob("docs/**/*.md")]:
        text = path.read_text(encoding="utf-8")
        if MARKER not in text:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if "✅" in line and CONTRADICTIONS.search(line):
                errors.append(f"{path.relative_to(ROOT)}:{line_no}: {line.strip()}")
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
