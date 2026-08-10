from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.v7.quality import web_research as research_module
from app.v7.quality.web_research import WebResearchError, WebResearchService, render_web_research_guidance


def _settings(**overrides):
    values = {
        "web_research_provider": "tavily",
        "tavily_api_key": "tvly-test",
        "tavily_base_url": "https://api.tavily.com",
        "web_research_timeout_seconds": 3,
        "web_research_cache_ttl_seconds": 3600,
        "web_research_max_results": 2,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeEventRepo:
    def __init__(self, events=None):
        self.events = list(events or [])

    async def list_by_novel(self, *_args, **_kwargs):
        return self.events


class FakeEventBus:
    def __init__(self, events=None):
        self.event_repo = FakeEventRepo(events)
        self.published = []

    async def publish(self, *args, **kwargs):
        self.published.append((args, kwargs))


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return next(self.responses)


@pytest.mark.asyncio
async def test_off_mode_does_not_call_search_or_ai(monkeypatch):
    monkeypatch.setattr(research_module, "settings", _settings(tavily_api_key=""))
    bus = FakeEventBus()
    gateway = SimpleNamespace(generate_json=AsyncMock())
    service = WebResearchService(novel_id="novel-1", event_bus=bus, ai_gateway=gateway)

    result = await service.collect(chapter_number=1, quality_profile={"web_research_mode": "off"})

    assert result["status"] == "disabled"
    assert result["cards"] == []
    gateway.generate_json.assert_not_awaited()
    assert bus.published == []


@pytest.mark.asyncio
async def test_required_mode_without_key_fails_and_audits(monkeypatch):
    monkeypatch.setattr(research_module, "settings", _settings(tavily_api_key=""))
    bus = FakeEventBus()
    service = WebResearchService(
        novel_id="novel-1", event_bus=bus, ai_gateway=SimpleNamespace(generate_json=AsyncMock())
    )

    with pytest.raises(WebResearchError, match="TAVILY_API_KEY"):
        await service.collect(chapter_number=1, quality_profile={"web_research_mode": "required"})

    assert bus.published[-1][0][0] == "web_research.failed"
    assert bus.published[-1][1]["event_data"]["error_type"] == "WebResearchError"


@pytest.mark.asyncio
async def test_required_mode_searches_normalises_cards_and_persists_sources(monkeypatch):
    monkeypatch.setattr(research_module, "settings", _settings())
    client = FakeClient([
        FakeResponse(200, {"results": [{"url": "https://example.com/a", "title": "读者讨论", "content": "短摘要"}]}),
        FakeResponse(200, {"results": [{"url": "https://example.com/b", "title": "第二个讨论", "content": "第二条摘要"}]}),
    ])
    monkeypatch.setattr(research_module.httpx, "AsyncClient", lambda **_kwargs: client)
    gateway = SimpleNamespace(generate_json=AsyncMock(return_value={
        "data": {"cards": [{
            "label": "反差亮相",
            "usage_scene": "主角被低估后主动亮底牌",
            "emotion_effect": "让读者立刻获得反转快感",
            "avoid": "不要照搬任何原句",
        }]},
        "usage": {"tokens_input": 12, "tokens_output": 8, "cost": 0.01, "model": "test"},
    }))
    bus = FakeEventBus()
    result = await WebResearchService(novel_id="novel-1", event_bus=bus, ai_gateway=gateway).collect(
        chapter_number=2,
        quality_profile={"web_research_mode": "required", "genre": "都市", "subgenre": "都市系统"},
        plot_brief={"hook": "当众揭穿对手"},
    )

    assert result["status"] == "live"
    assert result["cards"][0]["label"] == "反差亮相"
    assert len(result["sources"]) == 2
    assert len(client.calls) == 2
    assert client.calls[0][1]["headers"]["Authorization"] == "Bearer tvly-test"
    assert bus.published[-1][0][0] == "web_research.completed"
    assert "usage" not in bus.published[-1][1]["event_data"]


@pytest.mark.asyncio
async def test_fresh_cache_skips_provider_and_returns_cached(monkeypatch):
    monkeypatch.setattr(research_module, "settings", _settings())
    queries = research_module.build_web_research_queries(
        quality_profile={"genre": "都市", "web_research_mode": "required"}, chapter_number=1
    )
    query_hash = research_module._query_hash(
        queries=queries, chapter_number=1, quality_profile={"genre": "都市", "web_research_mode": "required"}
    )
    event = SimpleNamespace(
        event_time=datetime.now(timezone.utc),
        event_data={
            "schema_version": "web-research-v1",
            "query_hash": query_hash,
            "cards": [{"label": "缓存卡", "usage_scene": "场景", "emotion_effect": "爽", "avoid": "别抄"}],
            "sources": [],
            "provider": "tavily",
        },
    )
    bus = FakeEventBus([event])
    gateway = SimpleNamespace(generate_json=AsyncMock())
    result = await WebResearchService(novel_id="novel-1", event_bus=bus, ai_gateway=gateway).collect(
        chapter_number=1,
        quality_profile={"genre": "都市", "web_research_mode": "required"},
    )

    assert result["status"] == "cached"
    assert result["cache_status"] == "hit"
    gateway.generate_json.assert_not_awaited()
    assert bus.published == []


@pytest.mark.asyncio
async def test_provider_http_failure_is_not_a_success(monkeypatch):
    monkeypatch.setattr(research_module, "settings", _settings())
    client = FakeClient([FakeResponse(503, {"error": "unavailable"})])
    monkeypatch.setattr(research_module.httpx, "AsyncClient", lambda **_kwargs: client)
    bus = FakeEventBus()
    with pytest.raises(WebResearchError, match="HTTP 503"):
        await WebResearchService(
            novel_id="novel-1", event_bus=bus, ai_gateway=SimpleNamespace(generate_json=AsyncMock())
        ).collect(chapter_number=1, quality_profile={"web_research_mode": "required"})
    assert bus.published[-1][0][0] == "web_research.failed"


def test_render_guidance_is_original_card_only():
    text = render_web_research_guidance({
        "status": "live",
        "cards": [{"label": "反差亮相", "usage_scene": "打脸", "emotion_effect": "兴奋", "avoid": "不要复制"}],
    })
    assert "反差亮相" in text
    assert "禁止复制原句" in text
    assert "https://" not in text


def test_query_builder_does_not_exfiltrate_outline_text():
    queries = research_module.build_web_research_queries(
        quality_profile={"genre": "都市", "web_research_mode": "required"},
        chapter_number=1,
        outline="这是用户创作圣经中的秘密人物和未公开设定",
    )
    assert all("秘密人物" not in query and "未公开设定" not in query for query in queries)
