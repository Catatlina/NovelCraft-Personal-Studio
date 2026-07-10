"""M4: Publishing gateway — multi-platform publishing with 3 modes."""
from __future__ import annotations

import os

from app.db import connect, encode, new_id

PUBLISH_MODES = {
    "medium": {"mode": "auto", "api": True},
    "substack": {"mode": "auto", "api": True},
    "twitter": {"mode": "auto", "api": True},
    "wordpress": {"mode": "auto", "api": True},
    "wechat": {"mode": "semi", "api": False},
    "toutiao": {"mode": "semi", "api": False},
    "xiaohongshu": {"mode": "semi", "api": False},
    "zhihu": {"mode": "semi", "api": False},
    "baijia": {"mode": "semi", "api": False},
    "dayu": {"mode": "semi", "api": False},
    "wangyi": {"mode": "semi", "api": False},
    "royalroad": {"mode": "auto", "api": True},
    "webnovel": {"mode": "semi", "api": False},
    "scribblehub": {"mode": "auto", "api": True},
    "kdp": {"mode": "manual", "api": False},
}


def publish_content(content_id: str, platform: str, mode: str | None = None) -> dict:
    """Queue content for publishing to a platform."""
    pub_config = PUBLISH_MODES.get(platform)
    if not pub_config:
        return {"error": f"unknown platform: {platform}"}

    actual_mode = mode or pub_config["mode"]
    if actual_mode == "auto" and platform in ("wechat","toutiao","xiaohongshu","zhihu","baijia"):
        return {"error": f"auto-publish not allowed for {platform} without explicit consent"}

    db = connect()
    pid = new_id()
    db.execute(
        """INSERT INTO publish_records (id, content_id, platform, mode, status)
           VALUES (%s, %s, %s, %s, %s)""",
        (pid, content_id, platform, actual_mode, "pending"),
    )
    db.commit()
    db.close()
    return {"publish_id": pid, "platform": platform, "mode": actual_mode, "status": "pending"}


def list_publish_records(content_id: str | None = None, project_ids: list[str] | None = None) -> list[dict]:
    db = connect()
    if content_id:
        rows = db.execute(
            "SELECT * FROM publish_records WHERE content_id = %s ORDER BY created_at DESC", (content_id,)
        ).fetchall()
    elif project_ids:
        rows = db.execute(
            """
            SELECT pr.* FROM publish_records pr
            JOIN contents c ON pr.content_id = c.id
            WHERE c.project_id = ANY(%s::uuid[])
            ORDER BY pr.created_at DESC LIMIT 50
            """,
            (project_ids,),
        ).fetchall()
    else:
        rows = []
    db.close()
    return [dict(r) for r in rows]


def record_metrics(content_id: str, platform: str, data: dict) -> dict:
    """Record data reflow metrics."""
    db = connect()
    mid = new_id()
    db.execute(
        """INSERT INTO metrics (id, content_id, platform, date, views, likes, favorites, comments, shares, revenue)
           VALUES (%s,%s,%s,CURRENT_DATE,%s,%s,%s,%s,%s,%s)
           ON CONFLICT(content_id, platform, date) DO UPDATE SET
           views=metrics.views+EXCLUDED.views, likes=metrics.likes+EXCLUDED.likes""",
        (mid, content_id, platform, data.get("views",0), data.get("likes",0),
         data.get("favorites",0), data.get("comments",0), data.get("shares",0), data.get("revenue",0)),
    )
    db.commit()
    db.close()
    return {"metric_id": mid, "status": "recorded"}


SENSITIVE_WORDS_BASE = [
    "敏感词1", "敏感词2", "违禁内容", "政治敏感", "色情", "暴力恐怖",
    "赌博", "毒品", "枪支", "诈骗", "传销", "邪教",
]


def check_sensitive(text: str) -> dict:
    """Check text against sensitive word list."""
    db = connect()
    words = db.execute("SELECT word FROM sensitive_words").fetchall()
    db.close()
    blocked = []
    for w in words:
        if w["word"] in text:
            blocked.append(w["word"])
    # Also check base list
    for w in SENSITIVE_WORDS_BASE:
        if w in text and w not in blocked:
            blocked.append(w)
    return {"passed": len(blocked) == 0, "blocked_words": blocked, "count": len(blocked)}


# M4: Publish adapters — platform-specific publishing logic
class PublishAdapter:
    """Base class for platform-specific publishing."""
    platform_key: str = ""

    def publish(self, content: dict) -> dict:
        raise NotImplementedError

    def check_credentials(self) -> bool:
        return False


class ManualAdapter(PublishAdapter):
    """Manual/semi-auto platforms — user copies content manually."""
    def publish(self, content: dict) -> dict:
        return {"mode": "manual", "status": "ready_for_copy", "content_preview": str(content.get("title", ""))[:200]}


class WechatAdapter(ManualAdapter):
    platform_key = "wechat"


class MediumAdapter(PublishAdapter):
    platform_key = "medium"

    def publish(self, content: dict) -> dict:
        token = os.getenv("MEDIUM_TOKEN", "")
        if not token:
            return {"mode": "manual", "status": "no_credentials", "hint": "Set MEDIUM_TOKEN env var"}
        return {"mode": "auto", "status": "pending", "platform": "medium"}


class WordPressAdapter(PublishAdapter):
    platform_key = "wordpress"

    def publish(self, content: dict) -> dict:
        wp_url = os.getenv("WORDPRESS_URL", "")
        wp_user = os.getenv("WORDPRESS_USER", "")
        if not wp_url or not wp_user:
            return {"mode": "manual", "status": "no_credentials"}
        return {"mode": "auto", "status": "pending", "platform": "wordpress"}


ADAPTERS: dict[str, PublishAdapter] = {
    "wechat": WechatAdapter(),
    "medium": MediumAdapter(),
    "wordpress": WordPressAdapter(),
    "toutiao": ManualAdapter(),
    "xiaohongshu": ManualAdapter(),
    "zhihu": ManualAdapter(),
    "baijia": ManualAdapter(),
    "dayu": ManualAdapter(),
    "wangyi": ManualAdapter(),
    "substack": ManualAdapter(),
    "twitter": ManualAdapter(),
    "royalroad": ManualAdapter(),
    "webnovel": ManualAdapter(),
    "scribblehub": ManualAdapter(),
    "kdp": ManualAdapter(),
}


def execute_publish(publish_id: str, content: dict, platform: str) -> dict:
    """Execute actual publishing via platform adapter."""
    adapter = ADAPTERS.get(platform, ManualAdapter())
    result = adapter.publish(content)
    db = connect()
    db.execute(
        "UPDATE publish_records SET status = %s, result = %s, updated_at = now() WHERE id = %s",
        (result.get("status", "unknown"), encode(result), publish_id),
    )
    db.commit()
    db.close()
    return result
