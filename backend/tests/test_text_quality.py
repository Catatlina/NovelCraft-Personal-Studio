from __future__ import annotations

import pytest

from app.services.text_quality import (
    content_chars,
    deduplicate_full_paragraphs,
    duplicate_paragraph_stats,
    normalize_and_validate_rewrite,
    normalize_narrative_paragraphs,
)
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


def test_duplicate_paragraph_stats_flags_material_full_paragraph_repetition():
    paragraph = "沈夜把手按在门上，门内的声音停了一瞬，随后又传来三下敲击，事情因此留下新的后果。"
    stats = duplicate_paragraph_stats("\n\n".join([paragraph, paragraph, "林薇没有回头，只把短棍往掌心里收紧。" ]))

    assert stats["duplicate_paragraph_count"] == 1
    assert stats["duplicate_ratio"] > 0.01
    assert stats["adjacent_duplicate_count"] == 1


def test_duplicate_paragraph_stats_ignores_short_refrains():
    stats = duplicate_paragraph_stats("好。\n\n好。\n\n好。")

    assert stats["duplicate_paragraph_count"] == 0
    assert stats["duplicate_ratio"] == 0.0


def test_canonical_dedup_repair_removes_only_exact_full_paragraph_copies():
    first = "沈夜按住门把手，门内的声音停了一瞬，随后又传来三下敲击，事情因此留下新的后果。那声音贴着门板往外渗，像有人在里面等他做出选择。"
    second = "林薇把灯光压低，示意他先别出声，巷口的脚步声正在靠近。她没有回头，只用手指在墙上敲了两下，提醒他别急着开门。"
    repaired, evidence = deduplicate_full_paragraphs(
        "\n\n".join([first, second, first])
    )

    assert repaired == "\n\n".join([first, second])
    assert evidence["removed_paragraphs"] == 1
