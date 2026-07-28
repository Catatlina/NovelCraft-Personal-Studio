"""M3 support utilities: file parsing, book metrics, briefing scheduling, and comparison reports."""
import os, re, json
from app.db import connect, new_id, encode


# --- TASK-035: PDF/Word/Markdown parser ---

def parse_uploaded_file(file_path: str) -> list[dict]:
    """Parse PDF, DOCX, TXT, MD files into knowledge items."""
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    
    if ext == ".pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            text = "\n".join(page.get_text() for page in doc)
        except ImportError:
            text = f"[PDF parser requires: pip install pymupdf]\nFile: {file_path}"
    elif ext in (".docx", ".doc"):
        try:
            import docx
            doc = docx.Document(file_path)
            text = "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            text = f"[DOCX parser requires: pip install python-docx]\nFile: {file_path}"
    elif ext in (".txt", ".md", ".json"):
        with open(file_path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    
    # Split into sections by headings
    sections = re.split(r'\n(?=#{1,3}\s|\d+[\.\、])', text)
    items = []
    for sec in sections:
        sec = sec.strip()
        if len(sec) < 10:
            continue
        title = sec.split('\n')[0].lstrip('#').strip()[:120]
        items.append({"title": title, "body": sec[:8000], "kind": "reference", "source": file_path})
    return items


def import_parsed_items(items: list[dict], project_id: str = "") -> int:
    """Store parsed knowledge items."""
    db = connect()
    count = 0
    for item in items:
        try:
            db.execute(
                "INSERT INTO knowledge_items (id, kind, title, body, meta, project_id) VALUES (%s,%s,%s,%s,%s,%s)",
                (new_id(), item["kind"], item["title"], item["body"], encode({"source": item.get("source", "")}), project_id),
            )
            count += 1
        except Exception:
            pass
    db.commit(); db.close()
    return count


# --- TASK-036: Book analysis workflow ---

def analyze_book_structure(text: str) -> dict:
    """Analyze book structure: opening hooks, rhythm patterns, tropes."""
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    chapters = [p for p in paragraphs if re.match(r'^第[一二三四五六七八九十百千\d]+章', p)]
    
    return {
        "total_chapters": len(chapters) or len(paragraphs) // 100 + 1,
        "estimated_words": len(text),
        "opening_hook": paragraphs[0][:200] if paragraphs else "",
        "chapter_titles": chapters[:20],
        "dialogue_ratio": round(text.count('"') / max(len(text), 1) * 100, 1),
    }


# --- TASK-038: 7-day briefing scheduler ---

BRIEFING_SCHEDULE_DAYS = 7


def schedule_week_briefings(project_id: str) -> list[str]:
    """Schedule 7 daily briefings (one per day)."""
    from datetime import datetime, timedelta
    task_ids = []
    for day in range(BRIEFING_SCHEDULE_DAYS):
        scheduled_time = (datetime.utcnow() + timedelta(days=day)).replace(hour=8, minute=0)
        db = connect()
        tid = new_id()
        # Get or create reference content for FK constraint
        ref = db.execute("SELECT id FROM contents WHERE project_id = %s LIMIT 1", (project_id,)).fetchone()
        cid = ref["id"] if ref else new_id()
        if not ref:
            db.execute("INSERT INTO contents (id, project_id, type, title, body, status) VALUES (%s,%s,%s,%s,%s,%s)",
                       (cid, project_id, "note", "briefing_ref", encode({}), "draft"))
        db.execute(
            "INSERT INTO publish_records (id, content_id, platform, status, meta) VALUES (%s,%s,%s,%s,%s)",
            (tid, cid, "daily_briefing", "scheduled", encode({
                "scheduled_at": scheduled_time.isoformat(),
                "day": day + 1,
                "project_id": project_id,
            })),
        )
        db.commit(); db.close()
        task_ids.append(tid)
    return task_ids


# --- TASK-039: Comparison report ---

def generate_model_comparison(prompt_name: str, models: list, variables: dict = {}) -> dict:
    """Generate A/B comparison report across models."""
    from app.gateway import complete
    results = []
    for model in models:
        try:
            output = complete(
                run_id=None, node_key=None, project_id="",
                task_type="lab_compare", prompt_name=prompt_name,
                variables=variables,
            )
            results.append({
                "model": model,
                "tokens": output.get("tokens", 0),
                "latency_ms": output.get("latency_ms", 0),
                "cost_cny": output.get("cost_cny", 0),
                "output_preview": str(output.get("text", ""))[:100],
            })
        except Exception as e:
            results.append({"model": model, "error": str(e)[:100]})
    
    return {
        "prompt": prompt_name,
        "models_tested": len(models),
        "results": results,
        "fastest": min((r for r in results if "error" not in r), key=lambda r: r.get("latency_ms", 9999), default={"model": "N/A"}).get("model", "N/A") if results else "N/A",
    }
