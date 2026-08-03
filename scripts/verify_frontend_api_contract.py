#!/usr/bin/env python3
"""Fail when a frontend API path has no matching FastAPI/OpenAPI route."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app  # noqa: E402


FRONTEND_PATH = re.compile(r"""["'`](/api/v1/[^"'`\s]*)["'`]""")
DYNAMIC_SEGMENT = re.compile(r"\$\{[^}]+\}")
ROUTE_PARAMETER = re.compile(r"^\{[^}]+\}$")

CRITICAL_METHODS = {
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/register"),
    ("GET", "/api/v1/projects"),
    ("GET", "/api/v1/library/books"),
    ("GET", "/api/v1/library/books/{book_id}"),
    ("GET", "/api/v1/contents"),
    ("GET", "/api/v1/contents/{content_id}"),
    ("PUT", "/api/v1/contents/{content_id}"),
}


def normalize_frontend_path(raw: str) -> str:
    return DYNAMIC_SEGMENT.sub("{dynamic}", raw.split("?", 1)[0]).rstrip("/") or "/"


def paths_match(frontend_path: str, backend_path: str) -> bool:
    frontend_parts = frontend_path.strip("/").split("/")
    backend_parts = backend_path.strip("/").split("/")
    if len(frontend_parts) != len(backend_parts):
        return False
    return all(
        left == right or ROUTE_PARAMETER.match(left) or ROUTE_PARAMETER.match(right)
        for left, right in zip(frontend_parts, backend_parts)
    )


def main() -> int:
    schema = app.openapi()
    backend_paths = set(schema["paths"])
    backend_operations = {
        (method.upper(), path)
        for path, operations in schema["paths"].items()
        for method in operations
        if method.lower() in {"get", "post", "put", "patch", "delete"}
    }

    missing_critical = sorted(CRITICAL_METHODS - backend_operations)
    used_paths: dict[str, set[str]] = {}
    for source in sorted((ROOT / "frontend" / "src").rglob("*")):
        if source.suffix not in {".ts", ".tsx"}:
            continue
        for match in FRONTEND_PATH.finditer(source.read_text(encoding="utf-8")):
            raw_path = match.group(1)
            # Ignore a quoted prefix that is immediately concatenated with a
            # dynamic id (for example "/api/v1/novels/" + novelId). It is not
            # an endpoint by itself; the following literal suffix completes
            # the route and is checked by the dynamic-path matcher below.
            if raw_path.endswith("/"):
                continue
            path = normalize_frontend_path(raw_path)
            used_paths.setdefault(path, set()).add(str(source.relative_to(ROOT)))

    missing_frontend = {
        path: files
        for path, files in used_paths.items()
        if not any(paths_match(path, backend_path) for backend_path in backend_paths)
    }

    if missing_critical or missing_frontend:
        print("Frontend/API contract verification failed:")
        for method, path in missing_critical:
            print(f"- missing critical operation: {method} {path}")
        for path, files in sorted(missing_frontend.items()):
            print(f"- no backend route for {path}: {', '.join(sorted(files))}")
        return 1

    print(
        "Frontend/API contract verified: "
        f"{len(used_paths)} frontend paths, {len(CRITICAL_METHODS)} critical operations."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
