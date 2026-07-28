import pytest

from app.gateway import OutputValidationError
from app.workers.tasks import _assert_story_revision_quality


def _paragraphs(count: int, *, chars: int = 140) -> list[str]:
    return [f"第{i + 1}段：" + ("桂香穿过旧巷，人物动作与感受自然推进。" * chars) for i in range(count)]


def test_story_revision_quality_allows_paragraph_merging_when_content_is_preserved():
    before = "\n".join(_paragraphs(15))
    merged = [" ".join(parts) for parts in zip(_paragraphs(5), _paragraphs(5), _paragraphs(5))]
    after = [paragraph for paragraph in merged for _ in range(2)]

    _assert_story_revision_quality(
        task_type="write_polish",
        before_text=before,
        after_paragraphs=after[:10],
    )


def test_story_revision_quality_rejects_excessive_paragraph_loss():
    before = "\n".join(_paragraphs(15))

    with pytest.raises(OutputValidationError, match="dropped too many paragraphs"):
        _assert_story_revision_quality(
            task_type="write_polish",
            before_text=before,
            after_paragraphs=_paragraphs(6, chars=350),
        )


def test_story_revision_quality_rejects_destructive_shortening():
    before = "\n".join(_paragraphs(15))

    with pytest.raises(OutputValidationError, match="shortened chapter too much"):
        _assert_story_revision_quality(
            task_type="write_polish",
            before_text=before,
            after_paragraphs=_paragraphs(10, chars=10),
        )
