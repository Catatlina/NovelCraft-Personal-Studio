"""Canonical V7 chapter review service.

The editor, live audit endpoint and generation pipeline must not maintain
separate scoring contracts.  This module is the V7 read-only review boundary:
it builds the same story context as generation, runs ``ReviewEngine`` through
the same 7-macro/33-detail contract, and returns a stable payload containing
continuity evidence and provider provenance.
"""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from ..db import connect, decode
from ..services.novel_export import extract_body_text
from ..services.quality_profiles import quality_profile_metadata
from .brain.novel_brain import NovelBrain
from .db import AsyncSessionLocal, async_engine
from .engines.review_engine import REVIEW_PROMPT_VERSION, ReviewEngine
from .events.event_bus import EventBus
from .quality.continuity import validate_prose_continuity, validate_transition_contract
from .quality.novel_reviewer_reference import (
    build_editorial_review_view,
    novel_reviewer_reference_metadata,
)
from .quality.review_evidence import validate_review_evidence
from .runtime import _load_quality_profile, seed_v6_context
from .trace.tracer import ExecutionTracer


CANONICAL_REVIEW_ENGINE = "v7"
CANONICAL_REVIEW_PROMPT = "v7.review.33_dimension"
CANONICAL_REVIEW_PROMPT_VERSION = REVIEW_PROMPT_VERSION


def text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _meta(value: Any) -> dict[str, Any]:
    result = decode(value, {}) if not isinstance(value, dict) else value
    return result if isinstance(result, dict) else {}


def _review_provenance_matches(provenance: Any, chapter_text: str) -> bool:
    """Return whether a stored review is the snapshot for this audit input.

    The text hash is the primary identity.  Prompt fields are checked when
    present so a deliberate audit-contract upgrade invalidates old scores;
    old records without those fields remain readable for compatibility.
    """
    provenance = provenance if isinstance(provenance, dict) else {}
    if provenance.get("text_hash") != text_hash(chapter_text):
        return False
    for key, expected in (
        ("audit_source", CANONICAL_REVIEW_PROMPT),
        ("prompt_name", CANONICAL_REVIEW_PROMPT),
        ("prompt_version", CANONICAL_REVIEW_PROMPT_VERSION),
    ):
        actual = provenance.get(key)
        if actual and str(actual) != expected:
            return False
    return True


def _chapter_number(content: dict[str, Any]) -> int:
    metadata = _meta(content.get("meta"))
    try:
        return int(content.get("seq") or metadata.get("seq") or 1)
    except (TypeError, ValueError):
        return 1


def _chapter_context(content: dict[str, Any], text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build review context from the current and immediately previous V6 row.

    V6 is read here only as the compatibility content boundary.  Story facts
    used by the reviewer are seeded into/read from V7 Novel Brain below.
    """
    novel_id = str(content.get("parent_id") or content.get("id") or "")
    chapter_number = _chapter_number(content)
    current_meta = _meta(content.get("meta"))
    previous_tail = ""
    previous_title = ""
    previous_contract: dict[str, Any] = {}
    chapter_plan: dict[str, Any] = {}
    conn = connect()
    try:
        if novel_id and chapter_number > 1:
            previous = conn.execute(
                """
                SELECT title, body, meta, seq
                FROM contents
                WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE
                  AND COALESCE(seq, (meta->>'seq')::int, 0) < %s
                ORDER BY COALESCE(seq, (meta->>'seq')::int, 0) DESC
                LIMIT 1
                """,
                (novel_id, chapter_number),
            ).fetchone()
            if previous:
                previous_title = str(previous.get("title") or "").strip()
                previous_meta = _meta(previous.get("meta"))
                previous_text = extract_body_text(previous.get("body") or "")
                previous_tail = previous_text[-1200:]
                previous_contract = previous_meta.get("transition_contract") or {}

        novel = conn.execute(
            "SELECT meta FROM contents WHERE id=%s AND type='novel' AND is_deleted=FALSE",
            (novel_id,),
        ).fetchone()
        novel_meta = _meta((novel or {}).get("meta"))
        for item in novel_meta.get("chapter_outlines") or []:
            if isinstance(item, dict) and int(item.get("seq") or 0) == chapter_number:
                chapter_plan = item
                break
    finally:
        conn.close()

    context = {
        "chapter_text": text,
        "chapter_number": chapter_number,
        "chapter_title": str(
            content.get("title")
            or current_meta.get("chapter_title")
            or (current_meta.get("scene_plan") or {}).get("chapter_title")
            or ""
        ).strip(),
        "previous_chapter_title": previous_title,
        "previous_chapter_tail": previous_tail,
        "previous_transition_contract": previous_contract,
        "chapter_plan": chapter_plan or current_meta.get("outline") or {},
        "scene_plan": current_meta.get("scene_plan") or {},
        "deai_metrics": current_meta.get("deai") or {},
        "pov_metrics": current_meta.get("pov_metrics") or {},
        "content_policy": current_meta.get("content_policy") or {},
        "generation_quality": current_meta.get("generation_quality") or {},
        "quality_profile": current_meta.get("quality_profile") or {},
        "payoff_contract": current_meta.get("payoff_contract") or {},
    }
    return context, current_meta


def _continuity_evidence(
    review: dict[str, Any],
    *,
    context: dict[str, Any],
    current_meta: dict[str, Any],
    chapter_text: str,
) -> dict[str, Any]:
    """Combine model narrative-flow evidence with truthful deterministic checks."""
    audit_report = review.get("audit_report") or {}
    items = audit_report.get("items") or {}
    continuity_keys = (
        "causality",
        "plot_progress",
        "timeline",
        "space_location",
        "foreshadowing_state",
        "ending_hook",
    )
    continuity_items = [items[key] for key in continuity_keys if isinstance(items.get(key), dict)]
    scores = [item.get("score") for item in continuity_items if isinstance(item.get("score"), (int, float))]
    model_score = round(sum(scores) / len(scores), 1) if scores else None
    evidence = [str(item.get("evidence") or "").strip() for item in continuity_items]
    evidence = [item for item in evidence if item]
    gaps: list[dict[str, Any]] = []
    for item in continuity_items:
        score = item.get("score")
        if isinstance(score, (int, float)) and score < 85:
            gaps.append({
                "dimension": item.get("key"),
                "description": item.get("evidence") or item.get("repair") or "该连续性细项低于产品目标",
                "suggestion": item.get("repair") or "补足触发、承接、后果和章末桥接证据",
            })

    chapter_number = int(context.get("chapter_number") or 1)
    previous_contract = context.get("previous_transition_contract") or {}
    current_title = str(
        context.get("chapter_title")
        or current_meta.get("chapter_title")
        or (current_meta.get("scene_plan") or {}).get("chapter_title")
        or ""
    ).strip()
    previous_title = str(context.get("previous_chapter_title") or "").strip()
    contract = current_meta.get("transition_contract")
    deterministic: dict[str, Any]
    if isinstance(contract, dict) and contract:
        last_tail = str((contract.get("end_state") or {}).get("last_tail") or "").strip()
        contract_matches_text = bool(last_tail and chapter_text.rstrip().endswith(last_tail))
        if contract_matches_text:
            deterministic = validate_transition_contract(
                contract,
                chapter_number=chapter_number,
                previous_contract=previous_contract,
                state_conflicts=(contract.get("state_conflicts") or []),
            )
        else:
            deterministic = {
                "schema_version": "continuity-v1",
                "status": "not_checked",
                "checked": False,
                "passed": False if chapter_number > 1 else True,
                "reason": "当前正文尚未保存与之匹配的 V7 转场契约",
            }
    else:
        deterministic = {
            "schema_version": "continuity-v1",
            "status": "not_checked" if chapter_number > 1 else "not_applicable",
            "checked": False,
            "passed": False if chapter_number > 1 else True,
            "reason": "当前草稿没有可验证的 V7 转场契约",
        }

    prose = validate_prose_continuity(
        chapter_number=chapter_number,
        current_text=chapter_text,
        current_title=current_title,
        previous_title=previous_title,
        current_contract=contract if isinstance(contract, dict) else {},
        previous_contract=previous_contract,
    )

    deterministic_checked = bool(
        deterministic.get("checked") is True
        or isinstance(deterministic.get("checked"), list)
    )
    model_checked = bool(model_score is not None and evidence)
    deterministic_passed = deterministic.get("passed") is True
    deterministic_required = chapter_number > 1
    prose_passed = prose.get("passed") is True
    if deterministic_required and not deterministic_checked:
        status = "not_checked"
    elif not deterministic_passed or not prose_passed:
        status = "broken"
    elif model_score is not None and model_score < 60:
        status = "broken"
    elif model_score is not None and model_score < 85:
        status = "warning"
    elif deterministic_passed and prose_passed:
        status = "continuous"
    else:
        status = "not_checked"

    checked = deterministic_checked or model_checked or not deterministic_required
    passed = bool(
        prose_passed
        and (deterministic_passed if deterministic_required else True)
        and (model_score is not None and model_score >= 85 if model_checked else not deterministic_required)
    )
    combined_gaps = [*gaps]
    combined_gaps.extend(deterministic.get("issues") or [])
    combined_gaps.extend(prose.get("issues") or [])

    return {
        "status": status,
        "checked": checked,
        "passed": passed,
        "source": CANONICAL_REVIEW_PROMPT,
        "model_score": model_score,
        "narrative_flow": "；".join(evidence) or "V7 审阅器已完成跨章因果、时间线和章末桥接检查。",
        "gaps": combined_gaps,
        "deterministic_contract": deterministic,
        "prose_continuity": prose,
    }


def _provenance(
    review: dict[str, Any],
    *,
    chapter_text: str,
    provider: str,
    model: str | None,
    cache_hit: bool,
    source: str,
) -> dict[str, Any]:
    existing = review.get("provenance") if isinstance(review.get("provenance"), dict) else {}
    return {
        "engine": CANONICAL_REVIEW_ENGINE,
        "audit_source": CANONICAL_REVIEW_PROMPT,
        "prompt_name": CANONICAL_REVIEW_PROMPT,
        "prompt_version": CANONICAL_REVIEW_PROMPT_VERSION,
        "provider": provider,
        "model": model or review.get("model"),
        "text_hash": text_hash(chapter_text),
        "cache_hit": cache_hit,
        "source": source,
        # A cache hit is the same audit snapshot, not a new score. Preserve
        # its original timestamp so the UI does not imply a re-score.
        "scored_at": (
            existing.get("scored_at")
            if cache_hit and existing.get("scored_at")
            else datetime.now(timezone.utc).isoformat()
        ),
    }


def _decorate_review(
    review: dict[str, Any],
    *,
    context: dict[str, Any],
    current_meta: dict[str, Any],
    chapter_text: str,
    provider: str,
    model: str | None,
    cache_hit: bool,
    source: str,
) -> dict[str, Any]:
    result = dict(review)
    # V7's canonical name is ``overall_score``.  Keep ``score`` as a
    # read-only compatibility alias for the editor and older integrations so
    # a valid review never renders as an unscored review.
    if result.get("score") is None and result.get("overall_score") is not None:
        result["score"] = result["overall_score"]
    continuity = _continuity_evidence(
        result,
        context=context,
        current_meta=current_meta,
        chapter_text=chapter_text,
    )
    result.update({
        "canonical_engine": CANONICAL_REVIEW_ENGINE,
        "audit_source": CANONICAL_REVIEW_PROMPT,
        "continuity": continuity,
        "final_continuity_audit": {"continuity": continuity},
        "provenance": _provenance(
            result,
            chapter_text=chapter_text,
            provider=provider,
            model=model,
            cache_hit=cache_hit,
            source=source,
        ),
    })
    result["review_reference"] = novel_reviewer_reference_metadata()
    result["editorial_review"] = build_editorial_review_view(result)
    evidence = validate_review_evidence(result, require_continuity=True)
    result["review_evidence"] = evidence
    if evidence.get("passed") is not True:
        result["review_valid"] = False
        existing = list(result.get("validation_failures") or [])
        existing.append({
            "code": "review_evidence_incomplete",
            "message": "V7 实时审阅证据链不完整：" + "；".join(evidence.get("issues") or []),
            "detail": evidence,
        })
        result["validation_failures"] = existing
    return result


def _cached_review(
    *,
    context: dict[str, Any],
    current_meta: dict[str, Any],
    chapter_text: str,
) -> dict[str, Any] | None:
    review = current_meta.get("canonical_review")
    provenance = current_meta.get("review_provenance")
    if not isinstance(review, dict) or not isinstance(provenance, dict):
        return None
    if not _review_provenance_matches(provenance, chapter_text):
        return None
    return _decorate_review(
        review,
        context=context,
        current_meta=current_meta,
        chapter_text=chapter_text,
        provider=str(provenance.get("provider") or "deepseek"),
        model=provenance.get("model"),
        cache_hit=True,
        source="persisted_v7_review",
    )


def _cached_version_review(
    *,
    content_id: str,
    context: dict[str, Any],
    current_meta: dict[str, Any],
    chapter_text: str,
) -> dict[str, Any] | None:
    """Read the latest matching live-audit snapshot from the version ledger."""
    if not content_id:
        return None
    conn = None
    try:
        conn = connect()
        rows = conn.execute(
            """
            SELECT snapshot
            FROM versions
            WHERE entity_type='content' AND entity_id=%s AND label='ai_review'
            ORDER BY created_at DESC
            LIMIT 32
            """,
            (content_id,),
        ).fetchall()
    except Exception:
        # Cache lookup must never make an otherwise healthy audit unavailable.
        return None
    finally:
        if conn is not None:
            conn.close()

    for row in rows:
        snapshot = _meta(row.get("snapshot"))
        review = snapshot.get("review") if isinstance(snapshot.get("review"), dict) else None
        provenance = review.get("provenance") if isinstance(review, dict) else None
        if not review or not _review_provenance_matches(provenance, chapter_text):
            continue
        return _decorate_review(
            review,
            context=context,
            current_meta=current_meta,
            chapter_text=chapter_text,
            provider=str((provenance or {}).get("provider") or "deepseek"),
            model=(provenance or {}).get("model"),
            cache_hit=True,
            source="persisted_v7_live_review",
        )
    return None


async def review_chapter_v7(
    content: dict[str, Any],
    text: str,
    *,
    api_key: str = "",
    api_url: str = "",
    model: str = "",
    use_cache: bool = True,
) -> dict[str, Any]:
    """Run or retrieve the canonical V7 review for the current chapter text."""
    chapter_text = str(text or "").strip()
    context, current_meta = _chapter_context(content, chapter_text)
    if use_cache:
        cached = _cached_review(
            context=context,
            current_meta=current_meta,
            chapter_text=chapter_text,
        )
        if cached is not None:
            return cached
        cached = _cached_version_review(
            content_id=str(content.get("id") or ""),
            context=context,
            current_meta=current_meta,
            chapter_text=chapter_text,
        )
        if cached is not None:
            return cached

    novel_id = str(content.get("parent_id") or content.get("id") or "")
    project_id = str(content.get("project_id") or "")
    quality_profile = await asyncio.to_thread(_load_quality_profile, novel_id)
    context["quality_profile"] = context.get("quality_profile") or quality_profile_metadata(quality_profile)
    provider_config = {
        key: value
        for key, value in {"api_key": api_key, "base_url": api_url, "model": model}.items()
        if value
    }

    async with AsyncSessionLocal() as db:
        try:
            novel_uuid = uuid.UUID(novel_id)
            brain = NovelBrain(db, novel_uuid)
            await seed_v6_context(brain, novel_id, int(context.get("chapter_number") or 1))
            tracer = ExecutionTracer(db, novel_uuid)
            event_bus = EventBus(db, novel_uuid)
            engine = ReviewEngine(
                db,
                novel_uuid,
                brain,
                tracer,
                event_bus,
                project_id=project_id,
                provider_config=provider_config,
                quality_profile=quality_profile,
            )
            # ``run_read_only`` means “do not update Novel Brain/content”, not
            # “do not trace”.  The phase tracer requires an active run, and a
            # live/editor audit must leave the same auditable execution record
            # as a generation-time review.
            trace_run_id = await tracer.start_run(
                "review",
                trigger="live_audit",
                input_data={
                    "chapter_number": int(context.get("chapter_number") or 1),
                    "text_hash": text_hash(chapter_text),
                    "canonical_engine": CANONICAL_REVIEW_ENGINE,
                },
                chapter_number=int(context.get("chapter_number") or 1),
            )
            try:
                result = await engine.run_read_only(context)
            except Exception as exc:
                await tracer.complete_run(
                    trace_run_id,
                    error_message=str(exc)[:1000],
                    error_type=type(exc).__name__,
                )
                raise
            if not result.success or not isinstance(result.result, dict):
                await tracer.complete_run(
                    trace_run_id,
                    output_data={
                        "canonical_engine": CANONICAL_REVIEW_ENGINE,
                        "review_valid": False,
                        "reason": result.reason or "V7 review did not return a structured result",
                    },
                )
                raise RuntimeError(result.reason or "V7 review did not return a structured result")
            review = _decorate_review(
                result.result,
                context=context,
                current_meta=current_meta,
                chapter_text=chapter_text,
                provider=getattr(engine.ai_gateway, "provider", "unknown"),
                model=(result.result or {}).get("model") or getattr(engine.ai_gateway, "default_model", None),
                cache_hit=False,
                source="live_v7_review",
            )
            await tracer.complete_run(
                trace_run_id,
                output_data={
                    "canonical_engine": CANONICAL_REVIEW_ENGINE,
                    "overall_score": review.get("overall_score"),
                    "review_valid": review.get("review_valid", True),
                    "text_hash": text_hash(chapter_text),
                },
            )
            review["provenance"]["trace_run_id"] = str(trace_run_id)
            await db.commit()
            return review
        except Exception:
            await db.rollback()
            raise


async def _review_worker(*args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return await review_chapter_v7(*args, **kwargs)
    finally:
        await async_engine.dispose()


def review_chapter_v7_sync(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Synchronous bridge for FastAPI/Celery compatibility entrypoints."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_review_worker(*args, **kwargs))
    raise RuntimeError("review_chapter_v7_sync cannot run inside an active event loop")
