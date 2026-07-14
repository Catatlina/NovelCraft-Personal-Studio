#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== NovelCraft AI development gate =="

required_files=(
  "AGENTS.md"
  "PROJECT_PROGRESS.md"
  "docs/NovelCraft-开发文档/23-AI开发边界与交付真实性规范.md"
  "docs/NovelCraft-开发文档/37-新增需求任务分解-20260713.md"
)

for file in "${required_files[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "MISSING_REQUIRED_FILE: $file" >&2
    exit 2
  fi
done

echo "Required governance files exist."

echo
echo "== Mandatory reading markers =="
rg -n "开发前必读|AI_EXECUTION_CONTRACT|反撒谎扫描|标准交付汇报格式" \
  "docs/NovelCraft-开发文档/23-AI开发边界与交付真实性规范.md" \
  "docs/NovelCraft-开发文档/README-文档索引.md" \
  "docs/NovelCraft-开发文档/37-新增需求任务分解-20260713.md" \
  "PROJECT_PROGRESS.md" >/tmp/novelcraft_gate_markers.txt
cat /tmp/novelcraft_gate_markers.txt

echo
echo "== Suspicion scan: mock/fallback/placeholders/deprecated/dead returns =="
set +e
rg -n "mock|fake|fallback|placeholder|TODO|FIXME|DEPRECATED|No active callers|NotImplemented|except: pass|return \\{\\}|return \\[\\]" \
  backend/app frontend/src \
  --glob '!backend/app/prompts/upstream/**' \
  > /tmp/novelcraft_gate_suspicion_1.txt
status1=$?
set -e
if [[ $status1 -eq 0 ]]; then
  cat /tmp/novelcraft_gate_suspicion_1.txt
  echo "GATE_WARNING: Suspicion scan produced matches. Each match must be fixed or explicitly justified before claiming completion." >&2
else
  echo "No matches."
fi

echo
echo "== Suspicion scan: fixed-template or fabricated-output wording =="
set +e
rg -n "震惊！|你不知道的|固定模板|Estimated|hardcoded|demo" \
  backend/app frontend/src \
  --glob '!backend/app/prompts/upstream/**' \
  > /tmp/novelcraft_gate_suspicion_2.txt
status2=$?
set -e
if [[ $status2 -eq 0 ]]; then
  cat /tmp/novelcraft_gate_suspicion_2.txt
  echo "GATE_WARNING: Fabrication/template scan produced matches. Fix or justify before claiming completion." >&2
else
  echo "No matches."
fi

echo
echo "== Suspicion scan: hard-coded active/wired self-reporting =="
set +e
rg -n "deep_.*wired.*True|available.*True|status.*active" \
  backend/app/services backend/app/api \
  > /tmp/novelcraft_gate_suspicion_3.txt
status3=$?
set -e
if [[ $status3 -eq 0 ]]; then
  cat /tmp/novelcraft_gate_suspicion_3.txt
  echo "GATE_WARNING: Self-reporting scan produced matches. Status must be evidence-driven." >&2
else
  echo "No matches."
fi

echo
echo "== AST truthfulness gate: AI provenance + hard-coded capability claims =="
python3 scripts/verify_ai_truthfulness.py

echo
echo "== Git whitespace check =="
git diff --check

echo
echo "== Gate completed =="
if [[ ${status1:-1} -eq 0 || ${status2:-1} -eq 0 || ${status3:-1} -eq 0 ]]; then
  echo "RESULT: failed with warnings. Do not claim completion until warnings are handled or justified."
  echo "If every warning is intentionally justified in the final report, rerun with GATE_ALLOW_WARNINGS=1."
  if [[ "${GATE_ALLOW_WARNINGS:-0}" != "1" ]]; then
    exit 3
  fi
  echo "GATE_ALLOW_WARNINGS=1 set; continuing only because caller accepted responsibility to document every warning."
else
  echo "RESULT: clean."
fi
