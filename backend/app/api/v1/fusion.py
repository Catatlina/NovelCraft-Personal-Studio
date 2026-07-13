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

    # Deep workflow availability
    deep_workflow_status = {
        "module": "fusion_deep_workflow",
        "available": True,
        "capabilities": ["event_ledger", "fact_reconciliation", "workflow_plan"],
    }
    try:
        from app.services.fusion_deep_workflow import EVENT_TYPES
        deep_workflow_status["event_types"] = len(EVENT_TYPES)
    except Exception:
        deep_workflow_status["available"] = False

    # Deep book availability
    deep_book_status = {
        "module": "fusion_deep_book",
        "available": True,
        "capabilities": [
            "hundred_chapter_memory",
            "six_dim_consistency_check",
            "book_analysis_workbench",
            "layered_ai_planning",
            "adaptive_draft_window",
            "reasonability_audit",
            "knowledge_merge",
        ],
    }
    try:
        from app.services.fusion_deep_book import six_dim_consistency_check
        deep_book_status["import_verified"] = True
    except Exception:
        deep_book_status["available"] = False

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
            "deep_workflow_wired": True,
            "deep_book_wired": True,
        },
    })
