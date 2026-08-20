"""Multi-model provider interface — Claude, OpenAI, Gemini support."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


# P3-T3: 统一可配的 provider 请求超时（秒）。默认 60s；可通过 PROVIDER_TIMEOUT 调整。
PROVIDER_TIMEOUT = int(os.getenv("PROVIDER_TIMEOUT", "60"))


def _request_overrides() -> tuple[str, str, str]:
    """Per-request BYOK overrides from frontend headers.

    Kept inside this module as a lazy import to avoid gateway/provider import
    cycles. Environment variables remain the source for workers and scheduled
    jobs; browser BYOK is for interactive requests only.
    """
    try:
        from app.gateway import _request_api_key, _request_api_base_url, _request_model
        return (_request_api_key.get() or "", _request_api_base_url.get() or "", _request_model.get() or "")
    except Exception:
        return "", "", ""


def call_claude(prompt: str, model: str = "claude-sonnet-4-20250514", params: dict | None = None) -> dict:
    """Call Claude API. Returns (output_dict, prompt_tokens, completion_tokens)."""
    override_key, override_url, override_model = _request_overrides()
    api_key = override_key or os.getenv("CLAUDE_API_KEY", "")
    if not api_key:
        raise RuntimeError("CLAUDE_API_KEY not configured")
    model = override_model or model

    body = {
        "model": model,
        "max_tokens": params.get("max_tokens", 4096) if params else 4096,
        "messages": [
            {"role": "user", "content": "只输出合法JSON，不要任何额外文本。\n" + prompt},
        ],
    }
    req = urllib.request.Request(
        override_url or os.getenv("CLAUDE_API_URL", "https://api.anthropic.com/v1/messages"),
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=PROVIDER_TIMEOUT) as r:
        payload = json.loads(r.read())
    text = payload["content"][0]["text"]
    usage = payload.get("usage", {})
    return json.loads(text), usage.get("input_tokens", 0), usage.get("output_tokens", 0)


def call_openai(prompt: str, model: str = "gpt-4o", params: dict | None = None) -> dict:
    """Call OpenAI API."""
    override_key, override_url, override_model = _request_overrides()
    api_key = override_key or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    model = override_model or model

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "只输出合法JSON。"},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": (params or {}).get("temperature", 0.7),
    }
    req = urllib.request.Request(
        override_url or os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions"),
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=PROVIDER_TIMEOUT) as r:
        payload = json.loads(r.read())
    content = payload["choices"][0]["message"]["content"]
    usage = payload.get("usage", {})
    return json.loads(content), usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


def call_doubao(prompt: str, model: str = "", params: dict | None = None) -> dict:
    """Call Doubao/Volcengine Ark through its OpenAI-compatible API.

    Ark model ids are endpoint ids, so an empty default is intentional: a real
    route must provide ``DOUBAO_MODEL`` or a model value.  Missing credentials
    never fall back to a local or fabricated response.
    """
    override_key, override_url, override_model = _request_overrides()
    api_key = override_key or os.getenv("DOUBAO_API_KEY", "")
    model = override_model or model or os.getenv("DOUBAO_MODEL", "")
    if not api_key:
        raise RuntimeError("DOUBAO_API_KEY not configured")
    if not model:
        raise RuntimeError("DOUBAO_MODEL not configured")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "只输出合法JSON。"},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": (params or {}).get("temperature", 0.7),
    }
    req = urllib.request.Request(
        override_url or os.getenv(
            "DOUBAO_API_URL",
            os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3") + "/chat/completions",
        ),
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=PROVIDER_TIMEOUT) as r:
        payload = json.loads(r.read())
    content = payload["choices"][0]["message"]["content"]
    usage = payload.get("usage", {})
    return json.loads(content), usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


def call_gemini(prompt: str, model: str = "gemini-2.0-flash", params: dict | None = None) -> dict:
    """Call Gemini API."""
    override_key, override_url, override_model = _request_overrides()
    api_key = override_key or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")
    model = override_model or model

    body = {
        "contents": [{"parts": [{"text": "只输出合法JSON。\n" + prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }
    req = urllib.request.Request(
        override_url or os.getenv("GEMINI_API_URL", f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"),
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    with urllib.request.urlopen(req, timeout=PROVIDER_TIMEOUT) as r:
        payload = json.loads(r.read())
    text = payload["candidates"][0]["content"]["parts"][0]["text"]
    usage = payload.get("usageMetadata", {})
    return json.loads(text), usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0)


PROVIDERS = {
    "deepseek": None,  # Handled directly in gateway
    "claude": call_claude,
    "openai": call_openai,
    "gemini": call_gemini,
    "doubao": call_doubao,
}


# ═══ LLMProvider 抽象接口 (§9.1) ══════════════════════════════════════════════
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Concrete implementations must implement ``complete`` which returns a dict
    with at minimum a top-level JSON-serializable output.  The gateway calls
    ``provider.complete(task_type, prompt, model, params)`` instead of writing
    provider-specific code inline.
    """

    @abstractmethod
    def complete(self, task_type: str, prompt: str, model: str,
                 params: dict[str, Any] | None = None,
                 project_id: str | None = None) -> tuple[dict, int, int]:
        """Send a prompt and return (parsed_output, prompt_tokens, completion_tokens).

        Raises:
            ProviderError on transport/auth failures.
            OutputValidationError on malformed responses.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'deepseek', 'claude')."""
        ...

    @property
    def default_model(self) -> str:
        """Default model if none specified in params."""
        return ""


class DeepSeekProvider(LLMProvider):
    """DeepSeek implementation — delegates to the existing _deepseek_complete in gateway."""

    def __init__(self):
        # Lazy import to avoid circular dependency
        self._impl = None

    def _get_impl(self):
        if self._impl is None:
            from app.gateway import _deepseek_complete
            self._impl = _deepseek_complete
        return self._impl

    def complete(self, task_type: str, prompt: str, model: str,
                 params: dict[str, Any] | None = None,
                 project_id: str | None = None) -> tuple[dict, int, int]:
        impl = self._get_impl()
        parsed, pt, ct = impl(task_type, prompt, model, params or {})
        return parsed, pt, ct

    @property
    def name(self) -> str:
        return "deepseek"

    @property
    def default_model(self) -> str:
        return "deepseek-chat"


# Provider registry (ABC-based)
PROVIDER_REGISTRY: dict[str, LLMProvider] = {
    "deepseek": DeepSeekProvider(),
}


def get_provider(name: str) -> LLMProvider:
    """Get a registered LLMProvider by name."""
    p = PROVIDER_REGISTRY.get(name)
    if not p:
        raise ValueError(f"Unknown provider: {name}. Registered: {list(PROVIDER_REGISTRY)}")
    return p
