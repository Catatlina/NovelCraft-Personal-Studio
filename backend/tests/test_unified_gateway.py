from __future__ import annotations

import json


def test_shared_sync_stream_normalises_sse_and_usage(monkeypatch):
    import app.services.unified_gateway as gateway_module
    from app.services.unified_gateway import UnifiedAIGateway

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __iter__(self):
            yield 'data: {"choices":[{"delta":{"content":"第一段"}}]}\n'.encode()
            yield 'data: {"choices":[{"delta":{"content":"第二段"}}]}\n'.encode()
            yield 'data: {"usage":{"prompt_tokens":11,"completion_tokens":7},"choices":[]}\n'.encode()
            yield b"data: [DONE]\n"

    captured = {}

    def _urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(gateway_module.urllib.request, "urlopen", _urlopen)
    usage: dict[str, int] = {}
    chunks = list(
        UnifiedAIGateway(
            provider="deepseek",
            api_key="test-key",
            base_url="https://provider.test/v1/",
            model="deepseek-chat",
            timeout=12,
        ).stream_sync(
            "正文",
            system_prompt="系统",
            temperature=0.4,
            max_tokens=1024,
            usage_out=usage,
        )
    )

    assert chunks == ["第一段", "第二段"]
    assert usage == {"prompt_tokens": 11, "completion_tokens": 7}
    assert captured["timeout"] == 12
    payload = json.loads(captured["request"].data.decode("utf-8"))
    assert payload["stream"] is True
    assert payload["messages"][-1] == {"role": "user", "content": "正文"}
    assert captured["request"].headers["Authorization"] == "Bearer test-key"
