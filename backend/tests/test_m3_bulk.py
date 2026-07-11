"""M3: Bulk module tests — parser, book analysis, briefing scheduler, comparison report."""
import os, uuid
os.environ["NOVELCRAFT_ENV"] = "dev"

import pytest


def test_pdf_parser_simple_text():
    """TASK-035: Parse basic text into knowledge items."""
    from app.services.m3_bulk import parse_uploaded_file
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# Introduction\nThis is a test.\n\n## Chapter 1\nContent here.\n")
        path = f.name
    items = parse_uploaded_file(path)
    os.unlink(path)
    assert len(items) >= 1


def test_book_analyzer():
    """TASK-036: Book structure analysis."""
    from app.services.m3_bulk import analyze_book_structure
    text = "# Chapter 1\n" * 10 + "The beginning. " * 200
    result = analyze_book_structure(text)
    assert result["total_chapters"] >= 1
    assert result["estimated_words"] > 0


def test_schedule_briefings():
    """TASK-038: 7-day briefing schedule."""
    from app.services.m3_bulk import schedule_week_briefings
    from app.db import connect, new_id, encode
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.rate_limit import limiter
    limiter.reset()
    tc = TestClient(app)
    e = f"bf-{uuid.uuid4().hex[:6]}@nc.dev"
    tok = tc.post("/api/v1/auth/register", json={"email": e, "password": "test1234"}).json()["data"]["access_token"]
    pid = tc.get("/api/v1/projects", headers={"Authorization": f"Bearer {tok}"}).json()["data"][0]["id"]
    ids = schedule_week_briefings(pid)
    assert len(ids) == 7


def test_comparison_report_structure():
    """TASK-039: Comparison report generates correct structure."""
    from app.services.m3_bulk import generate_model_comparison
    result = generate_model_comparison("test", [])
    assert result["prompt"] == "test"
    assert result["models_tested"] == 0
    assert isinstance(result["results"], list)


def test_parse_import_cycle():
    """Cross-check: m3_bulk imports without circular errors."""
    from app.services.m3_bulk import parse_uploaded_file, analyze_book_structure, schedule_week_briefings, generate_model_comparison
    assert all([parse_uploaded_file, analyze_book_structure, schedule_week_briefings, generate_model_comparison])
