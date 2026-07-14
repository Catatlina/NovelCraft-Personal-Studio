"""NC-FUS: Fusion status API — unified governance + deep workflow + deep book status."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.auth import get_current_user
from app.api.v1.complete_api import ok

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
    integration = get_fusion_integration_status()
    integrity = validate_fusion_data_integrity()

    # Deep workflow availability is evidence-driven: importable module +
    # expected exported contract. Never hard-code "wired".
    deep_workflow_status = {
        "module": "fusion_deep_workflow",
        "available": False,
        "wired": False,
        "capabilities": ["event_ledger", "fact_reconciliation", "workflow_plan"],
    }
    try:
        from app.services.fusion_deep_workflow import EVENT_TYPES
        deep_workflow_status["event_types"] = len(EVENT_TYPES)
        deep_workflow_status["available"] = bool(EVENT_TYPES)
        deep_workflow_status["wired"] = bool(EVENT_TYPES)
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
        "reason": "Legacy clean-room helpers are not active product paths; active book analysis uses Gateway task_type=book_analysis.",
        "active_replacement": "app.services.providers_and_adapters.book_analysis_workbench",
        "capabilities": [],
    }
    try:
        from app.services.providers_and_adapters import book_analysis_workbench
        deep_book_status["replacement_import_verified"] = callable(book_analysis_workbench)
        deep_book_status["wired"] = callable(book_analysis_workbench)
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
            "deep_workflow_wired": bool(deep_workflow_status.get("wired")),
            "deep_book_wired": bool(deep_book_status.get("wired")),
        },
    })
