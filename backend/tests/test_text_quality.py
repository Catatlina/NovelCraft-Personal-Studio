from __future__ import annotations

import pytest

from app.services.text_quality import content_chars, normalize_and_validate_rewrite, normalize_narrative_paragraphs
from app.v7.quality.deai_metrics import analyze_deai_patterns


def _sentence(index: int) -> str:
    return f"第{index}段里人物做出选择，现场因此发生变化，留下一个必须在下一段处理的后果。"


def test_reflow_restores_collapsed_paragraphs_without_losing_content():
    source = "\n\n".join(_sentence(index) for index in range(1, 60))
    collapsed = "".join(_sentence(index) for index in range(1, 60))

    normalized = normalize_narrative_paragraphs(
        collapsed,
        minimum_paragraphs=36,
        max_paragraph_chars=120,
    )

    assert len(normalized.split("\n\n")) >= 36
    assert content_chars(normalized) == content_chars(collapsed)


def test_rewrite_guard_rejects_real_content_loss_after_reflow():
    source = "\n\n".join(_sentence(index) for index in range(1, 20))
    candidate = "\n\n".join(_sentence(index) for index in range(1, 10))

    with pytest.raises(ValueError, match="chapter length"):
        normalize_and_validate_rewrite(source, candidate, minimum_chars=50)


def test_dash_metric_counts_long_dash_as_one_and_flags_density_only():
    text = "\n\n".join(
        f"人物停了一下——他没有解释。随后他继续向前走，脚下的水声越来越近。" + "现场的风从门缝里灌进来，桌上的纸张被吹得贴住了墙角。" * 8
        for _ in range(8)
    )
    metrics = analyze_deai_patterns(text)

    assert metrics["dash_count"] == 8
    assert metrics["dash_density_per_1000"] < 5
    assert not any(flag["code"] == "dash_density" for flag in metrics["flags"])
