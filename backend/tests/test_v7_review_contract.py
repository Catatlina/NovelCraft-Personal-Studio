from __future__ import annotations


def _review_fixture() -> dict:
    items = {}
    for key in (
        "chapter_goal",
        "causality",
        "plot_progress",
        "timeline",
        "space_location",
        "foreshadowing_state",
        "ending_hook",
    ):
        items[key] = {"key": key, "score": 90, "evidence": f"{key} evidence", "repair": ""}
    return {
        "overall_score": 90.0,
        "dimension_scores": {"consistency": 90},
        "audit_report": {"items": items},
        "issues": [],
        "provenance": {"provider": "deepseek", "model": "route-model"},
    }


def test_v7_review_candidates_resolve_to_the_existing_review_route():
    from app.v7.generation.generation_engine import AIGateway

    assert "review_7dim" in AIGateway._route_candidates("v7.review.33_dimension")
    assert "gen_next_chapter" in AIGateway._route_candidates("v7.generation.chapter")


def test_cached_v7_review_keeps_the_same_score_and_provenance():
    from app.v7.review_service import _cached_review, text_hash

    text = "沈夜推开旧门，门后的风立刻停了。"
    review = _review_fixture()
    review["provenance"] = {
        "provider": "deepseek",
        "model": "route-model",
        "text_hash": text_hash(text),
    }
    cached = _cached_review(
        context={"chapter_number": 2},
        current_meta={
            "canonical_review": review,
            "review_provenance": review["provenance"],
            "transition_contract": {},
        },
        chapter_text=text,
    )

    assert cached is not None
    assert cached["overall_score"] == 90.0
    assert cached["score"] == 90.0
    assert cached["canonical_engine"] == "v7"
    assert cached["provenance"]["model"] == "route-model"
    assert cached["provenance"]["cache_hit"] is True
    assert cached["continuity"]["model_score"] == 90.0


def test_cached_v7_review_rejects_a_different_text_hash():
    from app.v7.review_service import _cached_review, text_hash

    review = _review_fixture()
    review["provenance"] = {"text_hash": text_hash("原正文")}
    assert _cached_review(
        context={"chapter_number": 1},
        current_meta={
            "canonical_review": review,
            "review_provenance": review["provenance"],
        },
        chapter_text="改过的正文",
    ) is None


def test_review_provenance_rejects_an_old_prompt_version_for_same_text():
    from app.v7.review_service import _review_provenance_matches, text_hash

    text = "同一段正文"
    assert _review_provenance_matches(
        {"text_hash": text_hash(text), "prompt_version": "1.2.0"}, text
    ) is True
    assert _review_provenance_matches(
        {"text_hash": text_hash(text), "prompt_version": "1.1.0"}, text
    ) is False


def test_review_issue_normalization_requires_source_evidence_and_bounds_character_advice():
    from app.v7.engines.review_engine import normalize_review_issues

    issues, suppressed = normalize_review_issues(
        [
            {
                "dimension": "character_voice",
                "description": "对白略显平淡，建议增加口头禅",
                "suggestion": "为角色增加口头禅",
                "excerpt": "你干什么",
            },
            {
                "dimension": "writing_quality",
                "description": "建议整体更生动",
                "suggestion": "增加细节",
            },
        ],
        "他抬头问：“你干什么？”",
    )

    assert len(issues) == 1
    assert issues[0]["evidence_status"] == "verified"
    assert "不要新增口头禅" in issues[0]["suggestion"]
    assert len(suppressed) == 1
    assert suppressed[0]["evidence_status"] == "unverified"
