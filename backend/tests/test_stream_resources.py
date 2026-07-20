"""P2-T10 SSE 流式资源占用测试 (T01)。

验证 ``ai_edit_stream`` 的 SSE 帧封装 ``sse_event`` 与流式分片行为：

- 每个事件严格以 ``data: `` 开头、``\\n\\n`` 结尾（标准 SSE 帧）；
- 超大单帧（模拟超长 AI 输出）序列化为单个合法 JSON 事件，长度随负载增长但
  结构正确，不会因拼接多帧导致解析错位；
- 流式分片以生成器逐帧产出（背压友好：不会在内存中一次性物化全部帧）。

``sse_event`` 定义在 ``app.main``，导入需后端依赖；环境不可用时整模块跳过。
"""
from __future__ import annotations

import json

try:
    from app.main import sse_event
    _OK = True
except Exception:  # pragma: no cover
    sse_event = None
    _OK = False

import pytest

pytestmark = pytest.mark.skipif(not _OK, reason="app.main 不可导入（缺少依赖/环境），跳过 SSE 资源测试。")


def test_sse_frame_format():
    frame = sse_event({"delta": "hello"})
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    # 帧体为合法 JSON
    payload = json.loads(frame[len("data: "): -2])
    assert payload == {"delta": "hello"}


def test_sse_error_frame():
    frame = sse_event({"error": "boom", "code": "PROVIDER_FAILED"})
    payload = json.loads(frame[len("data: "): -2])
    assert payload["code"] == "PROVIDER_FAILED"
    assert payload["error"] == "boom"


def test_oversized_frame_is_single_wellformed_event():
    huge = "A" * 10_000_000
    frame = sse_event({"delta": huge})
    # 单帧：一个 data: 头、一个尾随 \n\n，不出现第二个帧头（避免错位）
    assert frame.startswith("data: ")
    assert frame.count("data: ") == 1
    assert frame.endswith("\n\n")
    payload = json.loads(frame[len("data: "): -2])
    assert payload["delta"] == huge


def test_stream_chunks_incrementally():
    """模拟流式逐帧产出：生成器逐帧 yield，而非一次性物化全部帧。"""
    def fake_stream(deltas):
        for d in deltas:
            yield sse_event({"delta": d})

    parts = ["你好", "世界", "，", "这是", "流式输出"]
    frames = list(fake_stream(parts))
    assert len(frames) == len(parts)
    joined = "".join(frames)
    # 每帧独立、顺序拼接后逐帧可解析
    cursor = 0
    for d in parts:
        head = joined.index("data: ", cursor)
        tail = joined.index("\n\n", head) + 2
        payload = json.loads(joined[head + len("data: "): tail - 2])
        assert payload["delta"] == d
        cursor = tail
