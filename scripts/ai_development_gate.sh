#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== Starlume AI development gate =="

required_files=(
  "AGENTS.md"
  "PROJECT_PROGRESS.md"
  "docs/Starlume-AI-开发文档/README.md"
  "docs/Starlume-AI-开发文档/03-开发路径与里程碑.md"
  "docs/Starlume-AI-开发文档/05-AI遵从与开发真实性规范.md"
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
rg -n "每次工作前必须读取|STARLUME_AI_EXECUTION_CONTRACT|禁止的假完成|交付报告格式" \
  "docs/Starlume-AI-开发文档/05-AI遵从与开发真实性规范.md" \
  "docs/Starlume-AI-开发文档/README.md" \
  "docs/Starlume-AI-开发文档/03-开发路径与里程碑.md" \
  "PROJECT_PROGRESS.md" >/tmp/starlume_gate_markers.txt
cat /tmp/starlume_gate_markers.txt

echo
echo "== Suspicion scan: fabricated AI output or swallowed failures =="
set +e
rg -n "mock (output|content|result)|fake (output|content|result)|placeholder (output|content)|return [\"'](mock|fake|demo)|except: pass|NotImplemented" \
  backend/app frontend/src \
  --glob '!backend/app/prompts/upstream/**' \
  --glob '!**/*.test.*' \
  --glob '!**/tests/**' \
  > /tmp/starlume_gate_suspicion_1.txt
status1=$?
set -e
if [[ $status1 -eq 0 ]]; then
  cat /tmp/starlume_gate_suspicion_1.txt
  echo "GATE_WARNING: Suspicion scan produced matches. Each match must be fixed or explicitly justified before claiming completion." >&2
else
  echo "No matches."
fi

echo
echo "== Suspicion scan: fixed fabricated-output wording =="
set +e
rg -n "震惊！|背后的真相|你不知道的|# \\{topic\\}|Estimated beats|Would call complete\\(\\) in production" \
  backend/app frontend/src \
  --glob '!backend/app/prompts/upstream/**' \
  --glob '!**/*.test.*' \
  --glob '!**/tests/**' \
  > /tmp/starlume_gate_suspicion_2.txt
status2=$?
set -e
if [[ $status2 -eq 0 ]]; then
  cat /tmp/starlume_gate_suspicion_2.txt
  echo "GATE_WARNING: Fabrication/template scan produced matches. Fix or justify before claiming completion." >&2
else
  echo "No matches."
fi

echo
echo "== Suspicion scan: hard-coded capability claims =="
echo "AST truthfulness gate below checks dictionary capability claims with syntax-aware matching."
status3=1

echo
echo "== AST truthfulness gate: AI provenance + hard-coded capability claims =="
python3 scripts/verify_ai_truthfulness.py

echo
echo "== Delivery claim evidence gate =="
python3 scripts/verify_delivery_claims.py

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
