"""Versioned, low-risk automatic rule learning for the V7 chain.

Rules live in the existing ``v7_story_states`` store.  The state version and
change log provide auditability without creating a second rule database.
Learning is deliberately conservative: a rule needs repeated evidence, then
passes a deterministic canary rollout, before it can affect every chapter.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Any

from ..brain.state_manager import StoryStateManager


RULE_SCHEMA_VERSION = "rule-learning-v2"
LOW_RISK_CODES = {
    "dash_density", "ellipsis_density", "uniform_cadence", "ai_phrase", "repeated_phrase",
    "repeated_tic",
}
RULE_STATUSES = {"candidate", "canary", "active", "rolled_back"}
CANARY_ROLLOUT_PERCENT = 25
QUALITY_LEARNING_SCHEMA_VERSION = "quality-learning-v1"


def _fingerprint(code: str, scope: str = "novel") -> str:
    return "rule:" + hashlib.sha256(f"{scope}:{code}".encode("utf-8")).hexdigest()[:24]


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def validate_rule_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a persisted rule before it reaches the prompt."""
    if not isinstance(value, dict):
        raise ValueError("rule payload must be an object")
    code = str(value.get("code") or "").strip()
    status = str(value.get("status") or "candidate")
    if not code:
        raise ValueError("rule code is required")
    if status not in RULE_STATUSES:
        raise ValueError(f"unsupported rule status: {status}")
    instruction = str(value.get("instruction") or "").strip()
    if not instruction:
        raise ValueError("rule instruction is required")
    rollout = int(value.get("rollout_percent") or 0)
    if not 0 <= rollout <= 100:
        raise ValueError("rule rollout_percent must be between 0 and 100")
    return {
        **value,
        "schema_version": str(value.get("schema_version") or RULE_SCHEMA_VERSION),
        "code": code,
        "status": status,
        "instruction": instruction[:500],
        "risk": str(value.get("risk") or "high"),
        "rollout_percent": rollout,
    }


def _metrics_pair(metrics: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    metrics = metrics or {}
    before = metrics.get("before") if isinstance(metrics.get("before"), dict) else metrics
    after = metrics.get("after") if isinstance(metrics.get("after"), dict) else metrics
    return dict(before or {}), dict(after or {})


class RuleLearningStore:
    """Observe quality evidence and safely promote stable low-risk rules."""

    def __init__(self, state: StoryStateManager):
        self.state = state

    async def observe(
        self,
        *,
        chapter_number: int,
        accepted: bool,
        deai_metrics: dict[str, Any] | None = None,
        issues: list[dict[str, Any]] | None = None,
        source_run_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        before_metrics, after_metrics = _metrics_pair(deai_metrics)
        before_flags = (before_metrics.get("flags") or []) if isinstance(before_metrics, dict) else []
        after_flags = (after_metrics.get("flags") or []) if isinstance(after_metrics, dict) else []
        # Keep the signal even when the repair succeeds and the after-scan no
        # longer reports the flag.  Otherwise the very rule that worked would
        # never accumulate enough evidence to graduate.
        flags = [*before_flags, *after_flags]
        observations: dict[str, dict[str, Any]] = {}
        for flag in flags:
            if isinstance(flag, dict) and flag.get("code"):
                code = str(flag["code"])
                observations[code] = {
                    "code": code,
                    "instruction": str(flag.get("message") or "对该模式做定向修复"),
                    "risk": "low" if code in LOW_RISK_CODES else "high",
                }
        for item in issues or []:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or item.get("dimension") or "").strip()
            if code in {"ai_pattern_risk", "punctuation_anomaly", "sentence_rhythm"}:
                observations.setdefault(
                    code,
                    {
                        "code": code,
                        "instruction": str(item.get("suggestion") or item.get("description") or "定向修复该风格风险"),
                        "risk": "low" if code in LOW_RISK_CODES else "high",
                    },
                )

        before_risk = _number(before_metrics.get("risk_score"))
        after_risk = _number(after_metrics.get("risk_score"))
        improved = (
            (before_risk is not None and after_risk is not None and after_risk < before_risk)
            or (before_risk is None and accepted)
        )

        results: list[dict[str, Any]] = []
        for observation in observations.values():
            key = _fingerprint(observation["code"])
            existing = await self.state.get_state("learning_rule", key)
            previous = dict((existing or {}).get("value") or {})
            previous_status = str(previous.get("status") or "candidate")
            evidence_count = int(previous.get("evidence_count") or 0) + 1
            accepted_count = int(previous.get("accepted_count") or 0) + (1 if accepted else 0)
            rejected_count = int(previous.get("rejected_count") or 0) + (0 if accepted else 1)
            improved_count = int(previous.get("improved_count") or 0) + (1 if improved else 0)
            canary_count = int(previous.get("canary_count") or 0)
            canary_success_count = int(previous.get("canary_success_count") or 0)
            if previous_status == "canary":
                canary_count += 1
                if accepted and improved:
                    canary_success_count += 1

            status = previous_status if previous_status in RULE_STATUSES else "candidate"
            rollout_percent = int(previous.get("rollout_percent") or 0)
            if status == "rolled_back":
                # A rollback is an explicit human veto.  New evidence may be
                # recorded but cannot silently reactivate the rule.
                rollout_percent = 0
            elif observation["risk"] == "low" and evidence_count >= 3 and improved_count >= 2:
                if status == "candidate":
                    status = "canary"
                    rollout_percent = CANARY_ROLLOUT_PERCENT
                elif status == "canary" and canary_count >= 3 and canary_success_count >= 2:
                    status = "active"
                    rollout_percent = 100
            elif status not in {"active", "canary", "rolled_back"}:
                status = "candidate"

            instruction = observation["instruction"] or str(previous.get("instruction") or "定向修复该模式")
            rule_version = int(previous.get("rule_version") or 0)
            if instruction != previous.get("instruction"):
                rule_version += 1
            value = validate_rule_payload({
                "schema_version": RULE_SCHEMA_VERSION,
                "rule_key": key,
                "rule_version": rule_version or 1,
                "code": observation["code"],
                "instruction": instruction,
                "risk": observation["risk"],
                "status": status,
                "rollout_percent": rollout_percent,
                "evidence_count": evidence_count,
                "accepted_count": accepted_count,
                "rejected_count": rejected_count,
                "improved_count": improved_count,
                "canary_count": canary_count,
                "canary_success_count": canary_success_count,
                "last_risk_before": before_risk,
                "last_risk_after": after_risk,
                "last_observed_chapter": chapter_number,
                "activation_policy": (
                    "manual_reenable_after_rollback" if status == "rolled_back"
                    else "canary_after_3_observations_then_full_after_3_canary"
                    if observation["risk"] == "low" else "human_review_required"
                ),
            })
            updated = await self.state.update_state(
                "learning_rule",
                key,
                value,
                0.92 if status in {"active", "canary"} else 0.75,
                source="rule_learning",
                source_run_id=source_run_id,
                reason=f"observe chapter {chapter_number}: {status}",
            )
            results.append({"key": key, "status": status, "action": updated["action"], **value})
        return results

    async def list_rules(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        rules = await self.state.list_states("learning_rule", limit=limit)
        result = []
        for item in rules:
            value = item.get("value") if isinstance(item.get("value"), dict) else {}
            if status and value.get("status") != status:
                continue
            try:
                result.append(validate_rule_payload({**value, "state_key": item.get("key"), "state_version": item.get("version")}))
            except ValueError:
                # Do not inject malformed historical state into a generation
                # prompt; surface it to the operator as a validation warning.
                result.append({"state_key": item.get("key"), "status": "invalid", "validation_error": "规则状态不符合当前契约"})
        return result

    @staticmethod
    def _rollout_enabled(rule: dict[str, Any], chapter_number: int | None) -> bool:
        percent = int(rule.get("rollout_percent") or 0)
        if percent >= 100:
            return True
        if percent <= 0:
            return False
        seed = f"{rule.get('rule_key', '')}:{chapter_number if chapter_number is not None else 'default'}"
        bucket = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % 100
        return bucket < percent

    async def active_instructions(self, limit: int = 20, *, chapter_number: int | None = None) -> list[dict[str, Any]]:
        rules = await self.list_rules(limit=limit)
        return [
            item for item in rules
            if item.get("status") in {"active", "canary"}
            and self._rollout_enabled(item, chapter_number)
        ]

    async def rollback(self, rule_key: str, *, reason: str, source_run_id: uuid.UUID | None = None) -> dict[str, Any]:
        reason = str(reason or "").strip()
        if not reason:
            raise ValueError("rollback reason is required")
        existing = await self.state.get_state("learning_rule", rule_key)
        if not existing:
            raise KeyError(f"learning rule not found: {rule_key}")
        value = dict(existing.get("value") or {})
        value["status"] = "rolled_back"
        value["rollout_percent"] = 0
        value["rollback_reason"] = reason
        value["rollback_count"] = int(value.get("rollback_count") or 0) + 1
        value["activation_policy"] = "manual_reenable_after_rollback"
        value = validate_rule_payload(value)
        return await self.state.update_state(
            "learning_rule",
            rule_key,
            value,
            0.95,
            source="human",
            source_run_id=source_run_id,
            reason=reason,
        )


class QualityPatternLearningStore:
    """Learn reader-facing payoff signals without silently rewriting policy.

    A single chapter can record a sample, but it cannot change the global
    generation contract.  Only repeated positive/negative observations become
    an active, low-risk prompt hint.  The hint is deliberately about keeping
    the result visible and varying feedback; it never copies prose or a living
    author's wording into the generator.
    """

    def __init__(self, state: StoryStateManager):
        self.state = state

    @staticmethod
    def _key(payoff_type: str) -> str:
        digest = hashlib.sha256(f"payoff:{payoff_type}".encode("utf-8")).hexdigest()[:24]
        return f"quality:{digest}"

    @staticmethod
    def _rollout_enabled(value: dict[str, Any], chapter_number: int | None) -> bool:
        rollout = int(value.get("rollout_percent") or 0)
        if rollout >= 100:
            return True
        if rollout <= 0:
            return False
        seed = f"{value.get('quality_key', '')}:{chapter_number or 'default'}"
        bucket = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % 100
        return bucket < rollout

    async def observe_sample(
        self,
        *,
        chapter_number: int,
        accepted: bool,
        payoff_type: str | None,
        payoff_score: float | None,
        review_score: float | None,
        reader_payoff: float | None,
        continuity_passed: bool,
        source_run_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        payoff_type = str(payoff_type or "").strip()
        if not payoff_type:
            return []

        numeric = [
            value for value in (payoff_score, review_score, reader_payoff)
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        quality_score = round(sum(float(value) for value in numeric) / len(numeric), 1) if numeric else 0.0
        positive = bool(
            accepted
            and continuity_passed
            and quality_score >= 80
            and (reader_payoff is None or float(reader_payoff) >= 70)
        )
        key = self._key(payoff_type)
        existing = await self.state.get_state("learning_quality", key)
        previous = dict((existing or {}).get("value") or {})
        samples = int(previous.get("sample_count") or 0) + 1
        positive_count = int(previous.get("positive_count") or 0) + (1 if positive else 0)
        negative_count = int(previous.get("negative_count") or 0) + (0 if positive else 1)
        old_average = float(previous.get("average_score") or 0.0)
        average_score = round(((old_average * (samples - 1)) + quality_score) / samples, 1)
        positive_rate = round(positive_count / samples, 3)
        status = str(previous.get("status") or "candidate")
        if status not in {"candidate", "canary", "active", "rolled_back"}:
            status = "candidate"
        if status != "rolled_back":
            if samples >= 5 and positive_count >= 3:
                status = "active"
                rollout_percent = 100
            elif samples >= 3:
                status = "canary"
                rollout_percent = CANARY_ROLLOUT_PERCENT
            else:
                rollout_percent = 0
        else:
            rollout_percent = 0

        if positive_rate >= 0.6:
            instruction = (
                f"爽点类型 {payoff_type} 已有多章正向验证：先写清主角行动造成的结果，"
                "再用资源、关系、规则或对手反应呈现反馈，避免只用旁白宣布情绪。"
            )
        else:
            instruction = (
                f"爽点类型 {payoff_type} 的近期兑现偏弱：生成时必须补足依据、可见结果、"
                "外部反馈和下一压力，不得只重复上一章的表达。"
            )
        value = {
            "schema_version": QUALITY_LEARNING_SCHEMA_VERSION,
            "quality_key": key,
            "payoff_type": payoff_type,
            "status": status,
            "rollout_percent": rollout_percent,
            "sample_count": samples,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "positive_rate": positive_rate,
            "average_score": average_score,
            "last_quality_score": quality_score,
            "last_reader_payoff": reader_payoff,
            "last_continuity_passed": bool(continuity_passed),
            "last_observed_chapter": chapter_number,
            "instruction": instruction[:500],
            "activation_policy": "5_samples_3_positive_then_active",
        }
        updated = await self.state.update_state(
            "learning_quality",
            key,
            value,
            0.9 if status in {"canary", "active"} else 0.7,
            source="quality_learning",
            source_run_id=source_run_id,
            reason=f"chapter {chapter_number}: {'positive' if positive else 'negative'} payoff sample",
        )
        return [{"key": key, "action": updated.get("action"), **value}]

    async def active_recommendations(
        self,
        *,
        chapter_number: int | None = None,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        states = await self.state.list_states("learning_quality", limit=max(limit * 4, 20))
        recommendations: list[dict[str, Any]] = []
        for state in states:
            value = state.get("value") if isinstance(state.get("value"), dict) else {}
            if value.get("status") not in {"canary", "active"}:
                continue
            if not self._rollout_enabled(value, chapter_number):
                continue
            recommendations.append({
                "quality_key": value.get("quality_key") or state.get("key"),
                "payoff_type": value.get("payoff_type"),
                "status": value.get("status"),
                "sample_count": value.get("sample_count", 0),
                "positive_rate": value.get("positive_rate", 0.0),
                "instruction": value.get("instruction"),
            })
        return recommendations[: max(1, limit)]
