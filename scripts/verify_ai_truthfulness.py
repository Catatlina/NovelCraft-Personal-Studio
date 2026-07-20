#!/usr/bin/env python3
"""NovelCraft truthfulness gate.

This is intentionally AST-based instead of a broad grep:
- AI-looking functions must either call the real gateway/provider path or be
  explicitly allowlisted as deterministic data plumbing.
- Capability/status dictionaries must not hard-code availability.
- Cliché fixed-output templates are blocked before they become "AI" features.

The allowlist is part of the audit surface. Additions require a reason that
explains why the function is deterministic/non-AI rather than generated output.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = [ROOT / "backend/app"]

AI_NAME_RE = re.compile(r"(^|_)(generate|analyze|score|review|plan)(_|$)")
CLICHE_RE = re.compile(r"(震惊！|震惊|背后的真相|你不知道的|# \\{topic\\}|Estimated beats|Would call complete\\(\\) in production)")

GATEWAY_CALLS = {
    "complete",
    "complete_stream",
    "_deepseek_complete",
    "_claude_complete",
    "_openai_complete",
    "_gemini_complete",
}

AI_WRAPPER_CALLS = {
    "book_analysis_workbench",
    "multi_round_review",
    "cross_model_audit",
    "matrix_batch_run",
    "generate_title_variants",
    "generate_video_script",
    "generate_material_suggestions",
    "generate_daily_briefing",
    "_review_via_gateway",
    "_call_ai",
    "deai_score",
    "execute_bootstrap",
    "batch_generate_chapters_task",
}

# Explicit non-AI/deterministic exceptions. These functions must not return
# generated prose masquerading as AI output; they are data aggregation,
# scheduling, scoring heuristics, or endpoint dispatch wrappers.
ALLOWLIST: dict[str, str] = {
    "backend/app/main.py:batch_generate_chapters": "API dispatcher; queues batch_generate_chapters_task, no generated output",
    "backend/app/main.py:_chapter_review_context": "DB context assembler for review UI, no generated output",
    "backend/app/main.py:manual_review_chapter": "human approve/reject state transition; rejection only dispatches the real-AI regeneration worker",
    "backend/app/workers/tasks.py:batch_generate_chapters_task": "Celery orchestration; generation occurs in _generate_next_chapter_unlocked via gateway",
    "backend/app/services/hotspot_collector.py:_safe_score": "numeric normalization of collected source scores",
    "backend/app/services/hotspot_collector.py:compute_freshness_score": "deterministic recency score from timestamps",
    "backend/app/services/fusion_deep_book.py:layered_ai_planning": "legacy deterministic helper not counted as active product AI",
    "backend/app/services/m3_deep.py:generate_topic_bank": "static category bank, not personalized/generated content",
    "backend/app/services/publish_hub.py:generate_roi_report": "database aggregation report",
    "backend/app/services/publish_hub.py:generate_topic_suggestions_from_data": "database aggregation over performance rows",
    "backend/app/services/t5_long_run.py:adjacent_repeat_scores": "deterministic n-gram quality metric",
    "backend/app/services/m3_bulk.py:analyze_book_structure": "file parser/statistical structure metrics, not AI analysis",
    "backend/app/api/v1/complete_api.py:multi_round_review_endpoint": "endpoint delegates to AI wrapper multi_round_review",
    "backend/app/api/v1/complete_api.py:cross_model_review": "endpoint delegates to AI wrapper cross_model_audit",
    "backend/app/api/v1/complete_api.py:analyze_book": "endpoint delegates to AI wrapper book_analysis_workbench",
    "backend/app/api/v1/batch_endpoints.py:get_layered_plan": "read-only outline view endpoint",
    "backend/app/api/v1/ranking.py:generate_book": "book creation endpoint; AI generation is dispatched by worker after persistence",
    "backend/app/api/v1/ranking.py:analyze_rankings": "endpoint dispatcher; delegates ten-layer AI work to TenLayerAnalyzer._call_ai and persists partial/failed status honestly",
    "backend/app/api/v1/deai.py:quick_score": "explicit heuristic-only endpoint; name is API-compatible but it does not claim provider-backed AI scoring",
    "backend/app/services/deai_pipeline.py:quick_deai_score": "explicit heuristic-only local metric used as context/quick estimate, not provider-backed scoring",
    "backend/app/services/ten_layer_analysis.py:analyze_book_profile": "Layer 1 deterministic metadata normalization; no generated prose",
    "backend/app/services/ten_layer_analysis.py:analyze_genre_report": "Layer 2 deterministic counts/co-occurrence statistics; no generated prose",
    "backend/app/services/ten_layer_analysis.py:analyze_selling_points": "Layer 3 deterministic regex hook extraction; no generated prose",
    "backend/app/services/ten_layer_analysis.py:analyze": "orchestrator over local layers plus gateway-backed AI layer methods; generated analysis is delegated to _call_ai",
    "backend/app/services/ten_layer_analysis.py:_generate_heat_map": "deterministic aggregation report over collected ranking metrics",
    "backend/app/services/ten_layer_analysis.py:_generate_keyword_cloud": "deterministic tag/hook frequency extraction from layer outputs",
    "backend/app/services/ten_layer_analysis.py:_generate_trend_report": "deterministic packaging of AIInsight output and local top genres/hooks",
}


@dataclass
class Finding:
    path: Path
    line: int
    code: str
    message: str

    def render(self) -> str:
        rel = self.path.relative_to(ROOT) if self.path.is_absolute() and self.path.is_relative_to(ROOT) else self.path
        return f"{rel}:{self.line}: {self.code}: {self.message}"


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _string_literals(node: ast.AST) -> Iterable[tuple[int, str]]:
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            yield getattr(child, "lineno", 1), child.value
        elif isinstance(child, ast.JoinedStr):
            parts: list[str] = []
            for value in child.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    parts.append(value.value)
                elif isinstance(value, ast.FormattedValue):
                    parts.append("{expr}")
            yield getattr(child, "lineno", 1), "".join(parts)


def _truthy_constant(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _constant_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _function_key(path: Path, name: str) -> str:
    rel = path.relative_to(ROOT).as_posix() if path.is_absolute() and path.is_relative_to(ROOT) else path.as_posix()
    return f"{rel}:{name}"


def analyze_file(path: Path) -> list[Finding]:
    source = path.read_text(encoding="utf-8")
    findings: list[Finding] = []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [Finding(path, exc.lineno or 1, "syntax-error", str(exc))]

    for lineno, text in _string_literals(tree):
        negative_instruction = any(marker in text for marker in ("禁止", "不使用", "不得", "避免"))
        short_keyword = len(text.strip()) <= 6 and "{" not in text
        if CLICHE_RE.search(text) and not negative_instruction and not short_keyword:
            findings.append(Finding(path, lineno, "fixed-template", "blocked cliché/fabricated-output wording"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                key_text = _constant_str(key) if key is not None else None
                if key_text in {"wired", "available", "active", "integrated"} and _truthy_constant(value):
                    findings.append(Finding(path, getattr(value, "lineno", getattr(node, "lineno", 1)),
                                            "hardcoded-capability", f"{key_text}: True must be evidence-driven"))
                if key_text == "status" and _constant_str(value) == "active":
                    findings.append(Finding(path, getattr(value, "lineno", getattr(node, "lineno", 1)),
                                            "hardcoded-capability", "status='active' must be evidence-driven"))

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and AI_NAME_RE.search(node.name):
            key = _function_key(path, node.name)
            if key in ALLOWLIST:
                continue
            calls = {_call_name(call) for call in ast.walk(node) if isinstance(call, ast.Call)}
            if not (calls & GATEWAY_CALLS or calls & AI_WRAPPER_CALLS):
                findings.append(Finding(path, node.lineno, "ai-gateway-required",
                                        f"{node.name} looks like AI generation/analysis but does not call gateway or an approved wrapper"))

    return findings


def iter_py_files(paths: list[Path]) -> Iterable[Path]:
    for path in paths:
        path = path if path.is_absolute() else ROOT / path
        if path.is_file() and path.suffix == ".py":
            yield path
        elif path.is_dir():
            for file in path.rglob("*.py"):
                if ".venv" not in file.parts and "__pycache__" not in file.parts:
                    yield file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path, default=DEFAULT_PATHS)
    args = parser.parse_args(argv)

    findings: list[Finding] = []
    for path in iter_py_files(args.paths):
        findings.extend(analyze_file(path))

    if findings:
        print("AI truthfulness verification failed:")
        for finding in findings:
            print(f"- {finding.render()}")
        return 1
    print("AI truthfulness verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
