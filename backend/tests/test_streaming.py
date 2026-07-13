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
    content_id = new_id()
    db = connect()
    db.execute(
        "INSERT INTO contents (id, project_id, type, title, body, meta, status) VALUES (%s,%s,'chapter','流式测试',%s,%s,'draft')",
        (content_id, project_id, encode({"type": "doc", "content": [{"type": "paragraph", "text": "原文"}]}), encode({"seq": 1})),
    )
    db.commit()
    db.close()
    return {"client": client, "headers": headers, "project_id": project_id, "content_id": content_id}


def _patch_stream(monkeypatch, deltas=("润色", "结果"), usage=None):
    import app.gateway as gateway

    def fake_stream(prompt, model, params, usage_out):
        usage_out.update(usage or {"prompt_tokens": 20, "completion_tokens": 10})
        yield from deltas

    monkeypatch.setattr(gateway, "_deepseek_stream", fake_stream)


def test_stream_endpoint_emits_deltas_then_done_and_writes_ledger(ctx, monkeypatch):
    from app.db import connect

    _patch_stream(monkeypatch)
    mutation = f"stream-{uuid.uuid4().hex[:8]}"
    response = ctx["client"].post(
        f"/api/v1/contents/{ctx['content_id']}/ai/polish/stream", headers=ctx["headers"],
        json={"selection": "原文", "instruction": "", "client_mutation_id": mutation})
    assert response.status_code == 200
    frames = _frames(response.text)
    assert [f.get("delta") for f in frames[:2]] == ["润色", "结果"]
    assert frames[-1] == {"done": True, "text": "润色结果"}

    db = connect()
    call = db.execute(
        "SELECT * FROM ai_calls WHERE client_mutation_id=%s AND status='succeeded'", (mutation,)
    ).fetchone()
    version = db.execute(
        "SELECT * FROM versions WHERE entity_id=%s AND label='ai_edit'", (ctx["content_id"],)
    ).fetchone()
    db.close()
    assert call is not None and call["task_type"] == "editor_polish"
    assert call["prompt_tokens"] == 20 and call["completion_tokens"] == 10
    assert version is not None


def test_stream_replays_cached_mutation_without_provider_call(ctx, monkeypatch):
    import app.gateway as gateway

    _patch_stream(monkeypatch)
    mutation = f"stream-replay-{uuid.uuid4().hex[:8]}"
    url = f"/api/v1/contents/{ctx['content_id']}/ai/polish/stream"
    body = {"selection": "原文", "instruction": "", "client_mutation_id": mutation}
    first = ctx["client"].post(url, headers=ctx["headers"], json=body)
    assert _frames(first.text)[-1]["text"] == "润色结果"

    def boom(*args, **kwargs):
        raise AssertionError("provider must not be called on replay")

    monkeypatch.setattr(gateway, "_deepseek_stream", boom)
    second = ctx["client"].post(url, headers=ctx["headers"], json=body)
    frames = _frames(second.text)
    assert frames[-1] == {"done": True, "text": "润色结果"}


def test_stream_provider_failure_emits_error_frame_only(ctx, monkeypatch):
    import app.gateway as gateway
    from app.db import connect

    def down(prompt, model, params, usage_out):
        raise gateway.ProviderError("no key")
        yield  # pragma: no cover — make it a generator

    monkeypatch.setattr(gateway, "_deepseek_stream", down)
    mutation = f"stream-fail-{uuid.uuid4().hex[:8]}"
    response = ctx["client"].post(
        f"/api/v1/contents/{ctx['content_id']}/ai/polish/stream", headers=ctx["headers"],
        json={"selection": "原文", "instruction": "", "client_mutation_id": mutation})
    frames = _frames(response.text)
    assert len(frames) == 1
    assert frames[0]["code"] == "PROVIDER_FAILED"

    db = connect()
    call = db.execute(
        "SELECT status, error FROM ai_calls WHERE client_mutation_id=%s", (mutation,)
    ).fetchone()
    db.close()
    assert call and call["status"] == "failed"
    assert "no key" in call["error"]


def test_stream_budget_failure_has_distinct_code(ctx, monkeypatch):
    import app.gateway as gateway

    def over_budget(**_kwargs):
        raise gateway.BudgetExceeded("daily budget exceeded")
        yield  # pragma: no cover

    monkeypatch.setattr(gateway, "complete_stream", over_budget)
    response = ctx["client"].post(
        f"/api/v1/contents/{ctx['content_id']}/ai/polish/stream", headers=ctx["headers"],
        json={"selection": "原文", "instruction": "", "client_mutation_id": f"budget-{uuid.uuid4().hex}"})
    assert _frames(response.text) == [{"error": "daily budget exceeded", "code": "PENDING_BUDGET"}]


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
    assert 'payload.code === "PENDING_BUDGET" ? 429 : 502' in api_src
    assert "/stream" in app_src  # 流式优先
    assert "queueOfflineMutation" in app_src  # 离线回退仍在
