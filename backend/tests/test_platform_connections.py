from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient


def _auth():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"conn-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers


def test_platform_connection_specs_save_list_test_and_delete():
    client, headers = _auth()

    specs = client.get("/api/v1/platform-connections/specs", headers=headers)
    assert specs.status_code == 200
    assert "hotspot_xiaohongshu" in specs.json()["data"]
    assert "wordpress" in specs.json()["data"]

    missing = client.post("/api/v1/platform-connections", headers=headers,
                          json={"platform": "wordpress", "account_name": "blog", "credentials": {"wp_url": "https://example.com"}})
    assert missing.status_code == 422
    assert missing.json()["detail"]["code"] == "CONNECTION_REQUIRED_FIELDS_MISSING"

    saved = client.post("/api/v1/platform-connections", headers=headers, json={
        "platform": "wordpress",
        "account_name": "blog",
        "credentials": {"wp_url": "https://example.com", "wp_user": "admin", "wp_pass": "secret-pass"},
    })
    assert saved.status_code == 200
    account_id = saved.json()["data"]["account_id"]

    listed = client.get("/api/v1/platform-connections", headers=headers)
    assert listed.status_code == 200
    item = next(row for row in listed.json()["data"] if row["id"] == account_id)
    assert item["platform"] == "wordpress"
    assert item["missing_required"] == []
    assert "wp_pass" in item["configured_fields"]
    assert "secret-pass" not in json.dumps(item, ensure_ascii=False)

    test = client.post("/api/v1/platform-connections/wordpress/test", headers=headers)
    assert test.status_code == 200
    assert test.json()["data"]["status"] == "configured"

    deleted = client.delete(f"/api/v1/platform-connections/{account_id}", headers=headers)
    assert deleted.status_code == 200
    listed = client.get("/api/v1/platform-connections", headers=headers)
    assert account_id not in [row["id"] for row in listed.json()["data"]]


def test_hotspot_collector_uses_visual_connection(monkeypatch):
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"hotcfg-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["data"]["id"] if False else None

    # Save through public API so encryption/decryption path is covered.
    client.post("/api/v1/platform-connections", headers=headers, json={
        "platform": "hotspot_xiaohongshu",
        "account_name": "default",
        "credentials": {"url": "https://example.com/hot.json", "cookie": "sid=abc", "proxy": "http://127.0.0.1:10809"},
    })

    from app.services import hotspot_collector

    seen = {}
    proxies: list[str] = []

    class _Resp:
        headers = {"Content-Type": "application/json"}
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self):
            return b'{"items":[{"title":"XHS hot","score":99,"url":"https://example.com/u"}]}'

    class _Opener:
        def open(self, req, timeout=10):
            seen["url"] = req.full_url
            seen["cookie"] = req.headers.get("Cookie")
            return _Resp()

    def fake_opener(proxy_override: str = ""):
        seen["proxy"] = proxy_override
        proxies.append(proxy_override)
        return _Opener()

    monkeypatch.setattr(hotspot_collector, "_hotspot_opener", fake_opener)
    # Avoid noisy network for the built-in sources; we only assert configured xhs path.
    monkeypatch.setitem(hotspot_collector.HOTSPOT_SOURCES, "baidu", {"name": "百度", "url_env": "MISSING", "kind": "generic_json"})
    monkeypatch.setitem(hotspot_collector.HOTSPOT_SOURCES, "zhihu", {"name": "知乎", "url_env": "MISSING", "kind": "generic_json"})
    monkeypatch.setitem(hotspot_collector.HOTSPOT_SOURCES, "weibo", {"name": "微博", "url_env": "MISSING", "kind": "generic_json"})
    monkeypatch.setitem(hotspot_collector.HOTSPOT_SOURCES, "douyin", {"name": "抖音", "url_env": "MISSING", "kind": "generic_json"})
    monkeypatch.setitem(hotspot_collector.HOTSPOT_SOURCES, "x", {"name": "X", "url_env": "MISSING", "kind": "generic_json"})

    # Extract user id from token-authenticated connection by listing accounts.
    # The collector API itself normally passes user["id"].
    from app.core.security import decode_token
    uid = decode_token(token)["sub"]
    items, status = hotspot_collector.fetch_hotspots(user_id=uid)
    assert any(item["title"] == "XHS hot" for item in items)
    assert status["xiaohongshu"] == "ok"
    assert seen["url"] == "https://example.com/hot.json"
    assert seen["cookie"] == "sid=abc"
    assert "http://127.0.0.1:10809" in proxies
