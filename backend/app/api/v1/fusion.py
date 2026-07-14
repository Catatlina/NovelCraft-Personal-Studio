"""NC-FUS: Fusion status API — unified governance + deep workflow + deep book status."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.auth import get_current_user
from app.api.v1.complete_api import ok, user_project_ids

router = APIRouter(prefix="/fusion", tags=["fusion"])


@router.get("/status")
def fusion_status(user: dict = Depends(get_current_user)):
    """Aggregated fusion status: governance + deep workflow + deep book integration."""
    from app.services.fusion_governance import (
        get_fusion_report,
        validate_fusion_contracts,
        get_fusion_integration_status,
        validate_fusion_data_integrity,
    )

    governance_report = get_fusion_report()
    contracts = validate_fusion_contracts()
    project_ids = user_project_ids(user)
    integration = get_fusion_integration_status(project_ids=project_ids)
    integrity = validate_fusion_data_integrity()

    # Deep workflow status is evidence-driven: importable module + recent
    # immutable ledger evidence for the current user's projects.
    deep_workflow_status = {
        "module": "fusion_deep_workflow",
        "available": False,
        "wired": False,
        "status": "missing",
        "capabilities": ["event_ledger", "fact_reconciliation", "workflow_plan"],
    }
    try:
        from app.services.fusion_deep_workflow import EVENT_TYPES
        from app.services.fusion_governance import _recent_workflow_evidence
        deep_workflow_status["event_types"] = len(EVENT_TYPES)
        workflow_evidence = _recent_workflow_evidence(project_ids=project_ids)
        deep_workflow_status["available"] = bool(EVENT_TYPES)
        deep_workflow_status["evidence"] = workflow_evidence
        deep_workflow_status["status"] = "verified" if workflow_evidence["success_count"] > 0 else "wired_unverified"
        deep_workflow_status["wired"] = deep_workflow_status["status"] == "verified"
    except Exception:
        deep_workflow_status["error"] = "module import failed"

    # Deep book legacy module is intentionally deprecated. Its functions are
    # not counted as active integration; active book analysis now lives in
    # providers_and_adapters.book_analysis_workbench and goes through Gateway.
    deep_book_status = {
        "module": "fusion_deep_book",
        "available": False,
        "wired": False,
        "deprecated": True,
        "status": "removed",
        "reason": "Legacy clean-room helpers are not active product paths; active book analysis uses Gateway task_type=book_analysis.",
        "active_replacement": "app.services.providers_and_adapters.book_analysis_workbench",
        "capabilities": [],
    }
    try:
        from app.services.providers_and_adapters import book_analysis_workbench
        from app.services.fusion_governance import _recent_ai_evidence
        book_evidence = _recent_ai_evidence(["book_analysis"], project_ids=project_ids)
        deep_book_status["replacement_import_verified"] = callable(book_analysis_workbench)
        deep_book_status["evidence"] = book_evidence
        deep_book_status["status"] = "verified" if book_evidence["success_count"] > 0 else "wired_unverified"
        deep_book_status["wired"] = deep_book_status["status"] == "verified"
    except Exception:
        deep_book_status["replacement_import_verified"] = False

    return ok({
        "fusion_governance": {
            "capability_matrix": governance_report,
            "contracts": contracts,
            "integration": integration,
            "data_integrity": integrity,
        },
        "deep_workflow": deep_workflow_status,
        "deep_book": deep_book_status,
        "summary": {
            "contracts_met": contracts.get("contracts_met", False),
            "integrity_pass": integrity.get("integrity_pass", False),
            "total_capabilities": integration.get("total_capabilities", 0),
            "integrated_capabilities": integration.get("integrated", 0),
            "wired_unverified_capabilities": integration.get("wired_unverified", 0),
            "deep_workflow_wired": deep_workflow_status.get("status") == "verified",
            "deep_book_wired": deep_book_status.get("status") == "verified",
        },
    })
