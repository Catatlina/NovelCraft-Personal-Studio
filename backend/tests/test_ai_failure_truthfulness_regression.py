from __future__ import annotations

import pytest

from app.gateway import ProviderError
from app.services import deai_pipeline
from app.services.ten_layer_analysis import TenLayerAnalyzer


def test_deai_score_provider_failure_is_terminal(monkeypatch):
    def fail_complete(**kwargs):
        raise ProviderError("provider unavailable")

    monkeypatch.setattr(deai_pipeline, "complete", fail_complete)

    with pytest.raises(ProviderError):
        deai_pipeline.deai_score("project-1", "不仅如此，命运的齿轮开始转动。")


def test_ten_layer_ai_call_marks_provider_failure_failed(monkeypatch):
    def fail_complete(**kwargs):
        raise ProviderError("provider unavailable")

    monkeypatch.setattr("app.services.ten_layer_analysis.complete", fail_complete)

    analyzer = TenLayerAnalyzer(project_id="project-1")
    result = analyzer._call_ai(
        task_type="analysis_ai_insight",
        prompt_name="analysis.ai_insight",
        layer="10_AIInsight",
        system_context="system",
        analysis_instructions="instructions",
    )

    assert result["status"] == "failed"
    assert result["error_type"] == "ProviderError"
