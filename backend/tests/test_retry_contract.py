"""P1-T1 重试 / 429 契约测试 (T03)。

直接验证 ``app.core.retry`` 的 ``with_provider_retry`` 与 ``RetryPolicy``：
  * 指数退避并在 cap 处封顶；
  * ``transport_exc`` / ``rate_limit_exc`` 分别走各自策略；
  * ``no_retry_exc`` 立即原样重抛（不重试、不触发 final）；
  * ``on_final_failure`` 仅在**终态耗尽后**触发一次 —— 这是 T03 的核心不变量：
    瞬时 429/5xx 抖动绝不会提前把熔断器的 ``record_failure`` 置为打开。

本文件不依赖数据库 / Redis。网关 ``gateway.complete`` 正是用
``with_provider_retry(..., on_final_failure=lambda exc: record_failure(provider))``
包装 provider 调用，所以本测试即是对该协同契约的最小验证。

运行：``pytest backend/tests/test_retry_contract.py``
"""
from __future__ import annotations

import pytest

from app.core.retry import (
    RATE_LIMIT_POLICY,
    TRANSPORT_POLICY,
    RetryPolicy,
    with_provider_retry,
)
from app.gateway import ProviderRateLimitError


def test_retry_policy_backoff_and_cap():
    p = RetryPolicy(base=1.0, factor=2.0, cap=30.0, max_retries=3)
    assert p.backoff_seconds(1) == 1.0
    assert p.backoff_seconds(2) == 2.0
    assert p.backoff_seconds(3) == 4.0
    # 超过 cap 一律封顶
    assert p.backoff_seconds(10) == 30.0
    assert p.backoff_seconds(100) == 30.0


def test_retry_policy_presets():
    # 429 策略：base=1, factor=2, cap=30
    assert RATE_LIMIT_POLICY.base == 1.0
    assert RATE_LIMIT_POLICY.cap == 30.0
    assert RATE_LIMIT_POLICY.max_retries == 3
    # 传输策略：base=0.5, factor=2, cap=10
    assert TRANSPORT_POLICY.base == 0.5
    assert TRANSPORT_POLICY.cap == 10.0
    assert TRANSPORT_POLICY.max_retries == 3


def test_success_returns_value_no_retry_no_final():
    calls: list[str] = []

    @with_provider_retry(
        transport_exc=(ValueError,),
        sleep=lambda s: calls.append(f"sleep:{s}"),
        on_final_failure=lambda e: calls.append("FINAL"),
    )
    def ok_fn():
        return "done"

    assert ok_fn() == "done"
    assert calls == []  # 一次成功：无 sleep、无 final


def test_transport_failure_retries_then_final_failure_once():
    sleeps: list[float] = []
    finals: list[object] = []

    policy = RetryPolicy(base=1.0, factor=2.0, cap=30.0, max_retries=3)

    @with_provider_retry(
        transport_exc=(ValueError,),
        transport_policy=policy,
        sleep=lambda s: sleeps.append(s),
        on_final_failure=lambda e: finals.append(e),
    )
    def flaky():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        flaky()

    # max_retries=3 => 3 次退避（1,2,4）+ 终态触发 1 次 on_final_failure
    assert sleeps == [1.0, 2.0, 4.0]
    assert len(finals) == 1  # 关键：仅在耗尽后触发一次
    assert isinstance(finals[0], ValueError)


def test_on_final_failure_not_called_on_intermediate_retry():
    """瞬时失败期间绝对不能调用 on_final_failure（否则会误触熔断器）。"""
    finals: list[object] = []
    attempts = {"n": 0}

    policy = RetryPolicy(base=0.0, factor=2.0, cap=10.0, max_retries=3)

    @with_provider_retry(
        transport_exc=(ValueError,),
        transport_policy=policy,
        sleep=lambda s: None,
        on_final_failure=lambda e: finals.append(e),
    )
    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:  # 前两次瞬败，第三次成功
            raise ValueError("transient")
        return "recovered"

    assert flaky() == "recovered"
    assert finals == []  # 中途重试成功 => 永不触发 final
    assert attempts["n"] == 3


def test_no_retry_exc_reraised_immediately():
    sleeps: list[float] = []
    finals: list[object] = []

    @with_provider_retry(
        transport_exc=(ValueError,),
        no_retry_exc=(KeyError,),
        sleep=lambda s: sleeps.append(s),
        on_final_failure=lambda e: finals.append(e),
    )
    def flaky():
        raise KeyError("schema contract violation")

    with pytest.raises(KeyError):
        flaky()

    assert sleeps == []   # 不重试
    assert finals == []   # 不触发 final


def test_rate_limit_uses_own_policy():
    sleeps: list[float] = []

    policy = RetryPolicy(base=1.0, factor=2.0, cap=30.0, max_retries=2)

    @with_provider_retry(
        rate_limit_exc=(ProviderRateLimitError,),
        rate_limit_policy=policy,
        sleep=lambda s: sleeps.append(s),
    )
    def flaky():
        raise ProviderRateLimitError("429")

    with pytest.raises(ProviderRateLimitError):
        flaky()

    # base=1, factor=2 => 1, 2
    assert sleeps == [1.0, 2.0]


def test_unknown_exception_not_retried():
    sleeps: list[float] = []

    @with_provider_retry(
        transport_exc=(ValueError,),
        sleep=lambda s: sleeps.append(s),
    )
    def flaky():
        raise RuntimeError("unexpected")

    with pytest.raises(RuntimeError):
        flaky()

    assert sleeps == []  # 不在配置内的异常类型立即上抛
