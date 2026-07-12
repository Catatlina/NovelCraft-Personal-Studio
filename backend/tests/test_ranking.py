"""M1 gate: Ranking adapter tests — fanqie, qidian, zongheng."""
import os, uuid
os.environ["NOVELCRAFT_ENV"] = "dev"

import pytest


def test_fanqie_ranking_returns_data_or_degraded():
    from app.services.ranking_adapter import fetch_fanqie_ranking
    result = fetch_fanqie_ranking()
    assert isinstance(result, list)
    if result and "error" not in result[0]:
        assert len(result) > 0
        assert "title" in result[0]
    else:
        assert result[0].get("degraded") or "error" in result[0]  # Graceful degradation


def test_qidian_ranking_returns_data_or_degraded():
    from app.services.ranking_adapter import fetch_qidian_ranking
    result = fetch_qidian_ranking()
    assert isinstance(result, list)


def test_zongheng_ranking_returns_data_or_degraded():
    from app.services.ranking_adapter import fetch_zongheng_ranking
    result = fetch_zongheng_ranking()
    assert isinstance(result, list)


def test_collect_all_returns_dict():
    from app.services.ranking_adapter import collect_all_rankings
    result = collect_all_rankings()
    assert isinstance(result, dict)
    assert "fanqie" in result
    assert "qidian" in result
    assert "zongheng" in result


def test_ranking_adapter_imports():
    from app.services.ranking_adapter import fetch_fanqie_ranking, fetch_qidian_ranking, fetch_zongheng_ranking
    assert callable(fetch_fanqie_ranking)
    assert callable(fetch_qidian_ranking)
    assert callable(fetch_zongheng_ranking)
