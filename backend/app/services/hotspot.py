"""M3: Hotspot monitoring — topic detection + daily briefing."""
from __future__ import annotations

from app.db import connect, encode, new_id
from app.gateway import complete


def fetch_hotspots(project_id: str) -> list[dict]:
    """Fetch and analyze current hotspots via AI."""
    prompt = "列出当前中文互联网最热门的5个话题。输出JSON: {\"topics\":[{\"title\":\"话题\",\"category\":\"分类\",\"score\":85,\"angle\":\"创作角度建议\"}]}"
    try:
        output = complete(
            run_id=None, node_key=None, project_id=project_id,
            task_type="fetch_hotspots", prompt_name="social.fetch_hotspots",
            variables={},
        )
        topics = output.get("topics", [])
        # Store in knowledge hub
        db = connect()
        for t in topics:
            db.execute(
                "INSERT INTO knowledge_items (id, project_id, kind, title, body, meta) VALUES (%s,%s,%s,%s,%s,%s)",
                (new_id(), project_id, "hotspot", t.get("title", ""), t.get("angle", ""),
                 encode({"score": t.get("score", 0), "category": t.get("category", "")})),
            )
        db.commit(); db.close()
        return topics
    except Exception as e:
        return [{"error": str(e)}]


def generate_daily_briefing(project_id: str) -> dict:
    """Generate daily content briefing from hotspots."""
    topics = fetch_hotspots(project_id)
    if not topics or "error" in topics[0]:
        return {"status": "no_topics", "topics": topics}

    # Generate platform-specific drafts
    briefing = {"topics": topics, "generated": []}
    for topic in topics[:3]:
        try:
            draft = complete(
                run_id=None, node_key=None, project_id=project_id,
                task_type="gen_daily_brief", prompt_name="social.gen_daily_brief",
                variables={"topic": topic.get("title", ""), "angle": topic.get("angle", "")},
            )
            briefing["generated"].append({"topic": topic.get("title"), "draft": draft})
        except Exception:
            pass
    return briefing
