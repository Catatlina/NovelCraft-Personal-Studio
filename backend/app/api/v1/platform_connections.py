"""Visual, encrypted configuration for real platform/API connections."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.services.publish_hub import (
    delete_platform_account,
    get_platform_credentials,
    list_platform_accounts_with_config_status,
    register_platform_account,
)

router = APIRouter(prefix="/api/v1/platform-connections", tags=["platform-connections"])


CONNECTION_SPECS: dict[str, dict] = {
    # Hotspot sources
    "hotspot_baidu": {"category": "hotspot", "display_name": "百度热搜", "help": "公开源，通常无需配置；可填写 cookie/proxy 覆盖默认请求。", "fields": [
        {"key": "url", "label": "自定义 URL", "type": "url", "required": False},
        {"key": "history_url", "label": "历史归档 URL（支持 {date}）", "type": "url", "required": False},
        {"key": "cookie", "label": "Cookie", "type": "secret", "required": False},
        {"key": "proxy", "label": "HTTP 代理", "type": "url", "required": False},
    ]},
    "hotspot_zhihu": {"category": "hotspot", "display_name": "知乎热榜", "help": "公开 API 可能限流；必要时填写 cookie/proxy。", "fields": [
        {"key": "url", "label": "自定义 URL", "type": "url", "required": False},
        {"key": "history_url", "label": "历史归档 URL（支持 {date}）", "type": "url", "required": False},
        {"key": "cookie", "label": "Cookie", "type": "secret", "required": False},
        {"key": "proxy", "label": "HTTP 代理", "type": "url", "required": False},
    ]},
    "hotspot_weibo": {"category": "hotspot", "display_name": "微博热搜", "help": "公开接口可能需要 cookie。", "fields": [
        {"key": "url", "label": "自定义 URL", "type": "url", "required": False},
        {"key": "history_url", "label": "历史归档 URL（支持 {date}）", "type": "url", "required": False},
        {"key": "cookie", "label": "Cookie", "type": "secret", "required": False},
        {"key": "proxy", "label": "HTTP 代理", "type": "url", "required": False},
    ]},
    "hotspot_xiaohongshu": {"category": "hotspot", "display_name": "小红书热点源", "help": "请填合法授权的数据源 URL；不配置不伪造数据。", "fields": [
        {"key": "url", "label": "热点 JSON URL", "type": "url", "required": True},
        {"key": "history_url", "label": "历史归档 URL（支持 {date}）", "type": "url", "required": False},
        {"key": "cookie", "label": "Cookie/授权头", "type": "secret", "required": False},
        {"key": "proxy", "label": "HTTP 代理", "type": "url", "required": False},
    ]},
    "hotspot_douyin": {"category": "hotspot", "display_name": "抖音热点源", "help": "请填合法授权的数据源 URL；不配置不伪造数据。", "fields": [
        {"key": "url", "label": "热点 JSON URL", "type": "url", "required": True},
        {"key": "history_url", "label": "历史归档 URL（支持 {date}）", "type": "url", "required": False},
        {"key": "cookie", "label": "Cookie/授权头", "type": "secret", "required": False},
        {"key": "proxy", "label": "HTTP 代理", "type": "url", "required": False},
    ]},
    "hotspot_x": {"category": "hotspot", "display_name": "X / Twitter Trends", "help": "请填官方 API 或授权聚合源 URL。", "fields": [
        {"key": "url", "label": "Trends JSON URL", "type": "url", "required": True},
        {"key": "history_url", "label": "历史归档 URL（支持 {date}）", "type": "url", "required": False},
        {"key": "bearer_token", "label": "Bearer Token", "type": "secret", "required": False},
        {"key": "proxy", "label": "HTTP 代理", "type": "url", "required": False},
    ]},

    # Publishing accounts
    "wechat": {"category": "publish", "display_name": "微信公众号", "help": "可填写草稿 API/第三方授权信息；未配置时只生成草稿。", "fields": [
        {"key": "app_id", "label": "AppID", "type": "text", "required": False},
        {"key": "app_secret", "label": "AppSecret", "type": "secret", "required": False},
        {"key": "access_token", "label": "Access Token", "type": "secret", "required": False},
    ]},
    "toutiao": {"category": "publish", "display_name": "头条号", "fields": [
        {"key": "client_id", "label": "Client ID", "type": "text", "required": False},
        {"key": "client_secret", "label": "Client Secret", "type": "secret", "required": False},
        {"key": "access_token", "label": "Access Token", "type": "secret", "required": False},
    ]},
    "baijia": {"category": "publish", "display_name": "百家号", "fields": [
        {"key": "app_id", "label": "App ID", "type": "text", "required": False},
        {"key": "app_token", "label": "App Token", "type": "secret", "required": False},
    ]},
    "dayu": {"category": "publish", "display_name": "大鱼号", "fields": [
        {"key": "account_id", "label": "账号 ID", "type": "text", "required": False},
        {"key": "access_token", "label": "Access Token", "type": "secret", "required": False},
    ]},
    "xiaohongshu": {"category": "publish", "display_name": "小红书", "fields": [
        {"key": "account_id", "label": "账号 ID", "type": "text", "required": False},
        {"key": "cookie", "label": "Cookie/授权信息", "type": "secret", "required": False},
    ]},
    "douyin": {"category": "publish", "display_name": "抖音", "fields": [
        {"key": "client_key", "label": "Client Key", "type": "text", "required": False},
        {"key": "client_secret", "label": "Client Secret", "type": "secret", "required": False},
        {"key": "access_token", "label": "Access Token", "type": "secret", "required": False},
    ]},
    "wordpress": {"category": "publish", "display_name": "WordPress", "fields": [
        {"key": "wp_url", "label": "站点 URL", "type": "url", "required": True},
        {"key": "wp_user", "label": "用户名", "type": "text", "required": True},
        {"key": "wp_pass", "label": "应用密码", "type": "secret", "required": True},
    ]},
    "medium": {"category": "publish", "display_name": "Medium", "fields": [
        {"key": "medium_token", "label": "Integration Token", "type": "secret", "required": True},
    ]},
    "x": {"category": "publish", "display_name": "X / Twitter", "fields": [
        {"key": "bearer_token", "label": "Bearer Token", "type": "secret", "required": True},
    ]},
    "substack": {"category": "publish", "display_name": "Substack", "fields": [
        {"key": "api_url", "label": "API URL", "type": "url", "required": False},
        {"key": "api_key", "label": "API Key", "type": "secret", "required": False},
    ]},

    # Notifications / ops
    "telegram_alert": {"category": "ops", "display_name": "Telegram 告警", "fields": [
        {"key": "bot_token", "label": "Bot Token", "type": "secret", "required": True},
        {"key": "chat_id", "label": "Chat ID", "type": "text", "required": True},
    ]},
}


class ConnectionSave(BaseModel):
    platform: str
    account_name: str = Field(default="default", max_length=120)
    credentials: dict[str, str] = Field(default_factory=dict)


def _ok(data):
    return {"code": 0, "message": "ok", "data": data}


@router.get("/specs")
def specs(user: dict = Depends(get_current_user)):
    return _ok(CONNECTION_SPECS)


@router.get("")
def list_connections(user: dict = Depends(get_current_user)):
    return _ok(list_platform_accounts_with_config_status(user["id"], CONNECTION_SPECS))


@router.post("")
def save_connection(payload: ConnectionSave, user: dict = Depends(get_current_user)):
    if payload.platform not in CONNECTION_SPECS:
        raise HTTPException(422, f"unsupported platform: {payload.platform}")
    spec = CONNECTION_SPECS[payload.platform]
    allowed = {field["key"] for field in spec.get("fields", [])}
    credentials = {key: value for key, value in payload.credentials.items() if key in allowed and str(value).strip()}
    missing = [field["key"] for field in spec.get("fields", []) if field.get("required") and not credentials.get(field["key"])]
    if missing:
        raise HTTPException(422, {"code": "CONNECTION_REQUIRED_FIELDS_MISSING", "missing": missing})
    return _ok(register_platform_account(payload.platform, payload.account_name or "default", credentials, user_id=user["id"]))


@router.delete("/{account_id}")
def delete_connection(account_id: str, user: dict = Depends(get_current_user)):
    if not delete_platform_account(account_id, user["id"]):
        raise HTTPException(404, "connection not found")
    return _ok({"deleted": True})


@router.post("/{platform}/test")
def test_connection(platform: str, user: dict = Depends(get_current_user)):
    creds = get_platform_credentials(user["id"], platform)
    spec = CONNECTION_SPECS.get(platform)
    if not spec:
        raise HTTPException(422, f"unsupported platform: {platform}")
    if not creds:
        return _ok({"status": "missing", "message": "尚未配置"})
    required = [field["key"] for field in spec.get("fields", []) if field.get("required")]
    missing = [key for key in required if not str(creds.get(key, "")).strip()]
    if missing:
        return _ok({"status": "incomplete", "missing": missing})
    # Avoid performing writes or risky live logins here. The purpose is a safe
    # local readiness check; real publish/fetch calls will still fail explicitly.
    return _ok({"status": "configured", "configured_fields": [k for k, v in creds.items() if str(v).strip()]})
