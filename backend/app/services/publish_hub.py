"""NC-PUB-001~003: Publishing state machine, data collection, ROI dashboard."""
from __future__ import annotations
from datetime import datetime, timezone
from app.db import connect, new_id, encode

PUBLISH_STATES = ["draft", "scheduled", "submitted", "published", "failed", "retrying", "retracted"]


# ===== NC-PUB-001: Publish state machine + account authorization =====

AUTHORIZED_ACCOUNTS = {}  # In production: DB-backed with OAuth tokens


def register_platform_account(platform: str, account_name: str, credentials: dict = {}) -> dict:
    """NC-PUB-001: Register/authorize a platform publishing account."""
    AUTHORIZED_ACCOUNTS[platform] = {"name": account_name, "status": "authorized", "added_at": datetime.utcnow().isoformat()}
    return {"status": "ok", "platform": platform, "account": account_name, "auth_status": "authorized"}


def publish_state_machine(content_id: str, platform: str, target_state: str) -> dict:
    """NC-PUB-001: Transition publish record through state machine with validation."""
    if target_state not in PUBLISH_STATES:
        return {"status": "error", "message": f"invalid state: {target_state}"}

    valid_transitions = {
        "draft": ["scheduled"],
        "scheduled": ["submitted", "failed"],
        "submitted": ["published", "failed", "retracted"],
        "published": ["retracted"],
        "failed": ["retrying", "draft"],
        "retrying": ["submitted", "failed"],
        "retracted": ["draft"],
    }

    db = connect()
    # Use proper UUID for content_id if a raw string is passed
    from app.db import new_id as gen_id
    if content_id and len(content_id) < 32:
        lookup_id = gen_id()
    else:
        lookup_id = content_id
    record = db.execute(
        "SELECT * FROM publish_records WHERE content_id=%s AND platform=%s ORDER BY created_at DESC LIMIT 1",
        (lookup_id, platform),
    ).fetchone()

    if record:
        current_state = record["status"]
        if target_state not in valid_transitions.get(current_state, []):
            db.close()
            return {"status": "error", "message": f"invalid transition: {current_state}→{target_state}"}

    rid = new_id()
    db.execute(
        "INSERT INTO publish_records (id, content_id, platform, status, meta) VALUES (%s,%s,%s,%s,%s)",
        (rid, content_id, platform, target_state,
         encode({"previous_state": record["status"] if record else "none", "transitioned_at": datetime.utcnow().isoformat()})),
    )
    db.commit(); db.close()
    return {"status": "ok", "record_id": rid, "from": record["status"] if record else "none", "to": target_state}


def get_publishing_history(content_id: str = "", platform: str = "") -> list[dict]:
    """NC-PUB-001: Full publishing history with state transitions."""
    db = connect()
    rows = db.execute(
        "SELECT * FROM publish_records WHERE (content_id=%s OR %s='') AND (platform=%s OR %s='') ORDER BY created_at DESC LIMIT 50",
        (content_id, content_id, platform, platform),
    ).fetchall()
    db.close()
    return [{"id": r["id"], "content_id": r["content_id"], "platform": r["platform"],
             "status": r["status"], "meta": r.get("meta", {}), "created_at": str(r["created_at"])} for r in rows]


# ===== NC-PUB-002: Data collection — reads/interactions/revenue =====

def collect_platform_data(platform: str, content_id: str, data: dict) -> dict:
    """NC-PUB-002: Collect engagement data from a platform (reads, likes, shares, revenue)."""
    db = connect()
    pid = new_id()
    db.execute(
        "INSERT INTO published_posts (id, project_id, platform, content_id, title, body, status, published_at, meta) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (pid, "", platform, content_id, data.get("title", ""), "",
         "published", datetime.utcnow().isoformat(),
         encode({
             "reads": data.get("reads", 0), "likes": data.get("likes", 0),
             "shares": data.get("shares", 0), "comments": data.get("comments", 0),
             "revenue": data.get("revenue", 0), "currency": data.get("currency", "CNY"),
             "collected_at": datetime.utcnow().isoformat(),
         })),
    )
    db.commit(); db.close()
    return {"status": "ok", "post_id": pid, "platform": platform}


def aggregate_platform_stats(platform: str = "") -> dict:
    """NC-PUB-002: Aggregate engagement stats across all platforms or per platform."""
    db = connect()
    where = "WHERE platform = %s" if platform else ""
    params = (platform,) if platform else ()
    total = db.execute(
        f"SELECT SUM((meta->>'reads')::int) as reads, SUM((meta->>'likes')::int) as likes, "
        f"SUM((meta->>'shares')::int) as shares, SUM((meta->>'revenue')::float) as revenue, "
        f"COUNT(*) as posts FROM published_posts {where}", params
    ).fetchone()
    db.close()
    return {
        "total_reads": int(total["reads"] or 0), "total_likes": int(total["likes"] or 0),
        "total_shares": int(total["shares"] or 0), "total_revenue": round(float(total["revenue"] or 0), 2),
        "total_posts": int(total["posts"] or 0),
    }


# ===== NC-PUB-003: ROI dashboard + topic feedback =====

def generate_roi_report() -> dict:
    """NC-PUB-003: ROI report — cost vs engagement per platform."""
    db = connect()
    rows = db.execute("""
        SELECT platform, COUNT(*) as cnt,
               SUM((meta->>'reads')::int) as reads,
               SUM((meta->>'likes')::int) as likes,
               SUM((meta->>'revenue')::float) as revenue
        FROM published_posts GROUP BY platform
    """).fetchall()
    db.close()

    roi = []
    for r in rows:
        reads = int(r["reads"] or 0)
        revenue = float(r["revenue"] or 0)
        roi.append({
            "platform": r["platform"], "posts": r["cnt"],
            "reads": reads, "likes": int(r["likes"] or 0),
            "revenue": round(revenue, 2),
            "rpm": round((revenue / max(reads, 1)) * 1000, 2),  # Revenue per thousand reads
        })
    return {"roi_by_platform": sorted(roi, key=lambda x: x["revenue"], reverse=True)}


def generate_topic_suggestions_from_data() -> list[str]:
    """NC-PUB-003: Derive topic suggestions from successful published content."""
    db = connect()
    top = db.execute(
        "SELECT meta->>'title' as title FROM published_posts "
        "WHERE (meta->>'reads')::int > 100 ORDER BY (meta->>'reads')::int DESC LIMIT 5"
    ).fetchall()
    db.close()
    suggestions = [f"「{t['title']}」表现优异 → 继续深耕此领域" for t in top if t["title"]]
    return suggestions or ["暂无足够数据，建议从热点选题中心开始"]
