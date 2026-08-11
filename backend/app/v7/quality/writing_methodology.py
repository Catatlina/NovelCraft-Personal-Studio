"""Machine-readable implementation of the shared writing methodology.

The source methodology is deliberately not pasted into every provider prompt.
This module owns the small, auditable contract that the generation and review
chains can carry from planning through publication:

* a chapter contract (problem -> visible payoff -> cost -> next pressure);
* a five-column causal ledger for every planned event;
* the state that must not change without an on-page cause;
* a fail-closed external-evaluation record bound to the exact text hash.

The prose rules remain guidance.  The fields below are evidence contracts, so
they can be inspected in ``contents.meta`` and cannot be replaced by a vague
"make it more human" instruction.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

WRITING_METHODOLOGY_VERSION = "1.0.0"
WRITING_WORKFLOW_SCHEMA_VERSION = "writing-workflow-v1"
EXTERNAL_EVALUATION_SCHEMA_VERSION = "external-evaluation-v1"
EXTERNAL_SCORE_THRESHOLD = 90.0

WORKFLOW_STATUSES: tuple[str, ...] = (
    "input_pending",
    "causal_ready",
    "drafted",
    "causal_passed",
    "style_passed",
    "external_pending",
    "external_90_plus",
    "published",
    "blocked",
)

WORKFLOW_TRANSITIONS: dict[str, frozenset[str]] = {
    "input_pending": frozenset({"causal_ready", "blocked"}),
    "causal_ready": frozenset({"drafted", "blocked"}),
    "drafted": frozenset({"causal_passed", "blocked"}),
    "causal_passed": frozenset({"style_passed", "external_pending", "blocked"}),
    "style_passed": frozenset({"external_pending", "blocked"}),
    "external_pending": frozenset({"external_90_plus", "blocked"}),
    "external_90_plus": frozenset({"published", "blocked"}),
    "published": frozenset({"published"}),
    "blocked": frozenset({"input_pending", "causal_ready", "drafted", "blocked"}),
}


def text_sha256(text: str) -> str:
    """Return the stable hash used to bind an external report to正文."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return "unknown"


def _list(value: Any, limit: int = 12) -> list[Any]:
    if isinstance(value, list):
        return value[:limit]
    if value in (None, ""):
        return []
    return [value]


def _normalise_ledger(rows: Any, beats: Any = None) -> list[dict[str, Any]]:
    """Normalise provider rows without inventing missing causal facts."""
    source = rows if isinstance(rows, list) else []
    if not source and isinstance(beats, list):
        source = beats
    normalised: list[dict[str, Any]] = []
    for index, raw in enumerate(source[:8], start=1):
        raw = raw if isinstance(raw, dict) else {"event": raw}
        normalised.append({
            "id": _first_text(raw.get("id"), f"event_{index}"),
            "event": _first_text(raw.get("event"), raw.get("content"), raw.get("name")),
            "knower": _first_text(raw.get("knower"), raw.get("who_knows"), raw.get("known_by")),
            "motive": _first_text(raw.get("motive"), raw.get("why_now"), raw.get("reason"), raw.get("purpose")),
            "cost": _first_text(raw.get("cost"), raw.get("price"), raw.get("代价")),
            "next_effect": _first_text(raw.get("next_effect"), raw.get("next_event"), raw.get("consequence"), raw.get("effect")),
            "source": "provider" if raw.get("event") or raw.get("knower") else "beat_projection",
        })
    return normalised


def _missing_contract_fields(contract: dict[str, Any], ledger: list[dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    for field in ("core_problem", "observable_payoff", "cost", "next_inevitable_event"):
        if not _text(contract.get(field)) or contract.get(field) == "unknown":
            missing.append(f"chapter_contract.{field}")
    if not ledger:
        missing.append("causal_ledger")
    for index, row in enumerate(ledger, start=1):
        for field in ("event", "knower", "motive", "cost", "next_effect"):
            if not _text(row.get(field)) or row.get(field) == "unknown":
                missing.append(f"causal_ledger[{index}].{field}")
    return missing


def validate_writing_workflow(workflow: dict[str, Any] | None) -> dict[str, Any]:
    """Validate the pre-generation causal contract deterministically."""
    workflow = workflow if isinstance(workflow, dict) else {}
    chapter_contract = workflow.get("chapter_contract") or {}
    ledger = workflow.get("causal_ledger") or []
    missing = _missing_contract_fields(chapter_contract, ledger)
    return {
        "schema_version": WRITING_WORKFLOW_SCHEMA_VERSION,
        "passed": not missing,
        "missing": missing,
        "blocking": bool(missing),
        "message": "causal contract ready" if not missing else "pre-generation causal contract incomplete",
    }


def transition_workflow_status(workflow: dict[str, Any], next_status: str) -> dict[str, Any]:
    """Apply the source package's state machine without silently skipping gates."""
    if not isinstance(workflow, dict):
        raise ValueError("writing workflow must be an object")
    current = _text(workflow.get("status")) or "input_pending"
    if next_status not in WORKFLOW_STATUSES:
        raise ValueError(f"unsupported writing workflow status: {next_status}")
    if next_status != current and next_status not in WORKFLOW_TRANSITIONS.get(current, frozenset()):
        raise ValueError(f"invalid writing workflow transition: {current} -> {next_status}")
    workflow["status"] = next_status
    return workflow


def _default_external_evaluation() -> dict[str, Any]:
    return {
        "schema_version": EXTERNAL_EVALUATION_SCHEMA_VERSION,
        "status": "not_run",
        "provider": None,
        "input_hash": None,
        "scope": None,
        "scores": {},
        "flagged_segments": [],
    }


def build_writing_workflow_contract(
    chapter_number: int,
    *,
    context_layers: dict[str, Any] | None = None,
    plot_brief: dict[str, Any] | None = None,
    scene_plan: dict[str, Any] | None = None,
    chapter_text: str | None = None,
    review: dict[str, Any] | None = None,
    external_evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one contract from existing V7 planning and review artifacts."""
    context_layers = context_layers if isinstance(context_layers, dict) else {}
    plot_brief = plot_brief if isinstance(plot_brief, dict) else {}
    scene_plan = scene_plan if isinstance(scene_plan, dict) else {}
    review = review if isinstance(review, dict) else {}
    source = {**plot_brief, **scene_plan}
    payoff = source.get("payoff_contract") or {}
    previous = context_layers.get("previous_transition_contract") or {}
    previous_end = previous.get("end_state") or {}
    previous_state = previous.get("state_delta") or {}
    current_state = {
        "time": _first_text(context_layers.get("current_time"), previous_end.get("time"), previous_state.get("time")),
        "location": _first_text(context_layers.get("current_location"), previous_end.get("location"), previous_state.get("location")),
        "knowledge": _list(context_layers.get("known_facts") or previous_end.get("knowledge") or previous_state.get("knowledge")),
        "objects": _list(context_layers.get("objects") or previous_end.get("objects") or previous_state.get("objects")),
        "resources": _list(context_layers.get("resources") or previous_end.get("resources") or previous_state.get("resources")),
        "relationships": _list(context_layers.get("relationships") or previous_end.get("relationships") or previous_state.get("relationships")),
    }
    must_accomplish = source.get("must_accomplish")
    first_objective = must_accomplish[0] if isinstance(must_accomplish, list) and must_accomplish else None
    supplied_contract = source.get("chapter_contract") or {}
    chapter_contract = {
        "core_problem": _first_text(supplied_contract.get("core_problem"), source.get("core_problem"), source.get("scene_goal"), source.get("tension_target"), first_objective),
        "observable_payoff": _first_text(supplied_contract.get("observable_payoff"), source.get("observable_payoff"), payoff.get("visible_result")),
        "cost": _first_text(supplied_contract.get("cost"), source.get("cost"), payoff.get("cost")),
        "next_inevitable_event": _first_text(supplied_contract.get("next_inevitable_event"), source.get("next_inevitable_event"), payoff.get("next_pressure"), source.get("hook")),
    }
    ledger = _normalise_ledger(
        scene_plan.get("causal_ledger") or plot_brief.get("causal_ledger"),
        scene_plan.get("beats") or plot_brief.get("suggested_beats"),
    )
    if chapter_text:
        status = "drafted"
    else:
        status = "causal_ready" if not _missing_contract_fields(chapter_contract, ledger) else "input_pending"
    if review:
        causal_passed = review.get("causal_passed")
        style_passed = review.get("style_passed")
        if causal_passed is False:
            status = "blocked"
        elif style_passed is True:
            status = "style_passed"
        elif causal_passed is True:
            status = "causal_passed"
    external = dict(_default_external_evaluation())
    if isinstance(external_evaluation, dict):
        external.update(external_evaluation)
    workflow = {
        "schema_version": WRITING_WORKFLOW_SCHEMA_VERSION,
        "methodology_version": WRITING_METHODOLOGY_VERSION,
        "chapter_number": int(chapter_number),
        "status": status,
        "chapter_contract": chapter_contract,
        "causal_ledger": ledger,
        "current_state": current_state,
        "state_delta": source.get("state_delta") or {},
        "open_threads": _list(source.get("open_threads") or previous.get("open_threads")),
        "forbidden_changes": _list(context_layers.get("constraints")),
        "review": {
            "causal_passed": review.get("causal_passed"),
            "style_passed": review.get("style_passed"),
            "review_score": review.get("review_score"),
        },
        "external_evaluation": external,
        "provenance": {
            "source": "v7.plot_scene_review",
            "chapter_text_hash": text_sha256(chapter_text) if chapter_text is not None else None,
        },
    }
    validation = validate_writing_workflow(workflow)
    workflow["validation"] = validation
    return workflow


def render_writing_methodology_contract(workflow: dict[str, Any] | None) -> str:
    """Render the compact, provider-facing contract."""
    workflow = workflow if isinstance(workflow, dict) else {}
    contract = workflow.get("chapter_contract") or {}
    ledger = workflow.get("causal_ledger") or []
    ledger_lines = []
    for row in ledger[:8]:
        ledger_lines.append(
            f"- 事件：{row.get('event') or 'unknown'}；知情：{row.get('knower') or 'unknown'}；"
            f"现在发生因为：{row.get('motive') or 'unknown'}；代价：{row.get('cost') or 'unknown'}；"
            f"下一影响：{row.get('next_effect') or 'unknown'}"
        )
    if not ledger_lines:
        ledger_lines.append("- （缺失：生成前必须先补齐五列因果账本）")
    state = workflow.get("current_state") or {}
    known_facts = state.get("knowledge") or []
    known_facts_text = "；".join(_text(item) for item in known_facts[:12]) if known_facts else "暂无已确认的知情事实"
    return (
        f"【通用写作方法论 v{WRITING_METHODOLOGY_VERSION}｜工作流 {workflow.get('status') or 'input_pending'}】\n"
        "生成必须遵守：事件先于解释；人物只使用已知信息；物件、时间、地点和资源不能无因跳变。\n"
        "本章契约：\n"
        f"- 核心问题：{contract.get('core_problem') or 'unknown'}\n"
        f"- 可见兑现：{contract.get('observable_payoff') or 'unknown'}\n"
        f"- 代价/余波：{contract.get('cost') or 'unknown'}\n"
        f"- 下一必然压力：{contract.get('next_inevitable_event') or 'unknown'}\n"
        "五列因果账本（事件 / 谁知道 / 为什么现在 / 代价 / 下一影响）：\n"
        + "\n".join(ledger_lines)
        + "\n当前状态锚点："
        + json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        + "\n知情边界："
        + known_facts_text
        + "\n未知信息禁止被人物直接当成已知；新事实必须先通过本章可见事件、对白或证据让具体人物获得。"
        + "因果账本的‘谁知道’必须写具体人物/群体和获得信息的时点，不得用‘大家都知道’覆盖未建立的知情关系。"
        + "\n写完后必须能指出：状态改变了什么、改变由哪一个可见事件触发、主角付出了什么。"
        "不强行套短句比例、感官比例、段落比例或固定反转；不靠错别字和批量删‘的/了’制造人工感。"
    )


def register_external_evaluation(
    chapter_text: str,
    payload: dict[str, Any],
    *,
    score_threshold: float = EXTERNAL_SCORE_THRESHOLD,
) -> dict[str, Any]:
    """Validate and register an actual external report; never fabricate scores."""
    payload = payload if isinstance(payload, dict) else {}
    expected_hash = text_sha256(chapter_text)
    supplied_hash = _text(payload.get("input_hash"))
    if supplied_hash != expected_hash:
        raise ValueError("external evaluation input_hash does not match current chapter text")
    provider = _text(payload.get("provider"))
    scope = _text(payload.get("scope"))
    status = _text(payload.get("status")) or "completed"
    if not provider or not scope:
        raise ValueError("external evaluation requires provider and scope")
    scores = payload.get("scores") if isinstance(payload.get("scores"), dict) else {}
    if payload.get("human_score") is not None:
        scores = {**scores, "human_score": payload.get("human_score")}
    if payload.get("suspected_ai_score") is not None:
        scores = {**scores, "suspected_ai_score": payload.get("suspected_ai_score")}
    human_score = scores.get("human_score")
    if human_score is not None:
        try:
            human_score = float(human_score)
        except (TypeError, ValueError) as exc:
            raise ValueError("human_score must be numeric") from exc
        if human_score < 0 or human_score > 100:
            raise ValueError("human_score must be between 0 and 100")
        scores["human_score"] = human_score
    final_status = "completed" if status in {"completed", "complete", "done"} else status
    if final_status == "completed" and human_score is None:
        raise ValueError("completed external evaluation requires human_score")
    return {
        "schema_version": EXTERNAL_EVALUATION_SCHEMA_VERSION,
        "status": "external_90_plus" if human_score is not None and human_score >= score_threshold else final_status,
        "provider": provider,
        "input_hash": expected_hash,
        "scope": scope,
        "scores": scores,
        "flagged_segments": _list(payload.get("flagged_segments"), limit=30),
        "threshold": score_threshold,
    }
