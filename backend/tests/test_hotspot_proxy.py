"""BUG-001 follow-up: hotspot fetches can be routed through HOTSPOT_HTTP_PROXY
(scoped to hotspots only). Verifies the opener is proxy-configured when the env is
set and plain otherwise — without needing a live proxy."""
from __future__ import annotations

import urllib.request

from app.services.hotspot_collector import _hotspot_opener


def _proxy_handler(opener):
    return next((h for h in opener.handlers if isinstance(h, urllib.request.ProxyHandler)), None)


def test_no_proxy_env_does_not_force_our_proxy(monkeypatch):
    # Without the env we return a default opener (which may still honor system
    # proxies) — but it must never carry our explicit override.
    monkeypatch.delenv("HOTSPOT_HTTP_PROXY", raising=False)
    handler = _proxy_handler(_hotspot_opener())
    proxies = handler.proxies if handler else {}
    assert "http://127.0.0.1:10809" not in proxies.values()


def test_proxy_env_configures_http_and_https(monkeypatch):
    monkeypatch.setenv("HOTSPOT_HTTP_PROXY", "http://127.0.0.1:10809")
    handler = _proxy_handler(_hotspot_opener())
    assert handler is not None
    assert handler.proxies.get("http") == "http://127.0.0.1:10809"
    assert handler.proxies.get("https") == "http://127.0.0.1:10809"
