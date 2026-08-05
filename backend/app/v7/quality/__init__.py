"""Quality primitives shared by the canonical V7 generation chain."""

from .audit_dimensions import (
    AUDIT_DIMENSIONS,
    AUDIT_DIMENSION_GROUPS,
    normalize_audit_report,
)
from .continuity import build_state_delta, validate_transition_contract
from .deai_metrics import analyze_deai_patterns
from .failure_patterns import (
    FAILURE_PATTERN_SCHEMA_VERSION,
    failure_pattern_metadata,
    generation_constraints,
    get_failure_pattern,
    list_failure_patterns,
)
from .payoff_strategy import (
    PAYOFF_STRATEGY_SCHEMA_VERSION,
    choose_payoff_type,
    select_payoff_strategy,
    strategy_metadata,
)
from .review_evidence import (
    REVIEW_EVIDENCE_SCHEMA_VERSION,
    build_review_evidence,
    validate_review_evidence,
)

__all__ = [
    "AUDIT_DIMENSIONS",
    "AUDIT_DIMENSION_GROUPS",
    "normalize_audit_report",
    "build_state_delta",
    "validate_transition_contract",
    "analyze_deai_patterns",
    "FAILURE_PATTERN_SCHEMA_VERSION",
    "failure_pattern_metadata",
    "generation_constraints",
    "get_failure_pattern",
    "list_failure_patterns",
    "PAYOFF_STRATEGY_SCHEMA_VERSION",
    "choose_payoff_type",
    "select_payoff_strategy",
    "strategy_metadata",
    "REVIEW_EVIDENCE_SCHEMA_VERSION",
    "build_review_evidence",
    "validate_review_evidence",
]
