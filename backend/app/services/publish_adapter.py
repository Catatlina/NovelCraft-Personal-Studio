"""M4: Publish adapter — automated platform publishing."""
from __future__ import annotations

import os
import urllib.request
import json

from app.db import connect, encode


def publish_to_medium(content_id: str, content: dict, token: str) -> dict:
    """TASK-041: Publish to Medium via their API."""
    url = f"https://api.medium.com/v1/users/{os.getenv('MEDIUM_USER_ID','')}/posts"
    body = {
        "title": content.get("title", ""),
        "contentFormat": "markdown",
        "content": str(content.get("body", "")),
        "publishStatus": "draft",
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                  headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            db = connect()
            db.execute("UPDATE publish_records SET status=%s, result=%s WHERE content_id=%s AND platform='medium'",
                       ("published", encode(result), content_id))
            db.commit(); db.close()
            return {"status": "published", "url": result.get("data", {}).get("url", "")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def publish_to_wordpress(content_id: str, content: dict, wp_url: str, wp_user: str, wp_pass: str) -> dict:
    """TASK-041: Publish to WordPress REST API."""
    url = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
    body = {
        "title": content.get("title", ""),
        "content": str(content.get("body", "")),
        "status": "draft",
    }
    auth = f"{wp_user}:{wp_pass}"
    import base64
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                  headers={"Authorization": f"Basic {base64.b64encode(auth.encode()).decode()}",
                                           "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            db = connect()
            db.execute("UPDATE publish_records SET status=%s, result=%s WHERE content_id=%s AND platform='wordpress'",
                       ("published", encode(result), content_id))
            db.commit(); db.close()
            return {"status": "published", "url": result.get("link", "")}
    except Exception as e:
        return {"status": "error", "message": str(e)}
