from app.v7.integration.v6_bridge import build_transition_contract
from app.v7.quality.audit_dimensions import AUDIT_DIMENSIONS, normalize_audit_report
from app.v7.quality.continuity import validate_transition_contract
from app.v7.quality.deai_metrics import analyze_deai_patterns
from app.v7.quality.rule_learning import RuleLearningStore, _fingerprint, validate_rule_payload
from app.v7.integration.quality import evaluate_review


def test_internal_audit_contract_has_exactly_33_items_and_explicit_risks():
    assert len(AUDIT_DIMENSIONS) == 33
    keys = {item.key for item in AUDIT_DIMENSIONS}
    assert {"logic_exposition", "punctuation_anomaly", "ai_pattern_risk"} <= keys
    assert any(item.key == "causality" and item.hard_gate for item in AUDIT_DIMENSIONS)


def test_old_macro_review_is_transparently_projected_not_claimed_as_full_audit():
    report = normalize_audit_report(
        None,
        macro_scores={
            "consistency": 90,
            "character_voice": 88,
            "pacing": 86,
            "plot_logic": 91,
            "writing_quality": 87,
            "constraint_compliance": 95,
        },
        reader_experience={"expectation": 84, "payoff": 80, "emotion_shift": 82, "worth_continuing": 86},
    )

    assert report["count"] == 33
    assert report["complete"] is False
    assert report["source"] == "macro_projection"
    assert report["items"]["logic_exposition"]["status"] == "projected"


def test_transition_contract_requires_previous_chapter_for_non_first_chapter():
    contract = build_transition_contract(
        chapter_number=2,
        title="第二章",
        text="门内传来三下敲击。",
        summary="主角确认门后有人。",
        word_count=10,
        review_score=90,
        dimension_scores={"consistency": 90},
        previous_context={},
        memory_items=[{"category": "plot_events", "key": "door", "summary": "门后有人"}],
    )
    result = validate_transition_contract(contract, chapter_number=2, previous_contract={})
    assert result["passed"] is False
    assert any(item["code"] == "previous_contract_missing" for item in result["issues"])


def test_transition_contract_passes_with_structured_state_delta():
    previous = build_transition_contract(
        chapter_number=1,
        title="第一章",
        text="他按住门把手。",
        summary="门后出现异常声音。",
        word_count=8,
        review_score=90,
        dimension_scores={"consistency": 90},
        memory_items=[{"category": "foreshadowing", "key": "door", "summary": "门后有人"}],
    )
    current = build_transition_contract(
        chapter_number=2,
        title="第二章",
        text="门内传来三下敲击。",
        summary="主角确认门后有人。",
        word_count=10,
        review_score=90,
        dimension_scores={"consistency": 90},
        previous_context={"previous_transition_contract": previous},
        memory_items=[{"category": "plot_events", "key": "door", "summary": "门后回应"}],
    )
    result = validate_transition_contract(
        current,
        chapter_number=2,
        previous_contract=previous,
    )
    assert result["passed"] is True
    assert current["state_delta"]["causal_events"][0]["key"] == "door"


def test_transition_contract_persists_state_conflicts_for_runtime_gate():
    conflicts = [{"key": "location", "description": "地点冲突", "severity": "high"}]
    contract = build_transition_contract(
        chapter_number=1,
        title="第一章",
        text="他停在门口。",
        summary="主角发现异常。",
        word_count=6,
        review_score=80,
        dimension_scores={},
        state_conflicts=conflicts,
    )

    assert contract["state_conflicts"] == conflicts


def test_deai_metrics_flag_abnormal_dash_density_without_banning_punctuation():
    natural = "他停了一下——不是犹豫，只是在听门后的动静。门里没有声音。"
    noisy = "".join(f"他说——然后又想了想——接着解释——事情还没结束——。" for _ in range(8))

    natural_report = analyze_deai_patterns(natural)
    noisy_report = analyze_deai_patterns(noisy)

    assert natural_report["dash_count"] > 0
    assert noisy_report["dash_density_per_1000"] > natural_report["dash_density_per_1000"]
    assert any(flag["code"] == "dash_density" for flag in noisy_report["flags"])


def test_deai_metrics_does_not_treat_generic_single_pronoun_as_template():
    varied = "\n\n".join(
        [
            "他抬头看了一眼门牌，随后把钥匙收回口袋。",
            "他转身走到窗边，先确认楼下没有人。",
            "他把报纸折好，压在桌角的旧账本下面。",
            "他停在楼梯口，听见水管里传来一声闷响。",
            "他低头检查鞋底，发现沾着一小片红泥。",
            "他推开半掩的门，屋里只剩一盏应急灯。",
            "他拿出手机记下门牌，没有立刻拨电话。",
            "他回到街口，才发现林岚一直站在雨棚下。",
            "他问了一句，陈姨却把视线移向别处。",
            "他没有追问，先把工具箱重新扣好。",
            "他看着那张图，终于认出被划掉的线。",
            "他走出巷子，身后的铁门又响了一次。",
        ]
    )

    report = analyze_deai_patterns(varied)

    assert report["repeated_paragraph_opening"]["opening"] != "他"
    assert not any(flag["code"] == "repeated_paragraph_opening" for flag in report["flags"])


def test_deai_metrics_flags_repeated_two_character_opening():
    repeated = "\n\n".join(
        ["顾沉低头看了一眼门缝，手指没有离开锁扣。" for _ in range(8)]
        + [
            "林岚把灯光压低，示意他先别出声。",
            "陈姨站在门外，迟迟没有敲门。",
            "赵启明收起文件，转身走向电梯。",
            "雨水沿着窗框往下淌，屋里没人说话。",
        ]
    )

    report = analyze_deai_patterns(repeated)

    assert report["repeated_paragraph_opening"]["opening"] == "顾沉"
    assert any(flag["code"] == "repeated_paragraph_opening" for flag in report["flags"])


class _LearningState:
    def __init__(self):
        self.values = {}
        self.version = 0

    async def get_state(self, state_type, state_key):
        value = self.values.get((state_type, state_key))
        return dict(value) if value else None

    async def update_state(self, state_type, state_key, value, confidence, **_kwargs):
        self.version += 1
        self.values[(state_type, state_key)] = {
            "value": dict(value),
            "confidence": confidence,
            "version": self.version,
        }
        return {"action": "updated", "state": self.values[(state_type, state_key)], "confidence": confidence}

    async def list_states(self, state_type, *, skip=0, limit=100):
        return [
            {"key": key[1], "value": item["value"], "version": item["version"]}
            for key, item in self.values.items()
            if key[0] == state_type
        ][:limit]


def _deai_pair(before=80, after=40):
    return {
        "before": {"risk_score": before, "flags": [{"code": "dash_density", "message": "破折号偏密"}]},
        "after": {"risk_score": after, "flags": [{"code": "dash_density", "message": "破折号偏密"}]},
    }


def test_rule_learning_uses_before_after_metrics_and_enters_canary_then_active():
    import asyncio

    state = _LearningState()
    store = RuleLearningStore(state)

    async def run():
        for chapter in range(1, 4):
            result = await store.observe(
                chapter_number=chapter,
                accepted=True,
                deai_metrics=_deai_pair(),
            )
        assert result[0]["status"] == "canary"
        for chapter in range(4, 7):
            result = await store.observe(
                chapter_number=chapter,
                accepted=True,
                deai_metrics=_deai_pair(60, 20),
            )
        assert result[0]["status"] == "active"
        active = await store.active_instructions(chapter_number=7)
        assert active[0]["rollout_percent"] == 100

    asyncio.run(run())


def test_rule_learning_rollback_is_validated_and_never_auto_reactivates():
    import asyncio

    state = _LearningState()
    store = RuleLearningStore(state)

    async def run():
        for chapter in range(1, 4):
            await store.observe(chapter_number=chapter, accepted=True, deai_metrics=_deai_pair())
        key = _fingerprint("dash_density")
        await store.rollback(key, reason="人工确认该规则误伤角色对白")
        await store.observe(chapter_number=4, accepted=True, deai_metrics=_deai_pair())
        assert not await store.active_instructions(chapter_number=4)
        assert (await store.list_rules())[0]["status"] == "rolled_back"

    asyncio.run(run())


def test_rule_payload_rejects_invalid_rollout_and_status():
    base = {"code": "dash_density", "instruction": "定向修复", "status": "candidate", "rollout_percent": 0}
    assert validate_rule_payload(base)["schema_version"] == "rule-learning-v2"
    import pytest

    with pytest.raises(ValueError):
        validate_rule_payload({**base, "status": "unknown"})
    with pytest.raises(ValueError):
        validate_rule_payload({**base, "rollout_percent": 101})


def test_quality_gate_keeps_overall_score_when_audit_items_are_present():
    result = evaluate_review({
        "overall_score": 91,
        "dimension_scores": {
            "consistency": 90,
            "character_voice": 90,
            "plot_logic": 90,
            "pacing": 90,
            "writing_quality": 90,
            "constraint_compliance": 90,
        },
        "audit_report": {
            "items": {"causality": {"score": 86, "evidence": "因果成立"}},
        },
    })
    assert result["score"] == 91
