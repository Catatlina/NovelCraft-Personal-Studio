from __future__ import annotations


def test_novel_reviewer_lexicon_is_advisory_and_has_bounded_evidence():
    from app.v7.quality.deai_metrics import analyze_deai_patterns

    text = "\n\n".join(
        [
            "他嘴角微扬，目光落在门缝里。",
            "她眼中闪过一丝迟疑，手却没有停。",
            "对方心中一震，终于退开半步。",
        ]
    )
    metrics = analyze_deai_patterns(text)
    lexicon = metrics["novel_reviewer_lexicon"]

    assert lexicon["mode"] == "grayscale_observation"
    assert lexicon["hard_gate"] is False
    assert lexicon["reference"]["scoring_authority"] == "v7.review.33_dimension"
    evidence = lexicon["categories"]["classic_description"]["evidence"]
    assert evidence
    assert all(item["line"] >= 1 and item["excerpt"] for item in evidence)
    assert lexicon["candidate_risks"] == []


def test_system_and_simulator_terms_are_not_treated_as_ai_flavor_risk():
    from app.v7.quality.novel_reviewer_reference import analyze_novel_reviewer_lexicon

    result = analyze_novel_reviewer_lexicon(
        "系统弹窗亮起，模拟器给出三条未来分支，面板记录了回收的修为。",
        profile={"genre": "玄幻", "subgenre": "系统流", "mechanic": "simulator"},
    )

    assert result["system_context"] is True
    assert result["categories"]["system_terms"]["active"] is False
    assert not any(
        item["category"] == "system_terms" for item in result["candidate_risks"]
    )


def test_ai_flavor_lexicon_is_versioned_editable_and_preserves_custom_signals():
    from app.v7.quality.novel_reviewer_reference import (
        AI_FLAVOR_LEXICON_SCHEMA_VERSION,
        default_ai_flavor_lexicon,
        normalize_ai_flavor_lexicon,
        render_ai_flavor_guidance,
    )

    defaults = default_ai_flavor_lexicon()
    assert defaults["schema_version"] == AI_FLAVOR_LEXICON_SCHEMA_VERSION
    assert len(defaults["categories"]) >= 10
    assert defaults["mode"] == "advisory"
    assert defaults["hard_gate"] is False

    custom = normalize_ai_flavor_lexicon({
        "version": 9,
        "mode": "hard_gate",
        "hard_gate": True,
        "categories": [{
            "key": "my_signal",
            "label": "我的观察项",
            "description": "只做编辑提示",
            "phrases": [{"phrase": "机械地说", "enabled": True, "note": "复核语境"}],
        }],
    })

    assert custom["version"] == 9
    assert custom["mode"] == "advisory"
    assert custom["hard_gate"] is False
    custom_category = next(item for item in custom["categories"] if item["key"] == "my_signal")
    assert custom_category["phrases"][0]["phrase"] == "机械地说"
    guidance = render_ai_flavor_guidance({"ai_flavor_lexicon": custom})
    assert "不是禁词表" in guidance
    assert "机械地说" in guidance


def test_editorial_view_maps_existing_v7_evidence_without_a_second_score():
    from app.v7.quality.novel_reviewer_reference import build_editorial_review_view

    audit_keys = (
        "causality",
        "choice_consequence",
        "plot_progress",
        "logic_exposition",
        "world_rules",
        "ability_system",
        "terminology",
        "resource_ledger",
        "timeline",
        "space_location",
        "foreshadowing_state",
        "knowledge_boundary",
        "motivation_consistency",
        "character_arc_progress",
        "behavior_credibility",
        "relationship_change",
        "personality_consistency",
        "capability_consistency",
        "character_voice",
        "sentence_rhythm",
        "stakes",
        "ending_hook",
        "payoff",
        "emotion_shift",
        "continuation_intent",
        "expectation",
    )
    review = {
        "overall_score": 91.0,
        "dimension_scores": {
            "consistency": 92,
            "character_voice": 90,
            "pacing": 88,
            "plot_logic": 91,
            "writing_quality": 89,
        },
        "audit_report": {
            "items": {
                key: {
                    "key": key,
                    "label": key,
                    "score": 90,
                    "evidence": f"{key} 的正文证据",
                    "repair": f"检查 {key} 的局部承接",
                    "source": "llm",
                }
                for key in audit_keys
            }
        },
        "reader_experience": {
            "expectation": 87,
            "conflict": 88,
            "payoff": 92,
            "emotion_shift": 86,
            "worth_continuing": 91,
        },
        "continuity": {"checked": True, "model_score": 89, "status": "continuous"},
        "deai_metrics": {"risk_score": 12, "flags": []},
    }

    view = build_editorial_review_view(review)

    assert len(view["facets"]) == 12
    assert {item["key"] for item in view["facets"]} == {
        "logic",
        "canon",
        "lint",
        "fact",
        "character",
        "consistency",
        "pace",
        "hook_density",
        "retention",
        "bridge",
        "prose",
        "ai_flavor",
    }
    assert not any(key == "overall_score" for key in view)
    assert view["overall_score_source"] == "v7.review.33_dimension"
    assert next(item for item in view["facets"] if item["key"] == "ai_flavor")["score"] == 88.0
    assert next(item for item in view["facets"] if item["key"] == "lint")["score"] == 89.0
