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


def test_generation_context_uses_the_real_async_session_factory():
    source = (ROOT / "app/v7/generation/generation_engine.py").read_text(encoding="utf-8")

    assert "from ..db import AsyncSessionLocal" in source
    assert "async with AsyncSessionLocal() as db:" in source
    assert "from ..db import async_session" not in source


def test_wizard_genre_tree_is_authenticated_but_genre_management_stays_admin_only():
    source = (ROOT / "app/v7/api/genres.py").read_text(encoding="utf-8")

    # Authors need the built-in tree to create a novel. CRUD/list/detail
    # endpoints remain explicitly admin-read protected; removing the old
    # router-wide guard must not turn the manager API into a public API.
    assert "_user: dict = Depends(get_current_user)" in source
    assert '@router.get("/tree", response_model=dict)' in source
    assert 'response_model=dict, dependencies=[Depends(require_admin_reads)]' in source
    assert 'router = APIRouter(\n    prefix="",\n    tags=["v7-genres"],\n)' in source
