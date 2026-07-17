"""Browser-capture and metadata-validation helpers for ranking ingestion.

The browser is deliberately user controlled.  Challenge pages are reported as
requiring intervention; this module never attempts to solve or bypass them.
Captured artifacts contain public ranking metadata only, never chapter text.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_CAPTURE_SOURCES = {"fanqie", "qidian", "zongheng", "qqread", "sfacg", "xxsy", "jjwxc", "manual"}
REQUIRED_IMPORT_FIELDS = {"rank", "title"}


@dataclass(frozen=True)
class CaptureResult:
    source: str
    status: str
    items: list[dict[str, Any]]
    evidence: dict[str, Any]
    error: str | None = None

    def as_adapter_items(self) -> list[dict[str, Any]]:
        if self.status != "succeeded":
            return [{
                "source": self.source,
                "error": self.error or self.status,
                "degraded": True,
                "capture_status": self.status,
                "evidence": self.evidence,
            }]
        return [
            {
                **item,
                "source": self.source,
                "collector": item.get("collector", self.evidence.get("collector", "browser")),
                "confidence": float(item.get("confidence", 1.0)),
                "evidence": {**self.evidence, **item.get("evidence", {})},
            }
            for item in self.items
        ]


def load_capture_artifact(path: str | Path, expected_source: str | None = None) -> CaptureResult:
    """Load a versioned JSON artifact produced by a visible browser/OCR worker."""
    artifact_path = Path(path).expanduser().resolve()
    data = json.loads(artifact_path.read_text(encoding="utf-8"))
    source = str(data.get("source", "")).lower()
    if source not in ALLOWED_CAPTURE_SOURCES:
        raise ValueError(f"unsupported capture source: {source or '<empty>'}")
    if expected_source and source != expected_source:
        raise ValueError(f"capture source mismatch: expected {expected_source}, got {source}")
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("capture items must be a list")
    evidence = dict(data.get("evidence") or {})
    artifact_digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    if evidence.get("screenshot"):
        evidence["screenshot"] = Path(str(evidence["screenshot"])).name
    evidence.pop("browser_profile", None)
    evidence.update({
        "artifact_name": artifact_path.name,
        "artifact_sha256": artifact_digest,
        "captured_at": data.get("captured_at") or datetime.now(timezone.utc).isoformat(),
        "collector": data.get("collector", "browser"),
    })
    return CaptureResult(source, str(data.get("status", "succeeded")), items, evidence, data.get("error"))


def configured_capture(source: str) -> CaptureResult | None:
    path = os.getenv(f"RANKING_CAPTURE_{source.upper()}_PATH", "").strip()
    return load_capture_artifact(path, source) if path else None


def import_ranking_file(path: str | Path, source: str = "manual") -> list[dict[str, Any]]:
    """Import user-authorized public metadata from CSV or JSON."""
    import_path = Path(path).expanduser().resolve()
    if import_path.suffix.lower() == ".csv":
        with import_path.open(encoding="utf-8-sig", newline="") as handle:
            items = list(csv.DictReader(handle))
    elif import_path.suffix.lower() == ".json":
        payload = json.loads(import_path.read_text(encoding="utf-8"))
        items = payload.get("items", payload) if isinstance(payload, dict) else payload
    else:
        raise ValueError("ranking import supports CSV or JSON only")
    if not isinstance(items, list):
        raise ValueError("ranking import must contain a list")
    artifact_digest = hashlib.sha256(import_path.read_bytes()).hexdigest()
    output = []
    for index, raw in enumerate(items, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"row {index} is not an object")
        missing = REQUIRED_IMPORT_FIELDS - raw.keys()
        if missing or not str(raw.get("title", "")).strip():
            raise ValueError(f"row {index} missing required fields: {sorted(missing or {'title'})}")
        output.append({**raw, "source": source, "collector": "manual_import", "confidence": 1.0,
                       "evidence": {"artifact_name": import_path.name, "artifact_sha256": artifact_digest,
                                    "row": index}})
    return output


def validate_with_open_library(title: str, author: str = "", timeout: float = 8.0) -> dict[str, Any]:
    """Cross-check metadata against Open Library without retrieving book content."""
    query = urllib.parse.urlencode({"title": title, "author": author, "limit": 3, "fields": "key,title,author_name,first_publish_year,isbn"})
    request = urllib.request.Request(
        f"https://openlibrary.org/search.json?{query}",
        headers={"User-Agent": "NovelCraft/1.0 metadata-validator"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        matches = payload.get("docs", [])[:3]
        return {"provider": "open_library", "status": "matched" if matches else "not_found", "matches": matches}
    except Exception as exc:
        return {"provider": "open_library", "status": "unavailable", "matches": [], "error": str(exc)}
