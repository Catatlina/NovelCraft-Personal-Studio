"""Pure unit tests for ``app.core.circuit_breaker`` (P2-T9 / Q5).

Uses an in-memory fake Redis so no real Redis is required, and monkeypatches
``time`` to drive the half-open transition deterministically.
"""
from __future__ import annotations

import types

import pytest

import app.core.circuit_breaker as cb


class FakeRedis:
    """Minimal in-memory stand-in for the bits of redis-py we use."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, key: str):
        return self.data.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.data[key] = value
        return True

    def incr(self, key: str) -> int:
        self.data[key] = str(int(self.data.get(key, 0)) + 1)
        return int(self.data[key])

    def expire(self, key: str, t: int) -> bool:
        return True

    def delete(self, *keys: str) -> None:
        for k in keys:
            self.data.pop(k, None)


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def time(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


@pytest.fixture
def fake_redis(monkeypatch):
    fr = FakeRedis()
    monkeypatch.setattr(cb, "_get_redis", lambda: fr)
    return fr


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    # Replace the imported `time` module reference with our controllable clock.
    monkeypatch.setattr(cb, "time", c)
    return c


def test_closed_by_default(fake_redis):
    assert cb.circuit_breaker("deepseek") is True


def test_consecutive_failures_open(fake_redis):
    for _ in range(cb.THRESHOLD):
        cb.record_failure("deepseek")
    assert cb.circuit_breaker("deepseek") is False  # OPEN


def test_cooldown_then_half_open(fake_redis, clock):
    for _ in range(cb.THRESHOLD):
        cb.record_failure("deepseek")
    assert cb.circuit_breaker("deepseek") is False  # still within cooldown
    clock.advance(cb.COOLDOWN + 1)
    # Cooldown elapsed → HALF_OPEN admits a probe.
    assert cb.circuit_breaker("deepseek") is True


def test_half_open_probe_success_closes(fake_redis, clock):
    for _ in range(cb.THRESHOLD):
        cb.record_failure("deepseek")
    clock.advance(cb.COOLDOWN + 1)
    assert cb.circuit_breaker("deepseek") is True  # half-open probe
    cb.record_success("deepseek")
    assert cb.circuit_breaker("deepseek") is True  # CLOSED again


def test_half_open_probe_failure_reopens(fake_redis, clock):
    for _ in range(cb.THRESHOLD):
        cb.record_failure("deepseek")
    clock.advance(cb.COOLDOWN + 1)
    assert cb.circuit_breaker("deepseek") is True  # half-open probe 1
    cb.record_failure("deepseek")  # probe fails → reopen
    assert cb.circuit_breaker("deepseek") is False  # OPEN again


def test_scope_isolation(fake_redis):
    # Failures in one scope must not trip another scope.
    for _ in range(cb.THRESHOLD):
        cb.record_failure("deepseek", scope="project:AAA")
    assert cb.circuit_breaker("deepseek", scope="project:AAA") is False
    assert cb.circuit_breaker("deepseek", scope="global") is True
    assert cb.circuit_breaker("deepseek", scope="project:BBB") is True


def test_token_bucket_allows_up_to_rate(fake_redis, monkeypatch):
    monkeypatch.setattr(cb, "DEFAULT_TOKEN_RATE", 3)
    for _ in range(3):
        assert cb.acquire_provider_token("deepseek") is True
    assert cb.acquire_provider_token("deepseek") is False  # 4th rejected


def test_token_bucket_scope_isolation(fake_redis, monkeypatch):
    monkeypatch.setattr(cb, "DEFAULT_TOKEN_RATE", 1)
    assert cb.acquire_provider_token("deepseek", scope="project:AAA") is True
    assert cb.acquire_provider_token("deepseek", scope="project:AAA") is False
    # Different scope has its own bucket.
    assert cb.acquire_provider_token("deepseek", scope="project:BBB") is True


def test_redis_down_does_not_crash(fake_redis, monkeypatch):
    def _boom():
        raise RuntimeError("redis gone")

    monkeypatch.setattr(cb, "_get_redis", _boom)
    # Breaker fails open; token bucket fails open; record_* are no-ops.
    assert cb.circuit_breaker("deepseek") is True
    assert cb.acquire_provider_token("deepseek") is True
    cb.record_failure("deepseek")
    cb.record_success("deepseek")
