"""AI output evaluation & scoring system.

Evaluates AI-generated content across multiple dimensions:
  - relevance: does output match the prompt intent?
  - completeness: are all required sections present?
  - coherence: is the output logically consistent?
  - toxicity: does output contain harmful content?
  - json_validity: is structured output parseable?
  - contract_compliance: does output match OUTPUT_CONTRACTS?

Returns a score (0-100) and detailed dimension breakdown.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalDimension:
    name: str
    score: float      # 0.0 - 1.0
    weight: float     # relative weight
    details: str = ""


@dataclass
class EvalResult:
    overall: float                     # 0.0 - 100.0
    dimensions: list[EvalDimension] = field(default_factory=list)
    passed: bool = False
    issues: list[str] = field(default_factory=list)


def evaluate(output: str, prompt_intent: str = "", contract: dict | None = None) -> EvalResult:
    """Evaluate AI output quality. Non-AI heuristic evaluation."""
    dims: list[EvalDimension] = []

    # 1. Completeness — non-empty output
    if output and len(output.strip()) > 10:
        dims.append(EvalDimension("completeness", 1.0, 0.15, f"{len(output)} chars"))
    else:
        dims.append(EvalDimension("completeness", 0.0, 0.15, "too short/empty"))

    # 2. Structure check — look for headers or sections
    has_structure = bool(re.search(r"(?:^|\n)#{1,3}\s|【|##|[0-9]+\.", output))
    dims.append(EvalDimension("structure", 1.0 if has_structure else 0.3, 0.10))

    # 3. JSON validity (for structured outputs)
    json_ok = True
    try:
        json.loads(output)
    except (json.JSONDecodeError, ValueError):
        json_ok = False
    if contract:
        dims.append(EvalDimension("json_validity", 1.0 if json_ok else 0.0, 0.25))
    else:
        dims.append(EvalDimension("json_validity", 1.0, 0.0))  # N/A

    # 4. Relevance — keyword overlap with prompt intent
    if prompt_intent:
        intent_words = set(prompt_intent.lower().split())
        output_words = set(output.lower().split())
        overlap = len(intent_words & output_words) / max(len(intent_words), 1)
        dims.append(EvalDimension("relevance", min(overlap * 3, 1.0), 0.20,
                                  f"overlap={overlap:.2f}"))
    else:
        dims.append(EvalDimension("relevance", 1.0, 0.0))  # N/A

    # 5. Toxicity — basic keyword check
    toxic_patterns = ["死", "杀光", "轮奸"]  # non-exhaustive
    toxic_hits = sum(1 for p in toxic_patterns if p in output)
    toxicity_score = max(0.0, 1.0 - toxic_hits * 0.3)
    dims.append(EvalDimension("toxicity", toxicity_score, 0.15))

    # 6. Contract compliance
    if contract:
        missing = _check_contract(output, contract)
        comp_score = max(0.0, 1.0 - len(missing) * 0.2)
        dims.append(EvalDimension("contract", comp_score, 0.15,
                                  f"missing={missing}" if missing else "ok"))
    else:
        dims.append(EvalDimension("contract", 1.0, 0.0))

    # Overall weighted score
    total_weight = sum(d.weight for d in dims)
    if total_weight > 0:
        overall = sum(d.score * d.weight for d in dims) / total_weight * 100
    else:
        overall = 100.0

    issues = [f"{d.name}: {d.details}" for d in dims if d.score < 0.5 and d.weight > 0]
    return EvalResult(
        overall=round(overall, 1),
        dimensions=dims,
        passed=overall >= 60.0,
        issues=issues,
    )


def _check_contract(output: str, contract: dict) -> list[str]:
    """Check if output contains required keys from contract."""
    missing = []
    required = contract.get("required_fields", contract.get("fields", {}))
    if isinstance(required, list):
        for field in required:
            if field not in output:
                missing.append(field)
    return missing
