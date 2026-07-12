"""Strict allow-list validation for user-selectable AI provider base URLs."""
from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit


DEFAULT_AI_HOSTS = {
    "api.deepseek.com",
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
}


def allowed_ai_hosts() -> set[str]:
    configured = {
        host.strip().lower().rstrip(".")
        for host in os.getenv("AI_API_BASE_HOST_ALLOWLIST", "").split(",")
        if host.strip()
    }
    return DEFAULT_AI_HOSTS | configured


def validate_ai_base_url(value: str) -> str:
    """Return a normalized HTTPS base URL or reject it before any key is attached."""
    parsed = urlsplit((value or "").strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host:
        raise ValueError("AI API Base URL must use HTTPS")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("AI API Base URL cannot contain credentials, query, or fragment")
    if parsed.port not in {None, 443}:
        raise ValueError("AI API Base URL only permits port 443")
    if host not in allowed_ai_hosts():
        raise ValueError(f"AI API host is not allowed: {host}")
    path = parsed.path or ""
    return urlunsplit(("https", host, path.rstrip("/"), "", ""))
