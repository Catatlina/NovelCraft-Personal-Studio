"""Regression tests for v0.9.2 publication-state guards."""
from __future__ import annotations

import pytest

from app.v7.quality.publishing_gates import GATE_DEFINITIONS
from app.v7.services.publishing_service import (
    create_ai_disclosure,
    update_variant_status,
)


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class _VariantDb:
    def __init__(self, gate_rows):
        self.gate_rows = gate_rows
        self.updates = []

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        if normalized.startswith("SELECT * FROM publication_variants"):
            return _Cursor([{"id": "variant-1", "publication_status": "quality_candidate"}])
        if "FROM quality_gate_results" in normalized:
            return _Cursor(self.gate_rows)
        if normalized.startswith("UPDATE publication_variants"):
            self.updates.append((normalized, params))
            return _Cursor([])
        raise AssertionError(f"unexpected SQL: {normalized}")


def test_publish_ready_requires_all_blocking_gate_evidence():
    db = _VariantDb([])

    with pytest.raises(ValueError, match="尚未满足publish_ready门禁"):
        update_variant_status(db, "variant-1", "publish_ready")

    assert db.updates == []


def test_publish_ready_records_published_at_only_after_all_blocking_gates_pass():
    rows = [
        {"gate_key": key, "passed": True}
        for key, definition in GATE_DEFINITIONS.items()
        if definition["is_blocking"]
    ]
    db = _VariantDb(rows)

    result = update_variant_status(db, "variant-1", "publish_ready")

    assert result["new_status"] == "publish_ready"
    assert len(db.updates) == 1


class _DisclosureDb:
    def __init__(self):
        self.insert_params = None
        self.variant_update_params = None

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        if normalized.startswith("SELECT * FROM publication_variants"):
            return _Cursor([{"id": "variant-1"}])
        if normalized.startswith("INSERT INTO ai_disclosure_records"):
            self.insert_params = params
            return _Cursor([])
        if normalized.startswith("UPDATE publication_variants"):
            self.variant_update_params = params
            return _Cursor([])
        raise AssertionError(f"unexpected SQL: {normalized}")

    def fetchone(self):
        return {"id": "disclosure-1"}


def test_disclosure_generation_does_not_auto_confirm():
    db = _DisclosureDb()

    result = create_ai_disclosure(db, "variant-1", disclosure_text="AI辅助创作")

    assert result["status"] == "generated"
    assert db.insert_params[3] == "generated"
    assert db.variant_update_params[0] == "generated"
