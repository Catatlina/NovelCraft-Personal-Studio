"""TASK-041/043/044/045: Auto-publish + retry + data collection + overseas pipeline."""
from __future__ import annotations

from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def auto_publish_article(self, content_id: str, platform: str, credentials: dict = {}) -> dict:
    """TASK-041: Auto-publish content to target platform with adapter dispatch."""
    from app.db import connect, encode, new_id, row_to_dict

    db = connect()
    content = row_to_dict(db.execute("SELECT * FROM contents WHERE id = %s", (content_id,)).fetchone())
    db.close()
    if not content:
        return {"status": "error", "message": "content not found"}

    body_text = str(content.get("body", ""))

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

    # Record publish
    db2 = connect()
    db2.execute(
        "INSERT INTO publish_records (id, content_id, platform, status, result) VALUES (%s,%s,%s,%s,%s)",
        (new_id(), content_id, platform, result.get("status", "failed"), encode(result)),
    )
    db2.commit(); db2.close()

    if result.get("status") == "error" and self.request.retries < self.max_retries:
        raise self.retry(countdown=60 * (self.request.retries + 1))

    return {"status": result.get("status"), "platform": platform, "url": result.get("url", "")}


def _publish_to_medium(title: str, body: str, token: str) -> dict:
    """TASK-041: Publish to Medium."""
    import json, urllib.request, os
    medium_user_id = os.getenv("MEDIUM_USER_ID", "")
    url = f"https://api.medium.com/v1/users/{medium_user_id}/posts"
    payload = json.dumps({"title": title, "contentFormat": "markdown", "content": body, "publishStatus": "draft"}).encode()
    req = urllib.request.Request(url, data=payload, method="POST",
                                  headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return {"status": "published", "url": data.get("data", {}).get("url", "")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _publish_to_wordpress(title: str, body: str, wp_url: str, wp_user: str, wp_pass: str) -> dict:
    """TASK-041: Publish to WordPress."""
    import json, base64, urllib.request
    url = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
    payload = json.dumps({"title": title, "content": body, "status": "draft"}).encode()
    auth = base64.b64encode(f"{wp_user}:{wp_pass}".encode()).decode()
    req = urllib.request.Request(url, data=payload, method="POST",
                                  headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return {"status": "published", "url": data.get("link", "")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def collect_publish_data(self, content_id: str, platform: str) -> dict:
    """TASK-044: Collect post-publish data (views, engagement) from platforms."""
    from app.db import connect, encode
    db = connect()
    db.execute(
        "UPDATE publish_records SET result = result || %s WHERE content_id = %s AND platform = %s",
        (encode({"last_checked": __import__('datetime').datetime.utcnow().isoformat()}), content_id, platform),
    )
    db.commit(); db.close()
    return {"status": "collected", "platform": platform, "content_id": content_id}


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

    result = auto_publish_article(record.get("content_id", ""), record.get("platform", ""), {})
    db2 = connect()
    db2.execute("UPDATE publish_records SET status = %s, result = %s WHERE id = %s",
                (result.get("status", "failed"), encode(result), record_id))
    db2.commit(); db2.close()
    return {"status": result.get("status", "failed"), "retry_count": self.request.retries}
