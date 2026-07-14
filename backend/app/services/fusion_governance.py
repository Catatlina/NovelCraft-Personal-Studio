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
    "oh-story.prompts": {"route": "/api/v1/prompts", "file": "app/prompt_registry.py", "evidence": "route"},
    "oh-story.scan_protocol": {"route": "/api/v1/ranking/*", "file": "app/services/ranking_adapter.py",
                               "task_types": ["ranking_market_analysis"]},
    "denova.workflow_engine": {"route": "/api/v1/runs/{id}/*", "file": "app/workers/tasks.py", "evidence": "audit_logs"},
    "denova.agent_trace": {"route": "/api/v1/agents", "file": "app/services/agent_registry.py", "evidence": "run_nodes"},
    "show-me-the-story.foreshadow": {"route": "/api/v1/novels/{id}/foreshadowings", "file": "app/services/narrative_engine.py",
                                     "task_types": ["extract_foreshadowing"]},
    "AI_NovelGenerator.chapter_parser": {"route": "/api/v1/novels/{id}/import-chapters", "file": "app/services/batch_fixes.py",
                                         "evidence": "contents.chapter"},
    "AI-auto-generates.book_analyzer": {"route": "/api/v1/books/analyze", "file": "app/services/providers_and_adapters.py",
                                        "task_types": ["book_analysis"]},
    "harnessNovel.layered_planning": {"route": "/api/v1/novels/layered-plan", "file": "app/services/batch_fixes.py",
                                      "task_types": ["plan_idea", "plan_market_fit", "plan_world_architecture"]},
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


def _recent_ai_evidence(task_types: list[str], project_ids: list[str] | None = None, days: int = 30) -> dict:
    if not task_types:
        return {"success_count": 0, "latest_at": None, "provider_count": 0}
    if project_ids is not None and not project_ids:
        return {"success_count": 0, "latest_at": None, "provider_count": 0}
    db = connect()
    try:
        if project_ids is None:
            row = db.execute(
                """
                SELECT COUNT(*) AS success_count, MAX(created_at) AS latest_at,
                       COUNT(DISTINCT provider) AS provider_count
                FROM ai_calls
                WHERE status='succeeded'
                  AND provider <> 'mock'
                  AND task_type = ANY(%s)
                  AND created_at > now() - (%s * interval '1 day')
                """,
                (task_types, days),
            ).fetchone()
        else:
            row = db.execute(
                """
                SELECT COUNT(*) AS success_count, MAX(created_at) AS latest_at,
                       COUNT(DISTINCT provider) AS provider_count
                FROM ai_calls
                WHERE status='succeeded'
                  AND provider <> 'mock'
                  AND task_type = ANY(%s)
                  AND project_id = ANY(%s::uuid[])
                  AND created_at > now() - (%s * interval '1 day')
                """,
                (task_types, project_ids, days),
            ).fetchone()
    finally:
        db.close()
    return {
        "success_count": int(row["success_count"] or 0) if row else 0,
        "latest_at": str(row["latest_at"]) if row and row["latest_at"] else None,
        "provider_count": int(row["provider_count"] or 0) if row else 0,
    }


def _recent_workflow_evidence(project_ids: list[str] | None = None, days: int = 30) -> dict:
    if project_ids is not None and not project_ids:
        return {"success_count": 0, "latest_at": None}
    db = connect()
    try:
        if project_ids is None:
            row = db.execute(
                """
                SELECT COUNT(*) AS success_count, MAX(al.created_at) AS latest_at
                FROM audit_logs al
                JOIN workflow_runs wr ON wr.id = al.entity_id
                WHERE al.entity_type='workflow_run'
                  AND al.action IN ('run.completed','node.completed','checkpoint.created')
                  AND al.created_at > now() - (%s * interval '1 day')
                """,
                (days,),
            ).fetchone()
        else:
            row = db.execute(
                """
                SELECT COUNT(*) AS success_count, MAX(al.created_at) AS latest_at
                FROM audit_logs al
                JOIN workflow_runs wr ON wr.id = al.entity_id
                WHERE al.entity_type='workflow_run'
                  AND al.action IN ('run.completed','node.completed','checkpoint.created')
                  AND wr.project_id = ANY(%s::uuid[])
                  AND al.created_at > now() - (%s * interval '1 day')
                """,
                (project_ids, days),
            ).fetchone()
    finally:
        db.close()
    return {
        "success_count": int(row["success_count"] or 0) if row else 0,
        "latest_at": str(row["latest_at"]) if row and row["latest_at"] else None,
    }


def _entry_state(entry: dict, project_ids: list[str] | None = None) -> tuple[str, dict]:
    if entry.get("expected_state") == "removed":
        return "removed", {"success_count": 0, "latest_at": None}
    route = entry.get("route")
    app_file = entry.get("file", "")
    wired = bool(route and _file_exists(app_file))
    if not wired:
        return "missing", {"success_count": 0, "latest_at": None}

    if entry.get("task_types"):
        evidence = _recent_ai_evidence(entry["task_types"], project_ids=project_ids)
        return ("verified" if evidence["success_count"] > 0 else "wired_unverified"), evidence

    if entry.get("evidence") == "audit_logs":
        evidence = _recent_workflow_evidence(project_ids=project_ids)
        return ("verified" if evidence["success_count"] > 0 else "wired_unverified"), evidence

    return "wired_unverified", {"success_count": 0, "latest_at": None, "evidence": entry.get("evidence", "route")}


def get_fusion_integration_status(project_ids: list[str] | None = None) -> dict:
    """NC-FUS-003: Integration status — which upstream capabilities have NovelCraft entry points."""
    entries = {}
    for key, entry in FUSION_ENTRY_MAP.items():
        status, evidence = _entry_state(entry, project_ids=project_ids)
        entries[key] = {**entry, "status": status, "evidence": evidence}
    verified = [key for key, item in entries.items() if item["status"] == "verified"]
    wired_unverified = [key for key, item in entries.items() if item["status"] == "wired_unverified"]
    return {
        "total_capabilities": len(FUSION_ENTRY_MAP),
        "integrated": len(verified),
        "wired_unverified": len(wired_unverified),
        "pending": len(FUSION_ENTRY_MAP) - len(verified) - len(wired_unverified),
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
