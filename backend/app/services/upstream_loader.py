"""Oh-Story prompt loader — reads upstream SKILL.md files and registers them as NovelCraft prompts."""
from __future__ import annotations

import os
import re
import yaml


UPSTREAM_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts", "upstream")


def load_upstream_skill(skill_name: str) -> dict:
    """Load an oh-story skill SKILL.md, parse frontmatter + body."""
    path = os.path.join(UPSTREAM_DIR, skill_name, "SKILL.md")
    if not os.path.exists(path):
        return {"name": skill_name, "error": "not found"}
    
    with open(path, encoding="utf-8") as f:
        content = f.read()
    
    # Parse YAML frontmatter
    fm = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
    
    return {
        "name": fm.get("name", skill_name),
        "version": fm.get("version", "1.0.0"),
        "description": fm.get("description", ""),
        "source": fm.get("metadata", {}).get("openclaw", {}).get("source", ""),
        "body": body,
        "char_count": len(body),
    }


def list_upstream_skills() -> list[str]:
    """List all available upstream skill directories."""
    if not os.path.isdir(UPSTREAM_DIR):
        return []
    return sorted(d for d in os.listdir(UPSTREAM_DIR)
                  if os.path.isdir(os.path.join(UPSTREAM_DIR, d)) and not d.startswith("."))


def render_upstream_prompt(skill_name: str, variables: dict = {}) -> str:
    """Load and render an upstream prompt with variable substitution."""
    skill = load_upstream_skill(skill_name)
    body = skill.get("body", "")
    
    # Simple {{ variable }} substitution
    for key, value in variables.items():
        body = body.replace("{{ " + key + " }}", str(value))
        body = body.replace("{{" + key + "}}", str(value))
    
    return body


def get_upstream_stats() -> dict:
    """Get statistics about imported upstream prompts."""
    skills = list_upstream_skills()
    total_chars = 0
    details = {}
    for s in skills:
        info = load_upstream_skill(s)
        total_chars += info.get("char_count", 0)
        details[s] = {"version": info.get("version"), "chars": info.get("char_count", 0)}
    return {
        "total_skills": len(skills),
        "total_chars": total_chars,
        "skills": details,
    }
