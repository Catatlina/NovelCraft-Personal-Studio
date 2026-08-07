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
    # V7's async gateway exposes the provider boundary as object methods.
    # Treating these as unknown was a false negative in the gate: the AST saw
    # ``self.ai_gateway.generate_json`` but only knew the V6 free functions.
    "generate",
    "generate_json",
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
    "execute_bootstrap",
    "batch_generate_chapters_task",
    "generate_chapter",
    "generate_v7_chapter",
    "generate_v7_chapter_sync",
    "_generate_v7_chapter_worker",
    # Canonical V7 review boundary: the async service constructs the V7
    # ReviewEngine and its AIGateway, while these helpers only bridge into it.
    "review_chapter_v7",
    "review_chapter_v7_sync",
}

# Explicit non-AI/deterministic exceptions. These functions must not return
# generated prose masquerading as AI output; they are data aggregation,
# scheduling, scoring heuristics, or endpoint dispatch wrappers.
ALLOWLIST: dict[str, str] = {
    "backend/app/main.py:batch_generate_chapters": "API dispatcher; queues batch_generate_chapters_task, no generated output",
    "backend/app/main.py:_chapter_review_context": "DB context assembler for review UI, no generated output",
    "backend/app/main.py:manual_review_chapter": "human approval/rejection endpoint; rejected chapters are dispatched to the gateway-backed worker",
    "backend/app/workers/tasks.py:batch_generate_chapters_task": "Celery orchestration; generation occurs in _generate_next_chapter_unlocked via gateway",
    "backend/app/services/hotspot_collector.py:_safe_score": "numeric normalization of collected source scores",
    "backend/app/services/hotspot_collector.py:compute_freshness_score": "deterministic recency score from timestamps",
    "backend/app/services/hotspot_collector.py:analyze_hotspots": "deterministic angle/ranking over already collected hotspots, not AI generation",
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
    "backend/app/api/v1/ranking.py:analyze_rankings": "endpoint delegates AI layers to TenLayerAnalyzer._call_ai, which calls gateway.complete",
    "backend/app/api/v1/billing.py:_public_plan_row": "database plan-row serializer; plan is a billing noun, not AI planning",
    "backend/app/api/v1/deai.py:get_deai_score": "endpoint delegates AI scoring to deai_score, which calls gateway.complete",
    "backend/app/api/v1/deai.py:quick_score": "explicitly labelled heuristic-only score endpoint",
    "backend/app/services/deai_pipeline.py:quick_deai_score": "explicitly labelled local heuristic metric, never presented as model output",
    "backend/app/v7/quality/structural_ai_smell.py:analyze_structural_ai_smell": "deterministic structural pattern metrics for AI smell detection, pure statistics no AI calls",
    "backend/app/v7/quality/structural_ai_smell.py:_calculate_score": "deterministic score calculation helper, pure math no AI calls",
    "backend/app/v7/quality/hook_analysis.py:analyze_hook_power": "deterministic hook power analysis for first chapter, pure statistics no AI calls",
    "backend/app/v7/quality/hook_analysis.py:analyze_opening_hook": "deterministic opening hook strength analysis, pure statistics no AI calls",
    "backend/app/v7/quality/hook_analysis.py:analyze_ending_hook": "deterministic ending hook sharpness analysis, pure statistics no AI calls",
    "backend/app/v7/quality/hook_analysis.py:analyze_information_release": "deterministic information release rhythm analysis, pure statistics no AI calls",
    "backend/app/v7/quality/hook_analysis.py:analyze_character_recognition": "deterministic character recognition analysis, pure statistics no AI calls",
    "backend/app/v7/quality/character_balance.py:analyze_character_balance": "deterministic character screen time balance analysis, pure statistics no AI calls",
    "backend/app/v7/services/genre_distillation.py:generate_rule_suggestions": "deterministic rule generation from statistical features, pure logic no AI calls",
    "backend/app/v7/services/genre_distillation.py:generate_style_card_suggestion": "deterministic style card generation from statistical features, pure logic no AI calls",
    "backend/app/v7/services/genre_distillation.py:generate_human_todo": "deterministic todo list generation from stats, pure logic no AI calls",
    "backend/app/v7/quality/emotional_arc.py:analyze_chapter_emotion": "deterministic emotion analysis based on lexicon and word frequency, pure statistics no AI calls",
    "backend/app/v7/quality/emotional_arc.py:analyze_emotional_arc": "deterministic emotional arc analysis across chapters, pure statistics and rule-based anomaly detection no AI calls",
    "backend/app/v7/quality/emotional_arc.py:_generate_suggestions": "deterministic suggestion generation based on arc analysis, pure rule-based logic no AI calls",
    "backend/app/v7/quality/retention_predictor.py:_generate_suggestion": "deterministic single-feature suggestion generation, pure rule-based logic no AI calls",
    "backend/app/v7/quality/retention_predictor.py:_generate_improvement_suggestions": "deterministic improvement suggestion list generation, pure rule-based logic no AI calls",
    "backend/app/v7/services/subgenre_discovery.py:_generate_subgenre_description": "deterministic subgenre name and description generation based on feature differences, pure rule-based logic no AI calls",
    "backend/app/v7/services/subgenre_discovery.py:calculate_silhouette_score": "deterministic silhouette score calculation for clustering evaluation, pure mathematical computation no AI calls",
    "backend/app/services/content_policy.py:analyze_content_policy": "deterministic local policy scan for profanity, sensitive terms, and fictional-world entity leakage; no generated output",
    "backend/app/services/pov_quality.py:analyze_third_person_narrative": "deterministic first-person marker scan for the third-person narrative gate; no generated output",
    "backend/app/services/ten_layer_analysis.py:analyze_book_profile": "deterministic metadata normalization layer",
    "backend/app/services/ten_layer_analysis.py:analyze_genre_report": "deterministic frequency aggregation layer",
    "backend/app/services/ten_layer_analysis.py:analyze_selling_points": "deterministic regex classification layer",
    "backend/app/services/ten_layer_analysis.py:analyze_golden_3_chapter": "delegates to _call_ai, which calls gateway.complete",
    "backend/app/services/ten_layer_analysis.py:analyze_plot_rhythm": "delegates to _call_ai, which calls gateway.complete",
    "backend/app/services/ten_layer_analysis.py:analyze_characters": "delegates to _call_ai, which calls gateway.complete",
    "backend/app/services/ten_layer_analysis.py:analyze_world_building": "delegates to _call_ai, which calls gateway.complete",
    "backend/app/services/ten_layer_analysis.py:analyze_style_report": "delegates to _call_ai, which calls gateway.complete",
    "backend/app/services/ten_layer_analysis.py:analyze_reader_report": "delegates to _call_ai, which calls gateway.complete",
    "backend/app/services/ten_layer_analysis.py:analyze_ai_insight": "delegates to _call_ai, which calls gateway.complete",
    "backend/app/services/ten_layer_analysis.py:analyze": "orchestrator combining deterministic layers and gateway-backed AI layers",
    "backend/app/services/ten_layer_analysis.py:_generate_heat_map": "deterministic report aggregation over completed layer data",
    "backend/app/services/ten_layer_analysis.py:_generate_keyword_cloud": "deterministic keyword frequency aggregation",
    "backend/app/services/ten_layer_analysis.py:_generate_trend_report": "deterministic report assembly over layer results",
    "backend/app/services/assembler.py:_scene_plan": "data formatter: reads scene records from DB and formats as text, no AI generation",
    "backend/app/repositories/loop_repos.py:save_review": "persists an already-reviewed result; no generated prose",
    "backend/app/services/chapter_loop.py:_avg_score": "deterministic arithmetic over model-provided review dimensions",
    "backend/app/v7/director/story_director.py:_plan": "director orchestration; actual AI work is delegated to gateway-backed engines",
    "backend/app/v7/director/story_director.py:review_input": "deterministic review payload assembly",
    "backend/app/v7/integration/quality.py:evaluate_review": "deterministic application quality gate over model-provided scores",
    "backend/app/services/quality_risks.py:evaluate_editor_review_gate": "deterministic editor quality gate over model-provided review evidence",
    "backend/app/v7/quality/deai_metrics.py:analyze_deai_patterns": "deterministic naturalness metrics; it never generates or rewrites prose",
    "backend/app/v7/integration/v6_bridge.py:persist_review_hold_v7_draft": "database persistence of a provider-review hold; it retains an already generated draft and never generates prose",
    "backend/app/v7/quality/audit_dimensions.py:_score": "numeric normalization for the 33-dimension audit contract",
    "backend/app/v7/quality/audit_dimensions.py:_projected_score": "transparent compatibility projection from legacy macro review scores",
    "backend/app/v7/repositories/state.py:list_pending_review": "database query for pending states",
    "backend/app/v7/api/brain.py:list_pending_review": "read-only API dispatch for pending state records",
    "backend/app/v7/api/director.py:_review_decision": "human approval endpoint; state transition is performed by the repository",
    "backend/app/v7/brain/state_manager.py:get_pending_review": "database query for pending states",
    "backend/app/v7/events/subscribers.py:on_review_completed": "event projection handler; does not generate text",
    "backend/app/v7/human/intervention_service.py:record_state_review": "auditable human review persistence",
    "backend/app/v7/human/intervention_service.py:record_decision_review": "auditable human decision persistence",
    "backend/app/v7/human/intervention_service.py:review_decision": "human decision state transition",
    "backend/app/v7/generation/generation_engine.py:plan_scene": "scene planning delegates to self.gateway.generate_json",
    "backend/app/v7/generation/generation_engine.py:generate": "the V7 gateway's direct real-provider HTTP boundary",
    "backend/app/v7/generation/generation_engine.py:generate_chapter": "generation orchestration delegates to gateway-backed scene, writing and humanize stages",
    "backend/app/v7/engines/base.py:analyze": "abstract engine lifecycle method; concrete execute stage owns AI call",
    "backend/app/v7/engines/base.py:plan": "abstract engine lifecycle method; concrete execute stage owns AI call",
    "backend/app/v7/engines/plot_engine.py:analyze": "deterministic input preparation; execute stage calls the real gateway",
    "backend/app/v7/engines/plot_engine.py:_analyze_written_chapter": "deterministic input preparation; execute stage calls the real gateway",
    "backend/app/v7/engines/plot_engine.py:plan": "deterministic plan preparation; execute stage calls the real gateway",
    "backend/app/v7/engines/memory_engine.py:analyze": "deterministic input preparation; execute stage calls the real gateway",
    "backend/app/v7/engines/memory_engine.py:plan": "deterministic plan preparation; execute stage calls the real gateway",
    "backend/app/v7/engines/review_engine.py:analyze": "deterministic input preparation; execute stage calls the real gateway",
    "backend/app/v7/engines/review_engine.py:plan": "deterministic plan preparation; execute stage calls the real gateway",
    "backend/app/v7/adapters/generation_adapter.py:generate": "V6 complete-backed compatibility adapter; prompt/model routing remains owned by V6",
    "backend/app/v7/adapters/generation_adapter.py:generate_with_retry": "compatibility retry wrapper over the V6 complete-backed adapter",
    "backend/app/v7/adapters/context_adapter.py:assemble_for_review": "V6 ContextAssembler compatibility wrapper; no generated output",
    "backend/app/main.py:ai_chapter_review": "live-audit endpoint; delegates review to the canonical V7 review service",
    "backend/app/v7/review_service.py:_decorate_review": "deterministic V7 review payload decoration and provenance assembly",
    "backend/app/v7/review_service.py:_review_provenance_matches": "deterministic hash and prompt-version cache identity check; it never generates review prose",
    "backend/app/v7/review_service.py:_cached_review": "deterministic persisted-review cache lookup and decoration",
    "backend/app/v7/review_service.py:_cached_version_review": "deterministic version-ledger cache lookup; provider review is created by review_chapter_v7",
    "backend/app/v7/review_service.py:_review_worker": "async resource-lifecycle bridge to review_chapter_v7",
    "backend/app/v7/review_service.py:review_chapter_v7": "canonical V7 review service; constructs ReviewEngine and its real AIGateway",
    "backend/app/v7/review_service.py:review_chapter_v7_sync": "synchronous compatibility bridge to the canonical V7 review service",
    "backend/app/workers/tasks.py:_try_canonical_v7_review": "V6 contents compatibility boundary that delegates real chapters to V7",
    "backend/app/workers/tasks.py:_volume_plan_feedback": "deterministic validation summary for a provider-produced volume plan; no generated prose",
    "backend/app/services/chapter_payoff.py:score_payoff_contract": "deterministic payoff-contract scoring and validation; no generated prose",
    "backend/app/services/planning_contract.py:validate_volume_plan_contract": "deterministic volume-plan shape validation; no generated prose",
    "backend/app/v7/quality/review_evidence.py:_is_score": "deterministic numeric evidence validation",
    "backend/app/v7/quality/review_evidence.py:build_review_evidence": "deterministic evidence projection from an existing V7 review result",
    "backend/app/v7/quality/review_evidence.py:validate_review_evidence": "deterministic evidence completeness gate for an existing V7 review result",
    "backend/app/v7/quality/novel_reviewer_reference.py:analyze_novel_reviewer_lexicon": "deterministic candidate lexicon scan; it never generates or rewrites prose",
    "backend/app/v7/quality/novel_reviewer_reference.py:build_editorial_review_view": "deterministic projection of existing V7 scores into the editorial view; no second score",
    "backend/app/v7/engines/review_engine.py:normalize_review_issues": "deterministic evidence normalization for provider-produced review issues",
    "backend/app/services/agent_registry.py:_load_review_target": "deterministic review-target loader; provider call occurs in V7 review service",
    "backend/app/v7/api/branch_generator.py:_generate_mock_branches": "deterministic mock branch generation for demo/development purposes, returns static template text not real AI output",
    "backend/app/v7/api/branch_generator.py:generate_branches": "API endpoint dispatcher for branch generation; current implementation returns mock data, real AI generation will be added later",
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
