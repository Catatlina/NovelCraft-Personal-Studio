from __future__ import annotations

import pytest

from app.gateway import OutputValidationError
from app.prompt_registry import PROMPT_SEEDS, render_prompt
from app.services.chapter_loop import _apply_replacements
from app.services.deai_pipeline import DeaiPipeline


def _chapter(paragraphs: int = 10, chars: int = 80) -> str:
    return "\n\n".join(
        f"第{i + 1}段：" + ("人物动作推动现场变化，细节不能被删掉。" * chars)
        for i in range(paragraphs)
    )


def test_final_humanize_rejects_destructive_provider_output(monkeypatch):
    source = _chapter()

    def fake_complete(**_kwargs):
        return {"humanized_text": "过短的摘要。", "changes": []}

    monkeypatch.setattr("app.gateway.complete", fake_complete)

    with pytest.raises(OutputValidationError, match="too-short"):
        DeaiPipeline("project-1", "content-1", "第1章").final_humanize(source)


def test_final_humanize_passes_facts_and_style_to_real_gateway(monkeypatch):
    source = _chapter(paragraphs=4, chars=5)
    captured = {}

    def fake_complete(**kwargs):
        captured.update(kwargs)
        return {
            "humanized_text": source.replace("现场变化", "现场变化"),
            "changes": ["打散模板化句式"],
            "ai_patterns_removed": ["总结体"],
        }

    monkeypatch.setattr("app.gateway.complete", fake_complete)

    result = DeaiPipeline("project-1", "content-1", "第1章").final_humanize(
        source,
        source_facts="主角仍在旧仓库",
        forbidden_changes="不得新增超自然能力",
        style_profile="短句、少解释、动作先行",
        run_id="run-1",
        user_id="user-1",
    )

    assert result["final_text"] == source
    assert captured["task_type"] == "final_humanize"
    assert captured["variables"]["source_facts"] == "主角仍在旧仓库"
    assert captured["variables"]["style_profile"] == "短句、少解释、动作先行"
    assert captured["run_id"] == "run-1"
    assert captured["user_id"] == "user-1"


def test_final_humanize_repairs_provider_collapsed_paragraphs(monkeypatch):
    source = _chapter(paragraphs=59, chars=5)
    collapsed = "".join(source.split("\n\n"))

    def fake_complete(**_kwargs):
        return {"humanized_text": collapsed, "changes": []}

    monkeypatch.setattr("app.gateway.complete", fake_complete)

    result = DeaiPipeline("project-1", "content-1", "第1章").final_humanize(source)

    assert len(result["final_text"].split("\n\n")) >= 36
    assert len(result["final_text"].replace("\n", "").replace(" ", "")) == len(collapsed.replace("\n", "").replace(" ", ""))


def test_fact_repair_requires_exact_anchor_and_never_invents_text():
    source = "周远山推开门。\n\n门后没有人。"

    repaired, applied = _apply_replacements(
        source,
        [
            {"anchor": "门后没有人", "replacement": "门后传来三下敲击"},
            {"anchor": "不存在的原文", "replacement": "不应被插入"},
        ],
    )

    assert applied == 1
    assert "门后传来三下敲击" in repaired
    assert "不应被插入" not in repaired


def test_prompts_expose_style_and_fact_repair_contracts():
    humanize = next(seed[3] for seed in PROMPT_SEEDS if seed[0] == "bootstrap.final_humanize")
    reconcile = next(seed[3] for seed in PROMPT_SEEDS if seed[0] == "bootstrap.write_fact_reconcile")

    rendered_humanize = render_prompt(
        humanize,
        {
            "_chapter_body": "正文。",
            "source_facts": "主角在仓库。",
            "forbidden_changes": "不得改地点。",
            "style_profile": "短句。",
            "quality_retry_feedback": "保留动作细节。",
        },
    )
    assert "短句。" in rendered_humanize
    assert "主角在仓库。" in rendered_humanize
    assert "repairs" in reconcile
