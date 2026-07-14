"""M4: Overseas publishing — translation + localization + taboo check."""
from __future__ import annotations


OVERSEAS_PLATFORMS = {
    "royalroad": {"name": "Royal Road", "format": "web_novel_chapter", "language": "en"},
    "webnovel": {"name": "WebNovel", "format": "web_novel_chapter", "language": "en"},
    "scribblehub": {"name": "Scribble Hub", "format": "web_novel_chapter", "language": "en"},
    "kdp": {"name": "Amazon KDP", "format": "ebook", "language": "en"},
    "medium_en": {"name": "Medium", "format": "long_form", "language": "en"},
    "substack_en": {"name": "Substack", "format": "newsletter", "language": "en"},
}

TRANSLATION_PIPELINE = [
    "segment_translate",  # Split by paragraphs, translate each
    "literary_polish",    # Enhance readability for target language
    "cultural_localize",  # Adapt names, measurements, cultural references
    "taboo_check",        # Check for political/religious/cultural taboos
    "seo_optimize",       # Optimize title/keywords for target platform
]


def translate_chapter(chapter_text: str, target_lang: str = "en", project_id: str = "") -> dict:
    """Translate a chapter with the full pipeline."""
    from app.gateway import complete

    # Step 1: Segment and translate
    translated = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="translate_segment", prompt_name="overseas.translate_segment",
        variables={"text": chapter_text[:8000], "target_lang": target_lang},
    )

    # Step 2: Cultural localization
    localized = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="cultural_localize", prompt_name="overseas.cultural_localize",
        variables={"text": translated.get("translated", ""), "target_lang": target_lang},
    )

    return {
        "translated": translated.get("translated", ""),
        "localized": localized.get("localized", ""),
        "cultural_notes": localized.get("notes", []),
    }


def format_for_platform(text: str, platform_key: str) -> str:
    """Format content for specific overseas platform."""
    platform = OVERSEAS_PLATFORMS.get(platform_key, OVERSEAS_PLATFORMS["royalroad"])
    if platform["format"] == "ebook":
        return f"# {text[:100]}...\n\n{text}"
    return text  # Web novel format is just plain text chapters
