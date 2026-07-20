"""P1-T5 错误信封契约测试 (T02)。

验证 ``app.main`` 中注册的全局 exception handler 输出统一的
``{code, message, data}`` 信封，并正确映射状态码：

    BudgetExceeded            -> 402
    ProviderRateLimitError    -> 429 (data.retry_after 可选)
    OutputValidationError     -> 502
    ProviderError             -> 502 (脱敏 message，detail 入 data)
    HTTPException             -> 原状态码，dict detail 透传 code/message/data
    psycopg2 PoolError        -> 503
    未捕获 Exception          -> 500 (脱敏 + uuid4 trace_id)

本文件不依赖任何数据库 / 外部服务：通过构造一个最小 FastAPI 应用，复用
``app.main`` 中**真实的** handler 函数并注册到测试应用上，再用
``TestClient`` 触发对应异常，端到端校验信封结构。同时提供直接调用 handler
的用例，确保即便框架分派行为有差异也能覆盖真实 handler 逻辑。

运行：``pytest backend/tests/test_error_contract.py``
"""
from __future__ import annotations

import asyncio
import uuid

import psycopg2.pool
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.gateway import (
    BudgetExceeded,
    OutputValidationError,
    ProviderError,
    ProviderRateLimitError,
)
from app.main import (
    database_pool_exhausted,
    handle_budget_exceeded,
    handle_http_exception,
    handle_output_validation,
    handle_provider_error,
    handle_provider_rate_limit,
    handle_unhandled,
)


# ── 最小应用：复用真实 handler ──────────────────────────────────────────────
def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(BudgetExceeded, handle_budget_exceeded)
    app.add_exception_handler(ProviderRateLimitError, handle_provider_rate_limit)
    app.add_exception_handler(OutputValidationError, handle_output_validation)
    app.add_exception_handler(ProviderError, handle_provider_error)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unhandled)
    app.add_exception_handler(psycopg2.pool.PoolError, database_pool_exhausted)

    @app.get("/budget")
    def r_budget():
        raise BudgetExceeded("本月预算已用尽（plan=Pro）")

    @app.get("/ratelimit")
    def r_ratelimit():
        raise ProviderRateLimitError("deepseek 429", retry_after=30)

    @app.get("/ratelimit-no-header")
    def r_ratelimit_no():
        raise ProviderRateLimitError("deepseek 429")

    @app.get("/output-invalid")
    def r_output_invalid():
        raise OutputValidationError("模型返回非 JSON 结构")

    @app.get("/provider-error")
    def r_provider_error():
        # 内部细节放入 data.detail（实现允许），但 message 必须脱敏
        raise ProviderError("SECRET_INTERNAL_DETAIL_xyz")

    @app.get("/http-dict")
    def r_http_dict():
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "无权限", "extra": 1},
        )

    @app.get("/http-plain")
    def r_http_plain():
        raise HTTPException(status_code=404, detail="资源不存在")

    @app.get("/boom")
    def r_boom():
        # 未捕获异常：消息绝不能泄露到响应体
        raise RuntimeError("SECRET_TRACE_DETAIL_abc")

    @app.get("/pool")
    def r_pool():
        raise psycopg2.pool.PoolError("connection pool exhausted")

    return app


@pytest.fixture(scope="module")
def client():
    # raise_server_exceptions=False: TestClient 默认会对未捕获异常的 500 重新抛错，
    # 导致无法验证全局 500 handler 返回的脱敏信封；关闭后返回响应体供断言。
    with TestClient(_build_app(), raise_server_exceptions=False) as c:
        yield c


# ── 直接调用 handler 的辅助（绕过框架分派，验证真实 handler 逻辑）──────────
def _req() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})


def _call(handler, exc):
    return asyncio.run(handler(_req(), exc))


def _body(resp) -> dict:
    import json

    return json.loads(resp.body.decode())


def _envelope_keys(body: dict) -> set:
    return set(body.keys())


# ── 1. BudgetExceeded -> 402 ────────────────────────────────────────────────
def test_budget_exceeded_402(client):
    r = client.get("/budget")
    assert r.status_code == 402
    body = r.json()
    assert _envelope_keys(body) == {"code", "message", "data"}
    assert body["code"] == 402
    assert "用尽" in body["message"]
    assert body["data"]["retryable"] is False


def test_budget_exceeded_402_direct():
    resp = _call(handle_budget_exceeded, BudgetExceeded("x"))
    assert resp.status_code == 402
    assert _body(resp)["code"] == 402


# ── 2. ProviderRateLimitError -> 429 (+ retry_after) ────────────────────────
def test_provider_rate_limit_429_with_retry_after(client):
    r = client.get("/ratelimit")
    assert r.status_code == 429
    body = r.json()
    assert body["code"] == 429
    assert body["data"]["retryable"] is True
    assert body["data"]["retry_after"] == 30


def test_provider_rate_limit_429_without_retry_after(client):
    r = client.get("/ratelimit-no-header")
    assert r.status_code == 429
    body = r.json()
    assert body["code"] == 429
    assert "retry_after" not in body["data"]


# ── 3. OutputValidationError -> 502 ─────────────────────────────────────────
def test_output_validation_502(client):
    r = client.get("/output-invalid")
    assert r.status_code == 502
    body = r.json()
    assert body["code"] == 502
    assert body["data"]["code"] == "PROVIDER_OUTPUT_INVALID"
    assert body["data"]["retryable"] is False


# ── 4. ProviderError -> 502 (message 脱敏) ──────────────────────────────────
def test_provider_error_502_envelope(client):
    r = client.get("/provider-error")
    assert r.status_code == 502
    body = r.json()
    assert body["code"] == 502
    assert _envelope_keys(body) == {"code", "message", "data"}
    # 用户可见的 message 必须脱敏（不含内部细节）
    assert "SECRET_INTERNAL_DETAIL_xyz" not in body["message"]
    assert body["message"] == "AI 服务商暂时不可用，请稍后重试"
    assert body["data"]["retryable"] is True
    # 实现将内部 detail 放入 data.detail（设计允许，便于排障；非 message 字段）
    assert body["data"]["detail"] == "SECRET_INTERNAL_DETAIL_xyz"


# ── 5. HTTPException -> 原码，dict detail 透传 ───────────────────────────────
def test_http_exception_dict_preserved(client):
    r = client.get("/http-dict")
    assert r.status_code == 403
    body = r.json()
    assert body["code"] == "FORBIDDEN"
    assert body["message"] == "无权限"
    assert body["data"] == {"extra": 1}


def test_http_exception_plain_detail(client):
    r = client.get("/http-plain")
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == 404
    assert body["message"] == "资源不存在"
    assert body["data"] is None


# ── 6. 未捕获 Exception -> 500 (脱敏 + trace_id) ─────────────────────────────
def test_unhandled_500_sanitized_with_trace_id(client):
    r = client.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == 500
    assert "SECRET_TRACE_DETAIL_abc" not in r.text
    assert body["message"] == "服务内部错误，请稍后重试"
    trace = body["data"]["trace_id"]
    # trace_id 必须是 uuid4().hex（32 位十六进制）
    assert isinstance(trace, str) and len(trace) == 32
    uuid.UUID(trace)  # 非法 uuid 会抛异常


def test_unhandled_500_direct():
    resp = _call(handle_unhandled, RuntimeError("boom"))
    assert resp.status_code == 500
    assert _body(resp)["code"] == 500
    assert "trace_id" in _body(resp)["data"]


# ── 7. psycopg2 PoolError -> 503 ────────────────────────────────────────────
def test_db_pool_exhausted_503(client):
    r = client.get("/pool")
    assert r.status_code == 503
    body = r.json()
    assert body["code"] == 503
    assert body["data"]["retryable"] is True


def test_db_pool_exhausted_503_direct():
    resp = _call(database_pool_exhausted, psycopg2.pool.PoolError("x"))
    assert resp.status_code == 503
    assert _body(resp)["code"] == 503
