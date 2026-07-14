"""NC-FUS-001~004: Six-project fusion — capability matrix, unified contracts, integration, migration."""
from __future__ import annotations
import json, os
from datetime import datetime
from app.db import connect, new_id, encode


# ===== NC-FUS-001: Capability matrix (keep/merge/drop) =====

FUSION_CAPABILITY_MATRIX = {
    "oh-story": {"prompts": "keep", "scan_protocol": "keep", "review_workflow": "merge", "long_write": "merge"},
    "denova": {"workflow_engine": "merge", "agent_trace": "keep", "checkpoint": "merge", "conversation_mode": "drop"},
    "show-me-the-story": {"foreshadow_lifecycle": "merge", "chapter_reconcile": "merge", "prose_counting": "drop"},
    "AI_NovelGenerator": {"chapter_parser": "keep", "vector_kb": "merge", "six_dim_consistency": "keep"},
    "AI-auto-generates": {"batch_production": "merge", "book_analyzer": "keep", "mind_map": "drop"},
    "harnessNovel": {"layered_planning": "merge", "world_knowledge": "keep", "reasonability_audit": "drop"},
    "BrowserAct": {"stealth_extract": "keep", "chrome_publish": "drop", "captcha_solve": "drop"},
    "insprira": {"account_tracking": "keep", "compliance_check": "keep", "skill_center": "merge", "dashboards": "drop"},
}


def get_fusion_report() -> dict:
    """NC-FUS-001: Full capability matrix with decisions and rationale."""
    summary = {"keep": 0, "merge": 0, "drop": 0, "projects": {}}
    for project, capabilities in FUSION_CAPABILITY_MATRIX.items():
        summary["projects"][project] = {}
        for cap, decision in capabilities.items():
            summary[decision] = summary.get(decision, 0) + 1
            summary["projects"][project][cap] = decision
    summary["total_keep"] = sum(1 for p in FUSION_CAPABILITY_MATRIX.values() for d in p.values() if d == "keep")
    summary["total_merge"] = sum(1 for p in FUSION_CAPABILITY_MATRIX.values() for d in p.values() if d == "merge")
    summary["total_drop"] = sum(1 for p in FUSION_CAPABILITY_MATRIX.values() for d in p.values() if d == "drop")
    return summary


# ===== NC-FUS-002: Unified contracts =====

UNIFIED_CONTRACTS = {
    "identity": {
        "project_id_format": "UUID v4",
        "content_id_format": "UUID v4 with parent_id tree",
        "user_id_format": "UUID v4 + JWT sub binding",
    },
    "model_routing": {
        "provider_registry": "config.py + model_routes table",
        "fallback_chain": "none; real provider failure is terminal and explicit",
        "budget_per_run": "project budget model, three-tier circuit breaker",
    },
    "storage": {
        "primary": "PostgreSQL (contents, versions, ai_calls, workflows)",
        "search": "pgvector HNSW index (installed, GIN fallback)",
        "cache": "Redis (Celery broker/backend)",
    },
    "api_contract": {
        "auth": "JWT Bearer token, /api/v1/auth/*",
        "content": "/api/v1/contents, /api/v1/novels/{id}/*",
        "workflow": "/api/v1/runs/{id}/* (SSE events)",
        "versioning": "/api/v1/versions/*",
    },
}


def validate_fusion_contracts() -> dict:
    """NC-FUS-002: Verify unified contracts are met by current codebase."""
    from app.db import connect
    db = connect()
    tables = db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()
    db.close()
    contract_tables = {"contents", "versions", "ai_calls", "workflow_runs", "workflows", "knowledge_items"}
    existing = {t["tablename"] for t in tables} if tables else set()
    missing = contract_tables - existing
    return {
        "contracts_met": len(missing) == 0,
        "existing_tables": sorted(existing),
        "missing_tables": sorted(missing),
        "total_tables": len(existing),
    }


# ===== NC-FUS-003: Integration — capability mapping with entry points =====

FUSION_ENTRY_MAP = {
    "oh-story.prompts": {"route": "/api/v1/prompts", "file": "app/prompt_registry.py"},
    "oh-story.scan_protocol": {"route": "/api/v1/ranking/*", "file": "app/services/ranking_adapter.py"},
    "denova.workflow_engine": {"route": "/api/v1/runs/{id}/*", "file": "app/workers/tasks.py"},
    "denova.agent_trace": {"route": "/api/v1/agents", "file": "app/services/agent_registry.py"},
    "show-me-the-story.foreshadow": {"route": "/api/v1/novels/{id}/foreshadowings", "file": "app/services/narrative_engine.py"},
    "AI_NovelGenerator.chapter_parser": {"route": "/api/v1/novels/{id}/import-chapters", "file": "app/services/batch_fixes.py"},
    "AI-auto-generates.book_analyzer": {"route": "/api/v1/books/analyze", "file": "app/services/providers_and_adapters.py"},
    "harnessNovel.layered_planning": {"route": "/api/v1/novels/layered-plan", "file": "app/services/batch_fixes.py"},
    "BrowserAct.chrome_publish": {"route": None, "file": "app/services/fusion_browseract_insprira.py",
                                  "expected_state": "removed",
                                  "reason": "BrowserAct scraping/anti-bot publish route was removed by compliance hardening; manual logged-in publishing remains outside API automation."},
    "insprira.account_tracking": {"route": "/api/v1/accounts/track", "file": "app/services/fusion_browseract_insprira.py"},
    "insprira.compliance_check": {"route": "/api/v1/content/check-compliance", "file": "app/services/fusion_browseract_insprira.py"},
}


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _file_exists(app_file: str) -> bool:
    return os.path.exists(os.path.join(_repo_root(), app_file))


def _entry_state(entry: dict) -> str:
    if entry.get("expected_state") == "removed":
        return "removed"
    route = entry.get("route")
    app_file = entry.get("file", "")
    if route and _file_exists(app_file):
        return "verified"
    return "missing"


def get_fusion_integration_status() -> dict:
    """NC-FUS-003: Integration status — which upstream capabilities have NovelCraft entry points."""
    entries = {key: {**entry, "status": _entry_state(entry)} for key, entry in FUSION_ENTRY_MAP.items()}
    verified = [key for key, item in entries.items() if item["status"] == "verified"]
    return {
        "total_capabilities": len(FUSION_ENTRY_MAP),
        "integrated": len(verified),
        "pending": len(FUSION_ENTRY_MAP) - len(verified),
        "entries": entries,
    }


# ===== NC-FUS-004: Migration tooling =====

def create_fusion_migration_checkpoint(name: str = "") -> dict:
    """NC-FUS-004: Create a migration checkpoint for rollback safety."""
    db = connect()
    checkpoint = {
        "name": name or f"fusion_checkpoint_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "created_at": datetime.utcnow().isoformat(),
        "table_counts": {},
        "fusion_capabilities": get_fusion_report(),
    }
    tables = db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()
    for t in tables:
        cnt = db.execute(f"SELECT COUNT(*) FROM {t['tablename']}").fetchone()
        checkpoint["table_counts"][t['tablename']] = cnt["count"] if cnt else 0
    db.close()
    return checkpoint


def validate_fusion_data_integrity() -> dict:
    """NC-FUS-004: Validate data integrity across fused systems — no orphans, correct refs."""
    db = connect()
    issues = []
    # Content tree: every non-novel content must have valid parent
    orphans = db.execute(
        "SELECT COUNT(*) FROM contents WHERE type!='novel' AND parent_id IS NOT NULL "
        "AND parent_id NOT IN (SELECT id FROM contents)"
    ).fetchone()
    if orphans and orphans["count"] > 0:
        issues.append(f"{orphans['count']} orphaned contents (broken parent_id)")

    # Run nodes must reference valid runs
    orphan_runs = db.execute(
        "SELECT COUNT(*) FROM run_nodes WHERE run_id NOT IN (SELECT id FROM workflow_runs)"
    ).fetchone()
    if orphan_runs and orphan_runs["count"] > 0:
        issues.append(f"{orphan_runs['count']} orphaned run_nodes")

    db.close()
    return {
        "integrity_pass": len(issues) == 0,
        "issues": issues,
        "checked": ["content_tree", "run_nodes"],
    }
