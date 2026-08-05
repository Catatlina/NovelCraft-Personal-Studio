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
from .engines.review_engine import ReviewEngine
from .events.event_bus import EventBus
from .quality.continuity import validate_transition_contract
from .runtime import _load_quality_profile, seed_v6_context
from .trace.tracer import ExecutionTracer


CANONICAL_REVIEW_ENGINE = "v7"
CANONICAL_REVIEW_PROMPT = "v7.review.33_dimension"
CANONICAL_REVIEW_PROMPT_VERSION = "1.1.0"


def text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _meta(value: Any) -> dict[str, Any]:
    result = decode(value, {}) if not isinstance(value, dict) else value
    return result if isinstance(result, dict) else {}


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

    contract = current_meta.get("transition_contract")
    deterministic: dict[str, Any]
    if isinstance(contract, dict) and contract:
        last_tail = str((contract.get("end_state") or {}).get("last_tail") or "").strip()
        contract_matches_text = bool(last_tail and chapter_text.rstrip().endswith(last_tail))
        if contract_matches_text:
            deterministic = validate_transition_contract(
                contract,
                chapter_number=int(context.get("chapter_number") or 1),
                previous_contract=context.get("previous_transition_contract") or {},
                state_conflicts=(contract.get("state_conflicts") or []),
            )
        else:
            deterministic = {
                "schema_version": "continuity-v1",
                "status": "not_checked",
                "checked": False,
                "reason": "当前正文尚未保存与之匹配的 V7 转场契约",
            }
    else:
        deterministic = {
            "schema_version": "continuity-v1",
            "status": "not_checked",
            "checked": False,
            "reason": "当前草稿没有可验证的 V7 转场契约",
        }

    deterministic_passed = deterministic.get("passed") is True
    if deterministic.get("checked") is False:
        status = "continuous" if model_score is not None and model_score >= 85 else "warning"
    elif deterministic_passed and (model_score is None or model_score >= 85):
        status = "continuous"
    elif deterministic.get("blocking_count", 0) > 0 or (model_score is not None and model_score < 60):
        status = "broken"
    else:
        status = "warning"

    return {
        "status": status,
        "checked": True,
        "source": CANONICAL_REVIEW_PROMPT,
        "model_score": model_score,
        "narrative_flow": "；".join(evidence) or "V7 审阅器已完成跨章因果、时间线和章末桥接检查。",
        "gaps": gaps,
        "deterministic_contract": deterministic,
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
        "scored_at": datetime.now(timezone.utc).isoformat(),
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
    if provenance.get("text_hash") != text_hash(chapter_text):
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
