"""TASK-041/043/044/045: Auto-publish + retry + data collection + overseas pipeline."""
from __future__ import annotations

import ipaddress
import base64
import json
import os
import socket
import urllib.request
from urllib.parse import urlparse

from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def auto_publish_article(self, content_id: str, platform: str, credentials: dict | None = None,
                         record_id: str | None = None) -> dict:
    """TASK-041: Auto-publish content to target platform with adapter dispatch."""
    from app.db import connect, encode, new_id, row_to_dict

    db = connect()
    content = row_to_dict(db.execute("SELECT * FROM contents WHERE id = %s", (content_id,)).fetchone())
    db.close()
    if not content:
        return {"status": "error", "message": "content not found"}

    credentials = credentials or {}
    if not credentials:
        owner_db = connect()
        owner = owner_db.execute(
            "SELECT pm.user_id FROM project_members pm WHERE pm.project_id=%s AND pm.role='owner' LIMIT 1",
            (content["project_id"],),
        ).fetchone()
        owner_db.close()
        if owner:
            from app.services.publish_hub import get_platform_credentials
            credentials = get_platform_credentials(str(owner["user_id"]), platform) or {}
    body = content.get("body", {})
    body_text = (
        "\n".join(item.get("text", "") for item in body.get("content", []) if isinstance(item, dict))
        if isinstance(body, dict) else str(body)
    )
    from app.services.publish_gateway import PUBLISH_MODES, check_sensitive
    if platform not in PUBLISH_MODES:
        return {"status": "error", "message": "unknown platform"}
    safety = check_sensitive(body_text)
    if not safety["passed"]:
        return {"status": "blocked", "message": "content safety check failed", "blocked_words": safety["blocked_words"]}

    if platform == "wordpress":
        url = credentials.get("wp_url", "")
        wp_user = credentials.get("wp_user", "")
        wp_pass = credentials.get("wp_pass", "")
        result = _publish_to_wordpress(content.get("title", ""), body_text, url, wp_user, wp_pass)
    elif platform == "medium":
        token = credentials.get("medium_token", "")
        result = _publish_to_medium(content.get("title", ""), body_text, token)
    else:
        # Semi-auto: store as draft for manual review
        result = {"status": "draft", "url": "", "message": f"{platform} requires manual review"}

    # Update the queued record; direct task invocations create one for compatibility.
    db2 = connect()
    if record_id:
        db2.execute(
            "UPDATE publish_records SET status=%s, result=%s, error=%s, updated_at=now() WHERE id=%s",
            (result.get("status", "failed"), encode(result),
             result.get("message") if result.get("status") == "error" else None, record_id),
        )
    else:
        db2.execute(
            "INSERT INTO publish_records (id, content_id, platform, status, result) VALUES (%s,%s,%s,%s,%s)",
            (new_id(), content_id, platform, result.get("status", "failed"), encode(result)),
        )
    db2.commit()
    db2.close()

    if result.get("status") == "error" and self.request.retries < self.max_retries:
        raise self.retry(countdown=60 * (self.request.retries + 1))

    return {"status": result.get("status"), "platform": platform, "url": result.get("url", "")}


def _publish_to_medium(title: str, body: str, token: str) -> dict:
    """TASK-041: Publish to Medium."""
    medium_user_id = os.getenv("MEDIUM_USER_ID", "")
    if not token or not medium_user_id:
        return {"status": "error", "message": "Medium credentials are not configured"}
    url = f"https://api.medium.com/v1/users/{medium_user_id}/posts"
    payload = json.dumps({"title": title, "contentFormat": "markdown", "content": body, "publishStatus": "draft"}).encode()
    req = urllib.request.Request(url, data=payload, method="POST",
                                  headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return {"status": "draft_created", "url": data.get("data", {}).get("url", "")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _publish_to_wordpress(title: str, body: str, wp_url: str, wp_user: str, wp_pass: str) -> dict:
    """TASK-041: Publish to WordPress."""
    if not wp_url or not wp_user or not wp_pass:
        return {"status": "error", "message": "WordPress credentials are not configured"}
    if not _is_public_https_url(wp_url):
        return {"status": "error", "message": "WordPress URL must resolve to a public HTTPS host"}
    url = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
    payload = json.dumps({"title": title, "content": body, "status": "draft"}).encode()
    auth = base64.b64encode(f"{wp_user}:{wp_pass}".encode()).decode()
    req = urllib.request.Request(url, data=payload, method="POST",
                                  headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return {"status": "draft_created", "url": data.get("link", "")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _is_public_https_url(value: str) -> bool:
    """Reject local/private publish targets to prevent SSRF through WordPress settings."""
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    if parsed.hostname in {"localhost"} or parsed.hostname.endswith((".local", ".internal")):
        return False
    try:
        addresses = {result[4][0] for result in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)}
        return bool(addresses) and all(ipaddress.ip_address(address).is_global for address in addresses)
    except (OSError, ValueError):
        return False


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def collect_publish_data(self, content_id: str, platform: str) -> dict:
    """TASK-044: Collect real publish metrics from the database."""
    from app.db import connect, encode
    from datetime import datetime, timezone
    db = connect()
    where_clauses = ["platform = %s"]
    params = [platform]
    if content_id:
        where_clauses.append("content_id = %s")
        params.append(content_id)
    where = " AND ".join(where_clauses)
    row = db.execute(
        f"SELECT COUNT(*) as total, SUM((meta->>'reads')::int) as reads, "
        f"SUM((meta->>'likes')::int) as likes, SUM((meta->>'shares')::int) as shares, "
        f"SUM((meta->>'revenue')::float) as revenue "
        f"FROM published_posts WHERE {where}",
        tuple(params),
    ).fetchone()
    db.execute(
        "UPDATE publish_records SET result = result || %s, updated_at = now() WHERE platform = %s",
        (encode({"last_checked": datetime.now(timezone.utc).isoformat(),
                 "reads": int(row["reads"] or 0), "likes": int(row["likes"] or 0)}), platform),
    )
    db.commit(); db.close()
    return {"status": "ok", "platform": platform, "reads": int(row["reads"] or 0),
            "likes": int(row["likes"] or 0), "shares": int(row["shares"] or 0),
            "posts": int(row["total"] or 0)}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def publish_retry_handler(self, record_id: str) -> dict:
    """TASK-043: Retry failed publish attempts with exponential backoff."""
    from app.db import connect, row_to_dict, encode
    db = connect()
    record = row_to_dict(db.execute("SELECT * FROM publish_records WHERE id = %s", (record_id,)).fetchone())
    if not record:
        db.close()
        return {"status": "error", "message": "record not found"}
    content = row_to_dict(db.execute("SELECT * FROM contents WHERE id = %s", (record.get("content_id", ""),)).fetchone())
    db.close()
    if not content:
        return {"status": "error", "message": "content not found"}

    owner = connect()
    member = owner.execute(
        "SELECT pm.user_id FROM project_members pm WHERE pm.project_id=%s AND pm.role='owner' LIMIT 1",
        (content["project_id"],),
    ).fetchone()
    owner.close()
    from app.services.publish_hub import get_platform_credentials
    credentials = get_platform_credentials(str(member["user_id"]), record["platform"]) if member else {}
    result = auto_publish_article.run(
        record.get("content_id", ""), record.get("platform", ""), credentials or {}, record_id,
    )
    return {"status": result.get("status", "failed"), "retry_count": self.request.retries}


@celery_app.task(bind=True, max_retries=1)
def check_scheduled_publishes(self) -> dict:
    """Periodic task: check for due scheduled publishes and dispatch them."""
    from app.db import connect, encode
    from datetime import datetime, timezone
    db = connect()
    now = datetime.now(timezone.utc)
    due = db.execute(
        "SELECT * FROM publish_records WHERE status = 'scheduled' AND scheduled_at <= %s ORDER BY scheduled_at LIMIT 10",
        (now,),
    ).fetchall()
    db.close()
    dispatched = 0
    for record in due:
        rec = dict(record) if not isinstance(record, dict) else record
        try:
            result = auto_publish_article.delay(
                rec.get("content_id", ""), rec.get("platform", ""), None, rec["id"]
            )
            db2 = connect()
            db2.execute(
                "UPDATE publish_records SET status = 'submitted', meta = meta || %s WHERE id = %s",
                (encode({"dispatched_at": now.isoformat(), "celery_task_id": result.id}), rec["id"]),
            )
            db2.commit()
            db2.close()
            dispatched += 1
        except Exception:
            pass
    return {"status": "ok", "due_count": len(due), "dispatched": dispatched}
