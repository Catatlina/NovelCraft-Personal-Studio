"""Regression contracts for the real genre-pack generation boundary."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_genre_pack_migration_creates_runtime_tables_and_builtin_seed_data():
    source = (ROOT / "alembic/versions/nc_v7_genre_packs.py").read_text(encoding="utf-8")

    assert 'down_revision: Union[str, None] = "nc_legacy_chapter_scope"' in source
    for table in (
        "v7_genre_packs",
        "v7_genre_rules",
        "v7_genre_knowledge",
        "v7_genre_prompts",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in source
    assert "ON CONFLICT (slug) DO NOTHING" in source
    assert "core_style" in source
    assert "writer.core" in source


def test_selected_genre_reaches_the_canonical_v7_generation_engine():
    director = (ROOT / "app/v7/director/story_director.py").read_text(encoding="utf-8")
    base = (ROOT / "app/v7/engines/base.py").read_text(encoding="utf-8")

    assert "genre_id: str | None = None" in base
    assert "self.genre_id = genre_id" in base
    assert "self.generation_engine = GenerationEngine(" in director
    assert "            genre_id=genre_id," in director
