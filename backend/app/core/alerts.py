"""Alerting — Telegram notifications for critical events."""
from __future__ import annotations

import os
import urllib.request
import json

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send_alert(message: str, level: str = "warning") -> bool:
    """Send alert to Telegram. Returns True if sent, False if not configured."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    prefix = {"warning": "⚠️", "error": "🚨", "info": "ℹ️"}.get(level, "⚠️")
    text = f"{prefix} *NovelCraft Alert* [{level}]\n{message}"

    try:
        body = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def alert_budget(project_id: str, scope: str, spent: float, limit: float) -> None:
    send_alert(f"预算触顶：项目 `{project_id[:8]}…` {scope} ¥{spent:.2f}/¥{limit:.2f}", "warning")


def alert_provider_error(task_type: str, error: str) -> None:
    send_alert(f"Provider 错误：`{task_type}` — {error[:200]}", "error")


def alert_login_locked(email_fingerprint: str) -> None:
    send_alert(f"登录失败次数超限：账号指纹 `{email_fingerprint}` 已锁定 15 分钟", "warning")


def alert_task_failed(run_id: str, node_key: str, error: str) -> None:
    send_alert(f"任务失败：run `{run_id[:8]}…` node `{node_key}` — {error[:200]}", "error")


def alert_backup_failed(error: str) -> None:
    send_alert(f"备份失败：{error[:200]}", "error")
