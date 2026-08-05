"""Structured failure patterns distilled from quality reports.

The catalog is deliberately small and explainable.  A report finding becomes
runtime behavior only after it has a scope, severity, evidence, and a
regression path; prose suggestions are never injected as an unbounded prompt
dump.
"""

from .catalog import (
    FAILURE_PATTERN_SCHEMA_VERSION,
    failure_pattern_metadata,
    generation_constraints,
    get_failure_pattern,
    list_failure_patterns,
)

__all__ = [
    "FAILURE_PATTERN_SCHEMA_VERSION",
    "failure_pattern_metadata",
    "generation_constraints",
    "get_failure_pattern",
    "list_failure_patterns",
]
