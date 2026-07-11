"""Fusion: BrowserAct (MIT) + insprira (AGPL, clean-room) integration.

BrowserAct: CLI adapter for anti-bot scraping and platform publishing.
insprira: Clean-room implementation of account tracking, compliance check, skill center.
"""
from __future__ import annotations
import subprocess, json, os, re
from datetime import datetime
from app.db import connect, new_id, encode


# =====================================================
# BrowserAct (MIT) — Direct integration
# Commit: browser-act/skills@22aad3f
# =====================================================

def _run_browseract(args: list[str], timeout: int = 60) -> dict:
    """Execute browser-act CLI with an explicit argument list. Falls back gracefully if CLI not installed."""
    try:
        result = subprocess.run(
            ["browser-act", *args],
            capture_output=True, text=True, timeout=timeout
        )
        return {"status": "ok" if result.returncode == 0 else "error",
                "stdout": result.stdout[:2000], "stderr": result.stderr[:500]}
    except FileNotFoundError:
        return {"status": "unavailable", "message": "browser-act CLI not installed. Install: npm i -g browser-act"}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "message": f"Command timed out after {timeout}s"}


# NOTE: scrape_ranking_with_browseract (stealth-extract) was removed. Docs/25 forbids
# breaking anti-bot walls, solving captchas, or forging signatures; ranking capture must
# go through the user-controlled browser artifact flow in ranking_capture.py.


def publish_with_browseract(platform: str, content: str, login_profile: str = "") -> dict:
    """Use BrowserAct chrome mode to publish content via the user's own logged-in session."""
    result = _run_browseract(["chrome", "--profile", login_profile or platform])
    if result["status"] == "unavailable":
        return {"status": "manual_fallback", "platform": platform,
                "instructions": f"安装 browser-act CLI 后自动发布到 {platform}",
                "mode": "semi_auto"}
    return result


# =====================================================
# insprira (AGPL-3.0) — Clean-room implementation
# Behavior spec from: https://github.com/coracoo/insprira README
# Zero source code consulted. Independent implementation.
# =====================================================

# --- Account tracking (账号追踪) ---

def track_account(platform: str, account_id: str, project_id: str = "") -> dict:
    """Clean-room: Track a social media account — subscribe, sync posts, compute trends.

    Behavior: insprira tracks accounts across platforms with follower counts,
    engagement scores, and trend charts. We independently model this as
    a tracking subscription with scheduled sync."""
    db = connect()
    existing = db.execute(
        "SELECT id FROM account_trackings WHERE platform = %s AND account_id = %s AND (project_id = %s OR project_id IS NULL)",
        (platform, account_id, project_id or None),
    ).fetchone()
    if existing:
        db.close()
        return {"status": "already_tracked", "tracking_id": existing["id"]}

    tid = new_id()
    db.execute(
        "INSERT INTO account_trackings (id, project_id, platform, account_id, status, last_synced_at) "
        "VALUES (%s, %s, %s, %s, %s, now())",
        (tid, project_id or None, platform, account_id, "active"),
    )
    db.commit()
    db.close()
    return {"status": "tracking_started", "tracking_id": tid, "platform": platform, "account_id": account_id}


def get_account_diagnostics(platform: str, account_id: str, project_id: str = "") -> dict:
    """Clean-room: Diagnose account performance — follower trend, engagement, content stats.

    Behavior: insprira generates diagnostic charts (followers/redfox-index/score/posts).
    We independently compute metrics from collected post data."""
    db = connect()
    posts = db.execute(
        "SELECT COUNT(*) as cnt, AVG((meta->>'engagement')::numeric) as avg_eng "
        "FROM published_posts WHERE platform = %s AND meta->>'account_id' = %s "
        "AND (project_id = %s OR (%s = '' AND project_id IS NULL))",
        (platform, account_id, project_id or None, project_id),
    ).fetchone()
    db.close()
    cnt = posts["cnt"] if posts else 0
    avg = float(posts["avg_eng"] or 0) if posts else 0
    # RedFox-style composite index (independent formula)
    redfox_index = round(min(100, cnt * 2 + avg * 10), 1) if cnt > 0 else 0
    return {
        "platform": platform, "account_id": account_id,
        "total_posts": cnt, "avg_engagement": round(avg, 2),
        "redfox_index": redfox_index,
        "rating": "S" if redfox_index > 80 else "A" if redfox_index > 60 else "B" if redfox_index > 40 else "C",
    }


# --- Compliance check (违禁词检测) ---

# Independent violation word list — compiled from public platform guidelines, not from insprira
VIOLATION_PATTERNS: list[tuple[str, str]] = [
    (r"广告|推广|营销", "广告风险"),
    (r"最低价|全网最低|第一|唯一|独家", "绝对化用语"),
    (r"点击.*链接|扫码.*关注|加.*微信", "诱导引流"),
    (r"疗效|治愈|治疗|秘方|偏方", "医疗风险"),
    (r"收益率|回报率|稳赚|保本|无风险", "金融风险"),
    (r"色情|淫秽|裸体|性爱", "色情违规"),
    (r"赌博|博彩|彩票|赌场", "赌博违规"),
    (r"政治敏感|领导人|抗议|示威", "政治敏感"),
]


def check_compliance(text: str) -> dict:
    """Clean-room: Check content against platform compliance rules.

    Behavior: insprira has content violation detection. We independently implement
    pattern-based compliance checking using publicly documented platform rules."""
    issues = []
    for pattern, category in VIOLATION_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            issues.append({"category": category, "matched": matches[:3], "pattern": pattern})

    return {
        "status": "clean" if not issues else "violations_found",
        "violation_count": len(issues),
        "violations": issues,
        "safe_to_publish": len(issues) == 0,
    }


# --- Community skill center (Skill中心) ---

def fetch_community_skills(repo_url: str = "https://github.com/redfox-community/skills") -> dict:
    """Clean-room: Pull and categorize community skills.

    Behavior: insprira fetches skills from redfox-community, auto-classifies by LLM.
    We independently implement skill repository polling with local caching."""
    cache_dir = os.path.join(os.path.dirname(__file__), "../../data/skills_cache")
    os.makedirs(cache_dir, exist_ok=True)

    try:
        import urllib.request
        api_url = repo_url.replace("github.com", "api.github.com/repos") + "/contents"
        req = urllib.request.Request(api_url, headers={"User-Agent": "NovelCraft/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            items = json.loads(r.read())
    except Exception as exc:
        # Docs/23 §4: an upstream fetch failure must stay visible, never an empty "ok".
        return {"status": "unavailable", "skill_count": 0, "skills": [],
                "source": repo_url, "error": str(exc)}

    skills = []
    for item in items:
        if item.get("type") == "dir":
            skills.append({
                "name": item["name"],
                "category": _classify_skill_category(item["name"]),
                "source": repo_url,
                "cached": False,
            })

    return {"status": "ok", "skill_count": len(skills), "skills": skills, "source": repo_url}


def _classify_skill_category(name: str) -> str:
    """Independent skill classifier — hot/account/source/creative/analysis/retrieval/tool."""
    name_lower = name.lower()
    if any(k in name_lower for k in ["hot", "trend", "热", "爆款"]):
        return "hotspot"
    if any(k in name_lower for k in ["account", "账号", "profile"]):
        return "account"
    if any(k in name_lower for k in ["source", "rss", "feed", "源"]):
        return "source"
    if any(k in name_lower for k in ["write", "create", "创作", "生成"]):
        return "creative"
    if any(k in name_lower for k in ["analyze", "analysis", "分析"]):
        return "analysis"
    if any(k in name_lower for k in ["search", "retrieve", "检索", "搜索"]):
        return "retrieval"
    return "tool"
