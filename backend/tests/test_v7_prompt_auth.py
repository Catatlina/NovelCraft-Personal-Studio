from fastapi.routing import APIRoute

from app.api.v1.config import require_admin, require_admin_reads
from app.v7.api.prompt import router


def _route(path: str, method: str) -> APIRoute:
    for item in router.routes:
        if isinstance(item, APIRoute) and item.path == path and method in item.methods:
            return item
    raise AssertionError(f"route not found: {method} {path}")


def test_prompt_router_has_admin_read_guard():
    assert router.dependencies
    assert router.dependencies[0].dependency is require_admin_reads


def test_prompt_mutations_have_admin_write_guard():
    for path, method in (
        ("/versions", "POST"),
        ("/versions/{version_id}/default", "POST"),
        ("/versions/{version_id}/deactivate", "POST"),
        ("/executions", "POST"),
    ):
        dependency_calls = {dependency.call for dependency in _route(path, method).dependant.dependencies}
        assert require_admin in dependency_calls, (method, path, dependency_calls)
