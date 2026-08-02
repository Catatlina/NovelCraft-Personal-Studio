"""Shared provider transport used by the V6 and V7 gateway adapters.

The application still has synchronous (V6) and asynchronous (V7) callers,
but provider HTTP semantics must not drift between them.  This module owns the
OpenAI-compatible DeepSeek request shape, timeout behaviour and response
normalisation.  Ledger, prompt provenance and budget accounting live in
``ai_runtime`` so both adapters close the same execution contract.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Iterator

import httpx


class UnifiedGatewayError(RuntimeError):
    """A provider transport failure at the shared gateway boundary."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ProviderResponse:
    """Provider output in the one shape consumed by both runtime adapters."""

    content: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str


class UnifiedAIGateway:
    """Canonical OpenAI-compatible provider transport.

    V6 calls :meth:`complete_sync` or :meth:`stream_sync`; V7 calls
    :meth:`complete_async`.  The caller remains responsible for its local
    retry/circuit-breaker policy and for persisting the returned usage in the
    shared execution ledger.
    """

    def __init__(
        self,
        *,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 180.0,
    ):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = float(timeout)

    def _payload(
        self,
        prompt: str,
        *,
        system_prompt: str,
        history: list[dict[str, str]] | None,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> dict[str, Any]:
        if self.provider != "deepseek":
            raise UnifiedGatewayError(
                f"unsupported shared provider transport: {self.provider}"
            )
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    @staticmethod
    def _response(payload: dict[str, Any]) -> ProviderResponse:
        try:
            choice = payload["choices"][0]
            message = choice["message"]
            content = str(message.get("content") or "")
        except (KeyError, IndexError, TypeError) as exc:
            raise UnifiedGatewayError("provider response has no usable choice") from exc
        if not content.strip():
            raise UnifiedGatewayError("provider returned empty content")
        usage = payload.get("usage") or {}
        return ProviderResponse(
            content=content,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            finish_reason=str(choice.get("finish_reason") or "stop"),
        )

    def complete_sync(
        self,
        prompt: str,
        *,
        system_prompt: str,
        history: list[dict[str, str]] | None = None,
        temperature: float,
        max_tokens: int,
        json_mode: bool = True,
    ) -> ProviderResponse:
        """Send one synchronous provider request for V6 workers."""
        if not self.api_key:
            raise UnifiedGatewayError("DEEPSEEK_API_KEY is not configured")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(
                self._payload(
                    prompt,
                    system_prompt=system_prompt,
                    history=history,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                )
            ).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise UnifiedGatewayError(
                f"provider http error {exc.code}", status_code=exc.code
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise UnifiedGatewayError(f"provider request failed: {exc}") from exc
        return self._response(payload)

    def stream_sync(
        self,
        prompt: str,
        *,
        system_prompt: str,
        history: list[dict[str, str]] | None = None,
        temperature: float,
        max_tokens: int,
        usage_out: dict[str, int] | None = None,
    ) -> Iterator[str]:
        """Yield text deltas from the same transport used by V6 completion.

        Streaming used to construct a second DeepSeek request in
        ``app.gateway``.  Keeping SSE parsing here makes auth, URL, timeout,
        message shape and usage handling identical for both V6 modes and V7.
        """
        if not self.api_key:
            raise UnifiedGatewayError("DEEPSEEK_API_KEY is not configured")
        payload = self._payload(
            prompt,
            system_prompt=system_prompt,
            history=history,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=False,
        )
        payload.update({"stream": True, "stream_options": {"include_usage": True}})
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    usage = chunk.get("usage") or {}
                    if usage_out is not None and usage:
                        usage_out.update(
                            {
                                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                                "completion_tokens": int(usage.get("completion_tokens") or 0),
                            }
                        )
                    choices = chunk.get("choices") or []
                    if choices:
                        delta = (choices[0].get("delta") or {}).get("content")
                        if delta:
                            yield str(delta)
        except urllib.error.HTTPError as exc:
            raise UnifiedGatewayError(
                f"provider http error {exc.code}", status_code=exc.code
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise UnifiedGatewayError(f"provider stream failed: {exc}") from exc

    async def complete_async(
        self,
        prompt: str,
        *,
        system_prompt: str,
        history: list[dict[str, str]] | None = None,
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
        client_factory: Callable[..., Any] | None = None,
    ) -> ProviderResponse:
        """Send one asynchronous provider request for V7 engines."""
        if not self.api_key:
            raise UnifiedGatewayError("DEEPSEEK_API_KEY is not configured")
        client_type = client_factory or httpx.AsyncClient
        timeout = httpx.Timeout(
            connect=self.timeout,
            read=self.timeout,
            write=self.timeout,
            pool=self.timeout,
        )
        async with client_type(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=self._payload(
                        prompt,
                        system_prompt=system_prompt,
                        history=history,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                ),
            )
            response.raise_for_status()
            return self._response(response.json())
