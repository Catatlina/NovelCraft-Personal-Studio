"""Stage-3 ①: SSE streaming for pure-text editor ops — frame protocol, ledger,
version branch, mutation replay, and explicit provider-failure semantics."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]


def _frames(body: str) -> list[dict]:
    out = []
    for frame in body.split("\n\n"):
        line = frame.strip()
        if line.startswith("data:"):
            out.append(json.loads(line[5:].strip()))
    return out


@pytest.fixture
def ctx(monkeypatch):
    from app.core.rate_limit import limiter
    from app.db import connect, encode, new_id
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"stream-{uuid.uuid4().hex[:6]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    novel_id = client.post(
        f"/api/v1/projects/{project_id}/novels",
        headers=headers,
        json={"idea": "流式编辑回归测试作品", "genre": "悬疑", "style": "紧凑", "target_words": 10000},
    ).json()["data"]["id"]
    content_id = new_id()
    db = connect()
    db.execute(
        "INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status) VALUES (%s,%s,%s,'chapter','流式测试',%s,%s,'draft')",
        (content_id, project_id, novel_id, encode({"type": "doc", "content": [{"type": "paragraph", "text": "原文"}]}), encode({"seq": 1})),
    )
    db.commit()
    db.close()
    return {"client": client, "headers": headers, "project_id": project_id, "content_id": content_id}


def _patch_stream(monkeypatch, deltas=("润色", "结果"), usage=None):
    import app.main as main_module

    monkeypatch.setattr(
        main_module,
        "_run_v7_editor",
        lambda *args, **kwargs: {
            "text": "".join(deltas),
            "canonical_engine": "v7",
            "editor_provenance": {"engine": "v7"},
            "usage": usage or {"tokens_input": 20, "tokens_output": 10},
        },
    )


def test_stream_endpoint_emits_deltas_then_done_and_writes_ledger(ctx, monkeypatch):
    from app.db import connect

    _patch_stream(monkeypatch)
    mutation = f"stream-{uuid.uuid4().hex[:8]}"
    response = ctx["client"].post(
        f"/api/v1/contents/{ctx['content_id']}/ai/polish/stream", headers=ctx["headers"],
        json={"selection": "原文", "instruction": "", "client_mutation_id": mutation})
    assert response.status_code == 200
    frames = _frames(response.text)
    assert "".join(f.get("delta", "") for f in frames if f.get("delta")) == "润色结果"
    assert frames[-1]["done"] is True
    assert frames[-1]["text"] == "润色结果"
    assert frames[-1]["canonical_engine"] == "v7"

    db = connect()
    version = db.execute(
        "SELECT * FROM versions WHERE entity_id=%s AND label='ai_edit'", (ctx["content_id"],)
    ).fetchone()
    db.close()
    assert version is not None
    assert version["snapshot"]["output"]["canonical_engine"] == "v7"


def test_stream_replays_cached_mutation_without_provider_call(ctx, monkeypatch):
    _patch_stream(monkeypatch)
    mutation = f"stream-replay-{uuid.uuid4().hex[:8]}"
    url = f"/api/v1/contents/{ctx['content_id']}/ai/polish/stream"
    body = {"selection": "原文", "instruction": "", "client_mutation_id": mutation}
    first = ctx["client"].post(url, headers=ctx["headers"], json=body)
    assert _frames(first.text)[-1]["text"] == "润色结果"

    def boom(*args, **kwargs):
        raise AssertionError("provider must not be called on replay")

    import app.main as main_module
    monkeypatch.setattr(main_module, "_run_v7_editor", boom)
    second = ctx["client"].post(url, headers=ctx["headers"], json=body)
    frames = _frames(second.text)
    assert frames[-1]["done"] is True
    assert frames[-1]["text"] == "润色结果"
    assert frames[-1]["canonical_engine"] == "v7"


def test_stream_provider_failure_emits_error_frame_only(ctx, monkeypatch):
    from app.db import connect
    from app.v7.editor_service import V7EditorError

    import app.main as main_module

    def down(*args, **kwargs):
        raise V7EditorError("V7_EDITOR_PROVIDER_FAILED", "no key")

    monkeypatch.setattr(main_module, "_run_v7_editor", down)
    mutation = f"stream-fail-{uuid.uuid4().hex[:8]}"
    response = ctx["client"].post(
        f"/api/v1/contents/{ctx['content_id']}/ai/polish/stream", headers=ctx["headers"],
        json={"selection": "原文", "instruction": "", "client_mutation_id": mutation})
    frames = _frames(response.text)
    assert len(frames) == 1
    assert frames[0]["code"] == "V7_EDITOR_PROVIDER_FAILED"
    assert frames[0]["canonical_engine"] == "v7"

    db = connect()
    version = db.execute(
        "SELECT * FROM versions WHERE entity_id=%s AND label='ai_edit'", (ctx["content_id"],)
    ).fetchone()
    db.close()
    assert version is None


def test_stream_budget_failure_has_distinct_code(ctx, monkeypatch):
    from app.v7.editor_service import V7EditorError
    import app.main as main_module

    def over_budget(*args, **kwargs):
        raise V7EditorError("V7_EDITOR_BUDGET", "daily budget exceeded")

    monkeypatch.setattr(main_module, "_run_v7_editor", over_budget)
    response = ctx["client"].post(
        f"/api/v1/contents/{ctx['content_id']}/ai/polish/stream", headers=ctx["headers"],
        json={"selection": "原文", "instruction": "", "client_mutation_id": f"budget-{uuid.uuid4().hex}"})
    frames = _frames(response.text)
    assert len(frames) == 1
    assert frames[0]["code"] == "V7_EDITOR_BUDGET"
    assert "daily budget exceeded" not in frames[0]["error"]
    assert "追踪码" in frames[0]["error"]


def test_non_deepseek_route_does_not_use_deepseek_stream(ctx, monkeypatch):
    import app.gateway as gateway

    monkeypatch.setattr(gateway, "_load_prompt_and_route",
                        lambda *_args, **_kwargs: ("prompt", "openai", "gpt-4o", {}))
    monkeypatch.setattr(gateway, "_deepseek_stream",
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("wrong adapter")))
    with pytest.raises(gateway.ProviderError, match="provider: openai"):
        list(gateway.complete_stream(project_id=ctx["project_id"], task_type="editor_polish",
                                     prompt_name="editor.polish", variables={"selection": "x"}))


def test_streaming_is_limited_to_text_tasks(ctx):
    from app.gateway import ProviderError, complete_stream

    with pytest.raises(ProviderError):
        list(complete_stream(project_id=ctx["project_id"], task_type="gen_chapter1",
                             prompt_name="bootstrap.gen_chapter1", variables={}))


def test_frontend_streams_with_fallback():
    app_src = (ROOT / "frontend/src/App.tsx").read_text(encoding="utf-8")
    api_src = (ROOT / "frontend/src/lib/api.ts").read_text(encoding="utf-8")
    assert "apiStream" in api_src and "getReader()" in api_src
    assert "response.status === 401" in api_src and "await tryRefreshToken()" in api_src
    assert 'payload.code === "PENDING_BUDGET" || payload.code === "V7_EDITOR_BUDGET"' in api_src
    assert "/stream" in app_src  # 流式优先
    assert "queueOfflineMutation" in app_src  # 离线回退仍在
