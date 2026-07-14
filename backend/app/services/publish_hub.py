"""NC-PUB-001~003: Publishing state machine, data collection, ROI dashboard."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

from app.db import connect, new_id, encode

PUBLISH_STATES = ["draft", "scheduled", "submitted", "published", "failed", "retrying", "retracted"]


# ===== NC-PUB-001: Publish state machine + account authorization =====
# Accounts live in platform_accounts with Fernet-encrypted credentials
# (the table was designed for this; see init migration comment). Credential
# plaintext is never returned by the registration/list APIs.


def _credentials_fernet():
    from cryptography.fernet import Fernet

    key = os.getenv("NOVELCRAFT_CREDENTIALS_KEY", "").strip()
    if key:
        return Fernet(key.encode())
    if os.getenv("NOVELCRAFT_ENV", "development").lower() == "production":
        raise RuntimeError("NOVELCRAFT_CREDENTIALS_KEY must be set in production")
    secret = os.getenv("NOVELCRAFT_JWT_SECRET", "dev-secret-change-in-production")
    derived = hashlib.sha256(f"platform-credentials:{secret}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def register_platform_account(platform: str, account_name: str, credentials: dict | None = None,
                              user_id: str = "") -> dict:
    """NC-PUB-001: Persist a platform publishing account with encrypted credentials."""
    if not user_id:
        return {"status": "error", "message": "user_id is required"}
    encrypted = _credentials_fernet().encrypt(
        json.dumps(credentials or {}, ensure_ascii=False).encode()
    ).decode()
    db = connect()
    existing = db.execute(
        "SELECT id FROM platform_accounts WHERE user_id=%s AND platform=%s AND account_name=%s AND is_deleted=FALSE",
        (user_id, platform, account_name),
    ).fetchone()
    if existing:
        account_id = existing["id"]
        db.execute(
            "UPDATE platform_accounts SET credentials_encrypted=%s, updated_at=now() WHERE id=%s",
            (encrypted, account_id),
        )
    else:
        account_id = new_id()
        db.execute(
            "INSERT INTO platform_accounts (id, user_id, platform, account_name, credentials_encrypted) "
            "VALUES (%s,%s,%s,%s,%s)",
            (account_id, user_id, platform, account_name, encrypted),
        )
    db.commit()
    db.close()
    return {"status": "ok", "account_id": account_id, "platform": platform,
            "account": account_name, "auth_status": "authorized"}


def list_platform_accounts(user_id: str) -> list[dict]:
    """Accounts for one user — never includes credential material."""
    db = connect()
    rows = db.execute(
        "SELECT id, platform, account_name, created_at, updated_at FROM platform_accounts "
        "WHERE user_id=%s AND is_deleted=FALSE ORDER BY platform, account_name",
        (user_id,),
    ).fetchall()
    db.close()
    return [{"id": r["id"], "platform": r["platform"], "account_name": r["account_name"],
             "updated_at": str(r["updated_at"])} for r in rows]


def delete_platform_account(account_id: str, user_id: str) -> bool:
    """Soft-delete one account/connection owned by a user."""
    db = connect()
    result = db.execute(
        "UPDATE platform_accounts SET is_deleted=TRUE, updated_at=now() WHERE id=%s AND user_id=%s AND is_deleted=FALSE",
        (account_id, user_id),
    )
    changed = getattr(result, "rowcount", 0) == 1
    db.commit()
    db.close()
    return changed


def list_platform_accounts_with_config_status(user_id: str, specs: dict[str, dict]) -> list[dict]:
    """Return account metadata and which required fields are configured.

    Credential values are decrypted only to compute boolean presence; plaintext is
    never returned.
    """
    db = connect()
    rows = db.execute(
        "SELECT id, platform, account_name, credentials_encrypted, created_at, updated_at FROM platform_accounts "
        "WHERE user_id=%s AND is_deleted=FALSE ORDER BY platform, account_name",
        (user_id,),
    ).fetchall()
    db.close()
    out: list[dict] = []
    from cryptography.fernet import InvalidToken
    for row in rows:
        creds: dict = {}
        if row.get("credentials_encrypted"):
            try:
                plaintext = _credentials_fernet().decrypt(row["credentials_encrypted"].encode())
                creds = json.loads(plaintext)
            except (InvalidToken, json.JSONDecodeError, TypeError):
                creds = {}
        spec = specs.get(row["platform"], {})
        fields = spec.get("fields", [])
        configured_fields = [f["key"] for f in fields if str(creds.get(f["key"], "")).strip()]
        required = [f["key"] for f in fields if f.get("required")]
        out.append({
            "id": row["id"],
            "platform": row["platform"],
            "account_name": row["account_name"],
            "display_name": spec.get("display_name", row["platform"]),
            "category": spec.get("category", "other"),
            "configured_fields": configured_fields,
            "missing_required": [key for key in required if key not in configured_fields],
            "updated_at": str(row["updated_at"]),
        })
    return out


def get_platform_credentials(user_id: str, platform: str, account_name: str = "") -> dict | None:
    """Decrypt credentials for internal publish flows only; never expose via API."""
    db = connect()
    row = db.execute(
        "SELECT credentials_encrypted FROM platform_accounts WHERE user_id=%s AND platform=%s "
        "AND (account_name=%s OR %s='') AND is_deleted=FALSE ORDER BY updated_at DESC LIMIT 1",
        (user_id, platform, account_name, account_name),
    ).fetchone()
    db.close()
    if not row or not row["credentials_encrypted"]:
        return None
    from cryptography.fernet import InvalidToken

    try:
        plaintext = _credentials_fernet().decrypt(row["credentials_encrypted"].encode())
    except InvalidToken:
        return None
    return json.loads(plaintext)


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
    # Validate content_id is a proper UUID
    import uuid as _uuid
    if content_id:
        try:
            _uuid.UUID(content_id)
        except (ValueError, AttributeError):
            db.close()
            return {"status": "error", "message": f"invalid content_id format: {content_id}"}
    else:
        db.close()
        return {"status": "error", "message": "content_id is required"}
    record = db.execute(
        "SELECT * FROM publish_records WHERE content_id=%s AND platform=%s ORDER BY created_at DESC LIMIT 1",
        (content_id, platform),
    ).fetchone()

    if record:
        current_state = record["status"]
        if target_state not in valid_transitions.get(current_state, []):
            db.close()
            return {"status": "error", "message": f"invalid transition: {current_state}→{target_state}"}

    elif target_state != "draft":
        db.close()
        return {"status": "error", "message": "first state must be draft"}

    rid = new_id()
    db.execute(
        "INSERT INTO publish_records (id, content_id, platform, status, meta) VALUES (%s,%s,%s,%s,%s)",
        (rid, content_id, platform, target_state,
         encode({"previous_state": record["status"] if record else "none", "transitioned_at": datetime.utcnow().isoformat()})),
    )
    db.commit(); db.close()
    return {"status": "ok", "record_id": rid, "from": record["status"] if record else "none", "to": target_state}


def get_publishing_history(content_id: str = "", platform: str = "",
                           project_ids: list[str] | None = None) -> list[dict]:
    """NC-PUB-001: Full publishing history with state transitions."""
    clauses, params = ["c.project_id = ANY(%s::uuid[])"], [project_ids or []]
    if content_id:
        clauses.append("pr.content_id=%s")
        params.append(content_id)
    if platform:
        clauses.append("pr.platform=%s")
        params.append(platform)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    db = connect()
    rows = db.execute(
        f"SELECT pr.* FROM publish_records pr JOIN contents c ON c.id=pr.content_id {where} "
        "ORDER BY pr.created_at DESC LIMIT 50",
        tuple(params),
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
        (pid, data.get("project_id") or None, platform, content_id or None, data.get("title", ""), "",
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


def aggregate_platform_stats(platform: str = "", project_ids: list[str] | None = None) -> dict:
    """NC-PUB-002: Aggregate engagement stats across all platforms or per platform."""
    db = connect()
    clauses, params = ["project_id = ANY(%s::uuid[])"], [project_ids or []]
    if platform:
        clauses.append("platform=%s")
        params.append(platform)
    where = "WHERE " + " AND ".join(clauses)
    total = db.execute(
        f"SELECT SUM((meta->>'reads')::int) as reads, SUM((meta->>'likes')::int) as likes, "
        f"SUM((meta->>'shares')::int) as shares, SUM((meta->>'revenue')::float) as revenue, "
        f"COUNT(*) as posts FROM published_posts {where}", tuple(params)
    ).fetchone()
    db.close()
    return {
        "total_reads": int(total["reads"] or 0), "total_likes": int(total["likes"] or 0),
        "total_shares": int(total["shares"] or 0), "total_revenue": round(float(total["revenue"] or 0), 2),
        "total_posts": int(total["posts"] or 0),
    }


# ===== NC-PUB-003: ROI dashboard + topic feedback =====

def generate_roi_report(project_ids: list[str] | None = None) -> dict:
    """NC-PUB-003: ROI report — cost vs engagement per platform."""
    db = connect()
    rows = db.execute("""
        SELECT platform, COUNT(*) as cnt,
               SUM((meta->>'reads')::int) as reads,
               SUM((meta->>'likes')::int) as likes,
               SUM((meta->>'revenue')::float) as revenue
        FROM published_posts WHERE project_id = ANY(%s::uuid[]) GROUP BY platform
    """, (project_ids or [],)).fetchall()
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


def generate_topic_suggestions_from_data(project_ids: list[str] | None = None) -> list[dict]:
    """NC-PUB-003: Derive topic suggestions from successful published content.
    Every suggestion is traceable to the source post that produced it."""
    db = connect()
    top = db.execute(
        "SELECT id, title, platform, COALESCE((meta->>'reads')::int, 0) AS reads "
        "FROM published_posts WHERE project_id = ANY(%s::uuid[]) "
        "AND COALESCE((meta->>'reads')::int, 0) > 100 "
        "ORDER BY (meta->>'reads')::int DESC LIMIT 5", (project_ids or [],)
    ).fetchall()
    db.close()
    suggestions = [{
        "suggestion": f"「{t['title']}」表现优异 → 继续深耕此领域",
        "source_post_id": str(t["id"]), "source_title": t["title"],
        "platform": t["platform"], "reads": int(t["reads"]),
    } for t in top if t["title"]]
    return suggestions or [{"suggestion": "暂无足够数据，建议从热点选题中心开始",
                            "source_post_id": None, "source_title": None, "platform": None, "reads": 0}]


# 指标口径 — the single source of truth the dashboard and reports reference.
METRICS_GLOSSARY = {
    "reads": "平台回流的阅读数（published_posts.meta.reads，来源为真实采集/人工录入）",
    "likes": "点赞数（meta.likes）",
    "shares": "转发/分享数（meta.shares）",
    "revenue": "收益（meta.revenue，单位为 meta.currency，默认 CNY）",
    "rpm": "每千次阅读收益 = revenue / max(reads,1) × 1000",
    "posts": "回流数据覆盖的已发布内容条数",
}


def build_performance_dashboard(project_ids: list[str] | None = None) -> dict:
    """NC-PUB-003: 效果看板数据 — 汇总统计 + 平台 ROI + 可追溯选题建议 + 指标口径。"""
    db = connect()
    top_posts = db.execute(
        "SELECT id, title, platform, COALESCE((meta->>'reads')::int,0) AS reads, "
        "COALESCE((meta->>'likes')::int,0) AS likes, COALESCE((meta->>'revenue')::float,0) AS revenue "
        "FROM published_posts WHERE project_id = ANY(%s::uuid[]) "
        "ORDER BY COALESCE((meta->>'reads')::int,0) DESC LIMIT 10", (project_ids or [],)
    ).fetchall()
    db.close()
    return {
        "metrics_glossary": METRICS_GLOSSARY,
        "totals": aggregate_platform_stats(project_ids=project_ids),
        "roi_by_platform": generate_roi_report(project_ids=project_ids)["roi_by_platform"],
        "top_posts": [{"post_id": str(p["id"]), "title": p["title"], "platform": p["platform"],
                       "reads": int(p["reads"]), "likes": int(p["likes"]),
                       "revenue": round(float(p["revenue"]), 2)} for p in top_posts],
        "topic_suggestions": generate_topic_suggestions_from_data(project_ids=project_ids),
    }


def performance_feedback(project_id: str, project_ids: list[str] | None = None) -> dict:
    """NC-PUB-003: 真实 AI 反哺 — 把真实回流数据交给网关，产出选题与写作建议。
    每条建议绑定 based_on 源数据（post id 列表），Provider 失败显式抛错。"""
    from app.gateway import complete

    dashboard = build_performance_dashboard(project_ids=project_ids)
    if not dashboard["top_posts"]:
        return {"status": "no_data", "message": "没有回流数据，无法生成反哺建议",
                "topic_suggestions": [], "writing_advice": []}
    data_digest = json.dumps({
        "totals": dashboard["totals"],
        "roi_by_platform": dashboard["roi_by_platform"][:8],
        "top_posts": dashboard["top_posts"],
    }, ensure_ascii=False)
    output = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="performance_feedback", prompt_name="publish.performance_feedback",
        variables={"performance_data": data_digest[:6000]},
    )
    valid_ids = {p["post_id"] for p in dashboard["top_posts"]}
    for item in output.get("topic_suggestions", []):
        item["based_on"] = [pid for pid in item.get("based_on", []) if pid in valid_ids]
    return {"status": "ok", "source_posts": sorted(valid_ids), **output}
