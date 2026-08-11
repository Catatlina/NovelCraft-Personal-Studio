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


def test_live_review_cannot_pass_chapter_two_from_model_score_alone():
    from app.v7.review_service import _continuity_evidence

    result = _continuity_evidence(
        _review_fixture(),
        context={
            "chapter_number": 2,
            "previous_transition_contract": {},
            "previous_chapter_title": "门后的声音",
            "chapter_title": "门后的声音·真相",
        },
        current_meta={},
        chapter_text="沈夜推开门，屋里没有人。",
    )

    assert result["status"] == "not_checked"
    assert result["passed"] is False
    assert result["deterministic_contract"]["passed"] is False


def test_live_review_blocks_parallel_title_without_opening_anchor():
    from app.v7.review_service import _continuity_evidence

    previous_contract = {
        "schema_version": "v1",
        "chapter_number": 1,
        "end_state": {
            "title": "江心岛迷雾",
            "last_tail": "船灯在江面上摇晃。",
            "summary": "周衡停在江边。",
        },
        "next_chapter_bridge": "船灯在江面上摇晃。",
        "state_delta": {},
        "open_threads": [],
    }
    current_contract = {
        "schema_version": "v1",
        "chapter_number": 2,
        "start_state": {
            "previous_transition_contract": previous_contract,
            "previous_tail": previous_contract["end_state"]["last_tail"],
        },
        "end_state": {
            "last_tail": "仓库七号的门锁弹开了。",
            "summary": "周衡进入仓库。",
        },
        "next_chapter_bridge": "仓库七号的门锁弹开了。",
        "state_delta": {},
        "open_threads": [],
    }
    result = _continuity_evidence(
        _review_fixture(),
        context={
            "chapter_number": 2,
            "previous_transition_contract": previous_contract,
            "previous_chapter_title": "江心岛迷雾",
            "chapter_title": "江心岛迷雾·周衡发现仓库",
        },
        current_meta={"transition_contract": current_contract},
        chapter_text="仓库七号的门锁弹开了。",
    )

    assert result["status"] == "broken"
    assert result["passed"] is False
    assert any(item["code"] == "parallel_version_candidate" for item in result["gaps"])


def test_review_provenance_rejects_an_old_prompt_version_for_same_text():
    from app.v7.engines.review_engine import REVIEW_PROMPT_VERSION
    from app.v7.review_service import _review_provenance_matches, text_hash

    text = "同一段正文"
    assert _review_provenance_matches(
        {"text_hash": text_hash(text), "prompt_version": REVIEW_PROMPT_VERSION}, text
    ) is True
    assert _review_provenance_matches(
        {"text_hash": text_hash(text), "prompt_version": "1.4.0"}, text
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


def test_async_v7_engine_is_safe_for_sync_bridges_on_multiple_event_loops():
    from sqlalchemy.pool import NullPool

    from app.v7.db import async_engine

    assert isinstance(async_engine.sync_engine.pool, NullPool)
