"""Unit tests for V3 §9 character cognition layering — split_known_info.

Real logic only — no mock providers.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.gateway import OutputValidationError, validate_task_output  # noqa: E402
from app.services import entity_tracker  # noqa: E402
from app.services.entity_tracker import get_states, split_known_info, KNOWN_INFO_LAYERS  # noqa: E402


def test_split_empty_returns_five_layers():
    res = split_known_info([])
    assert set(res.keys()) == set(KNOWN_INFO_LAYERS)
    assert all(v == [] for v in res.values())


def test_extract_entities_contract_requires_real_cognition_evidence():
    accepted = validate_task_output(
        "extract_entities",
        {
            "entities": [{
                "type": "character",
                "name": "林默",
                "state": "警惕",
                "location": "旧巷",
                "known_info": [
                    {"layer": "reader_known", "text": "林默收到了匿名信"},
                    {"layer": "character_misunderstood", "text": "林默误以为寄信人是同事"},
                ],
            }],
        },
    )
    assert len(accepted["entities"][0]["known_info"]) == 2

    with pytest.raises(OutputValidationError):
        validate_task_output(
            "extract_entities",
            {"entities": [{"type": "character", "name": "林默", "known_info": []}]},
        )


def test_get_states_is_scoped_to_one_novel_without_ambiguous_columns(monkeypatch):
    class FakeDb:
        def execute(self, sql, params):
            assert "c.parent_id = %s" in sql
            assert "es.updated_at" in sql
            assert params == ("novel-2", 7)
            return self

        def fetchall(self):
            return []

        def close(self):
            pass

    monkeypatch.setattr(entity_tracker, "connect", FakeDb)
    assert get_states("novel-2", limit=7) == []


def test_split_plain_strings_default_to_world_facts():
    res = split_known_info(["魔法源于元素核心", "国王已离世"])
    assert res["world_facts"] == ["魔法源于元素核心", "国王已离世"]
    assert res["reader_known"] == []
    assert res["character_misunderstood"] == []


def test_split_dict_with_explicit_layer():
    res = split_known_info([
        {"text": "妹妹还活着", "layer": "character_misunderstood"},
        {"text": "主角是重生者", "layer": "protagonist_known"},
        {"text": "城西有秘境", "layer": "reader_known"},
    ])
    assert res["character_misunderstood"] == ["妹妹还活着"]
    assert res["protagonist_known"] == ["主角是重生者"]
    assert res["reader_known"] == ["城西有秘境"]


def test_split_dict_misunderstood_flag():
    res = split_known_info([{"text": "敌人其实是恩人", "misunderstood": True}])
    assert res["character_misunderstood"] == ["敌人其实是恩人"]


def test_split_dict_unknown_layer_defaults_world_facts():
    res = split_known_info([{"text": "大陆分九国", "layer": "nonexistent"}])
    assert res["world_facts"] == ["大陆分九国"]


def test_split_accepts_single_string():
    res = split_known_info("平原一望无际")
    assert res["world_facts"] == ["平原一望无际"]
